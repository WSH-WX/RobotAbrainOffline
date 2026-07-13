
import os
import sys
import time
import json
import queue
import threading
import traceback
import logging
import hashlib
from functools import partial

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from opencc import OpenCC

from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

from funasr import AutoModel

from openai_chat_app import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessage,
    ChatUsage
)

from rabbitbot.provider import create_tts_agent
from rabbitbot.tools.sound_agno import tts_sound


app = FastAPI()

cc = OpenCC('t2s')
LOGGER = logging.getLogger("rabbitbot.stt_app_funasr")
if not LOGGER.handlers:
    _stt_log_handler = logging.StreamHandler()
    _stt_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(_stt_log_handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


def env_enabled(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _text_digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]

# ===== 配置参数 =====
# DJI Mic Mini 在现场表现为右声道有信号、左声道静音；默认采集双声道并自动选择电平最大的声道。
INPUT_CHANNELS = max(1, int(os.environ.get("STT_INPUT_CHANNELS", "2")))
INPUT_CHANNEL_SELECT_MODE = os.environ.get("STT_INPUT_CHANNEL_SELECT_MODE", "max_rms").strip().lower()
INPUT_CHANNEL_INDEX = max(0, int(os.environ.get("STT_INPUT_CHANNEL_INDEX", "0")))
STT_LEVEL_LOG_INTERVAL = max(0.0, float(os.environ.get("STT_LEVEL_LOG_INTERVAL", "10")))
SAMPLE_RATE_MODEL = 16000
SILENCE_SEC = float(os.environ.get("STT_SILENCE_SEC", "0.50"))
BUFFER_MAX_SEC = float(os.environ.get("STT_BUFFER_MAX_SEC", "15"))
VAD_WINDOW_SEC = float(os.environ.get("STT_VAD_WINDOW_SEC", "0.45"))
VAD_KEEP_SEC = float(os.environ.get("STT_VAD_KEEP_SEC", "0.12"))
VAD_SPEECH_THRES = float(os.environ.get("STT_VAD_SPEECH_THRES", "0.18"))
VAD_START_HITS = int(os.environ.get("STT_VAD_START_HITS", "1"))
MIN_RMS = float(os.environ.get("STT_MIN_RMS", "0.035"))
MIN_UTTERANCE_SEC = float(os.environ.get("STT_MIN_UTTERANCE_SEC", "0.45"))
INPUT_BLOCK_SEC = float(os.environ.get("STT_INPUT_BLOCK_SEC", "0.1"))
INPUT_LATENCY = os.environ.get("STT_INPUT_LATENCY", "high")
AUDIO_QUEUE_MAX_CHUNKS = int(os.environ.get("STT_AUDIO_QUEUE_MAX_CHUNKS", "160"))
INPUT_GAIN = float(os.environ.get("STT_INPUT_GAIN", "0.75"))

input_device_name = os.environ.get("INPUT_DEVICE_NAME", "").strip()
input_device_index = os.environ.get("INPUT_DEVICE_INDEX", "").strip()
if input_device_name:
    in_device_id = input_device_name
    input_device_source = "name"
elif input_device_index:
    in_device_id = int(input_device_index)
    input_device_source = "index"
else:
    in_device_id = None
    input_device_source = "default"
LOGGER.info("STT 输入设备选择器已解析：source=%s, selector=%s", input_device_source, in_device_id)

# ===== 模型路径配置 =====
DEFAULT_MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
SENSEVOICE_MODEL_PATH = os.environ.get(
    "STT_MODEL_PATH",
    os.path.join(DEFAULT_MODELS_DIR, "SenseVoiceSmall")
)
VAD_MODEL_PATH = os.environ.get(
    "VAD_MODEL_PATH",
    os.path.join(DEFAULT_MODELS_DIR, "fsmn_vad")
)
STT_DEVICE = os.environ.get("STT_DEVICE", "cuda")

print(f"Loading SenseVoice model from: {SENSEVOICE_MODEL_PATH}")
print(f"Loading VAD model from: {VAD_MODEL_PATH}")
print(f"STT device: {STT_DEVICE}")
print(
    "STT filter config: "
    f"silence_sec={SILENCE_SEC}, vad_window_sec={VAD_WINDOW_SEC}, "
    f"vad_speech_thres={VAD_SPEECH_THRES}, vad_start_hits={VAD_START_HITS}, "
    f"min_rms={MIN_RMS}, min_utterance_sec={MIN_UTTERANCE_SEC}, "
    f"input_block_sec={INPUT_BLOCK_SEC}, input_latency={INPUT_LATENCY}, "
    f"audio_queue_max_chunks={AUDIO_QUEUE_MAX_CHUNKS}, input_gain={INPUT_GAIN}, "
    f"input_channels={INPUT_CHANNELS}, channel_select={INPUT_CHANNEL_SELECT_MODE}, "
    f"fixed_channel={INPUT_CHANNEL_INDEX}, level_log_interval={STT_LEVEL_LOG_INTERVAL}"
)

import re

def parse_sensevoice_text(raw_text: str) -> str:
    """解析 SenseVoice 返回的原始文本，去掉标签"""
    if not raw_text:
        return ""
    # 去掉 <|...|> 格式的标签
    text = re.sub(r'<\|[^|]*\|>', '', raw_text).strip()
    return text

# ===== 加载模型 =====
asr_model = AutoModel(
    model=SENSEVOICE_MODEL_PATH,
    device=STT_DEVICE,
    disable_log=True,
    disable_update=True
)

vad_model = AutoModel(
    model=VAD_MODEL_PATH,
    device=STT_DEVICE,
    disable_log=True,
    disable_pbar=True,
    disable_update=True
)

# 预热模型
print("Warming up models...")
dummy_audio = np.random.randn(16000).astype(np.float32)
_ = asr_model.generate(input=dummy_audio, batch_size_s=0)
_ = vad_model.generate(input=dummy_audio, chunk_size=320)
print("Models warmed up!")

# ===== 麦克风配置 =====
try:
    if in_device_id is not None:
        device_info = sd.query_devices(in_device_id, 'input')
    else:
        device_info = sd.query_devices(None, 'input')
except Exception as exc:
    LOGGER.exception(
        "STT 输入设备初始化失败：source=%s, selector=%s, error_type=%s",
        input_device_source,
        in_device_id,
        type(exc).__name__,
    )
    raise RuntimeError(f"无法初始化 STT 输入设备：source={input_device_source}") from exc

device_max_input_channels = int(device_info.get("max_input_channels", INPUT_CHANNELS) or INPUT_CHANNELS)
STREAM_INPUT_CHANNELS = max(1, min(INPUT_CHANNELS, device_max_input_channels))

try:
    sd.check_input_settings(device=in_device_id, samplerate=SAMPLE_RATE_MODEL, channels=STREAM_INPUT_CHANNELS)
    DEVICE_SR = SAMPLE_RATE_MODEL
    NEED_RESAMPLE = False
    print(f"Device supports {SAMPLE_RATE_MODEL} Hz directly")
except Exception as exc:
    DEVICE_SR = int(device_info['default_samplerate'])
    NEED_RESAMPLE = True
    print(f"Device default samplerate: {DEVICE_SR} Hz, will resample to {SAMPLE_RATE_MODEL} Hz; reason={type(exc).__name__}: {exc}")

print(
    "STT input channel config: "
    f"device_max_channels={device_max_input_channels}, stream_channels={STREAM_INPUT_CHANNELS}, "
    f"select_mode={INPUT_CHANNEL_SELECT_MODE}, fixed_channel={INPUT_CHANNEL_INDEX}"
)

# ===== 录音状态管理 =====
class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.audio_buffer = []
        self.recording_complete = threading.Event()
        self.lock = threading.Lock()
        
        # VAD 相关
        self.vad_buffer = []
        self.last_voice_time = 0
        self.input_speech = False
        self.utterance_id = 0
        self.output_utterance_id = 0
        self.last_output_text = ""
        self.last_output_utterance_id = 0
        self.has_recognized = False
        self.speech_hit_count = 0
        
    def reset(self):
        with self.lock:
            self.audio_buffer = []
            self.vad_buffer = []
            self.input_speech = False
            self.last_voice_time = 0
            self.output_text = ""
            self.output_utterance_id = 0
            self.last_output_text = ""
            self.last_output_utterance_id = 0
            self.has_recognized = False
            self.speech_hit_count = 0
            self.recording_complete.clear()
            
    def start(self):
        self.reset()
        self.is_recording = True
        
    def stop(self):
        self.is_recording = False
        
    def add_audio(self, audio_16k):
        if not self.is_recording:
            return

        recognize_now = False
        with self.lock:
            self.vad_buffer.extend(audio_16k)
            
            # 如果已经开始录音，持续累积音频
            if self.input_speech:
                self.audio_buffer.extend(audio_16k)
                max_samples = int(BUFFER_MAX_SEC * SAMPLE_RATE_MODEL)
                if len(self.audio_buffer) > max_samples:
                    self.audio_buffer = self.audio_buffer[-max_samples:]
            
            # 按窗口做 VAD 检测；门限和音量门控都通过环境变量可调。
            if len(self.vad_buffer) >= int(VAD_WINDOW_SEC * SAMPLE_RATE_MODEL):
                vad_input = np.array(self.vad_buffer, dtype=np.float32)
                vad_rms = float(np.sqrt(np.mean(vad_input.astype(np.float32) ** 2)))
                segments = vad_model.generate(
                    input=vad_input,
                    chunk_size=160,
                    speech_thres=VAD_SPEECH_THRES
                )
                has_speech = len(segments) > 0 and len(segments[0]["value"]) > 0 and vad_rms >= MIN_RMS
                current_time = time.time()
                
                if has_speech:
                    self.speech_hit_count += 1
                    # 首次检测到语音，初始化录音缓冲
                    if not self.input_speech and self.speech_hit_count >= VAD_START_HITS:
                        self.input_speech = True
                        print(
                            "[SenseVoice] Speech detected, recording... "
                            f"rms={vad_rms:.4f}, threshold={MIN_RMS:.4f}, "
                            f"hits={self.speech_hit_count}/{VAD_START_HITS}"
                        )
                        self.audio_buffer = list(self.vad_buffer)
                    if self.input_speech:
                        self.last_voice_time = current_time
                else:
                    self.speech_hit_count = 0
                    if self.input_speech:
                        if current_time - self.last_voice_time > SILENCE_SEC:
                            self.input_speech = False
                            recognize_now = True
                
                # 保留最近一小段作为滑动窗口，避免切掉起音。
                self.vad_buffer = self.vad_buffer[-int(VAD_KEEP_SEC * SAMPLE_RATE_MODEL):]

        if recognize_now:
            self._recognize()
            self.recording_complete.set()

    def _recognize(self):
        if self.has_recognized:
            return
        if len(self.audio_buffer) < int(MIN_UTTERANCE_SEC * SAMPLE_RATE_MODEL):
            print(
                "[SenseVoice] Audio too short, skipping... "
                f"duration={len(self.audio_buffer)/SAMPLE_RATE_MODEL:.2f}s, "
                f"min={MIN_UTTERANCE_SEC:.2f}s"
            )
            return
            
        audio = np.array(self.audio_buffer, dtype=np.float32)
        rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
        
        if rms < MIN_RMS:
            print(
                "[SenseVoice] Audio too quiet, skipping... "
                f"rms={rms:.4f}, threshold={MIN_RMS:.4f}"
            )
            return
            
        print(f"[SenseVoice] Recognizing {len(audio)/SAMPLE_RATE_MODEL:.2f}s audio...")
        start_time = time.time()
        
        result = asr_model.generate(
            input=audio,
            language="zh"
        )
        
        if result and len(result) > 0:
            raw_text = result[0].get("text", "")
            text = parse_sensevoice_text(raw_text)
            if text:
                print(f"[SenseVoice] Recognized: {text}")
                print(f"[SenseVoice] Time: {time.time() - start_time:.2f}s")
                recorder.utterance_id += 1
                recorder.output_utterance_id = recorder.utterance_id
                recorder.output_text = text
                recorder.last_output_utterance_id = recorder.output_utterance_id
                recorder.last_output_text = text
                recorder.has_recognized = True
                
    def get_status(self):
        if self.is_recording and self.input_speech:
            return "<REC_START>"
        elif self.is_recording:
            return "<REC_START>"
        return "<REC_STOP>"
        
    def get_text(self):
        return getattr(self, 'output_text', "") or ""

    def get_utterance_id(self):
        return getattr(self, 'output_utterance_id', 0) or 0

    def peek_text(self):
        return getattr(self, 'last_output_text', "") or self.get_text()

    def peek_utterance_id(self):
        return getattr(self, 'last_output_utterance_id', 0) or self.get_utterance_id()


# ===== 全局录音器 =====
recorder = AudioRecorder()
recorder.output_text = ""
recorder.output_utterance_id = 0
recorder.last_output_text = ""
recorder.last_output_utterance_id = 0
audio_queue = queue.Queue(maxsize=AUDIO_QUEUE_MAX_CHUNKS)
injected_text_queue = queue.Queue()
# 标记“最近一次 get_text_async 消费的文本是否来自注入(inject_text_async)”。
# 注入文本是显式口令、无真实音频，不应被打断音量阈值(忽略低音量打断)过滤；
# get_last_rms 在此为真时返回高音量哨兵值，使注入文本无条件视为有效打断。
injection_state = {"last_consumed_injected": False}
audio_drop_count = 0
last_audio_status_log_time = 0.0
last_audio_level_log_time = 0.0
audio_level_lock = threading.Lock()
last_audio_level = {
    "rms": 0.0,
    "peak": 0.0,
    "channel": 0,
    "channels": STREAM_INPUT_CHANNELS,
    "channel_rms": [],
    "updated_at": 0.0,
}


def audio_worker():
    print("[SenseVoice] Audio worker started")
    while True:
        audio_48k = audio_queue.get()
        if audio_48k is None:
            audio_queue.task_done()
            break
        try:
            if NEED_RESAMPLE:
                audio_16k = resample_poly(audio_48k, SAMPLE_RATE_MODEL, DEVICE_SR).astype(np.float32)
            else:
                audio_16k = audio_48k.astype(np.float32)
            if INPUT_GAIN != 1.0:
                audio_16k = (audio_16k * INPUT_GAIN).astype(np.float32)
            recorder.add_audio(audio_16k)
        except Exception:
            traceback.print_exc()
        finally:
            audio_queue.task_done()


def _select_audio_channel(indata):
    if indata.ndim == 1 or indata.shape[1] <= 1:
        audio = indata.reshape(-1).copy()
        channel_rms = [float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))] if audio.size else [0.0]
        return audio, 0, channel_rms

    frame = indata.astype(np.float32, copy=False)
    channel_rms_array = np.sqrt(np.mean(frame ** 2, axis=0))
    channel_rms = [float(value) for value in channel_rms_array]

    if INPUT_CHANNEL_SELECT_MODE in {"fixed", "index"}:
        selected_channel = min(INPUT_CHANNEL_INDEX, frame.shape[1] - 1)
        audio = frame[:, selected_channel].copy()
    elif INPUT_CHANNEL_SELECT_MODE in {"mix", "mean", "mono"}:
        selected_channel = int(np.argmax(channel_rms_array))
        audio = frame.mean(axis=1).copy()
    else:
        selected_channel = int(np.argmax(channel_rms_array))
        audio = frame[:, selected_channel].copy()
    return audio, selected_channel, channel_rms


# ===== 音频流回调 =====
def audio_callback(indata, frames, time_info, status):
    global audio_drop_count, last_audio_status_log_time, last_audio_level_log_time
    if status:
        now = time.time()
        if now - last_audio_status_log_time > 5:
            print(f"Audio status: {status}")
            last_audio_status_log_time = now

    audio_48k, selected_channel, channel_rms = _select_audio_channel(indata)
    rms = float(np.sqrt(np.mean(audio_48k.astype(np.float32) ** 2))) if audio_48k.size else 0.0
    peak = float(np.max(np.abs(audio_48k))) if audio_48k.size else 0.0
    with audio_level_lock:
        last_audio_level.update(
            rms=rms,
            peak=peak,
            channel=selected_channel,
            channels=int(indata.shape[1]) if indata.ndim > 1 else 1,
            channel_rms=channel_rms,
            updated_at=time.time(),
        )

    now = time.time()
    if recorder.is_recording and STT_LEVEL_LOG_INTERVAL > 0 and now - last_audio_level_log_time >= STT_LEVEL_LOG_INTERVAL:
        LOGGER.info(
            "STT 输入电平: selected_channel=%s, rms=%.6f, peak=%.6f, channel_rms=%s, channels=%s",
            selected_channel,
            rms,
            peak,
            [round(value, 6) for value in channel_rms],
            last_audio_level["channels"],
        )
        last_audio_level_log_time = now

    try:
        audio_queue.put_nowait(audio_48k)
    except queue.Full:
        audio_drop_count += 1
        if audio_drop_count == 1 or audio_drop_count % 50 == 0:
            print(
                "[SenseVoice] Audio queue full, dropping chunk... "
                f"drop_count={audio_drop_count}, queue_size={audio_queue.qsize()}"
            )


# ===== 启动音频流 =====
if in_device_id is not None:
    print(f"Starting audio stream on device {in_device_id}...")
    threading.Thread(target=audio_worker, daemon=True).start()
    audio_stream = sd.InputStream(
        device=in_device_id,
        channels=STREAM_INPUT_CHANNELS,
        samplerate=DEVICE_SR,
        callback=audio_callback,
        blocksize=int(DEVICE_SR * INPUT_BLOCK_SEC),
        dtype='float32',
        latency=INPUT_LATENCY
    )
    audio_stream.start()
else:
    print("No input device, running in no-device mode")
    audio_stream = None


# ===== TTS 提示 =====
if env_enabled("RABBITBOT_STT_STARTUP_SPEECH", False):
    try:
        tts_agent = create_tts_agent()
        tts_sound(tts_agent, "，，机器人语音输入模块加载完毕", "zh")
    except Exception:
        LOGGER.exception("STT 启动提示播报失败")
else:
    LOGGER.info("STT 启动提示播报已关闭：RABBITBOT_STT_STARTUP_SPEECH=0")
print("Initialization completed!")


# ===== 核心执行函数 =====
async def _exec(task, lang, text, timeout):
    out_text = None
    utterance_id = 0
    
    if task == "set_language":
        out_text = "Set language success"
        
    elif task == "speech_to_text":
        recorder.reset()
        recorder.start()
        recorder.recording_complete.wait(timeout=timeout)
        recorder.stop()
        out_text = recorder.get_text()
        utterance_id = recorder.get_utterance_id()
        if lang == "zh" and out_text:
            out_text = cc.convert(out_text)
            
    elif task == "speech_to_text_async":
        recorder.reset()
        recorder.start()
        recorder.recording_complete.wait(timeout=timeout)
        recorder.stop()
        out_text = recorder.get_text()
        utterance_id = recorder.get_utterance_id()
        if lang == "zh" and out_text:
            out_text = cc.convert(out_text)
        if out_text is None:
            out_text = ""
            
    elif task == "start_async":
        recorder.reset()
        recorder.start()
        out_text = "Started"
        
    elif task == "stop_async":
        recorder.stop()
        # 立即进行一次识别
        if not recorder.get_text() and len(recorder.audio_buffer) > int(MIN_UTTERANCE_SEC * SAMPLE_RATE_MODEL):
            recorder._recognize()
        out_text = "Stopped"
        
    elif task == "get_status_async":
        out_text = recorder.get_status()

    elif task == "get_last_rms":
        if injection_state["last_consumed_injected"]:
            # 注入文本无真实音频，按高音量哨兵返回，避免被打断音量阈值过滤掉。
            out_text = f"{float(os.environ.get('STT_INJECTED_RMS', '1.0')):.8f}"
        else:
            with audio_level_lock:
                out_text = f"{last_audio_level['rms']:.8f}"

    elif task == "peek_text_async":
        out_text = recorder.peek_text()
        utterance_id = recorder.peek_utterance_id()
        if lang == "zh" and out_text:
            out_text = cc.convert(out_text)
        if out_text is None:
            out_text = ""

    elif task == "get_text_async":
        try:
            utterance_id, out_text = injected_text_queue.get_nowait()
            injection_state["last_consumed_injected"] = True
            if lang == "zh" and out_text:
                out_text = cc.convert(out_text)
            LOGGER.info(
                "STT 注入文本已消费：utterance_id=%s, text_len=%s, text_hash=%s, queue_remaining=%s",
                utterance_id,
                len(out_text or ""),
                _text_digest(out_text or ""),
                injected_text_queue.qsize(),
            )
        except queue.Empty:
            out_text = recorder.get_text()
            utterance_id = recorder.get_utterance_id()
            if lang == "zh" and out_text:
                out_text = cc.convert(out_text)
            if out_text is None:
                out_text = ""
            else:
                recorder.output_text = ""
                recorder.output_utterance_id = 0
                injection_state["last_consumed_injected"] = False

    elif task == "inject_text_async":
        out_text = text or ""
        with recorder.lock:
            recorder.utterance_id += 1
            utterance_id = recorder.utterance_id
            recorder.last_output_utterance_id = utterance_id
            recorder.last_output_text = out_text
        injected_text_queue.put((utterance_id, out_text))
        LOGGER.info(
            "STT 注入文本已入队：utterance_id=%s, text_len=%s, text_hash=%s, queue_size=%s",
            utterance_id,
            len(out_text),
            _text_digest(out_text),
            injected_text_queue.qsize(),
        )
            
    else:
        out_text = f"Unsupported task: {task}"
        
    if task == "peek_text_async":
        print(f"out_text: <peek_text_async text_len={len(out_text or '')} utterance_id={utterance_id}>")
    else:
        print("out_text:", out_text)
    return out_text or "", utterance_id


# ===== FastAPI 接口 =====
@app.post("/exec")
async def exec_api(task: str = Form(...)):
    try:
        input_dict = json.loads(task)
        task = input_dict["task"]
        lang = input_dict.get("lang", "zh")
        text = input_dict.get("text", "")
        timeout = input_dict.get("timeout", 30)
        
        out_text, utterance_id = await _exec(task, lang, text, timeout)
        return JSONResponse(content={"out_text": str(out_text), "utterance_id": utterance_id})
        
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        last_user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "Hello!")
        input_dict = json.loads(last_user_msg)
        task = input_dict["task"]
        lang = input_dict.get("lang", "zh")
        text = input_dict.get("text", "")
        timeout = input_dict.get("timeout", 30)
        
        out_text, _ = await _exec(task, lang, text, timeout)
        
        response = ChatCompletionResponse(
            id="chatcmpl-stt",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=out_text),
                    finish_reason="stop"
                )
            ],
            usage=ChatUsage(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2
            )
        )
        return response
        
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("STT_PORT", "28184"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

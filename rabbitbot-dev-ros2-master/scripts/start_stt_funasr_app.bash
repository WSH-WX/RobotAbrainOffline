#!/bin/bash
# 启动 SenseVoice STT 服务的脚本

# 设置环境变量
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
source "${SCRIPT_DIR}/path_env.sh"

if [ -f /opt/venv/bin/activate ]; then
    source /opt/venv/bin/activate
elif [ -f "${PROJECT_DIR}/py310/bin/activate" ]; then
    source "${PROJECT_DIR}/py310/bin/activate"
else
    echo "未找到 Python 虚拟环境，将使用系统 python"
fi

export STT_DEVICE=${STT_DEVICE:-cuda}
export STT_COMPUTE_TYPE=${STT_COMPUTE_TYPE:-float16}
export STT_PORT=${STT_PORT:-28184}
export STT_MODEL_PATH=${STT_MODEL_PATH:-${RABBITBOT_MODELS_DIR}/SenseVoiceSmall}
export VAD_MODEL_PATH=${VAD_MODEL_PATH:-${RABBITBOT_MODELS_DIR}/fsmn_vad}
export STT_SILENCE_SEC=${STT_SILENCE_SEC:-0.50}
export STT_VAD_WINDOW_SEC=${STT_VAD_WINDOW_SEC:-0.45}
export STT_VAD_KEEP_SEC=${STT_VAD_KEEP_SEC:-0.12}
export STT_VAD_SPEECH_THRES=${STT_VAD_SPEECH_THRES:-0.12}
export STT_VAD_START_HITS=${STT_VAD_START_HITS:-1}
export STT_MIN_RMS=${STT_MIN_RMS:-0.022}
export STT_MIN_UTTERANCE_SEC=${STT_MIN_UTTERANCE_SEC:-0.35}
export STT_INPUT_BLOCK_SEC=${STT_INPUT_BLOCK_SEC:-0.1}
export STT_INPUT_LATENCY=${STT_INPUT_LATENCY:-high}
export STT_AUDIO_QUEUE_MAX_CHUNKS=${STT_AUDIO_QUEUE_MAX_CHUNKS:-160}
# DJI Mic Mini 现场右声道电平约 -48 dBFS，默认放大后再进入 VAD，仍允许环境变量覆盖。
export STT_INPUT_GAIN=${STT_INPUT_GAIN:-8.0}
export STT_INPUT_VOLUME_PERCENT=${STT_INPUT_VOLUME_PERCENT:-80}
export REALTIME_TTS_BASE_URL=${REALTIME_TTS_BASE_URL:-http://127.0.0.1:28185/v1}
export RABBITBOT_STT_AUDIO_BACKEND=${RABBITBOT_STT_AUDIO_BACKEND:-alsa}
export RABBITBOT_ENABLE_PULSE_AUDIO=${RABBITBOT_ENABLE_PULSE_AUDIO:-0}
export PULSE_SERVER=${PULSE_SERVER:-unix:/run/user/1000/pulse/native}
export STT_DEVICE_WAIT_SECONDS=${STT_DEVICE_WAIT_SECONDS:-10}
export STT_DEVICE_STABLE_COUNT=${STT_DEVICE_STABLE_COUNT:-2}
export RABBITBOT_TTS_AGENT_URL=${RABBITBOT_TTS_AGENT_URL:-${REALTIME_TTS_BASE_URL}}
echo "STT 启动提示 TTS 地址: ${RABBITBOT_TTS_AGENT_URL}"

# STT_DEVICE_NAME 只在明确指定时作为最高优先级；默认自动选择外接麦克风。
DEVICE_NAME="${STT_DEVICE_NAME:-}"

# 查找输入设备。必须在激活虚拟环境后执行，否则默认 python 可能没有 sounddevice。
echo "查找输入设备，指定名称: ${DEVICE_NAME:-未指定}"
echo "STT 输入设备自动选择策略: 显式指定名称 > 外接麦克风类设备 > 其它外接输入设备 > Orin 内置音频设备"
echo "音频兼容层配置: stt_audio_backend=${RABBITBOT_STT_AUDIO_BACKEND}, pulse_enabled=${RABBITBOT_ENABLE_PULSE_AUDIO}, pulse_server=${PULSE_SERVER}, wait_seconds=${STT_DEVICE_WAIT_SECONDS}, stable_count=${STT_DEVICE_STABLE_COUNT}"
DEVICE_INFO=$(python -m rabbitbot.audio.device_probe stt 2>/tmp/rabbitbot_stt_device_probe.err || true)
DEVICE_INDEX=$(echo "${DEVICE_INFO}" | cut -d'|' -f1)
DEVICE_FOUND_NAME=$(echo "${DEVICE_INFO}" | cut -d'|' -f2)
DEVICE_SELECT_REASON=$(echo "${DEVICE_INFO}" | cut -d'|' -f3)
DEVICE_KIND=$(echo "${DEVICE_INFO}" | cut -d'|' -f4)
DEVICE_AVAILABLE=$(echo "${DEVICE_INFO}" | cut -d'|' -f5)

if [ "${DEVICE_AVAILABLE}" = "1" ] && [ -n "${DEVICE_INDEX}" ]; then
    export INPUT_DEVICE_INDEX="${DEVICE_INDEX}"
    echo "使用输入音频设备 ${DEVICE_FOUND_NAME}，index=${INPUT_DEVICE_INDEX}，kind=${DEVICE_KIND}，reason=${DEVICE_SELECT_REASON}"
    DEVICE_CARD=$(echo "${DEVICE_FOUND_NAME}" | sed -n 's/.*(hw:\([0-9][0-9]*\),[0-9][0-9]*).*/\1/p')
    if [ -n "${DEVICE_CARD}" ] && command -v amixer >/dev/null 2>&1; then
        if amixer -c "${DEVICE_CARD}" sset Mic "${STT_INPUT_VOLUME_PERCENT}%" >/dev/null 2>&1; then
            echo "设置输入麦克风音量: card=${DEVICE_CARD}, volume=${STT_INPUT_VOLUME_PERCENT}%"
        else
            echo "设置输入麦克风音量失败，将继续使用当前系统音量: card=${DEVICE_CARD}, volume=${STT_INPUT_VOLUME_PERCENT}%"
        fi
    else
        echo "未能解析输入声卡 card 或 amixer 不可用，跳过麦克风音量设置"
    fi
elif [ -n "${INPUT_DEVICE_INDEX}" ]; then
    echo "未自动找到输入设备，使用已设置的 INPUT_DEVICE_INDEX=${INPUT_DEVICE_INDEX}"
else
    echo "未找到可用输入设备，将以无输入设备模式启动；探测日志: /tmp/rabbitbot_stt_device_probe.err"
    unset INPUT_DEVICE_INDEX
fi

echo "STT 模型路径: ${STT_MODEL_PATH}"
echo "VAD 模型路径: ${VAD_MODEL_PATH}"
echo "STT 设备: ${STT_DEVICE}"
echo "STT 端口: ${STT_PORT}"
echo "STT 过滤参数: vad_thres=${STT_VAD_SPEECH_THRES}, min_rms=${STT_MIN_RMS}, silence=${STT_SILENCE_SEC}, min_utterance=${STT_MIN_UTTERANCE_SEC}, block_sec=${STT_INPUT_BLOCK_SEC}, latency=${STT_INPUT_LATENCY}, input_gain=${STT_INPUT_GAIN}"

# 启动服务
cd "${PROJECT_DIR}"
python stt_app_funasr.py

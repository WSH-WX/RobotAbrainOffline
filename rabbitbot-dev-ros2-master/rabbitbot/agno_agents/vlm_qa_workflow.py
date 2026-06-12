from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Optional

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rabbitbot.context import AppContext
from rabbitbot.provider import create_general_vlm_openai
from rabbitbot.tools.sound_agno import (
    audio_input_execute,
    audio_input_execute_timeout,
    tts_sound,
    tts_wait,
)


LOGGER = logging.getLogger("rabbitbot.vlm_qa_workflow")


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        LOGGER.warning("环境变量不是整数，使用默认值：name=%s, value=%s, default=%s", name, raw_value, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        LOGGER.warning("环境变量不是数字，使用默认值：name=%s, value=%s, default=%s", name, raw_value, default)
        return default


def _text_digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def _text_preview(text: str, max_chars: int = 24) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars]}..."


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def _is_valid_user_text(text: str) -> bool:
    text = _normalize_text(text)
    if text == "":
        return False
    return text not in {"<REC_TIMEOUT>", "<REC_STOP>", "<REC_DUPLICATE>", "Timeout", "Started", "Stopped"}


def _is_exit_text(text: str, exit_words: set[str]) -> bool:
    normalized = "".join(ch for ch in _normalize_text(text).lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    return normalized in exit_words


@dataclass
class QAWorkflowConfig:
    listen_timeout: int
    idle_sleep_seconds: float
    include_image: bool
    image_width: int
    image_height: int
    answer_max_chars: int
    thinking_speech: str
    startup_speech: str
    exit_words: set[str]

    @classmethod
    def from_env(cls) -> "QAWorkflowConfig":
        raw_exit_words = os.getenv("RABBITBOT_QA_EXIT_WORDS", "退出,停止,结束,再见,quit,exit")
        return cls(
            listen_timeout=_env_int("RABBITBOT_QA_LISTEN_TIMEOUT", 30),
            idle_sleep_seconds=_env_float("RABBITBOT_QA_IDLE_SLEEP_SECONDS", 0.2),
            include_image=_env_bool("RABBITBOT_QA_INCLUDE_IMAGE", "0"),
            image_width=_env_int("RABBITBOT_QA_IMAGE_WIDTH", 1280),
            image_height=_env_int("RABBITBOT_QA_IMAGE_HEIGHT", 720),
            answer_max_chars=_env_int("RABBITBOT_QA_MAX_ANSWER_CHARS", 180),
            thinking_speech=os.getenv("RABBITBOT_QA_THINKING_SPEECH", "我听到了，让我想一想。"),
            startup_speech=os.getenv("RABBITBOT_QA_STARTUP_SPEECH", "问答测试已启动，您可以直接向我提问。"),
            exit_words={word.strip().lower() for word in raw_exit_words.split(",") if word.strip()},
        )


class VLMQAWorkflow:
    def __init__(self, ctx: AppContext, config: QAWorkflowConfig):
        self.ctx = ctx
        self.config = config
        self.vlm = create_general_vlm_openai()
        self.stop_requested = False
        self.turn_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = time.perf_counter()

    def request_stop(self, *_args) -> None:
        self.stop_requested = True
        LOGGER.info("收到退出信号，准备停止问答 workflow")
        try:
            audio_input_execute(self.ctx.stt_agent, "stop_async")
        except Exception as exc:
            LOGGER.warning("停止 STT 异步监听失败：type=%s, error=%s", type(exc).__name__, exc)

    def _capture_image(self) -> Optional[np.ndarray]:
        if not self.config.include_image:
            return None

        source = os.getenv("RABBITBOT_QA_IMAGE_SOURCE", "robot").strip().lower()
        started_at = time.perf_counter()
        if source == "mock":
            image_path = os.getenv(
                "RABBITBOT_QA_MOCK_IMAGE",
                str(PROJECT_ROOT / "tests" / "tasks" / "resources" / "frig.jpg"),
            )
            image = cv2.imread(image_path)
            elapsed = time.perf_counter() - started_at
            if image is None:
                LOGGER.warning("mock 图像读取失败，将改为纯文本问答：path=%s, elapsed=%.3fs", image_path, elapsed)
                return None
            LOGGER.info("已读取 mock 图像：path=%s, shape=%s, elapsed=%.3fs", image_path, image.shape, elapsed)
            return image

        try:
            image = self.ctx.robot.get_camera_info(
                "view_2d",
                {"frame_size": (self.config.image_width, self.config.image_height)},
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            LOGGER.exception(
                "机器人图像读取异常，将改为纯文本问答：type=%s, elapsed=%.3fs",
                type(exc).__name__,
                elapsed,
            )
            return None

        elapsed = time.perf_counter() - started_at
        if image is None:
            LOGGER.warning("机器人图像为空，将改为纯文本问答：elapsed=%.3fs", elapsed)
            return None
        image = np.asarray(image, dtype=np.uint8)
        LOGGER.info("已读取机器人图像：shape=%s, elapsed=%.3fs", image.shape, elapsed)
        return image

    def _build_prompt(self, user_text: str, has_image: bool) -> str:
        visual_rule = "请结合当前画面回答用户问题。" if has_image else "当前没有可用画面，请只根据用户问题回答。"
        return dedent(f"""\
            你是 RabbitBot 的现场问答测试助手。{visual_rule}

            用户问题：{user_text}

            回答要求：
            - 使用中文，语气自然，适合机器人直接播报。
            - 优先给出明确答案，不要输出思考过程。
            - 如果问题依赖画面但画面不可用或看不清，请直接说明无法确认。
            - 回答尽量控制在 {self.config.answer_max_chars} 个中文字符以内。
        """)

    def _call_vlm(self, user_text: str, image: Optional[np.ndarray]) -> str:
        has_image = image is not None
        prompt = self._build_prompt(user_text, has_image)
        request_started_at = time.perf_counter()
        LOGGER.info(
            "VLM 推理开始：turn=%s, question_len=%s, question_hash=%s, has_image=%s",
            self.turn_count,
            len(user_text),
            _text_digest(user_text),
            has_image,
        )

        if has_image:
            messages, extra_body = self.vlm.prepare_message_for_vllm([image], prompt)
            answer = self.vlm.get_chat_response(messages, extra_body)
        else:
            response = self.vlm.client.chat.completions.create(
                model=self.vlm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                stream=True,
            )
            chunks = []
            for chunk in response:
                content = getattr(chunk.choices[0].delta, "content", None)
                if content:
                    print(content, end="", flush=True)
                    chunks.append(content)
            print("", flush=True)
            answer = "".join(chunks)

        elapsed = time.perf_counter() - request_started_at
        answer = _normalize_text(answer)
        LOGGER.info(
            "VLM 推理完成：turn=%s, answer_len=%s, answer_hash=%s, elapsed=%.3fs",
            self.turn_count,
            len(answer),
            _text_digest(answer),
            elapsed,
        )
        return answer

    def _speak_answer(self, answer: str) -> None:
        if not answer:
            answer = "抱歉，我刚才没有生成有效回答，请您再问一遍。"
        if len(answer) > self.config.answer_max_chars:
            LOGGER.info("回答超过长度限制，将截断播报：answer_len=%s, max=%s", len(answer), self.config.answer_max_chars)
            answer = answer[: self.config.answer_max_chars].rstrip() + "。"
        tts_index = tts_sound(self.ctx.tts_agent, answer, "zh")
        LOGGER.info("TTS 播报已提交：turn=%s, tts_index=%s, answer_len=%s", self.turn_count, tts_index, len(answer))
        tts_wait(self.ctx.tts_agent)

    async def run(self) -> None:
        LOGGER.info(
            "问答 workflow 启动：listen_timeout=%ss, include_image=%s, image_size=%sx%s",
            self.config.listen_timeout,
            self.config.include_image,
            self.config.image_width,
            self.config.image_height,
        )
        if self.config.startup_speech:
            tts_sound(self.ctx.tts_agent, self.config.startup_speech, "zh")

        while not self.stop_requested:
            self.turn_count += 1
            LOGGER.info("开始监听用户问题：turn=%s, timeout=%ss", self.turn_count, self.config.listen_timeout)
            listen_started_at = time.perf_counter()
            try:
                user_text = audio_input_execute_timeout(self.ctx.stt_agent, timeout=self.config.listen_timeout, text="")
            except Exception as exc:
                self.failure_count += 1
                LOGGER.exception("STT 监听异常：turn=%s, type=%s", self.turn_count, type(exc).__name__)
                await asyncio.sleep(self.config.idle_sleep_seconds)
                continue

            listen_elapsed = time.perf_counter() - listen_started_at
            user_text = _normalize_text(user_text)
            if not _is_valid_user_text(user_text):
                LOGGER.debug("本轮没有有效语音输入：turn=%s, raw=%s, elapsed=%.3fs", self.turn_count, user_text, listen_elapsed)
                await asyncio.sleep(self.config.idle_sleep_seconds)
                continue

            LOGGER.info(
                "收到用户问题：turn=%s, text_len=%s, text_hash=%s, text_preview=%s, elapsed=%.3fs",
                self.turn_count,
                len(user_text),
                _text_digest(user_text),
                _text_preview(user_text),
                listen_elapsed,
            )
            if _is_exit_text(user_text, self.config.exit_words):
                LOGGER.info("收到退出口令：turn=%s, text_hash=%s", self.turn_count, _text_digest(user_text))
                tts_sound(self.ctx.tts_agent, "问答测试已结束。", "zh")
                break

            try:
                if self.config.thinking_speech:
                    tts_sound(self.ctx.tts_agent, self.config.thinking_speech, "zh")
                image = self._capture_image()
                answer = self._call_vlm(user_text, image)
                self._speak_answer(answer)
                self.success_count += 1
            except Exception as exc:
                self.failure_count += 1
                LOGGER.exception("问答轮次失败：turn=%s, type=%s", self.turn_count, type(exc).__name__)
                tts_sound(self.ctx.tts_agent, "抱歉，我刚才处理问题时遇到异常，请您稍后再试。", "zh")

        total_elapsed = time.perf_counter() - self.start_time
        LOGGER.info(
            "问答 workflow 结束：turns=%s, success=%s, failure=%s, elapsed=%.3fs",
            self.turn_count,
            self.success_count,
            self.failure_count,
            total_elapsed,
        )


async def main(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose or _env_bool("RABBITBOT_QA_VERBOSE", "0"))
    config = QAWorkflowConfig.from_env()
    if args.include_image:
        config.include_image = True
    if args.text_only:
        config.include_image = False

    async with AppContext(with_memory=False) as ctx:
        workflow = VLMQAWorkflow(ctx, config)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, workflow.request_stop)
            except NotImplementedError:
                signal.signal(sig, workflow.request_stop)
        await workflow.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="持续监听语音并通过 VLM 回答的问答测试 workflow。")
    parser.add_argument("--include-image", action="store_true", help="每轮问题同时抓取一帧图像传给 VLM。")
    parser.add_argument("--text-only", action="store_true", help="强制只使用语音文字，不抓取图像。")
    parser.add_argument("--verbose", action="store_true", help="输出 DEBUG 级别诊断日志。")
    return parser


if __name__ == "__main__":
    asyncio.run(main(build_parser().parse_args()))

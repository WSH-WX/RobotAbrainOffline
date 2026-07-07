from __future__ import annotations

import json
import logging
import time
from urllib.parse import urljoin

import requests
from requests.exceptions import RequestException, Timeout

from rabbitbot.runtime.config import env_float

logger = logging.getLogger(__name__)


def _task_summary(task: str) -> dict[str, object]:
    return {"task_len": len(task or "")}


def _audio_timeout_seconds() -> float:
    return env_float("RABBITBOT_AUDIO_HTTP_TIMEOUT", 10.0)


class _ExecAudioClient:
    """调用音频服务 /exec 接口的基础客户端。"""

    service_name = "audio"

    def __init__(self, host_url: str):
        self.host_url = host_url
        self.timeout_seconds = _audio_timeout_seconds()
        logger.info("%s 客户端初始化完成：host_url=%s, timeout=%.2fs", self.service_name, host_url, self.timeout_seconds)

    def _post_exec(self, input_dict_str: str) -> dict | None:
        data = {"task": input_dict_str}
        url = urljoin(self.host_url, "exec")
        start_time = time.perf_counter()
        summary = _task_summary(input_dict_str)
        logger.debug("准备请求音频服务：service=%s, url=%s, %s", self.service_name, url, summary)
        try:
            resp = requests.post(url, data=data, timeout=self.timeout_seconds)
        except Timeout:
            elapsed = time.perf_counter() - start_time
            logger.warning(
                "%s 请求超时：url=%s, timeout=%.2fs, elapsed=%.3fs, task_len=%s",
                self.service_name, url, self.timeout_seconds, elapsed, summary["task_len"],
            )
            return None
        except RequestException as exc:
            elapsed = time.perf_counter() - start_time
            logger.warning(
                "%s 请求失败：url=%s, elapsed=%.3fs, task_len=%s, error_type=%s, error=%s",
                self.service_name, url, elapsed, summary["task_len"], type(exc).__name__, exc,
            )
            return None

        elapsed = time.perf_counter() - start_time
        if resp.status_code >= 400:
            logger.warning(
                "%s 返回异常状态码：url=%s, status_code=%s, elapsed=%.3fs, task_len=%s, response_len=%s",
                self.service_name, url, resp.status_code, elapsed, summary["task_len"], len(resp.text or ""),
            )
            return None
        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "%s 响应 JSON 解析失败：url=%s, elapsed=%.3fs, task_len=%s, response_len=%s, error=%s",
                self.service_name, url, elapsed, summary["task_len"], len(resp.text or ""), exc,
            )
            return None
        logger.debug(
            "%s 请求完成：url=%s, status_code=%s, elapsed=%.3fs, task_len=%s, keys=%s",
            self.service_name, url, resp.status_code, elapsed, summary["task_len"], sorted(payload.keys()),
        )
        return payload

    def run(self, input_dict_str: str) -> str:
        payload = self._post_exec(input_dict_str)
        if not payload:
            return ""
        out_text = payload.get("out_text")
        if out_text is None:
            logger.warning("%s 响应缺少 out_text 字段：keys=%s", self.service_name, sorted(payload.keys()))
            return ""
        return str(out_text)


class STTAgent(_ExecAudioClient):
    service_name = "STT"

    def __init__(self, host_url: str):
        super().__init__(host_url)
        self.last_utterance_id = 0

    def run(self, input_dict_str: str) -> str:
        payload = self._post_exec(input_dict_str)
        if not payload:
            return ""
        utterance_id = payload.get("utterance_id")
        if utterance_id is not None:
            try:
                self.last_utterance_id = int(utterance_id)
            except (TypeError, ValueError):
                logger.warning("STT 响应 utterance_id 解析失败：value=%s", utterance_id)
        out_text = payload.get("out_text")
        if out_text is None:
            logger.warning("STT 响应缺少 out_text 字段：keys=%s", sorted(payload.keys()))
            return ""
        return str(out_text)


class TTSAgent(_ExecAudioClient):
    service_name = "TTS"

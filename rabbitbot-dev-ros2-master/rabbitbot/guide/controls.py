from __future__ import annotations

import logging
import re
from typing import Iterable

logger = logging.getLogger(__name__)

_CONTROL_PUNCT_RE = re.compile(r"[\s，。！？?、,.!；;：:\"'“”‘’（）()\[\]【】]+")

DEFAULT_CONTINUE_TEXTS = {
    "好", "好的", "好啊", "好呀", "嗯", "嗯嗯", "可以", "行", "行的",
    "继续", "继续吧", "接着讲", "接着说", "往下讲", "往下说",
    "收到", "知道了", "明白", "明白了", "没问题",
}


def normalize_control_text(text: str | None) -> str:
    """归一化语音控制词，只返回匹配用摘要，不记录原文。"""
    return _CONTROL_PUNCT_RE.sub("", text or "").lower()


def build_control_commands(raw_value: str | None, defaults: Iterable[str]) -> list[str]:
    commands = [normalize_control_text(item) for item in (raw_value or "").split(",") if normalize_control_text(item)]
    if commands:
        logger.debug("控制词配置解析完成：count=%s", len(commands))
        return commands
    fallback = [normalize_control_text(item) for item in defaults if normalize_control_text(item)]
    logger.warning("控制词配置为空，使用默认值：count=%s", len(fallback))
    return fallback


def matches_control_command(text: str | None, commands: Iterable[str]) -> bool:
    normalized_text = normalize_control_text(text)
    if not normalized_text:
        logger.debug("控制词匹配跳过空文本：text_len=%s", len(text or ""))
        return False
    matched = any(command in normalized_text for command in commands)
    logger.debug("控制词匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched


def is_continue_text(text: str | None, continue_texts: Iterable[str] = DEFAULT_CONTINUE_TEXTS) -> bool:
    normalized_text = normalize_control_text(text)
    normalized_continue_texts = {normalize_control_text(item) for item in continue_texts}
    matched = normalized_text in normalized_continue_texts
    logger.debug("剧本继续词匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched

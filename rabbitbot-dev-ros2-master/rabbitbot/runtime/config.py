from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def env_url(name: str, default: str) -> str:
    """读取服务 URL，空值回退默认值。"""
    value = os.getenv(name, default).strip()
    if value:
        return value
    logger.warning("服务 URL 配置为空，使用默认值：name=%s, default=%s", name, default)
    return default


def env_float(name: str, default: float) -> float:
    """读取浮点配置，非法时记录上下文并回退默认值。"""
    raw_value = os.getenv(name, str(default))
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        logger.warning("浮点配置非法，使用默认值：name=%s, value=%s, default=%s", name, raw_value, default)
        return float(default)

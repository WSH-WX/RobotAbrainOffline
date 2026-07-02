from __future__ import annotations

import difflib
import logging
import re
from collections.abc import Iterable

logger = logging.getLogger(__name__)

NAV_TEXT_REPLACEMENTS = {
    "复新": "复星",
    "负星": "复星",
    "福星": "复星",
    "合营": "合影",
    "合迎": "合影",
    "和影": "合影",
    "合映": "合影",
    "合应": "合影",
    "合英": "合影",
    "和迎": "合影",
    "合音": "合影",
    "资源": "智元",
    "自原": "智元",
    "自愿": "智元",
    "原区": "园区",
    "骑石": "起始",
    "骑士": "起始",
    "骑是": "起始",
    "奇石": "起始",
    "奇士": "起始",
    "启示": "起始",
    "其实": "起始",
    "其是": "起始",
    "起事": "起始",
    "趣奇石": "去起始",
    "趣骑士": "去起始",
    "趣起始": "去起始",
    "去骑石": "去起始",
    "去骑士": "去起始",
    "去奇石": "去起始",
    "骑石板块": "起始板块",
    "骑士板块": "起始板块",
    "骑是板块": "起始板块",
    "奇石板块": "起始板块",
    "奇士板块": "起始板块",
    "启示板块": "起始板块",
    "其实板块": "起始板块",
    "其是板块": "起始板块",
    "起事板块": "起始板块",
}

CHAT_INFO_KEYWORDS = ["介绍", "讲讲", "说明", "了解", "是什么", "有什么", "内容", "功能", "特色", "怎么样"]
NAVIGATION_ACTION_KEYWORDS = [
    "我要去", "我想去", "带我去", "带我们去", "带着我去", "带着我们去",
    "去", "前往", "过去", "导航到", "走到", "参观", "逛一下",
]
VISUAL_KEYWORDS = [
    "你看到了什么", "你看到什么", "你现在看到什么", "前面有什么",
    "画面里有什么", "图片里有什么", "桌子上有什么", "桌上有什么",
    "帮我看一下", "看一下前面", "看看前面", "看一下画面", "看看画面",
    "识别一下", "视觉理解",
]
NEXT_BOARD_KEYWORDS = [
    "去下一个板块", "下一个板块", "下一板块", "下个板块",
    "去下一个展点", "下一个展点", "下一展点",
    "下一站", "去下一站", "继续下一个", "下一个地方",
]
FUZZY_REMOVE_WORDS = [
    "我要去", "我想去", "带我去", "带我们去", "带着我去", "带着我们去",
    "请", "帮我", "导航到", "走到", "前往", "过去", "去", "参观", "看看", "看一看", "看一下", "逛一下",
]


def normalize_nav_text(text: str | None) -> str:
    normalized = (text or "").strip()
    for old, new in NAV_TEXT_REPLACEMENTS.items():
        normalized = normalized.replace(old, new)
    return re.sub(r"[\s，。！？?、,.!]+", "", normalized)


def has_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def has_navigation_action(text: str | None) -> bool:
    normalized = normalize_nav_text(text)
    matched = has_any(normalized, NAVIGATION_ACTION_KEYWORDS)
    logger.debug("导航动作规则匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched


def is_chat_info_request(text: str | None) -> bool:
    normalized = normalize_nav_text(text)
    matched = has_any(normalized, CHAT_INFO_KEYWORDS) and not has_navigation_action(text)
    logger.debug("聊天信息规则匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched


def is_visual_request(text: str | None) -> bool:
    normalized = normalize_nav_text(text)
    matched = has_any(normalized, VISUAL_KEYWORDS)
    logger.debug("视觉规则匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched


def is_direct_navigation_request(text: str | None) -> bool:
    return has_navigation_action(text)


def is_next_board_request(text: str | None) -> bool:
    normalized = normalize_nav_text(text)
    matched = has_any(normalized, NEXT_BOARD_KEYWORDS)
    logger.debug("下一点位规则匹配完成：text_len=%s, matched=%s", len(text or ""), matched)
    return matched


def classify_task_by_rule(text: str | None) -> str | None:
    if is_visual_request(text):
        result = "V"
    elif is_chat_info_request(text):
        result = "C"
    elif has_navigation_action(text):
        result = "N"
    else:
        result = None
    logger.debug("任务规则分类完成：text_len=%s, result=%s", len(text or ""), result)
    return result


def resolve_navigation_entity_by_fuzzy(text: str | None, entity_lst: Iterable[str]) -> tuple[str | None, float]:
    normalized_text = normalize_nav_text(text)
    if normalized_text == "":
        logger.debug("导航实体模糊匹配跳过空文本：entity_count=%s", len(list(entity_lst)) if hasattr(entity_lst, "__len__") else "unknown")
        return None, 0.0

    target_text = normalized_text
    for word in FUZZY_REMOVE_WORDS:
        target_text = target_text.replace(word, "")

    best_entity = None
    best_score = 0.0
    entity_count = 0
    for entity_name in entity_lst:
        entity_count += 1
        normalized_entity = normalize_nav_text(entity_name)
        if not normalized_entity:
            continue
        if normalized_entity in normalized_text or normalized_entity in target_text:
            logger.debug("导航实体精确包含匹配：text_len=%s, entity_count=%s, matched=True", len(text or ""), entity_count)
            return entity_name, 1.0
        if target_text and target_text in normalized_entity:
            score = max(0.85, len(target_text) / max(len(normalized_entity), 1))
        else:
            score = max(
                difflib.SequenceMatcher(None, normalized_text, normalized_entity).ratio(),
                difflib.SequenceMatcher(None, target_text, normalized_entity).ratio() if target_text else 0.0,
            )
        if score > best_score:
            best_entity = entity_name
            best_score = score

    matched = best_score >= 0.62
    logger.debug(
        "导航实体模糊匹配完成：text_len=%s, entity_count=%s, matched=%s, best_score=%.3f",
        len(text or ""), entity_count, matched, best_score,
    )
    if matched:
        return best_entity, best_score
    return None, best_score

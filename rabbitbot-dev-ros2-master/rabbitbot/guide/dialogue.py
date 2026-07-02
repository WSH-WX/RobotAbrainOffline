from __future__ import annotations

import ast
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Mapping, MutableMapping

logger = logging.getLogger(__name__)

DEFAULT_DIALOGUE_INDEX = "0"
DOCX_POINT_LOCATION_REQUIRED_FIELDS = ("x", "y", "z", "ox", "oy", "oz", "ow", "mode")
DOCX_POINT_LOCATION_FLOAT_FIELDS = ("x", "y", "z", "ox", "oy", "oz", "ow")


def dialogue_index(env: Mapping[str, str] | None = None, default_index: str = DEFAULT_DIALOGUE_INDEX) -> str:
    if env is None:
        env = os.environ
    raw_dialogue_index = env.get("RABBITBOT_DIALOGUE_INDEX", "").strip()
    raw_legacy_index = env.get("RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX", "").strip()
    raw_index = raw_dialogue_index or raw_legacy_index or default_index
    if not re.fullmatch(r"[0-9]+", raw_index):
        logger.error(
            "DOCX 导览台词序号非法：dialogue_index_set=%s, legacy_index_set=%s, effective_len=%s",
            bool(raw_dialogue_index), bool(raw_legacy_index), len(raw_index),
        )
        raise ValueError(f"DOCX 导览台词序号必须是数字: {raw_index!r}")
    if not raw_dialogue_index and not raw_legacy_index:
        logger.info("DOCX 导览台词序号未设置，使用默认序号：index=%s", default_index)
    return raw_index


def dialogue_path(dialogue_dir: Path, env: Mapping[str, str] | None = None, default_index: str = DEFAULT_DIALOGUE_INDEX) -> Path:
    if env is None:
        env = os.environ
    configured_path = env.get("RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE", "").strip()
    if configured_path:
        logger.info("DOCX 导览台词使用显式文件路径：path=%s", configured_path)
        return Path(configured_path)
    return Path(dialogue_dir) / f"dialogue_{dialogue_index(env, default_index)}.json"


def _validate_dialogue(data, path: Path) -> dict:
    if not isinstance(data, dict):
        logger.error("DOCX 导览台词根节点类型非法：path=%s, actual_type=%s", path, type(data).__name__)
        raise ValueError(f"DOCX 导览台词文件根节点必须是对象: {path}")
    variables = data.get("variables", {})
    opening = data.get("opening", {})
    steps = data.get("steps", [])
    map_file = data.get("map_file", "")
    points = data.get("points", {})
    if not isinstance(variables, dict):
        logger.error("DOCX 导览台词 variables 类型非法：path=%s, actual_type=%s", path, type(variables).__name__)
        raise ValueError(f"DOCX 导览台词 variables 必须是对象: {path}")
    if not isinstance(opening, dict):
        logger.error("DOCX 导览台词 opening 类型非法：path=%s, actual_type=%s", path, type(opening).__name__)
        raise ValueError(f"DOCX 导览台词 opening 必须是对象: {path}")
    if not isinstance(steps, list):
        logger.error("DOCX 导览台词 steps 类型非法：path=%s, actual_type=%s", path, type(steps).__name__)
        raise ValueError(f"DOCX 导览台词 steps 必须是数组: {path}")
    if map_file is not None and not isinstance(map_file, str):
        logger.error("DOCX 导览台词 map_file 类型非法：path=%s, actual_type=%s", path, type(map_file).__name__)
        raise ValueError(f"DOCX 导览台词 map_file 必须是字符串: {path}")
    if points is None:
        points = {}
        data["points"] = points
    if not isinstance(points, dict):
        logger.error("DOCX 导览台词 points 类型非法：path=%s, actual_type=%s", path, type(points).__name__)
        raise ValueError(f"DOCX 导览台词 points 必须是对象: {path}")
    return data


def load_dialogue(dialogue_dir: Path, env: Mapping[str, str] | None = None, cache: MutableMapping | None = None, default_index: str = DEFAULT_DIALOGUE_INDEX) -> dict:
    path = dialogue_path(dialogue_dir, env, default_index)
    if cache is not None and cache.get("path") == path and cache.get("data") is not None:
        return cache["data"]

    start_time = time.perf_counter()
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except FileNotFoundError as exc:
        logger.error("DOCX 导览台词文件缺失：path=%s, error_type=%s", path, type(exc).__name__)
        raise FileNotFoundError(f"DOCX 导览台词文件缺失: {path}") from exc
    except json.JSONDecodeError as exc:
        logger.error(
            "DOCX 导览台词 JSON 解析失败：path=%s, line=%s, column=%s, message=%s",
            path, exc.lineno, exc.colno, exc.msg,
        )
        raise ValueError(f"DOCX 导览台词文件 JSON 解析失败: {path}") from exc

    data = _validate_dialogue(data, path)
    variables = data.get("variables", {})
    steps = data.get("steps", [])
    points = data.get("points", {})
    segment_count = sum(len(step.get("segments", []) or []) for step in steps if isinstance(step, dict))
    elapsed_seconds = time.perf_counter() - start_time
    logger.info(
        "DOCX 导览台词文件加载完成：path=%s, points=%s, steps=%s, segments=%s, leader_calling_set=%s, elapsed=%.3fs",
        path, len(points), len(steps), segment_count, bool(str(variables.get("leader_calling") or "").strip()), elapsed_seconds,
    )
    if cache is not None:
        cache["path"] = path
        cache["data"] = data
    return data


def guide_variables(data: dict, path: Path, extra_variables: Mapping | None = None) -> dict:
    variables = dict(data.get("variables", {}) or {})
    if "leader_calling" not in variables or not str(variables.get("leader_calling") or "").strip():
        logger.error("DOCX 导览台词缺少必填变量：path=%s, key=leader_calling", path)
        raise KeyError(f"DOCX 导览台词 variables 缺少必填称呼键: key=leader_calling, path={path}")
    variables["leader_calling"] = str(variables["leader_calling"]).strip()
    if extra_variables:
        variables.update(extra_variables)
        if "leader_calling" in variables:
            variables["leader_calling"] = str(variables["leader_calling"]).strip()
    return variables


def guide_leader_calling(data: dict, path: Path) -> str:
    return guide_variables(data, path)["leader_calling"]


def guide_map_file(data: dict) -> str:
    return str(data.get("map_file") or "").strip()


def format_guide_text(data: dict, path: Path, text, variables: Mapping | None = None) -> str:
    if text is None:
        return ""
    format_variables = guide_variables(data, path, variables)
    try:
        return str(text).format(**format_variables)
    except KeyError as exc:
        logger.error("DOCX 导览台词占位符缺少变量：path=%s, missing=%s, available=%s", path, exc.args[0], sorted(format_variables.keys()))
        raise


def opening_text(data: dict, path: Path, key: str, variables: Mapping | None = None) -> str:
    opening = data.get("opening", {}) or {}
    if key not in opening:
        logger.error("DOCX 导览台词 opening 缺少键：path=%s, key=%s", path, key)
        raise KeyError(f"DOCX 导览台词 opening 缺少键: key={key}, path={path}")
    return format_guide_text(data, path, opening[key], variables)


def normalize_point_entity(point_key: str, raw_point, path: Path) -> dict:
    if not isinstance(raw_point, dict):
        logger.error("DOCX 导览台词 points 条目类型非法：path=%s, key=%s, actual_type=%s", path, point_key, type(raw_point).__name__)
        raise ValueError(f"DOCX 导览台词 points 条目必须是对象: key={point_key}, path={path}")
    name = str(raw_point.get("name") or point_key).strip()
    if not name:
        logger.error("DOCX 导览台词 points 条目缺少名称：path=%s, key=%s", path, point_key)
        raise ValueError(f"DOCX 导览台词 points 条目缺少 name: key={point_key}, path={path}")
    raw_location = raw_point.get("location", [])
    if raw_location is None:
        raw_location = []
    if not isinstance(raw_location, list):
        logger.error("DOCX 导览台词 points.location 类型非法：path=%s, key=%s, actual_type=%s", path, point_key, type(raw_location).__name__)
        raise ValueError(f"DOCX 导览台词 points.location 必须是数组: key={point_key}, path={path}")
    location = []
    for index, item in enumerate(raw_location):
        if not isinstance(item, dict):
            logger.error("DOCX 导览台词 points.location 条目类型非法：path=%s, key=%s, index=%s, actual_type=%s", path, point_key, index, type(item).__name__)
            raise ValueError(f"DOCX 导览台词 points.location 条目必须是对象: key={point_key}, index={index}, path={path}")
        location_item = dict(item)
        missing_fields = [field for field in DOCX_POINT_LOCATION_REQUIRED_FIELDS if field not in location_item]
        if missing_fields:
            logger.error("DOCX 导览台词 points.location 缺少字段：path=%s, key=%s, index=%s, missing=%s", path, point_key, index, missing_fields)
            raise ValueError(
                "DOCX 导览台词 points.location 缺少坐标字段: "
                f"key={point_key}, index={index}, missing={missing_fields}, path={path}"
            )
        for field in DOCX_POINT_LOCATION_FLOAT_FIELDS:
            try:
                location_item[field] = float(location_item[field])
            except (TypeError, ValueError) as exc:
                logger.error("DOCX 导览台词 points.location 坐标字段非法：path=%s, key=%s, index=%s, field=%s, value_type=%s", path, point_key, index, field, type(location_item.get(field)).__name__)
                raise ValueError(
                    "DOCX 导览台词 points.location 坐标字段必须是数字: "
                    f"key={point_key}, index={index}, field={field}, path={path}"
                ) from exc
        try:
            location_item["mode"] = int(location_item["mode"])
        except (TypeError, ValueError) as exc:
            logger.error("DOCX 导览台词 points.location mode 字段非法：path=%s, key=%s, index=%s, value_type=%s", path, point_key, index, type(location_item.get("mode")).__name__)
            raise ValueError(f"DOCX 导览台词 points.location mode 必须是整数: key={point_key}, index={index}, path={path}") from exc
        location.append(location_item)
    return {
        "name": name,
        "summary": str(raw_point.get("summary") or name),
        "description": str(raw_point.get("description") or ""),
        "location": location,
    }


def point_entities(data: dict, path: Path) -> dict:
    raw_points = data.get("points", {}) or {}
    entities = {}
    for point_key, raw_point in raw_points.items():
        key = str(point_key).strip()
        if not key:
            logger.error("DOCX 导览台词 points 存在空 key：path=%s", path)
            raise ValueError(f"DOCX 导览台词 points 存在空 key: path={path}")
        entity = normalize_point_entity(key, raw_point, path)
        entities[key] = entity
        entities.setdefault(entity["name"], entity)
    return entities


def load_script_steps(data: dict, path: Path, point_entity: Mapping[str, str], entity_resolver=None) -> list[dict]:
    raw_steps = data.get("steps", [])
    if not raw_steps:
        logger.error("DOCX 导览台词 steps 为空：path=%s", path)
        raise ValueError(f"DOCX 导览台词 steps 为空: {path}")

    steps = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, dict):
            logger.error("DOCX 导览台词 step 类型非法：path=%s, index=%s, actual_type=%s", path, index, type(raw_step).__name__)
            raise ValueError(f"DOCX 导览台词 step 必须是对象: index={index}")
        step = dict(raw_step)
        entity_key = step.pop("entity_key", None)
        if entity_key:
            entity = entity_resolver(str(entity_key)) if entity_resolver else None
            if entity is None and entity_key in point_entity:
                entity = entity_resolver(point_entity[entity_key]) if entity_resolver else {"name": point_entity[entity_key]}
            if entity is None:
                logger.error("DOCX 导览台词 step entity_key 未定义：path=%s, index=%s, entity_key=%s", path, index, entity_key)
                raise KeyError(f"DOCX 导览台词 step entity_key 未定义: index={index}, entity_key={entity_key}")
            step["entity"] = entity["name"]
        segments = step.get("segments", [])
        if segments is None:
            segments = []
        if not isinstance(segments, list):
            logger.error("DOCX 导览台词 step segments 类型非法：path=%s, index=%s, scene=%s, actual_type=%s", path, index, step.get("scene"), type(segments).__name__)
            raise ValueError(f"DOCX 导览台词 step segments 必须是数组: index={index}, scene={step.get('scene')}")
        step["segments"] = [dict(segment) for segment in segments]
        steps.append(step)
    return steps

def extract_location_points(entity) -> list[tuple[float, float, float, float, float, float]]:
    if not entity:
        return []
    location = entity.get("location") if isinstance(entity, dict) else entity
    if isinstance(location, str):
        try:
            location = ast.literal_eval(location)
        except (SyntaxError, ValueError):
            logger.warning("导航点位字符串解析失败：location_len=%s", len(location))
            return []
    if isinstance(location, dict):
        location = [location]
    if not isinstance(location, (list, tuple)) or not location:
        return []

    if len(location) >= 6 and not isinstance(location[0], (list, tuple, dict)):
        location = [location]

    points = []
    for item in location:
        if isinstance(item, dict):
            point = [item.get("x"), item.get("y"), item.get("ox"), item.get("oy"), item.get("oz"), item.get("ow")]
        elif isinstance(item, (list, tuple)) and len(item) >= 6:
            point = list(item[:6])
        else:
            continue
        try:
            points.append(tuple(float(value) for value in point))
        except (TypeError, ValueError):
            logger.warning("导航点位条目包含非数字字段，已跳过：item_type=%s", type(item).__name__)
            continue
    return points

"""DOCX 台词与 JSON 实体/点位数据加载（含起点导航辅助）。从 workflow.py 拆出，行为不变。"""

import os
import json
import time
import asyncio
from pathlib import Path
from rabbitbot.robots.constants import NavigationStatus
from rabbitbot.tools.navi_agno import NavigationToolkit, NavigationQuery, is_navigating
from rabbitbot.guide.dialogue import (
    dialogue_index as guide_dialogue_index,
    dialogue_path as guide_dialogue_path,
    extract_location_points as guide_extract_location_points,
    format_guide_text as guide_format_text,
    guide_leader_calling as guide_dialogue_leader_calling,
    guide_map_file as guide_dialogue_map_file,
    guide_variables as guide_dialogue_variables,
    load_dialogue as guide_load_dialogue,
    load_script_steps as guide_load_script_steps,
    normalize_point_entity as guide_normalize_point_entity,
    opening_text as guide_opening_text,
    point_entities as guide_point_entities,
)
from .workflow_config import _workflow_log, _workflow_non_integration_enabled


DOCX_GUIDE_DIALOGUE_DIR = Path(__file__).resolve().parents[2] / "conf"
DOCX_GUIDE_DIALOGUE_DEFAULT_INDEX = "0"
_DOCX_GUIDE_DIALOGUE_CACHE = {"path": None, "data": None}
def _docx_guide_dialogue_index():
    return guide_dialogue_index(os.environ, DOCX_GUIDE_DIALOGUE_DEFAULT_INDEX)
def _docx_guide_dialogue_path():
    return guide_dialogue_path(DOCX_GUIDE_DIALOGUE_DIR, os.environ, DOCX_GUIDE_DIALOGUE_DEFAULT_INDEX)
def _load_docx_guide_dialogue():
    return guide_load_dialogue(
        DOCX_GUIDE_DIALOGUE_DIR,
        env=os.environ,
        cache=_DOCX_GUIDE_DIALOGUE_CACHE,
        default_index=DOCX_GUIDE_DIALOGUE_DEFAULT_INDEX,
    )
def reload_docx_guide_dialogue(reason="manual"):
    _DOCX_GUIDE_DIALOGUE_CACHE["path"] = None
    _DOCX_GUIDE_DIALOGUE_CACHE["data"] = None
    data = _load_docx_guide_dialogue()
    _workflow_log(
        "DOCX 导览台词缓存已刷新: "
        f"reason={reason}, path={_docx_guide_dialogue_path()}, "
        f"steps={len(data.get('steps', []) or [])}, points={len(data.get('points', {}) or {})}"
    )
    return data
def _docx_guide_variables(extra_variables=None):
    return guide_dialogue_variables(_load_docx_guide_dialogue(), _docx_guide_dialogue_path(), extra_variables)
def _docx_guide_leader_calling():
    return guide_dialogue_leader_calling(_load_docx_guide_dialogue(), _docx_guide_dialogue_path())
def _docx_guide_map_file():
    return guide_dialogue_map_file(_load_docx_guide_dialogue())
def _normalize_docx_point_entity(point_key, raw_point):
    return guide_normalize_point_entity(point_key, raw_point, _docx_guide_dialogue_path())
def _docx_guide_point_entities():
    return guide_point_entities(_load_docx_guide_dialogue(), _docx_guide_dialogue_path())
def _format_docx_guide_text(text, variables=None):
    return guide_format_text(_load_docx_guide_dialogue(), _docx_guide_dialogue_path(), text, variables)
def _docx_opening_text(key, variables=None):
    return guide_opening_text(_load_docx_guide_dialogue(), _docx_guide_dialogue_path(), key, variables)
def _load_docx_script_steps(point_entity):
    return guide_load_script_steps(
        _load_docx_guide_dialogue(),
        _docx_guide_dialogue_path(),
        point_entity,
        entity_resolver=_load_docx_point_entity,
    )
DOCX_SCRIPT_POINTS = {
    "点位1": {
        "summary": "点位1",
        "description": "DOCX 剧本起始点位。",
        "location": [
            {"x": 1.9105, "y": -1.6180, "z": 0.0117, "ox": -0.0029, "oy": 0.0265, "oz": -0.2046, "ow": 0.9785, "mode": 1},
        ],
    },
    "1->2过渡点位": {
        "summary": "1->2过渡点位",
        "description": "DOCX 剧本点位1前往点位2路径上的过渡点位；该点位只导航，不播报台词。",
        "location": [
            {"x": 8.6465, "y": -2.5763, "z": -0.0722, "ox": 0.0547, "oy": 0.0907, "oz": 0.5347, "ow": 0.8384, "mode": 1},
        ],
    },
    "点位2": {
        "summary": "点位2",
        "description": "DOCX 剧本问咖啡点位；点咖啡台词只允许在该最终点位播报。",
        "location": [
            {"x": 10.1203, "y": 0.8162, "z": -0.1335, "ox": 0.0904, "oy": 0.0373, "oz": 0.9074, "ow": 0.4087, "mode": 1},
        ],
    },
    "点位3": {
        "summary": "点位3",
        "description": "DOCX 剧本拿取咖啡点位。",
        "location": [
            {"x": 11.1090, "y": 4.3229, "z": -0.1892, "ox": 0.0937, "oy": 0.0170, "oz": 0.9717, "ow": 0.2162, "mode": 1},
        ],
    },
    "点位4": {
        "summary": "点位4",
        "description": "DOCX 剧本点位3前往点位5路径上的中转点位。",
        "location": [
            {"x": 13.9410, "y": -5.1633, "z": 0.0350, "ox": 0.0140, "oy": 0.0335, "oz": -0.9085, "ow": -0.4163, "mode": 1},
        ],
    },
    "3->5过渡点位": {
        "summary": "3->5过渡点位",
        "description": "DOCX 剧本点位3前往点位5路径上的过渡点位；该点位只导航，不播报台词。",
        "location": [
            {"x": 5.5507, "y": 14.4097, "z": -0.1921, "ox": 0.0779, "oy": 0.0578, "oz": 0.7806, "ow": 0.6174, "mode": 1},
        ],
    },
    "点位5": {
        "summary": "点位5",
        "description": "DOCX 剧本告别并指引小巴方向点位；告别台词只允许在该最终点位播报。",
        "location": [
            {"x": 4.7039, "y": 20.4749, "z": -0.2250, "ox": 0.0876, "oy": -0.0269, "oz": 0.9076, "ow": -0.4096, "mode": 1},
        ],
    },
}
def _load_docx_point_entity(name):
    dialogue_points = _docx_guide_point_entities()
    if name in dialogue_points:
        entity = dict(dialogue_points[name])
        _workflow_log(
            "DOCX 导览点位使用台词文件配置: "
            f"key={name}, entity={entity.get('name')}, points={len(entity.get('location', []) or [])}, "
            f"map_file={_docx_guide_map_file() or '未配置'}"
        )
        return entity

    point = DOCX_SCRIPT_POINTS.get(name)
    if not point:
        return None
    _workflow_log(f"DOCX 导览点位使用代码兜底配置: name={name}")
    return {
        "name": name,
        "summary": point.get("summary", name),
        "description": point.get("description", ""),
        "location": point.get("location", []),
    }
async def _ensure_start_position(ctx, start_entity_name="点位1"):
    if getattr(ctx, "start_position_confirmed", False):
        return NavigationStatus.SUCCEEDED

    start_entity = _load_docx_point_entity(start_entity_name) or _load_json_entity(start_entity_name)
    start_points = _extract_location_points(start_entity)
    if not start_points:
        print(f"{start_entity_name}缺少可用导航点位: {start_entity}")
        return NavigationStatus.ABORTED

    enable_navi = os.getenv("RABBITBOT_ENABLE_NAVI", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enable_navi:
        ctx.start_position_confirmed = True
        return NavigationStatus.SUCCEEDED

    if _wait_manual_navigation_success(start_entity_name):
        start_navi_status = NavigationStatus.SUCCEEDED
    else:
        navi_tools = NavigationToolkit(ctx)
        navi_query = NavigationQuery()
        x, y, ox, oy, oz, ow = start_points[0]
        await navi_tools.go_to_async(
            x, y, ox, oy, oz, ow, navi_query,
            waypoints=start_points if len(start_points) > 1 else None,
        )
        while await is_navigating(navi_tools):
            await asyncio.sleep(0.5)
        start_navi_status = await navi_tools.go_to_status()
        await navi_tools.reset_go_to_status()

    if start_navi_status == NavigationStatus.SUCCEEDED:
        ctx.start_position_confirmed = True
        ctx.current_entity_name = start_entity_name
        entity_order = getattr(ctx, 'json_entity_order', None) or JSON_ENTITY_ORDER or getattr(ctx, 'entity_lst', [])
        if start_entity_name in entity_order:
            ctx.current_entity_index = entity_order.index(start_entity_name)

    return start_navi_status
def _wait_manual_navigation_success(location_name):
    if not _workflow_non_integration_enabled():
        return False

    arrival_file = os.getenv("RABBITBOT_WORKFLOW_MANUAL_ARRIVAL_FILE", "").strip()
    if arrival_file:
        path = Path(arrival_file)
        start_ts = time.time()
        _workflow_log(f"[无机器人模式] 等待到达确认：location={location_name}, file={path}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.unlink()
        except OSError as exc:
            _workflow_log(f"[无机器人模式] 清理旧到达确认文件失败：location={location_name}, file={path}, error_type={type(exc).__name__}, error={exc}")
        while True:
            if path.exists():
                try:
                    path.unlink()
                except OSError as exc:
                    _workflow_log(f"[无机器人模式] 删除到达确认文件失败：location={location_name}, file={path}, error_type={type(exc).__name__}, error={exc}")
                elapsed = time.time() - start_ts
                _workflow_log(f"[无机器人模式] 已确认到达：location={location_name}, elapsed={elapsed:.3f}s")
                return True
            time.sleep(0.2)

    prompt = f"[无机器人模式] 请在确认到达“{location_name}”后按任意键，workflow 将视为导航成功..."
    print(prompt, flush=True)
    try:
        import sys
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print()
    except Exception:
        input(f"[无机器人模式] 请在确认到达“{location_name}”后按回车继续...")
    return True
def _load_combined_data():
    data_file = Path(__file__).resolve().parents[2] / "combined_data.json"
    try:
        return json.loads(data_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"加载 combined_data.json 失败: {exc}")
        return []
def _load_json_entity_order():
    return [item.get("name") for item in _load_combined_data() if item.get("name")]
def _load_json_entity(name):
    for item in _load_combined_data():
        if item.get("name") != name:
            continue
        sentences = item.get("sentences") or []
        description = "".join(sentences)
        return {
            "name": name,
            "summary": sentences[0] if sentences else name,
            "description": description,
            "location": item.get("location") or [],
        }
    return None
def _extract_first_location_point(entity):
    points = _extract_location_points(entity)
    return points[0] if points else None
def _extract_location_points(entity):
    return guide_extract_location_points(entity)
def _prefer_json_entity_location(entity):
    if not isinstance(entity, dict):
        return entity
    name = entity.get("name")
    if not name:
        return entity

    json_entity = _load_json_entity(name)
    json_points = _extract_location_points(json_entity)
    if not json_points:
        return entity

    merged_entity = dict(entity)
    merged_entity["location"] = json_entity["location"]
    if not merged_entity.get("description") and json_entity.get("description"):
        merged_entity["description"] = json_entity["description"]
    if not merged_entity.get("summary") and json_entity.get("summary"):
        merged_entity["summary"] = json_entity["summary"]

    memory_points = _extract_location_points(entity)
    if len(json_points) != len(memory_points):
        print(f"使用 combined_data.json 中的完整导航点位: {name}, points={len(json_points)}")
    return merged_entity
JSON_ENTITY_ORDER = _load_json_entity_order()

"""workflow 插装/耗时统计（profile JSONL 写入、span、退出汇总）。从 workflow.py 拆出，行为不变。"""

import time
import json
import threading
import atexit
from datetime import datetime
from .workflow_config import (
    _workflow_profile_enabled,
    _workflow_profile_path,
    _workflow_profile_summary_enabled,
)


class WorkflowTimePoints:
    PLAN_START = -1
    PLAN_END = -1
    NAVI_CHECK_START = -1
    NAVI_CHECK_END = -1
    CHAT_START = -1
    CHAT_FIRST_TEXT_START = -1
    CHAT_END = -1
_profile_lock = threading.Lock()
_profile_span_id = 0
_profile_summary_lock = threading.RLock()
_profile_summary = {}
def _workflow_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
def _format_log_fields(fields):
    return ", ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
def _workflow_action_log(stage, action_name=None, **fields):
    field_text = _format_log_fields(fields)
    suffix = f", {field_text}" if field_text else ""
    print(f"[{_workflow_timestamp()}] workflow动作链路: stage={stage}, action={action_name}{suffix}")
def _profile_json_safe(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _profile_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_profile_json_safe(item) for item in value]
    return str(value)
def _profile_write(record):
    if not _workflow_profile_enabled():
        return
    record = {key: _profile_json_safe(value) for key, value in record.items()}
    record.setdefault("ts", _workflow_timestamp())
    profile_path = _workflow_profile_path()
    try:
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with _profile_lock:
            with profile_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"workflow profile 写入失败: path={profile_path}, error={exc}")
def _profile_next_span_id():
    global _profile_span_id
    with _profile_lock:
        _profile_span_id += 1
        return _profile_span_id
def _profile_start(span, **fields):
    _profile_summary_start_if_needed()
    span_token = {
        "span_id": _profile_next_span_id(),
        "span": span,
        "start_perf": time.perf_counter(),
    }
    _profile_write({
        "event": "start",
        "span": span,
        "span_id": span_token["span_id"],
        **fields,
    })
    return span_token
def _profile_end(span_token, **fields):
    if not span_token:
        return
    elapsed_seconds = time.perf_counter() - span_token["start_perf"]
    _profile_write({
        "event": "end",
        "span": span_token["span"],
        "span_id": span_token["span_id"],
        "elapsed": round(elapsed_seconds, 6),
        **fields,
    })
    _profile_summary_record(span_token["span"], elapsed_seconds)
def _profile_instant(name, span=None, **fields):
    record = {
        "event": "instant",
        "name": name,
        **fields,
    }
    if span:
        record["span"] = span
    _profile_write(record)
def _profile_summary_reset():
    global _profile_summary
    with _profile_summary_lock:
        _profile_summary = {
            "start_perf": None,
            "printed": False,
            "loop_iterations": 0,
            "stats": {
                "audio_input": {"count": 0, "sum": 0.0},
                "plan_llm": {"count": 0, "sum": 0.0},
                "chat_llm": {"count": 0, "sum": 0.0},
                "chat_tts": {"count": 0, "sum": 0.0},
                "action": {"count": 0, "sum": 0.0},
                "navi_check": {"count": 0, "sum": 0.0},
                "completion_check": {"count": 0, "sum": 0.0},
            },
        }
def _profile_summary_start_if_needed():
    if not _workflow_profile_summary_enabled():
        return
    with _profile_summary_lock:
        if not _profile_summary:
            _profile_summary_reset()
        if _profile_summary["start_perf"] is None:
            _profile_summary["start_perf"] = time.perf_counter()
def _profile_summary_label(span):
    return {
        "audio_input": "audio_input",
        "listen_answer": "audio_input",
        "plan_llm": "plan_llm",
        "chat_llm": "chat_llm",
        "chat_tts": "chat_tts",
        "tts_segment": "chat_tts",
        "arm_action": "action",
        "navi_check": "navi_check",
        "completion_check": "completion_check",
    }.get(span)
def _profile_summary_record(span, elapsed_seconds):
    if not _workflow_profile_summary_enabled():
        return
    _profile_summary_start_if_needed()
    with _profile_summary_lock:
        if span == "loop_iteration":
            _profile_summary["loop_iterations"] += 1
        label = _profile_summary_label(span)
        if not label:
            return
        stat = _profile_summary["stats"][label]
        stat["count"] += 1
        stat["sum"] += float(elapsed_seconds)
def _profile_summary_line(label):
    stat = _profile_summary["stats"].get(label, {"count": 0, "sum": 0.0})
    count = stat["count"]
    avg = stat["sum"] / count if count else 0.0
    return f"{label + ' (avg):':<22}{avg:>9.3f}s  (×{count})"
def _profile_summary_print(reason="finished", force=False):
    if not _workflow_profile_summary_enabled():
        return
    with _profile_summary_lock:
        if not _profile_summary:
            return
        if _profile_summary.get("printed") and not force:
            return
        start_perf = _profile_summary.get("start_perf")
        loop_total = time.perf_counter() - start_perf if start_perf is not None else 0.0
        lines = [
            "========== Workflow Profile Summary ==========",
            f"loop_total:{loop_total:>20.3f}s",
            f"loop_iterations:{_profile_summary['loop_iterations']:>9}",
            _profile_summary_line("audio_input"),
            _profile_summary_line("plan_llm"),
            _profile_summary_line("chat_llm"),
            _profile_summary_line("chat_tts"),
            _profile_summary_line("action"),
            _profile_summary_line("navi_check"),
            _profile_summary_line("completion_check"),
        ]
        _profile_summary["printed"] = True

    print("\n".join(lines))
    _profile_write({
        "event": "instant",
        "name": "workflow_profile_summary_printed",
        "reason": reason,
        "loop_total": round(loop_total, 6),
    })
def _profile_summary_print_at_exit():
    _profile_summary_print(reason="process_exit")
_profile_summary_reset()
atexit.register(_profile_summary_print_at_exit)

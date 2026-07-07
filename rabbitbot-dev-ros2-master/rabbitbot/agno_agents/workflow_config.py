"""workflow 运行环境变量读取与开关判断（从 workflow.py 拆出，行为不变）。"""

import os
from pathlib import Path


def _env_enabled(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}
def _workflow_verbose_enabled():
    return _env_enabled("RABBITBOT_WORKFLOW_VERBOSE", "0")
def _workflow_non_integration_enabled():
    return _env_enabled("RABBITBOT_WORKFLOW_NON_INTEGRATION", "0")
def _strict_docx_script_enabled():
    return _env_enabled("RABBITBOT_STRICT_DOCX_SCRIPT", "1")
def _docx_guide_qa_interrupt_enabled():
    return _env_enabled("RABBITBOT_DOCX_GUIDE_QA_INTERRUPT", "1")
def _workflow_log(message, verbose=False):
    if verbose and not _workflow_verbose_enabled():
        return
    print(message)
def _workflow_profile_enabled():
    return _env_enabled("RABBITBOT_WORKFLOW_PROFILE", "1")
def _workflow_profile_path():
    explicit_path = os.getenv("RABBITBOT_WORKFLOW_PROFILE_LOG", "").strip()
    if explicit_path:
        return Path(explicit_path)
    log_dir = os.getenv("RABBITBOT_LOG_DIR", "").strip()
    if log_dir:
        return Path(log_dir) / "workflow_profile.jsonl"
    return Path.cwd() / "logs" / "workflow_profile.jsonl"
def _workflow_profile_summary_enabled():
    return _env_enabled("RABBITBOT_WORKFLOW_SUMMARY", "1")
def _should_speak_with_action(action_name, configured=False):
    if not action_name:
        return False
    return bool(configured) or action_name != "shake_hand"
def _env_float(name, default):
    raw_value = os.getenv(name, str(default))
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        print(f"Invalid {name}={raw_value}, use {default}")
        return float(default)

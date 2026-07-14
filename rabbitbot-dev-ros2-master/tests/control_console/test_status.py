import os
import time

from rabbitbot.control_console.config import ConsoleConfig
from rabbitbot.control_console.status import (
    WorkflowStatus,
    get_speech_status,
    get_latest_workflow_status,
    get_task_progress,
    latest_file,
    get_tail_lines,
    parse_latest_pose,
    strip_ansi,
)


def test_strip_ansi_removes_terminal_color_sequences():
    assert strip_ansi("\x1b[36m[Pose]\x1b[0m x: 1.0") == "[Pose] x: 1.0"


def test_parse_latest_pose_prefers_last_periodic_pose(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: \x1b[32m[Auto-Relocation] Success! Current pose:\x1b[0m\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   x: -0.3913  y: 16.9003  z: -0.0693\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   ox: 0.1253  oy: 0.0844  oz: 0.7378  ow: 0.6579\n"
        "[INFO] [1] [hybrid_navigation_node_66]: [Ready] Navigation system ready for commands!\n"
        "[INFO] [2] [hybrid_navigation_node_66]: \x1b[36m[Pose]\x1b[0m x: 1.2345  y: -2.3456  z: 0.1000  ox: 0.0100  oy: 0.0200  oz: 0.0300  ow: 0.9990\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is True
    assert pose.status_message == "定位成功"
    assert pose.source == "pose_log"
    assert pose.x == 1.2345
    assert pose.y == -2.3456
    assert pose.z == 0.1
    assert pose.ox == 0.01
    assert pose.oy == 0.02
    assert pose.oz == 0.03
    assert pose.ow == 0.999


def test_parse_latest_pose_uses_relocation_block_when_no_periodic_pose(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: [Auto-Relocation] Success! Current pose:\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   x: -0.3913  y: 16.9003  z: -0.0693\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   ox: 0.1253  oy: 0.0844  oz: 0.7378  ow: 0.6579\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is True
    assert pose.status_message == "定位成功"
    assert pose.source == "relocation_success"
    assert pose.x == -0.3913
    assert pose.y == 16.9003
    assert pose.z == -0.0693
    assert pose.ox == 0.1253
    assert pose.oy == 0.0844
    assert pose.oz == 0.7378
    assert pose.ow == 0.6579


def test_parse_latest_pose_returns_unavailable_for_missing_log(tmp_path):
    pose = parse_latest_pose(tmp_path / "missing.log")

    assert pose.available is False
    assert pose.localized is False
    assert "需要遥控机器人的位姿" in pose.status_message
    assert pose.message == "暂无定位位姿数据"


def test_get_latest_workflow_status_prefers_latest_running_status_mtime(tmp_path):
    control = tmp_path / "workflow_control"
    control.mkdir()
    (control / "20260608_090000.status").write_text("finished\n", encoding="utf-8")
    (control / "20260608_090000.exit_code").write_text("0\n", encoding="utf-8")
    (control / "20260609_100000.status").write_text("running\n", encoding="utf-8")
    (control / "20260609_100000.ready").write_text("ready\n", encoding="utf-8")
    (control / "20260609_100000.pid").write_text("1234\n", encoding="utf-8")

    workflow = get_latest_workflow_status(control)

    assert workflow.run_id == "20260609_100000"
    assert workflow.status == "waiting_for_go"
    assert workflow.ready is True
    assert workflow.pid == "1234"
    assert workflow.exit_code is None


def test_get_latest_workflow_status_ignores_future_stale_run_id(tmp_path):
    control = tmp_path / "workflow_control"
    control.mkdir()
    stale = control / "20260609_152359.status"
    stale.write_text("running\n", encoding="utf-8")
    (control / "20260609_152359.ready").write_text("ready\n", encoding="utf-8")
    (control / "20260609_152359.pid").write_text("old\n", encoding="utf-8")
    current = control / "20260608_202907.status"
    current.write_text("running\n", encoding="utf-8")
    (control / "20260608_202907.ready").write_text("ready\n", encoding="utf-8")
    (control / "20260608_202907.pid").write_text("new\n", encoding="utf-8")
    now = time.time()
    os.utime(stale, (now + 86400, now + 86400))
    os.utime(current, (now, now))

    workflow = get_latest_workflow_status(control)

    assert workflow.run_id == "20260608_202907"
    assert workflow.status == "waiting_for_go"
    assert workflow.ready is True
    assert workflow.pid == "new"


def test_get_latest_workflow_status_handles_missing_directory(tmp_path):
    workflow = get_latest_workflow_status(tmp_path / "missing")

    assert workflow.run_id is None
    assert workflow.status == "unknown"
    assert workflow.ready is False


def test_get_task_progress_reads_current_run_progress(tmp_path):
    control = tmp_path / "workflow_control"
    control.mkdir()
    (control / "20260609_100000.task_progress.json").write_text(
        '{"active":true,"task_name":"展厅导览","status":"navigating","current_site":"点位1","next_site":"点位2","completed_points":2,"total_points":5,"updated_at":"2026-06-09T10:00:00"}\n',
        encoding="utf-8",
    )
    workflow = WorkflowStatus(run_id="20260609_100000", status="running", ready=True)

    progress = get_task_progress(control, workflow)

    assert progress.active is True
    assert progress.task_name == "展厅导览"
    assert progress.status == "navigating"
    assert progress.current_site == "点位1"
    assert progress.next_site == "点位2"
    assert progress.completed_points == 2
    assert progress.total_points == 5


def test_get_task_progress_returns_empty_progress_without_file(tmp_path):
    workflow = WorkflowStatus(run_id="20260609_100000", status="running", ready=True)

    progress = get_task_progress(tmp_path, workflow)

    assert progress.active is False
    assert progress.task_name == "待命"
    assert progress.completed_points == 0
    assert progress.total_points == 0


def test_latest_file_ignores_future_mtime_when_current_log_exists(tmp_path):
    old_future = tmp_path / "nav_bridge_20260609_152348.log"
    current = tmp_path / "nav_bridge_20260608_204412.log"
    old_future.write_text("old future\n", encoding="utf-8")
    current.write_text("current\n", encoding="utf-8")
    now = time.time()
    os.utime(old_future, (now + 86400, now + 86400))
    os.utime(current, (now, now))

    assert latest_file(tmp_path, "nav_bridge_*.log") == current


def test_get_tail_lines_strips_ansi_and_limits_count(tmp_path):
    log = tmp_path / "nav.log"
    log.write_text("one\n\x1b[32mtwo\x1b[0m\nthree\n", encoding="utf-8")

    assert get_tail_lines(log, 2) == ["two", "three"]


def test_console_config_defaults_to_test9_map(monkeypatch):
    monkeypatch.delenv("NAV_PCD_PATH", raising=False)

    config = ConsoleConfig.from_env()

    assert config.map_path == "/home/unitree/test9.pcd"


def test_get_speech_status_reports_not_listening_when_stt_port_closed(monkeypatch):
    monkeypatch.setattr("rabbitbot.control_console.status.is_port_open", lambda host, port, timeout=0.25: False)

    speech = get_speech_status()

    assert speech.listening is False
    assert speech.service_online is False
    assert speech.message == "未在监听"
    assert speech.text == ""


def test_get_speech_status_reads_non_consuming_text_when_listening(monkeypatch):
    calls = []

    def fake_post(host, port, task, timeout=0.35):
        calls.append(task)
        if task == "get_status_async":
            return "<REC_START>", 0
        if task == "peek_text_async":
            return "你好", 7
        return "", 0

    monkeypatch.setattr("rabbitbot.control_console.status.is_port_open", lambda host, port, timeout=0.25: True)
    monkeypatch.setattr("rabbitbot.control_console.status._post_stt_exec", fake_post)

    speech = get_speech_status()

    assert calls == ["get_status_async", "peek_text_async"]
    assert speech.listening is True
    assert speech.service_online is True
    assert speech.message == "正在聆听"
    assert speech.text == "你好"
    assert speech.utterance_id == 7


def test_get_speech_status_does_not_read_text_when_not_listening(monkeypatch):
    calls = []

    def fake_post(host, port, task, timeout=0.35):
        calls.append(task)
        return "<REC_STOP>", 0

    monkeypatch.setattr("rabbitbot.control_console.status.is_port_open", lambda host, port, timeout=0.25: True)
    monkeypatch.setattr("rabbitbot.control_console.status._post_stt_exec", fake_post)

    speech = get_speech_status()

    assert calls == ["get_status_async"]
    assert speech.listening is False
    assert speech.service_online is True
    assert speech.message == "未在监听"
    assert speech.raw_status == "<REC_STOP>"


def test_parse_latest_pose_marks_unlocalized_after_new_relocation_attempt(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: [Auto-Relocation] Success! Current pose:\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   x: 1.0000  y: 2.0000  z: 3.0000\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   ox: 0.1000  oy: 0.2000  oz: 0.3000  ow: 0.9000\n"
        "[INFO] [2] [hybrid_navigation_node_66]: [Auto-Relocation] Attempt 2: start relocation with map /home/unitree/test9.pcd\n"
        "[INFO] [2] [hybrid_navigation_node_66]: [Auto-Relocation] Waiting for localization...\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is False
    assert "需要遥控机器人的位姿" in pose.status_message
    assert pose.x == 1.0
    assert pose.ow == 0.9


def test_parse_latest_pose_does_not_treat_ready_as_localization_success(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: [Ready] Navigation system ready for commands!\n"
        "[INFO] [2] [hybrid_navigation_node_66]: [Pose] x: 4.0000  y: 5.0000  z: 6.0000  ox: 0.4000  oy: 0.5000  oz: 0.6000  ow: 0.7000\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is False
    assert pose.status_message == "当前位姿已读取，定位状态待确认"
    assert pose.x == 4.0
    assert pose.ow == 0.7


def test_parse_latest_pose_does_not_treat_pose_line_as_localization_success(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: [Auto-Relocation] Waiting for localization...\n"
        "[INFO] [2] [hybrid_navigation_node_66]: [Pose] x: 4.0000  y: 5.0000  z: 6.0000  ox: 0.4000  oy: 0.5000  oz: 0.6000  ow: 0.7000\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is False
    assert "需要遥控机器人的位姿" in pose.status_message
    assert pose.x == 4.0
    assert pose.ow == 0.7


def test_parse_latest_pose_does_not_keep_old_success_forever(tmp_path):
    log = tmp_path / "nav_bridge_20260609.log"
    noisy_lines = "".join(f"dds noise {index}\n" for index in range(320))
    log.write_text(
        "[INFO] [1] [hybrid_navigation_node_66]: [Auto-Relocation] Success! Current pose:\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   x: 1.0000  y: 2.0000  z: 3.0000\n"
        "[INFO] [1] [hybrid_navigation_node_66]:   ox: 0.1000  oy: 0.2000  oz: 0.3000  ow: 0.9000\n"
        + noisy_lines
        + "[INFO] [2] [hybrid_navigation_node_66]: [Pose] x: 4.0000  y: 5.0000  z: 6.0000  ox: 0.4000  oy: 0.5000  oz: 0.6000  ow: 0.7000\n",
        encoding="utf-8",
    )

    pose = parse_latest_pose(log)

    assert pose.available is True
    assert pose.localized is False
    assert pose.status_message == "当前位姿已读取，定位状态待确认"
    assert pose.source == "pose_log"
    assert pose.x == 4.0
    assert pose.ow == 0.7

def test_service_status_marks_starting_within_startup_window(monkeypatch):
    # 主循环刚启动(处于启动窗口)且端口未就绪 → 状态应为“启动中”。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setattr(status_mod, "get_main_loop_start_epoch", lambda: time.time())
    monkeypatch.setattr(status_mod, "is_port_open", lambda host, port, timeout=0.12: False)
    statuses = status_mod.get_runtime_service_statuses()
    assert statuses
    assert all(item.state == "starting" for item in statuses)
    assert all("启动中" in (item.message or "") for item in statuses)


def test_service_status_marks_offline_outside_startup_window(monkeypatch):
    # 主循环未运行(取不到启动时间)且端口未就绪 → 状态应为“离线”。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setattr(status_mod, "get_main_loop_start_epoch", lambda: None)
    monkeypatch.setattr(
        status_mod,
        "_console_process_start_epoch",
        time.time() - status_mod.SERVICE_STARTUP_GRACE_SECONDS - 1,
    )
    monkeypatch.setattr(status_mod, "is_port_open", lambda host, port, timeout=0.12: False)
    statuses = status_mod.get_runtime_service_statuses()
    assert statuses
    assert all(item.state == "offline" for item in statuses)
    assert all("离线" in (item.message or "") for item in statuses)


def test_service_status_marks_online_when_port_open(monkeypatch):
    # 端口已就绪 → 状态应为“在线”，与启动窗口无关。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setattr(status_mod, "get_main_loop_start_epoch", lambda: time.time())
    monkeypatch.setattr(status_mod, "is_port_open", lambda host, port, timeout=0.12: True)
    statuses = status_mod.get_runtime_service_statuses()
    assert statuses
    assert all(item.state == "online" for item in statuses)


def test_resolve_service_container_compose_groups(monkeypatch):
    # compose 栈下服务->容器映射：TTS/STT 独立容器，VLM/Embedding 同 rabbitbot-vlm。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setenv("RABBITBOT_BASE_RUNTIME", "compose")
    assert status_mod.resolve_service_container("tts") == "rabbitbot-tts"
    assert status_mod.resolve_service_container("stt") == "rabbitbot-stt"
    assert status_mod.resolve_service_container("vlm") == "rabbitbot-vlm"
    assert status_mod.resolve_service_container("embedding") == "rabbitbot-vlm"
    assert status_mod.resolve_service_container("memory") == "rabbitbot-memory"
    assert status_mod.resolve_service_container("neo4j") == "neo4j"
    assert status_mod.resolve_service_container("navbridge") == "rabbitbot-navbridge"
    assert status_mod.resolve_service_container("nope") is None


def test_service_status_marks_starting_after_container_restart(monkeypatch):
    # 刚重启某容器(宽限期内)且端口未就绪 → 该容器服务显示“启动中”，其它容器服务仍“离线”。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setenv("RABBITBOT_BASE_RUNTIME", "compose")
    monkeypatch.setattr(status_mod, "get_main_loop_start_epoch", lambda: None)
    monkeypatch.setattr(
        status_mod,
        "_console_process_start_epoch",
        time.time() - status_mod.SERVICE_STARTUP_GRACE_SECONDS - 1,
    )
    monkeypatch.setattr(status_mod, "is_port_open", lambda host, port, timeout=0.12: False)
    monkeypatch.setattr(status_mod, "_recent_container_restarts", {"rabbitbot-tts": time.time()})
    by_key = {item.key: item for item in status_mod.get_runtime_service_statuses()}
    assert by_key["tts"].state == "starting"
    assert by_key["stt"].state == "offline"
    assert by_key["vlm"].state == "offline"
    assert by_key["tts"].container == "rabbitbot-tts"
    assert by_key["stt"].container == "rabbitbot-stt"


def test_mark_container_restarted_records_timestamp(monkeypatch):
    # mark_container_restarted 应把容器名记入重启时间戳表。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setattr(status_mod, "_recent_container_restarts", {})
    status_mod.mark_container_restarted("rabbitbot-tts")
    assert "rabbitbot-tts" in status_mod._recent_container_restarts


def test_service_status_force_starting_overrides_online(monkeypatch):
    # 重启发起后的强制窗口内，即使端口仍开(旧进程未退出)，该容器服务也显示“启动中”，优先于“在线”。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setenv("RABBITBOT_BASE_RUNTIME", "compose")
    monkeypatch.setattr(status_mod, "get_main_loop_start_epoch", lambda: None)
    monkeypatch.setattr(status_mod, "is_port_open", lambda host, port, timeout=0.12: True)
    monkeypatch.setattr(status_mod, "_recent_container_restarts", {"rabbitbot-tts": time.time()})
    by_key = {item.key: item for item in status_mod.get_runtime_service_statuses()}
    assert by_key["tts"].state == "starting"
    assert by_key["stt"].state == "online"
    assert by_key["vlm"].state == "online"

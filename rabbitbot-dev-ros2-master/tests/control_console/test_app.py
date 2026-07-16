import json

from fastapi.testclient import TestClient

from rabbitbot.control_console.app import create_app
from rabbitbot.control_console.config import ConsoleConfig


def make_config(tmp_path):
    project_root = tmp_path / "project"
    command_script = project_root / "scripts_1" / "send_nav_workflow_command.sh"
    systemctl_path = project_root / "bin" / "systemctl"
    docker_path = project_root / "bin" / "docker"
    systemctl_record = project_root / "systemctl_args.txt"
    docker_record = project_root / "docker_args.txt"
    nav_map_record = project_root / "nav_map_path.txt"
    map_env_file = project_root / "runtime" / "rabbitbot-loop.env"
    workflow_control_dir = project_root / "logs" / "nav_workflow_control" / "workflow_control"
    nav_log_dir = project_root / "logs" / "nav_workflow_control"
    workflow_log_dir = project_root / "logs" / "nav_workflow_control"
    current_runtime_log = project_root / "logs" / "current_runtime.log"
    dialogue_dir = project_root / "conf"
    command_script.parent.mkdir(parents=True)
    systemctl_path.parent.mkdir(parents=True)
    workflow_control_dir.mkdir(parents=True)
    nav_log_dir.mkdir(parents=True, exist_ok=True)
    workflow_log_dir.mkdir(parents=True, exist_ok=True)
    dialogue_dir.mkdir(parents=True, exist_ok=True)
    (dialogue_dir / "dialogue_0.json").write_text(
        '{"variables":{"leader_calling":"各位领导"},"opening":{},"steps":[{"segments":[{"text":"欢迎"}]}],"map_file":"test9.pcd","points":{}}\n',
        encoding="utf-8",
    )
    command_script.write_text("#!/usr/bin/env bash\necho \"已发送命令：$1\"\n", encoding="utf-8")
    command_script.chmod(0o755)
    systemctl_path.write_text(f"#!/usr/bin/env bash\nprintf '%s\n' \"$@\" > {systemctl_record}\n", encoding="utf-8")
    systemctl_path.chmod(0o755)
    docker_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = ps ]; then\n"
        "  printf '%s\\n' neo4j rabbitbot-vlm rabbitbot-tts rabbitbot-stt rabbitbot-memory rabbitbot-workflow rabbitbot-navbridge\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = logs ]; then\n"
        f"  printf '%s\n' \"$@\" > {docker_record}\n"
        "  printf '%s\\n' service-log-one service-log-two\n"
        "  exit 0\n"
        "fi\n"
        f"printf '%s\\n' \"$RABBITBOT_NAV_MAP_PATH\" > {nav_map_record}\n"
        f"printf '%s\n' \"$@\" > {docker_record}\n"
        "printf '%s\\n' rabbitbot-vlm rabbitbot-tts rabbitbot-stt rabbitbot-memory rabbitbot-workflow rabbitbot-navbridge neo4j\n",
        encoding="utf-8",
    )
    docker_path.chmod(0o755)
    return ConsoleConfig(
        project_root=project_root,
        host="127.0.0.1",
        port=8080,
        nav_port=9,
        map_path="/home/unitree/test9.pcd",
        command_script=command_script,
        workflow_control_dir=workflow_control_dir,
        nav_log_dir=nav_log_dir,
        nav_container_name="",
        runtime_container_name="rabbitbot-unified-runtime",
        docker_path=docker_path,
        workflow_log_dir=workflow_log_dir,
        current_runtime_log=current_runtime_log,
        loop_service_name="rabbitbot-loop.service",
        systemctl_path=systemctl_path,
        sudo_path=None,
        map_env_file=map_env_file,
        dialogue_dir=dialogue_dir,
        dialogue_index="0",
        dialogue_file=None,
    )


def test_status_does_not_require_login(tmp_path, monkeypatch):
    from rabbitbot.control_console import app as app_mod

    class DummySpeech:
        def to_dict(self):
            return {"listening": False, "service_online": False, "status": "offline", "message": "未在监听", "text": "", "utterance_id": 0, "raw_status": None}

    monkeypatch.setattr(app_mod, "get_speech_status", lambda: DummySpeech())
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["map_path"] == "/home/unitree/test9.pcd"
    service_by_key = {item["key"]: item for item in body["services"]}
    assert {"tts", "stt", "memory", "neo4j", "vlm", "embedding", "navbridge"}.issubset(service_by_key)
    assert service_by_key["vlm"]["required"] is True
    assert service_by_key["embedding"]["required"] is True
    assert service_by_key["navbridge"]["container"] == "rabbitbot-navbridge"
    assert body["speech"]["listening"] is False
    assert body["speech"]["message"] == "未在监听"


def test_status_prefers_runtime_map_env_file(tmp_path):
    config = make_config(tmp_path)
    config.map_env_file.parent.mkdir(parents=True)
    config.map_env_file.write_text('NAV_PCD_PATH="/home/unitree/new_map.pcd"\n', encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["map_path"] == "/home/unitree/new_map.pcd"


def test_status_returns_map_and_pose_without_login(tmp_path, monkeypatch):
    from rabbitbot.control_console import app as app_mod

    monkeypatch.setattr(app_mod, "detect_main_loop_running", lambda: "running")
    config = make_config(tmp_path)
    nav_log = config.nav_log_dir / "nav_bridge_20260609.log"
    nav_log.write_text(
        "[INFO] [2] [hybrid_navigation_node_66]: [Pose] x: 1.0000  y: 2.0000  z: 3.0000  ox: 0.1000  oy: 0.2000  oz: 0.3000  ow: 0.9000\n",
        encoding="utf-8",
    )
    (config.workflow_control_dir / "20260609_100000.status").write_text("running\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_100000.ready").write_text("ready\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["map_path"] == "/home/unitree/test9.pcd"
    assert body["workflow"]["status"] == "waiting_for_go"
    assert body["pose"]["available"] is True
    assert body["pose"]["localized"] is False
    assert body["pose"]["status_message"] == "当前位姿已读取，定位状态待确认"
    assert body["pose"]["x"] == 1.0


def test_status_returns_task_progress_for_current_workflow(tmp_path, monkeypatch):
    from rabbitbot.control_console import app as app_mod

    monkeypatch.setattr(app_mod, "detect_main_loop_running", lambda: "running")
    config = make_config(tmp_path)
    (config.workflow_control_dir / "20260609_100000.status").write_text("running\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_100000.ready").write_text("ready\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_100000.task_progress.json").write_text(
        json.dumps(
            {
                "active": True,
                "task_name": "展厅导览",
                "status": "navigating",
                "current_site": "点位1",
                "next_site": "点位2",
                "completed_points": 1,
                "total_points": 4,
                "updated_at": "2026-06-09T10:00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(config))

    response = client.get("/api/status")

    assert response.status_code == 200
    progress = response.json()["task_progress"]
    assert progress["active"] is True
    assert progress["status"] == "navigating"
    assert progress["current_site"] == "点位1"
    assert progress["next_site"] == "点位2"
    assert progress["completed_points"] == 1
    assert progress["total_points"] == 4


def test_control_page_contains_live_speech_panel(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'id="speechState"' in html
    assert 'id="voiceWave"' in html
    assert 'id="speechText"' in html
    assert "function renderSpeechStatus" in html
    assert "peek_text_async" not in html


def test_command_rejects_quit_without_login(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/command", json={"command": "quit"})

    assert response.status_code == 400
    assert "不支持的命令" in response.json()["detail"]


def test_command_sends_go_without_login(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/command", json={"command": "go"})

    assert response.status_code == 200
    assert response.json()["command"] == "go"


def test_command_sends_arrive_without_login(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/command", json={"command": "arrive"})

    assert response.status_code == 200
    assert response.json()["command"] == "arrive"


def test_task_guide_sends_go_without_login(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/task", json={"task": "guide"})

    assert response.status_code == 200
    assert response.json()["task"] == "guide"
    assert response.json()["command"] == "go"
    assert response.json()["message"] == "导览任务已启动"


def test_task_placeholders_return_message_without_login(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    dialogue = client.post("/api/task", json={"task": "dialogue"})
    vision = client.post("/api/task", json={"task": "vision"})

    assert dialogue.status_code == 200
    assert dialogue.json()["placeholder"] is True
    assert dialogue.json()["message"] == "对话任务暂未接入"
    assert vision.status_code == 200
    assert vision.json()["placeholder"] is True
    assert vision.json()["message"] == "视觉导航任务暂未接入"


def test_start_starts_loop_service_without_login(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/start")

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    assert response.json()["message"] == "已启动导航主程序"
    assert 'RABBITBOT_NAV_WORKFLOW_NO_ROBOT="0"' in config.map_env_file.read_text(encoding="utf-8")
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["start", "rabbitbot-loop.service"]


def test_start_no_robot_restarts_loop_service_and_writes_mode(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/start-no-robot")

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    assert response.json()["no_robot_mode"] is True
    content = config.map_env_file.read_text(encoding="utf-8")
    assert 'RABBITBOT_NAV_WORKFLOW_NO_ROBOT="1"' in content
    assert 'RABBITBOT_WORKFLOW_NON_INTEGRATION="1"' in content
    assert 'RABBITBOT_NAV_WORKFLOW_VOICE_START="0"' in content
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["restart", "rabbitbot-loop.service"]


def test_restart_restarts_loop_service_without_login(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/restart", json={"map_path": "/home/unitree/test10.pcd"})

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    assert response.json()["map_path"] == "/home/unitree/test10.pcd"
    content = config.map_env_file.read_text(encoding="utf-8")
    assert 'NAV_PCD_PATH="/home/unitree/test10.pcd"' in content
    assert 'RABBITBOT_NAV_WORKFLOW_NO_ROBOT="0"' in content
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["restart", "rabbitbot-loop.service"]


def test_confirm_map_writes_map_and_recreates_navbridge(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/map", json={"map_path": "/home/unitree/test13.pcd"})

    assert response.status_code == 200
    assert response.json()["map_path"] == "/home/unitree/test13.pcd"
    assert response.json()["message"] == "已确认使用地图 /home/unitree/test13.pcd，NavBridge 已按该路径重建"
    assert 'NAV_PCD_PATH="/home/unitree/test13.pcd"' in config.map_env_file.read_text(encoding="utf-8")
    assert not (config.project_root / "systemctl_args.txt").exists()
    args = (config.project_root / "docker_args.txt").read_text(encoding="utf-8").splitlines()
    assert args[-4:] == ["up", "-d", "--force-recreate", "rabbitbot-navbridge"]
    assert (config.project_root / "nav_map_path.txt").read_text(encoding="utf-8").strip() == "/home/unitree/test13.pcd"


def test_stop_stops_loop_service_without_login(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/stop")

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    assert response.json()["containers"] == ["neo4j", "rabbitbot-vlm", "rabbitbot-tts", "rabbitbot-stt", "rabbitbot-memory", "rabbitbot-workflow", "rabbitbot-navbridge"]
    assert response.json()["container_restarted"] is True
    assert "已关闭导航主程序" in response.json()["message"]
    assert "已重启项目服务相关容器" in response.json()["message"]
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["stop", "rabbitbot-loop.service"]
    docker_record = config.project_root / "docker_args.txt"
    assert docker_record.read_text(encoding="utf-8").splitlines() == ["restart", "-t", "20", "neo4j", "rabbitbot-vlm", "rabbitbot-tts", "rabbitbot-stt", "rabbitbot-memory", "rabbitbot-workflow", "rabbitbot-navbridge"]


def test_autostart_toggles_loop_service_without_login(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/autostart", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    assert response.json()["enabled"] is True
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["enable", "rabbitbot-loop.service"]


def test_static_robot_dashboard_image_is_served(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.get("/static/control_console/unitree-g1-dashboard.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_dialogue_loads_current_config(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.get("/api/dialogue")

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["summary"]["leader_calling"] == "各位领导"
    assert body["summary"]["map_file"] == "test9.pcd"
    assert '"text": "欢迎"' in body["content"]


def test_dialogue_save_validates_and_writes_config(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))
    content = '{"variables":{"leader_calling":"客户"},"opening":{},"steps":[{"segments":[{"text":"新的讲解词"}]}],"map_file":"test10.pcd","points":{}}'

    response = client.post("/api/dialogue", json={"content": content})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["leader_calling"] == "客户"
    saved = (config.dialogue_dir / "dialogue_0.json").read_text(encoding="utf-8")
    assert "新的讲解词" in saved
    assert list(config.dialogue_dir.glob("dialogue_0.json.*.bak"))


def test_dialogue_save_rejects_invalid_json(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/dialogue", json={"content": "{"})

    assert response.status_code == 400
    assert "JSON 解析失败" in response.json()["detail"]


def test_dialogue_save_rejects_invalid_structure(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.post("/api/dialogue", json={"content": "[]"})

    assert response.status_code == 400
    assert "根节点必须是对象" in response.json()["detail"]


def test_dialogue_leader_calling_reads_and_writes(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    loaded = client.get("/api/dialogue/leader-calling")
    saved = client.post("/api/dialogue/leader-calling", json={"leader_calling": "各位嘉宾"})

    assert loaded.status_code == 200
    assert loaded.json()["leader_calling"] == "各位领导"
    assert saved.status_code == 200
    assert saved.json()["leader_calling"] == "各位嘉宾"
    data = json.loads((config.dialogue_dir / "dialogue_0.json").read_text(encoding="utf-8"))
    assert data["variables"]["leader_calling"] == "各位嘉宾"


def test_dialogue_hot_rows_reads_and_writes(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    loaded = client.get("/api/dialogue/hot-rows")
    assert loaded.status_code == 200
    rows = loaded.json()["rows"]
    assert rows[0]["row_type"] == "opening"
    rows[0]["script"] = '{"short_mode_intro":"新开场"}'
    rows[1]["point_name"] = "新点位"
    rows[1]["coordinate"] = '{"x":1,"y":2,"z":3,"ox":0.1,"oy":0.2,"oz":0.3,"ow":0.9,"mode":1}'
    rows[1]["script"] = "第一段\n\n第二段"

    saved = client.post("/api/dialogue/hot-rows", json={"rows": rows})

    assert saved.status_code == 200
    data = json.loads((config.dialogue_dir / "dialogue_0.json").read_text(encoding="utf-8"))
    assert data["opening"]["short_mode_intro"] == "新开场"
    assert data["steps"][0]["scene"] == "新点位"
    assert data["steps"][0]["segments"] == [{"text": "第一段"}, {"text": "第二段"}]
    assert data["points"][data["steps"][0]["entity_key"]]["location"][0]["x"] == 1.0


def test_logs_return_latest_nav_log_lines(tmp_path):
    config = make_config(tmp_path)
    (config.nav_log_dir / "nav_bridge_1.log").write_text("old\n", encoding="utf-8")
    latest = config.nav_log_dir / "nav_bridge_2.log"
    latest.write_text("one\ntwo\nthree\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=nav&lines=2")

    assert response.status_code == 200
    assert response.json()["lines"] == ["two", "three"]


def test_logs_return_current_workflow_log_by_run_id(tmp_path):
    config = make_config(tmp_path)
    (config.workflow_control_dir / "20260609_100000.status").write_text("finished\n", encoding="utf-8")
    (config.workflow_log_dir / "rabbitbot_workflow_20260609_100000.log").write_text("old\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_110000.status").write_text("running\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_110000.ready").write_text("ready\n", encoding="utf-8")
    (config.workflow_log_dir / "rabbitbot_workflow_20260609_110000.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=workflow&lines=2")

    assert response.status_code == 200
    assert response.json()["path"].endswith("rabbitbot_workflow_20260609_110000.log")
    assert response.json()["lines"] == ["two", "three"]


def test_logs_do_not_fallback_to_old_workflow_when_no_current_run(tmp_path):
    config = make_config(tmp_path)
    (config.workflow_log_dir / "rabbitbot_workflow_20260616_143251.log").write_text("old workflow\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=workflow&lines=2")

    assert response.status_code == 200
    assert response.json()["path"] is None
    assert response.json()["lines"] == []


def test_logs_do_not_fallback_to_old_workflow_when_current_log_missing(tmp_path):
    config = make_config(tmp_path)
    (config.workflow_control_dir / "20260629_120000.status").write_text("running\n", encoding="utf-8")
    (config.workflow_control_dir / "20260629_120000.ready").write_text("ready\n", encoding="utf-8")
    (config.workflow_log_dir / "rabbitbot_workflow_20260616_143251.log").write_text("old workflow\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=workflow&lines=2")

    assert response.status_code == 200
    assert response.json()["path"] is None
    assert response.json()["lines"] == []


def test_runtime_logs_use_workflow_log_when_current_run_exists(tmp_path):
    config = make_config(tmp_path)
    (config.workflow_control_dir / "20260609_110000.status").write_text("running\n", encoding="utf-8")
    (config.workflow_control_dir / "20260609_110000.ready").write_text("ready\n", encoding="utf-8")
    (config.workflow_log_dir / "rabbitbot_workflow_20260609_110000.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=runtime&lines=2")

    assert response.status_code == 200
    assert response.json()["source"] == "workflow"
    assert response.json()["path"].endswith("rabbitbot_workflow_20260609_110000.log")
    assert response.json()["lines"] == ["two", "three"]


def test_runtime_logs_use_current_runtime_log_when_no_current_run(tmp_path):
    config = make_config(tmp_path)
    config.current_runtime_log.parent.mkdir(parents=True, exist_ok=True)
    config.current_runtime_log.write_text("loop starting\nwaiting TTS without newline", encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=runtime&lines=2")

    assert response.status_code == 200
    assert response.json()["source"] == "current"
    assert response.json()["path"].endswith("current_runtime.log")
    assert response.json()["lines"] == ["loop starting", "waiting TTS without newline"]


def test_runtime_logs_return_empty_when_no_current_run_log(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=runtime&lines=2")

    assert response.status_code == 200
    assert response.json()["source"] == "none"
    assert response.json()["path"] is None
    assert response.json()["lines"] == []


def test_service_logs_return_docker_container_logs(tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.get("/api/logs?target=service-tts&lines=2")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "docker"
    assert body["container"] == "rabbitbot-tts"
    assert body["path"] == "docker:rabbitbot-tts"
    assert body["lines"] == ["service-log-one", "service-log-two"]
    record = config.project_root / "docker_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["logs", "--tail", "2", "rabbitbot-tts"]


def test_main_module_exposes_run_function():
    from rabbitbot.control_console.__main__ import run

    assert callable(run)



def test_page_shows_console_without_login_form(tmp_path):
    client = TestClient(create_app(make_config(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'id="app"' in response.text
    assert 'style="display:none"' not in response.text
    assert 'id="loginForm"' not in response.text
    assert 'password' not in response.text.lower()
    assert '/api/login' not in response.text
    assert '双足机器人导览系统' in response.text
    assert '开始任务 / 运动控制' in response.text
    assert '导览' in response.text
    assert '/api/task' in response.text
    assert '返航' in response.text
    assert '点位台词热更新' in response.text
    assert '嘉宾称呼' in response.text
    assert '更新为机器人当前位置' in response.text
    assert 'unitree-g1-dashboard.png' in response.text
    assert '定位状态' in response.text
    assert '当前位姿' in response.text
    assert 'robot-status-card' in response.text
    assert 'page-status' not in response.text
    assert 'data-page="status"' not in response.text
    assert 'primary-control-actions' in response.text
    assert '开始程序(无机器人模式)' in response.text
    assert '开发人员选项' in response.text
    assert 'page-developer' in response.text
    assert '/api/start-no-robot' in response.text
    assert '一键重启' in response.text
    assert '一键重启主循环' not in response.text
    assert '关闭程序' in response.text
    assert '开机自启动' in response.text
    assert '/api/start' in response.text
    assert 'startProgram' in response.text
    assert 'waitForServicesReady' in response.text
    assert '所有服务已加载成功，可执行相关操作' in response.text
    assert '/api/stop' in response.text
    assert 'stopProgram' in response.text
    assert '/api/restart' in response.text
    assert '/api/map' in response.text
    assert '重启地图' in response.text
    assert '确认地图' in response.text
    assert 'confirmMap' in response.text
    assert 'confirmMapBtn' in response.text
    assert 'mapPathInput' in response.text
    assert 'map_path' in response.text
    assert '服务状态' in response.text
    assert '服务状态管理' in response.text
    assert '模型服务' not in response.text
    assert '运动状态' not in response.text
    assert 'dashboardServiceStatusList' in response.text
    assert 'renderDashboardServiceStatus' in response.text
    assert '语音合成服务，把文字讲解转成语音播报' in response.text
    assert '导览编排服务，负责台词、点位和任务流程' in response.text
    assert '导航桥接服务，连接控制台/workflow 与机器人导航' in response.text
    assert 'serviceStatusGrid' in response.text
    assert 'renderServiceStatus' in response.text
    assert "设备：" in response.text
    assert "svc.device_name" in response.text
    assert 'restartService' in response.text
    assert 'pendingRestartUntil' in response.text
    assert '/api/service/restart' in response.text
    assert '位于同一容器，将被一并重启' in response.text
    assert '保存点位台词' in response.text
    assert 'leaderCallingInput' in response.text
    assert 'hotRowsTable' in response.text
    assert '/api/dialogue' in response.text
    assert '/api/dialogue/leader-calling' in response.text
    assert '/api/dialogue/hot-rows' in response.text
    assert 'class="topbar"' not in response.text
    assert 'class="top-status"' not in response.text
    assert 'id="overall"' not in response.text
    assert 'id="mainLoop"' not in response.text
    assert 'id="navBridge"' not in response.text
    assert 'id="workflow"' not in response.text
    assert 'class="tech-status"' not in response.text
    assert '网络正常' not in response.text
    assert '电量 92%' not in response.text
    assert '92%' not in response.text
    assert '运行状态' not in response.text
    assert '当前模式' not in response.text
    assert '当前运行日志' in response.text
    assert 'Workflow 日志' in response.text
    assert '导航日志' in response.text
    assert 'Neo4j 服务日志' in response.text
    assert 'VLM 服务日志' in response.text
    assert 'Embedding 服务日志' in response.text
    assert 'TTS 服务日志' in response.text
    assert 'STT 服务日志' in response.text
    assert 'Memory 服务日志' in response.text
    assert 'Workflow 容器日志' in response.text
    assert 'NavBridge 服务日志' in response.text
    assert "showLog('runtime')" in response.text
    assert "showLog('workflow')" in response.text
    assert "showLog('nav')" in response.text
    assert "showLog('service-neo4j')" in response.text
    assert "showLog('service-vlm')" in response.text
    assert "showLog('service-embedding')" in response.text
    assert "showLog('service-tts')" in response.text
    assert "showLog('service-stt')" in response.text
    assert "showLog('service-memory')" in response.text
    assert "showLog('service-workflow')" in response.text
    assert "showLog('service-navbridge')" in response.text
    assert 'logsVisible=false' in response.text
    assert '<pre id="logs" class="log developer-log" hidden>' in response.text
    assert 'setInterval(refreshLogs,500)' in response.text

def test_restart_preserves_no_robot_mode(tmp_path):
    # 一键重启主循环：若重启前为无机器人模式，应沿用无机器人模式而非覆盖成真机。
    config = make_config(tmp_path)
    client = TestClient(create_app(config))
    config.map_env_file.parent.mkdir(parents=True, exist_ok=True)
    config.map_env_file.write_text(
        'RABBITBOT_NAV_WORKFLOW_NO_ROBOT="1"\nRABBITBOT_WORKFLOW_NON_INTEGRATION="1"\n',
        encoding="utf-8",
    )

    response = client.post("/api/restart", json={"map_path": "/home/unitree/test10.pcd"})

    assert response.status_code == 200
    assert response.json()["service"] == "rabbitbot-loop.service"
    content = config.map_env_file.read_text(encoding="utf-8")
    assert 'RABBITBOT_NAV_WORKFLOW_NO_ROBOT="1"' in content
    assert 'RABBITBOT_WORKFLOW_NON_INTEGRATION="1"' in content
    assert 'RABBITBOT_NAV_WORKFLOW_VOICE_START="0"' in content
    record = config.project_root / "systemctl_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["restart", "rabbitbot-loop.service"]


def test_service_restart_restarts_tts_container_for_tts(tmp_path, monkeypatch):
    # 重启 TTS：compose 栈下应只重启 rabbitbot-tts 容器。
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setenv("RABBITBOT_BASE_RUNTIME", "compose")
    monkeypatch.setattr(status_mod, "_recent_container_restarts", {})
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/service/restart", json={"key": "tts"})

    assert response.status_code == 200
    assert response.json()["container"] == "rabbitbot-tts"
    record = config.project_root / "docker_args.txt"
    assert record.read_text(encoding="utf-8").splitlines() == ["restart", "-t", "20", "rabbitbot-tts"]


def test_service_restart_recreates_navbridge_with_compose(tmp_path, monkeypatch):
    from rabbitbot.control_console import status as status_mod

    monkeypatch.setenv("RABBITBOT_BASE_RUNTIME", "compose")
    monkeypatch.setenv("RABBITBOT_DECOUPLED_COMPOSE_FILE", "")
    monkeypatch.setattr(status_mod, "_recent_container_restarts", {})
    config = make_config(tmp_path)
    config.map_env_file.parent.mkdir(parents=True, exist_ok=True)
    config.map_env_file.write_text('NAV_PCD_PATH="/home/unitree/test7.pcd"\n', encoding="utf-8")
    client = TestClient(create_app(config))

    response = client.post("/api/service/restart", json={"key": "navbridge"})

    assert response.status_code == 200
    assert response.json()["container"] == "rabbitbot-navbridge"
    assert response.json()["message"] == "已提交重启 rabbitbot-navbridge"
    record = config.project_root / "docker_args.txt"
    args = record.read_text(encoding="utf-8").splitlines()
    assert args[0:2] == ["compose", "-f"]
    assert args[-4:] == ["up", "-d", "--force-recreate", "rabbitbot-navbridge"]
    assert (config.project_root / "nav_map_path.txt").read_text(encoding="utf-8").strip() == "/home/unitree/test7.pcd"


def test_service_restart_rejects_unknown_service(tmp_path):
    # 未知服务 key 应返回 400。
    config = make_config(tmp_path)
    client = TestClient(create_app(config))

    response = client.post("/api/service/restart", json={"key": "nope"})

    assert response.status_code == 400

# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：将控制台任务控制页“语音交互”板块改为显示真实 STT 监听状态、声波动画和识别文本。

## 项目整体描述

`RobotAbrainOffline` 是 RabbitBot/Unitree 导览机器人离线部署项目集合，用于在 Orin/ROS2 环境中运行导览 workflow、语音交互、视觉识别、记忆检索、导航桥接、Web 控制台和 portable 容器化服务。核心链路是：控制台或 systemd 启动主循环，workflow 加载 JSON 台词与点位，STT/命令触发导览、返航或无机器人模式到点确认，导航桥接连接 Unitree 导航，TTS 播报讲解，VLM/Embedding/Memory/Neo4j 提供扩展问答能力。

## 主要模块与目录

- `deploy/`：宿主初始化、portable 栈启动、自检、systemd 安装脚本。
- `rabbitbot-dev-ros2-master/conf/`：导览台词、点位、地图等运行配置；本轮运行台词为 `dialogue_0.json`。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/`：FastAPI 控制台后端、静态页面、台词热更新逻辑、服务状态与命令执行。
- `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/`：导览 workflow 编排、数据加载、机械臂动作、日志和 profiling。
- `rabbitbot-dev-ros2-master/rabbitbot/guide/`：导览台词、控制命令和路由等纯逻辑。
- `rabbitbot-dev-ros2-master/docker/portable/`：portable core/nav 镜像与解耦 compose；本项目保持单个 portable core 镜像复用为多容器角色，另配 nav 镜像和 Neo4j。
- `rabbitbot-dev-ros2-master/scripts/`、`scripts_1/`：workflow 启动、主循环入口、控制命令脚本。
- `models/`：模型缓存目录；现场部署要求实体复制，不使用符号链接。
- `custom_action_ws/`、`unitree_slam_example_new/`：ROS2/Unitree 导航相关代码。

## 技术栈与运行入口

- Python `>=3.10`，FastAPI 控制台，Docker Compose host network，NVIDIA runtime，ROS2 Humble，Neo4j。
- 常用入口：
  - portable 基础服务：`bash deploy/start_portable_stack.sh`
  - 主循环：`bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`
  - workflow 控制：`bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh go|arrive|back`
  - 控制台：`rabbitbot.control_console` 或 systemd `rabbitbot-control-console.service`
- 关键配置：
  - `rabbitbot-dev-ros2-master/runtime/portable.env.example`
  - `rabbitbot-dev-ros2-master/runtime/portable.env`（运行态，通常不提交）
  - `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml`
  - `rabbitbot-dev-ros2-master/conf/dialogue_0.json`

## 本轮修改摘要

- `rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py` 新增 `SpeechStatus` 和 STT 状态探测：端口未开或未监听时返回“未在监听”，监听中返回“正在聆听”并通过非消费式接口读取最近识别文本。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py` 的 `/api/status` 新增 `speech` 字段；任务控制页“语音交互”板块改为真实状态文案、可跳动竖线声波和识别文本显示。
- `rabbitbot-dev-ros2-master/stt_app.py`、`stt_app1.py`、`stt_app_funasr.py` 新增 `peek_text_async`，用于查看最近识别结果且不清空工作流要消费的 `get_text_async` 输出。
- `rabbitbot-dev-ros2-master/tests/control_console/test_status.py` 增加语音状态单元测试；`test_app.py` 增加状态接口和页面模板断言。

## 日志新增或调整

- 控制台查询 STT 失败时仅 `DEBUG` 记录接口、任务和异常类型；STT 返回非 JSON 或结构异常时 `WARNING` 记录必要上下文，不记录识别正文。
- STT 新增的 `peek_text_async` 高频调用只打印文本长度和 utterance_id，不打印识别正文，避免控制台轮询把语音文本写入日志。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `1500f46`，分支 `air_robot_gt_projects-master`。
- `python3 -m py_compile rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py rabbitbot-dev-ros2-master/stt_app.py rabbitbot-dev-ros2-master/stt_app1.py rabbitbot-dev-ros2-master/stt_app_funasr.py` 通过。
- `git diff --check` 通过。
- 轻量脚本确认 `get_speech_status()` 在 STT 监听中会调用 `get_status_async` 与 `peek_text_async`，并返回识别文本与 utterance_id。
- 轻量脚本确认控制台页面模板包含 `speechState`、`voiceWave`、`speechText` 和 `renderSpeechStatus`，且不再保留固定“正在聆听...”文案。
- 本机系统 Python 缺少 `pytest`，因此未能在本机完整运行 `python3 -m pytest tests/control_console -q`。
- 本机系统 Python 缺少 `fastapi`，因此未能在本机用 `TestClient` 导入控制台应用做完整接口 smoke；改用文件文本检查页面模板。
- 本轮代码提交已同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline`，服务器与本机处于同一提交。
- 服务器上 `python3 -m py_compile rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py rabbitbot-dev-ros2-master/stt_app.py rabbitbot-dev-ros2-master/stt_app1.py rabbitbot-dev-ros2-master/stt_app_funasr.py` 通过。
- 已重启 `new-orin` 上的 `rabbitbot-control-console.service`，服务状态为 active。
- 已重启正在运行的 `rabbitbot-stt` 容器，健康状态恢复为 healthy。
- 已请求服务器控制台 `/api/status`，确认返回 `speech={"listening": false, "service_online": true, "status": "idle", "message": "未在监听", "text": "", "utterance_id": 0, "raw_status": "<REC_STOP>"}`；STT 服务状态为 `28184 在线`。
- 已请求服务器控制台首页，确认页面包含 `speechState`、`voiceWave`、`speechText` 和 `renderSpeechStatus`，且不再包含固定“正在聆听...”文案。

## 阻塞与风险

- 本机缺少测试依赖，完整控制台 pytest 和 FastAPI TestClient smoke 尚未在本机执行；服务器同步后可在具备项目运行环境的机器上补跑。
- 已重启 `rabbitbot-stt` 容器加载 `peek_text_async`；如果后续改为其他 STT 进程入口，仍需确保对应进程重启后再验证识别文本显示。

## 下一步

1. 浏览器刷新任务控制页，确认空闲态显示“未在监听”。
2. 启动 STT 监听并说话，确认面板切换为“正在聆听”、竖线跳动，并显示最新识别文本。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

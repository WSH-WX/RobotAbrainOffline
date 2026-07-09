# air_robot_gt_projects 交接报告

生成时间：2026-07-07（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/air_robot_gt_projects`
当前目标分支：`master`
本轮主题：将 `refactor/service-internal-decoupling` 合并到 `master`，保留合并提交并详细记录改动项。

## 项目整体描述

`air_robot_gt_projects` 是 RabbitBot/Unitree 导览机器人项目集合，用于在 Orin/ROS2 环境中运行导览 workflow、语音交互、视觉识别、记忆检索、导航桥接、控制台和 portable 容器化部署。项目面向离线或半离线现场部署，核心链路是：控制台或脚本启动基础服务，STT 接收语音，workflow 解析导览/问答/控制意图，按剧本导航与播报，必要时调用 VLM、Embedding、Memory、Neo4j 和 Unitree 导航桥接。

核心功能：
- 导览 workflow：DOCX/JSON 剧本、点位导航、返航、机械臂动作、QA/闲聊路径。
- 语音服务：TTS `28185`、STT `28184`，当前重构分支已拆为独立容器。
- 视觉与语义：VLM `8000`、Embedding `8005`。
- 记忆服务：Memory Agent `28182`，依赖 Neo4j 与 Embedding。
- 导航桥接：`humble_robot_agent_bridge.py` / portable nav 容器提供 `28180`，连接 Unitree 导航与自定义 action。
- 控制台：`rabbitbot.control_console` 提供启动、停止、状态和日志查看能力。
- 部署：`deploy/` 与 `docker/portable/` 支持镜像构建、导入、模型准备、自检、systemd/compose 启动。

## 主要目录

- `README.md`：顶层部署和运行说明。
- `deploy/`：portable 镜像、模型、宿主初始化、自检、基础栈启动脚本。
- `rabbitbot-dev-ros2-master/`：主 Python 项目与 Docker/脚本/测试。
- `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/`：导览编排；本轮合入后 `workflow.py` 已拆出 `workflow_config.py`、`workflow_profiling.py`、`workflow_text.py`、`workflow_data.py`、`workflow_arm.py`。
- `rabbitbot-dev-ros2-master/rabbitbot/guide/`：导览控制、对话、路由等纯逻辑模块。
- `rabbitbot-dev-ros2-master/rabbitbot/audio/`：音频设备探测与 Unitree TTS 后端。
- `rabbitbot-dev-ros2-master/rabbitbot/clients/`：TTS/STT HTTP 客户端。
- `rabbitbot-dev-ros2-master/rabbitbot/runtime/`：运行配置读取工具与 portable env 示例。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/`：控制台后端。
- `rabbitbot-dev-ros2-master/docker/portable/`：portable core/nav Dockerfile、解耦 compose、PulseAudio 可选覆盖。
- `rabbitbot-dev-ros2-master/scripts/`、`scripts_1/`：服务启动、workflow loop、统一/解耦容器入口。
- `rabbitbot-dev-ros2-master/tests/`：audio、clients、control_console、guide 等测试。
- `custom_action_ws/`、`unitree_slam_example_new/`：ROS2/Unitree 导航相关代码。
- `memory/`、`third_party/`、`models/`：记忆资料、外部依赖清单与模型缓存；模型目录内容在当前工作区是否完整未确认。

## 技术栈与依赖

- Python `>=3.10`，`pyproject.toml` 管理包元数据。
- 主要依赖：`qwen-agent[gui,rag,code_interpreter,mcp]`、`opencv-python-headless`、`PyGObject==3.42.1`、`numpy`、`graphiti-core`。
- 可选测试依赖：`pytest`、`fastapi`、`httpx`、`requests`。
- Web/API：FastAPI/HTTP `/exec` 风格服务。
- 容器：Docker Compose、host network、NVIDIA runtime。
- 数据库：Neo4j。
- 机器人：ROS2 Humble、Unitree SDK2、自定义 action、PCD 地图。
- 音频：默认 ALSA/Unitree，本轮合入包含 PulseAudio/蓝牙实验入口；完整蓝牙后端未确认。

## 运行入口与数据流

常用入口：
- portable 基础服务：`bash deploy/start_portable_stack.sh`
- 主循环：`bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`
- workflow 控制：`bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh go|arrive|back`
- 控制台服务：systemd 或 `rabbitbot.control_console` 入口，具体部署方式以现场配置为准。

核心数据流：
1. 读取 `rabbitbot-dev-ros2-master/runtime/portable.env`，缺失时参考 `portable.env.example`。
2. `docker/portable/docker-compose.decoupled.yaml` 拉起 Neo4j、VLM/Embedding、TTS、STT、Memory、workflow/navbridge 等服务。
3. workflow 进入 QA/导览控制状态，经 STT 文本或控制命令进入导览、返航、闲聊或找物品路径。
4. 导览路径加载剧本和点位，调用 TTS 播报、导航桥接移动、机械臂动作，并写入状态/日志。
5. 闲聊路径可通过 Memory RAG 检索 Neo4j/Markdown 资料，再交给 VLM/LLM 生成回答。

## 重要配置

- `rabbitbot-dev-ros2-master/runtime/portable.env.example`：portable 配置模板。
- `rabbitbot-dev-ros2-master/runtime/portable.env`：本机运行态配置，通常不提交；当前机器是否存在有效文件未确认。
- `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml`：解耦基础栈。
- `rabbitbot-dev-ros2-master/docker/portable/docker-compose.audio-pulse.yaml`：PulseAudio 可选覆盖。
- `rabbitbot-dev-ros2-master/conf/`：导览点位、台词、地图等配置。
- `third_party/manifest.lock`：外部依赖、镜像和模型来源清单。
- 现场路径 `/mnt/disk1/gt/air_robot_gt_projects` 来自项目文档；本轮本地工作区为 `/Users/firmiana/Desktop/air_robot_gt_projects`，现场路径未在本机验证。

## 当前状态

- new-orin 目标目录为 `/mnt/disk1/gt/RobotAbrainOffline`，本轮已尝试 portable 启动验证。
- 目标 Orin 已具备 Docker、Docker Compose、Python 3.10 和 portable core/nav/neo4j 镜像。
- `models/` 已在 new-orin 新项目目录中复制为实体目录，不再使用符号链接；模型来源为旧目录的现有缓存。
- 本轮修正 `docker-compose.decoupled.yaml` 的旧项目根硬编码，改为强制读取 `RABBITBOT_PROJECTS_DIR` / `RABBITBOT_MODELS_CACHE_DIR`；`bootstrap_host.sh` 会写入当前项目根和模型目录。
- new-orin 旧目录 `/mnt/disk1/gt/air_robot_gt_projects` 已删除；当前运行容器只挂载 `/mnt/disk1/gt/RobotAbrainOffline` 与其 `models/`。

## 本轮合并改动摘要

- 导览 workflow：从 `workflow.py` 拆出配置、插装、文本解析、数据加载和机械臂模块，外部入口保持兼容。
- 导览纯逻辑：新增 `rabbitbot/guide/controls.py`、`dialogue.py`、`routing.py` 及对应测试。
- 音频服务：新增设备探测，TTS/STT 从 `rabbitbot-audio` 拆为 `rabbitbot-tts` 与 `rabbitbot-stt`。
- 音频客户端：新增 `rabbitbot.clients.audio`，统一 `/exec` 请求、超时、异常和响应解析日志。
- 运行配置：新增 `rabbitbot.runtime.config`，集中读取 URL 和浮点配置并记录非法配置回退。
- 控制台：服务到容器映射改为 TTS/STT 独立容器，保留旧 `audio` 分组兼容。
- 部署脚本：更新 portable compose、启动脚本、统一容器角色入口、TTS/STT 默认参数和启动日志。
- 测试：新增 audio、clients、guide 测试，并调整 control_console 测试。
- 文档：同步 README 与交接报告，说明解耦栈和运行路径。

## 日志新增或调整

- `rabbitbot.clients.audio` 新增 INFO 级客户端初始化日志，WARNING 级请求超时、请求失败、异常状态码、JSON 解析失败和响应字段缺失日志。
- `rabbitbot.runtime.config` 对空 URL、非法浮点配置记录 WARNING 并回退默认值。
- 音频设备探测与 TTS/STT 启动脚本增加设备、后端、启动策略等诊断输出。
- 控制台容器映射变化不记录密钥、令牌、完整隐私数据或大体积原始输入输出。
- 本轮未新增代码日志；部署脚本继续使用既有 INFO/OK/WARN/ERROR 输出记录初始化、模型检查和启动上下文。

## 验证事实

- new-orin 上 `deploy/bootstrap_host.sh` 成功生成 portable env 和控制台 venv。
- new-orin 上 `PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh` 通过；仅提示 `/home/unitree/test9.pcd` 地图路径不可见。
- new-orin 上 `deploy/start_portable_stack.sh` 成功拉起基础服务：neo4j、rabbitbot-vlm、rabbitbot-tts、rabbitbot-stt、rabbitbot-memory、rabbitbot-workflow；VLM 首次启动等待较久，最终 healthy。
- 完全重建容器和可重建依赖卷后，new-orin 基础服务全部 healthy；`docker inspect` 确认 rabbitbot 容器只挂载新项目路径。
- 旧目录删除后，短时无机器人模式主循环已完成 workflow 预启动，并停在 `go` 闸门等待命令；本轮随后清理了该短跑 workflow 进程，仅保留基础服务运行。
- `git merge --no-ff --no-commit refactor/service-internal-decoupling` 无冲突。
- 合并前 `git merge-tree --write-tree master refactor/service-internal-decoupling` 通过。
- 合并前 `git diff --check master..refactor/service-internal-decoupling` 无输出。
- 本机 `python` 命令不存在；`python3` 存在但缺少 `pytest`，因此未运行完整 pytest。
- 已用 `python3 -m py_compile` 检查变更 Python 文件，通过。
- 已用 `bash -n` 检查变更 shell 脚本，通过。

## 阻塞与风险

- 完整 pytest 受本机缺少 `pytest` 阻塞。
- Docker Compose、GPU、模型、Neo4j、TTS/STT HTTP 服务、导航桥接和真机导览闭环未在本轮本地验证。
- PulseAudio/蓝牙音频仍是实验入口，完整可用性未确认。
- 真实地图 `/home/unitree/test9.pcd`、DDS 网卡、机器人网络与真机导航桥接未在本轮验证。
- 历史运行日志可能包含较完整文本或 payload，后续应继续治理隐私与日志体积。

## 下一步建议

1. 在目标运行环境安装测试依赖后执行 `python3 -m pytest tests/audio tests/clients tests/control_console tests/guide`。
2. 执行 `docker compose config` 与 portable 基础栈启动验证。
3. 在无机器人模式验证控制台启动/停止、服务状态和 workflow 控制命令。
4. 在真机环境验证 TTS/STT 互斥、导航桥接、点位到达、返航和异常恢复。
5. 持续检查关键流程日志，保留上下文和异常链，避免记录密钥、令牌、完整隐私数据和大体积原始输入输出。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型训练/推理、命令脚本、配置加载和异常处理应补充有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交本机运行态配置、密钥、令牌、模型缓存或大体积日志。

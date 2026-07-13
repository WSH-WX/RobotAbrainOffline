# RobotAbrainOffline 交接报告

更新时间：2026-07-13（Asia/Singapore）
工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
部署主机：`AGX-orin:/mnt/ssd/gt/RobotAbrainOffline`
本轮主题：在 AGX Orin 上完成 portable 解耦栈部署，替换旧 RabbitBot 运行资源，并修复导航地图挂载与 STT 音频设备选择。

## 项目整体描述

`RobotAbrainOffline` 是 RabbitBot/Unitree 导览机器人的离线部署仓库，用于在 NVIDIA Jetson AGX Orin、ROS2 Humble 和 Docker 环境中运行导览 workflow、语音识别与合成、视觉语言模型、向量模型、记忆检索、Neo4j、Unitree 导航桥接和局域网控制台。

核心数据流：控制台或 systemd 启动主循环；workflow 读取台词、点位与地图配置；STT/控制命令触发导览、返航或问答；workflow 通过 28180 导航桥接调用 Unitree 导航；TTS 播报；VLM、Embedding、Memory 与 Neo4j 提供视觉问答和记忆能力。

## 主要模块与目录

- `deploy/`：宿主初始化、镜像导入/构建、模型准备、网络配置、基础栈启动、自检和 systemd 安装。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/`：FastAPI 局域网控制台、状态展示和服务控制。
- `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/`：导览 workflow、工具调用、记忆与 profiling。
- `rabbitbot-dev-ros2-master/rabbitbot/guide/`：导览台词、命令和路由逻辑。
- `rabbitbot-dev-ros2-master/docker/portable/`：portable core/nav 镜像和解耦 Compose。
- `rabbitbot-dev-ros2-master/scripts/`、`scripts_1/`：语音服务、导航桥接、workflow 和主循环入口。
- `rabbitbot-dev-ros2-master/conf/`：台词、点位和地图文件名等运行配置。
- `custom_action_ws/`、`unitree_slam_example_new/`：ROS2 action、Unitree 导航和机械臂代码。
- `models/`：运行模型缓存，不进入 Git；AGX-orin 当前约 9.3GB。
- `runtime-data/`：AGX-orin 本轮使用的地图和部署日志，不进入 Git。
- `third_party/manifest.lock`：Git 外依赖、镜像和模型来源清单。

## 技术栈、入口与配置

- 技术栈：Python 3.10/3.12、FastAPI/Uvicorn、Docker Compose、NVIDIA runtime、CUDA、ROS2 Humble、Neo4j、vLLM、FunASR、ALSA。
- 基础栈入口：`bash deploy/start_portable_stack.sh`。
- 主循环入口：`rabbitbot-loop.service` 或 `bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`。
- 控制台入口：`rabbitbot-control-console.service`，监听 `0.0.0.0:8080`。
- 关键配置：`rabbitbot-dev-ros2-master/runtime/portable.env`（AGX 本机运行态，不提交）、对应 `.example`、两份 portable Compose、`conf/dialogue_0.json`。
- portable 数据流：宿主源码/模型/地图以 bind mount 注入；core 镜像复用为 VLM、TTS、STT、Memory、workflow 容器；nav 镜像提供 28180；全部使用 host 网络。
- 外部依赖：JetPack/Docker/NVIDIA runtime、机器人 DDS 网卡、现场地图、portable 镜像和模型缓存。AGX 上镜像来自 `outputs/portable-images` 离线包。

## AGX-orin 当前部署状态

- 新项目路径：`/mnt/ssd/gt/RobotAbrainOffline`。
- 已导入并核对镜像：core `9183fa54fd3e`、nav `87fc947332fb`、Neo4j `9fbe88679cbe`。
- 已把三套主模型和 Kokoro TTS 模型实体复制到新项目 `models/`，运行不依赖旧路径或符号链接。
- 地图位于 `runtime-data/maps/global_map_20260330_155423.pcd`，SHA-256 为 `ac7a6b66f6f7e996e190aab991d82aee4c78fd37cbd7dbb18a66ecdfbc71f41b`。
- `portable.env` 已生成，项目根、模型、地图和 Compose 路径均指向新项目。
- NetworkManager 连接 `rabbitbot-dds-eno1` 已创建，配置 `192.168.123.222/24` 且自动连接；当前网线无载波，`eno1` 显示 DOWN。
- `neo4j`、`rabbitbot-vlm`、`rabbitbot-tts`、`rabbitbot-stt`、`rabbitbot-memory`、`rabbitbot-workflow` 已运行且健康。
- `rabbitbot-control-console.service` 已安装并运行；`rabbitbot-loop.service` 已安装但保持 inactive。两个服务按现有安装策略均为 disabled。
- systemd 与 sudoers 已全部切换到新路径，不再引用 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`。
- 旧项目目录、旧 RabbitBot 容器/镜像和旧 Neo4j 卷已删除；用户随后明确要求无需恢复、继续部署新项目。

## 本轮代码修改

- 两份 portable Compose 为 nav 容器增加现场地图的同路径只读 bind mount，解决宿主地图存在但容器内不可见的问题。
- `deploy/check_air_project.sh` 新增地图挂载策略检查，单 nav 与解耦 Compose 缺少挂载时快速失败并输出具体文件。
- STT 启动脚本不再只跨进程传递易漂移的 PortAudio 数字索引，同时传递稳定设备名称。
- `stt_app_funasr.py` 优先使用设备名称，保留数字索引回退；设备初始化失败时记录来源、选择器和异常类型，并用异常链抛出。

## 日志新增或调整

- 新增 INFO 日志：STT 输入设备选择器来源（name/index/default）和已解析选择器。
- 新增异常日志：STT 输入设备初始化失败时记录必要上下文并保留原始异常链。
- 部署和自检继续使用现有 `[INFO]/[OK]/[WARN]/[ERROR]` 体系；未记录密码、令牌、完整隐私数据或大体积输入输出。

## 已验证事实

- 三个离线 tar 的 SHA-256 全部通过；导入后镜像 ID 与 `images.lock.json` 一致。
- `PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh` 在 AGX-orin 通过。
- 两份 Compose 均通过 `docker compose config -q`；地图挂载策略自检通过。
- 控制台 `/` 与 `/api/status`、VLM 8000、Embedding 8005、STT 28184、Memory 28182 均返回 HTTP 200。
- TTS 28185 `wait_speech` 返回 HTTP 200 和 `TTS finished`；Neo4j `RETURN 1` 成功。
- STT 修复后以名称选择 `NVIDIA Jetson AGX Orin APE (hw:2,0)`，容器健康且 28184 可用。
- 基础容器近 5 分钟日志关键字扫描未发现 `traceback/fatal/error/exception/failed`。
- 根分区从 100% 清理到约 98%、可用约 1.1GB；Docker 数据实际位于 SSD。SSD 清理旧运行资源后可用约 226GB。

## 阻塞、风险与未完成事项

- 真机网线/机器人链路当前未接通，`eno1` 无载波；未启动或验证 nav bridge、28180、定位、机械臂和真实导览全链路。
- 系统根分区仍约 98%，虽然 Docker 在 SSD，但系统日志、apt 或临时文件仍有满盘风险，应继续排查 `/home/pc` 和系统盘占用。
- 本机 Python 未安装 pytest（`No module named pytest`），本轮未运行 pytest 套件；已完成 Bash、Python 编译、Compose、自检和 AGX 运行验证。

## 下一步与常用命令

1. 接好机器人网线后确认 `ip -brief addr show eno1` 为 UP，并确认机器人侧 DDS 可达。
2. 启动主循环：`sudo systemctl start rabbitbot-loop.service`。
3. 检查导航：`ss -lntp | grep 28180`，并查看 `unitree_slam_example_new/example/run_logs/` 与 `logs/current_runtime.log`。
4. 控制台访问：`http://192.168.101.2:8080`；状态检查：`curl http://127.0.0.1:8080/api/status`。
5. 基础容器检查：`docker ps`；重启基础栈：`bash deploy/start_portable_stack.sh`。
6. 保持 `runtime/portable.env`、模型、地图、镜像 tar 和运行日志不进入 Git；不要在日志中写入密码或令牌。

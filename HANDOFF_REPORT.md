# RobotAbrainOffline 交接报告

更新时间：2026-07-16（Asia/Singapore）
本机工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
部署主机：`AGX-orin:/mnt/ssd/gt/RobotAbrainOffline`
本轮主题：控制台确认地图后同步重建 NavBridge，并确保使用机器人本体地图路径。

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
- portable 数据流：宿主源码、模型与日志按需 bind mount；机器人地图仅将本体绝对路径传给 Unitree SLAM，不挂载到 Orin 容器；core 镜像复用为 VLM、TTS、STT、Memory、workflow 容器；nav 镜像提供 28180；全部使用 host 网络。
- 外部依赖：JetPack/Docker/NVIDIA runtime、机器人 DDS 网卡、现场地图、portable 镜像和模型缓存。AGX 上镜像来自 `outputs/portable-images` 离线包。

## AGX-orin 当前部署状态

- 新项目路径：`/mnt/ssd/gt/RobotAbrainOffline`。
- 已导入并核对镜像：core `9183fa54fd3e`、nav `87fc947332fb`、Neo4j `9fbe88679cbe`。
- 已把三套主模型和 Kokoro TTS 模型实体复制到新项目 `models/`，运行不依赖旧路径或符号链接。
- Orin 归档地图位于 `runtime-data/maps/global_map_20260330_155423.pcd`；当前导航使用机器人本体已确认存在的 `/home/unitree/test7.pcd`。
- `portable.env` 已生成；其中旧的 Orin 地图值只作为启动回退，控制台确认值持久化在 `runtime/rabbitbot-loop.env` 并在重建 NavBridge 时显式覆盖。
- NetworkManager 连接 `rabbitbot-dds-eno1` 配置为 `192.168.123.222/24`；现场验证时 `eno1` 已连接机器人网络。
- `neo4j`、`rabbitbot-vlm`、`rabbitbot-tts`、`rabbitbot-stt`、`rabbitbot-memory`、`rabbitbot-workflow` 已运行且健康。
- `rabbitbot-control-console.service` 与 `rabbitbot-loop.service` 均已安装并运行；两个服务按现有安装策略均为 disabled，导航主循环由控制台按需启动。
- systemd 与 sudoers 已全部切换到新路径，不再引用 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`。
- 旧项目目录、旧 RabbitBot 容器/镜像和旧 Neo4j 卷已删除；用户随后明确要求无需恢复、继续部署新项目。

## 本轮代码修改

- TTS/STT 服务新增只读 `/device` 接口，分别返回实际输出设备或本体扬声器、实际输入麦克风，以及后端、声道、采样率等有限诊断信息。
- 控制台服务状态新增 `device_name`、`device_detail`，仅在 TTS/STT 在线时查询并在对应前端卡片显示“设备”行；展示使用 `textContent`，避免设备名称注入 HTML。
- `rabbitbot/guide/controls.py` 新增句首唤醒词校验与称呼剥离；未称呼“小智”的自由问答不会进入模型或 TTS，命中后仅把称呼后的请求交给原问答流程。
- `rabbitbot/agno_agents/workflow.py` 在普通 QA、连续追问、导览开场/途中自由提问和语音控制入口应用门控；机器人主动提问所等待的剧本回答不受影响。
- 默认导览注入口令改为“小智, 开始导览”，预导览超时提示同步说明称呼要求；可用 `RABBITBOT_GUIDE_WAKE_WORDS` 配置替代称呼。
- 服务状态列表新增 NavBridge（`127.0.0.1:28180` / `rabbitbot-navbridge`）卡片，可在控制台独立确认并重启。
- NavBridge 重启使用解耦 Compose `up -d --force-recreate rabbitbot-navbridge`，在线时重建、容器缺失或离线时重新创建，不依赖 `rabbitbot-loop.service` 已运行。
- 服务 key、容器映射和重启宽限状态均增加 `navbridge`，控制台首页避免重复显示同一 NavBridge 状态。
- NavBridge 订阅容器内 ROS2 `/current_pose` 并提供 `GET /current_pose`；解耦 Compose 将仓库内桥接脚本只读挂载进容器，宿主应用无需 ROS2 CLI 即可读取带时效校验的七元组位姿。
- 控制台“确认地图”现在持久化前端路径后同步重建 NavBridge，并通过 Compose 子进程环境显式传入 `RABBITBOT_NAV_MAP_PATH`；单独重启 NavBridge 也读取同一持久化值。
- 两份 portable Compose 移除错误的机器人地图 bind mount；`deploy/check_air_project.sh` 改为校验路径传递存在且禁止把机器人侧路径作为 Orin bind mount。
- 新增 `deploy/runtime_permissions.sh`，让 bootstrap 与 systemd 安装流程幂等修复仓库根 `logs/`、控制台 `runtime/` 和导航 run_logs 的服务用户所有权、组写权限及 setgid；修正旧 bootstrap 创建错误嵌套日志目录的问题。
- clean-Orin 自检新增运行目录所有者/可写性检查；主循环启动前输出权限诊断，控制台发现当前日志不可写时保留异常链并直接向前端报错，不再继续提交必然失败的 systemd 重启。
- STT 启动脚本不再只跨进程传递易漂移的 PortAudio 数字索引，同时传递稳定设备名称。
- `stt_app_funasr.py` 优先使用设备名称，保留数字索引回退；设备初始化失败时记录来源、选择器和异常类型，并用异常链抛出。

## 日志新增或调整

- TTS/STT 初始化完成时新增 INFO 设备状态日志，记录后端、设备名称、声道、采样率或 Unitree 网卡/扬声器 ID；设备接口请求失败仅记 DEBUG，非法响应记 WARNING。
- 唤醒词命中和忽略均使用 INFO 日志，只记录称呼、输入长度、请求长度和匹配状态，不记录完整语音文本。
- NavBridge 重启新增 INFO 日志，记录服务名、Compose 文件、Docker 路径和完成状态；超时或失败使用 ERROR 记录退出码与限量输出并保留超时异常链。
- 控制台确认地图成功新增 INFO 日志，记录有限的地图路径、环境文件和 NavBridge 容器上下文；不记录密钥或大体积输入。
- 部署权限修复逐目录输出 INFO/OK 所有者和权限；主循环启动前记录日志目录检查结果，失败时记录路径、所有者、模式和服务用户。
- NavBridge 首次取得有效位姿时以 INFO 记录有限的 x/y 上下文；无效位姿仅首次 WARNING，避免持续话题造成日志膨胀。
- 新增 INFO 日志：STT 输入设备选择器来源（name/index/default）和已解析选择器。
- 新增异常日志：STT 输入设备初始化失败时记录必要上下文并保留原始异常链。
- 部署和自检继续使用现有 `[INFO]/[OK]/[WARN]/[ERROR]` 体系；未记录密码、令牌、完整隐私数据或大体积输入输出。

## 已验证事实

- 提交归档在 Orin 的控制台定向测试 65/65 通过；本机 Python 语法编译和设备状态解析/序列化轻量校验通过。
- Orin 已重启 TTS、STT 和控制台完成现场验证：`/device` 与 `/api/status` 显示 TTS 为 `NVIDIA Jetson AGX Orin HDA: HDMI 0 (hw:1,3)`，STT 为 `Wireless Mic Rx: USB Audio (hw:0,0)`；两容器均 healthy，控制台 active。
- 唤醒词纯逻辑新增用例 7/7、`tests/guide` 全量 `unittest` 23/23 通过，覆盖带/不带“小智”、句首限制、标点、空请求及自定义称呼；变更 Python 文件通过 `py_compile`，workflow loop 脚本通过 `bash -n`。
- Orin 的 `runtime/portable.env` 未显式覆盖导览口令、唤醒词或预导览提示，代码默认值同步后可直接生效。
- 本轮新增 NavBridge 命令、API、状态和容器映射定向测试 4/4 通过；本机和 Orin 控制台完整测试均为 92/92 通过，并固定了既有启动宽限窗口和主循环探测用例的环境依赖。
- Orin 实际调用 `POST /api/service/restart` 成功创建此前缺失的 `rabbitbot-navbridge`；容器保持 running，`GET 127.0.0.1:28180/health` 返回 `ok=true`，22 秒保护窗口后控制台卡片从“启动中”转为“在线”。
- 本轮 Orin 控制台测试 94/94 通过，两份 Compose `config -q` 与 `PORTABLE_CHECK_MODE=clean_orin` 自检通过。
- 运行目录权限修复后 Orin 控制台测试 95/95 通过；实际重新安装 systemd 后四个目录均为 `pc:pc` 且可写，clean-Orin 自检通过。
- 现场调用“一键重启”对应 `/api/restart` 成功，`rabbitbot-loop.service` 为 active，`logs/current_runtime.log` 由 `pc:pc` 创建；近两分钟无 `Permission denied` 或日志目录不可写错误。
- 现场调用 `POST /api/map` 输入 `/home/unitree/test7.pcd` 后返回成功；容器环境确认同值且无地图 bind mount，NavBridge 健康接口正常，原 `507 Load pcd failed` 已消失。
- 重新创建后的 NavBridge 已加载宿主桥接脚本，`GET /current_pose` 持续返回 `localized=true`、七元组和位姿年龄；首次有效位姿 INFO 日志已验证。
- 三个离线 tar 的 SHA-256 全部通过；导入后镜像 ID 与 `images.lock.json` 一致。
- `PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh` 在 AGX-orin 通过。
- 两份 Compose 均通过 `docker compose config -q`；地图挂载策略自检通过。
- 控制台 `/` 与 `/api/status`、VLM 8000、Embedding 8005、STT 28184、Memory 28182 均返回 HTTP 200。
- TTS 28185 `wait_speech` 返回 HTTP 200 和 `TTS finished`；Neo4j `RETURN 1` 成功。
- STT 修复后以名称选择 `NVIDIA Jetson AGX Orin APE (hw:2,0)`，容器健康且 28184 可用。
- 基础容器近 5 分钟日志关键字扫描未发现 `traceback/fatal/error/exception/failed`。
- 根分区从 100% 清理到约 98%、可用约 1.1GB；Docker 数据实际位于 SSD。SSD 清理旧运行资源后可用约 226GB。

## 阻塞、风险与未完成事项

- 唤醒门控尚未使用现场麦克风和真实 STT 做端到端语音验证；需确认 ASR 对“小智”及其后停顿、逗号的识别稳定性。
- NavBridge 和 28180 已启动，导航核心日志持续输出 Pose；本轮未下发运动、机械臂或真实导览指令，完整机器人动作链路仍需现场安全监护下验证。
- `/home/unitree/test7.pcd` 已被机器人侧接受，但当前重定位返回 `509 The current location matching degree is low`，需将机器人置于地图特征明显的位置后再验证定位；这已不是地图加载失败。
- 系统根分区仍约 98%，虽然 Docker 在 SSD，但系统日志、apt 或临时文件仍有满盘风险，应继续排查 `/home/pc` 和系统盘占用。
- 本机 Python 未安装 pytest（`No module named pytest`），本轮未运行 pytest 套件；已完成 Bash、Python 编译、Compose、自检和 AGX 运行验证。

## 下一步与常用命令

1. 接好机器人网线后确认 `ip -brief addr show eno1` 为 UP，并确认机器人侧 DDS 可达。
2. 启动主循环：`sudo systemctl start rabbitbot-loop.service`。
3. 检查导航：`ss -lntp | grep 28180`，并查看 `unitree_slam_example_new/example/run_logs/` 与 `logs/current_runtime.log`。
4. 控制台访问：`http://192.168.101.2:8080`；状态检查：`curl http://127.0.0.1:8080/api/status`。
5. 基础容器检查：`docker ps`；重启基础栈：`bash deploy/start_portable_stack.sh`。
6. 保持 `runtime/portable.env`、模型、地图、镜像 tar 和运行日志不进入 Git；不要在日志中写入密码或令牌。

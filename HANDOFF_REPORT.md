# air_robot_gt_projects 项目交接报告

生成时间：2026-07-03 10:12（Asia/Singapore，CST +0800）
当前主机：`new-orin`
项目路径：`/mnt/disk1/gt/air_robot_gt_projects`
当前分支：`refactor/service-internal-decoupling`（自 `refactor/rabbitbot-runtime-structure-stabilization` 派生）
近期工作详见文末「近期工作」；更细粒度的逐轮改动请查 Git 历史。

## 项目整体描述

`air_robot_gt_projects` 是 RabbitBot 在 Orin 设备上的自主运行包，把导览 workflow、语音交互、视觉/记忆服务、Unitree 导航桥接和部署脚本组织成一套可迁移运行环境。当前默认方向是 portable 解耦多容器栈，同时保留 legacy 路径。

核心功能：

- DOCX/JSON 剧本导览 workflow：进入 QA 状态，等待“开始导览”等控制词后按点位讲解、导航、返航。
- 语音链路：TTS `28185`、STT `28184`，已拆为独立容器并保留 `/exec` 协议兼容。
- 视觉与语义：VLM `8000`、Embedding `8005`。
- 记忆服务：Memory Agent `28182`，依赖 Neo4j 和 Embedding。
- 导航桥接：`humble_robot_agent_bridge.py` / nav portable 容器提供 `28180`，连接 Unitree 导航、地图和机器人侧 action。
- 控制台：`rabbitbot.control_console` 默认监听 `8080`。
- 部署交付：构建机生成 portable 镜像、全新 Orin 离线导入、宿主初始化、自检、systemd 安装。

## 关键目录结构

- `README.md`：顶层 portable/legacy 部署说明（运行架构表描述解耦栈 7 个容器）。
- `HANDOFF_REPORT.md`：本交接报告。
- `deploy/`：宿主初始化、镜像构建/校验/导入导出、模型准备、自检、systemd 安装、portable 基础栈启动脚本。
- `rabbitbot-dev-ros2-master/`：主项目源码、控制台、workflow、TTS/STT/VLM/Memory 应用、Docker 定义、测试。
  - `docker/portable/`：portable core/nav Dockerfile 与解耦 compose。
  - `scripts_1/`：主循环、控制台、nav bridge、解耦/统一容器入口等运行脚本。
  - `scripts/`：各服务独立启动脚本和旧工作流脚本。
  - `rabbitbot/`：Python 包（上下文、provider、grounding、控制台、音频兼容层等）。
    - `agno_agents/`：导览编排。原 3888 行巨石 `workflow.py` 已按关注点拆为同目录子模块：`workflow_config.py`（env 开关）、`workflow_profiling.py`（插装/退出汇总）、`workflow_text.py`（语音文本解析）、`workflow_data.py`（DOCX 台词与实体/点位加载）、`workflow_arm.py`（机械臂手势）；`workflow.py` 经显式 import 重导出全部符号，对外仍只暴露 `create_main_workflow`/`guide_opening_speech`，命名空间与行为不变。
  - `tests/`：audio、clients、control_console、guide、memory、tasks、view、vln 等。
- `models/`：本机模型缓存（Kokoro、Qwen2.5-VL、Qwen3-Embedding、SenseVoice、fsmn_vad）。
- `custom_action_ws/`：ROS2 Humble 自定义 action 工作区。
- `unitree_slam_example_new/`：Unitree 导航、地图、手臂/nav bridge 源码与脚本。
- `unitree_sdk2/`、`vln/`、`pyorbbecsdk-v2-py310/`：portable 构建/运行外部依赖。
- `third_party/manifest.lock`：仓库外依赖、镜像和模型来源清单。
- `logs/`：运行日志、workflow 控制状态、解耦容器服务日志。

## 主要技术栈与外部依赖

- Python ≥3.10（`pyproject.toml`），主要依赖 `qwen-agent[gui,rag,code_interpreter,mcp]`、`opencv-python-headless`、`PyGObject==3.42.1`、`numpy`、`graphiti-core`。
- Web/API：FastAPI/uvicorn 风格，TTS/STT/Memory/Robot Agent 均暴露 HTTP 接口。
- 容器：Docker Compose，host network，NVIDIA runtime；portable core/nav 镜像默认 `ghcr.io/aaronai/rabbitbot-*-portable:20260611`。
- 数据库：Neo4j 5.26 community。
- 机器人/导航：ROS2 Humble、Unitree SDK2、自定义 action、PCD 地图。
- 模型：Qwen2.5-VL-7B-Instruct-GPTQ-Int4、Qwen3-Embedding-0.6B、SenseVoiceSmall、fsmn_vad、Kokoro-82M。
- 音频：ALSA 为默认后端；PulseAudio/蓝牙仅有探测和可选 compose override，未实现完整后端。
- 外部账号、远端 GitHub URL、镜像发布凭据：未确认；本报告不记录任何密钥或令牌。

## 运行入口与核心数据流

解耦基础栈由 `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml` 定义，7 个容器全部 `network_mode: host`、服务间走 `127.0.0.1`：`neo4j`、`rabbitbot-vlm`(8000+8005)、`rabbitbot-tts`(28185)、`rabbitbot-stt`(28184)、`rabbitbot-memory`(28182，依赖 neo4j+embedding)、`rabbitbot-navbridge`(28180，完整 loop 时才起)、`rabbitbot-workflow`(保活宿主，loop 经 `docker exec` 注入 workflow)。

主循环数据流：

1. systemd 或人工执行 `scripts_1/start_loop_entry.sh`。
2. 读取 `runtime/portable.env`（缺失回退 `portable.env.example`，正式部署先跑 `deploy/bootstrap_host.sh`）。
3. portable 模式设置 `RABBITBOT_BASE_RUNTIME=compose`、`RABBITBOT_NAV_RUNTIME=compose`、地图路径、DDS 网卡、VLM/Embedding/STT 开关。
4. `scripts_1/start_nav_bridge_workflow_loop.sh` 准备模型、确保基础服务、起/复用 nav bridge，再把 workflow 注入 `rabbitbot-workflow`。
5. workflow 先进入 QA 状态，TTS 播放提示、STT 监听；识别到“开始导览”进入剧本导览，点位到达/返航由脚本或控制台触发。
6. 控制命令：`scripts_1/send_nav_workflow_command.sh go/back/arrive` 或控制台。

## 重要配置文件

以下除顶层文件外均在 `rabbitbot-dev-ros2-master/` 下：

- `runtime/portable.env.example`：可迁移默认模板，进入 Git。
- `runtime/portable.env`：本机运行态配置，不进 Git（当前远端存在）。
- `runtime/rabbitbot-loop.env`：loop 运行环境配置。
- `docker/portable/docker-compose.decoupled.yaml`：当前解耦栈主 compose。
- `docker/portable/docker-compose.audio-pulse.yaml`：可选 PulseAudio/蓝牙覆盖，默认不启用。
- `conf/dialogue_*.json`：导览点位、台词、地图配置。
- 顶层 `third_party/manifest.lock`：外部依赖、镜像、模型来源与 blocker 清单。
- 顶层 `.dockerignore`、`.gitignore`：控制 portable 构建上下文和 Git 提交边界。

## 常用命令

均在 `/mnt/disk1/gt/air_robot_gt_projects` 下执行：

```bash
git status --short                                                # Git 状态
PORTABLE_CHECK_MODE=builder    bash deploy/check_air_project.sh    # 构建机自检
PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh    # 全新 Orin 自检
MODE=check bash deploy/build_or_pull_images.sh                     # 校验镜像（MODE=build 则构建）
bash deploy/start_portable_stack.sh                               # 启动 portable 基础服务
sudo systemctl start rabbitbot-control-console.service            # 控制台
sudo systemctl start|stop rabbitbot-loop.service                 # 启停导航主循环
bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh      # 手工启动主循环入口
bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh go|arrive|back  # workflow 控制
# 核心单测（在 rabbitbot-dev-ros2-master 下）
python3 -m unittest tests.audio.test_device_probe tests.clients.test_audio_clients tests.clients.test_runtime_config -v
python3 -m unittest discover tests -v
```

## 当前状态

- 远端 `/mnt/disk1/gt/air_robot_gt_projects` 为 Git 仓库，分支 `refactor/rabbitbot-runtime-structure-stabilization`。
- 基础容器 `neo4j`、`rabbitbot-vlm`、`rabbitbot-tts`、`rabbitbot-stt`、`rabbitbot-memory` 正常 healthy，`rabbitbot-workflow` 运行但无健康检查；`rabbitbot-navbridge`（28180）仅在完整 loop 时启动。
- workflow 常停留在 QA 等待语音循环，每 30 秒 STT 超时后再次 TTS 提示。
- 未验证：真机导航/返航/DOCX 完整导览闭环、远端 Git remote 与 CI/CD。

## 已知阻塞与风险

- QA/导览链路未稳定闭环：workflow 长时间停在 QA 等待语音并反复超时；TTS 播放期间 STT 回声/空输入触发 planner 异常仍是未完成风险。
- TTS/STT 未互斥门控：TTS 播放期间 STT 仍可能收到提示音或环境回声。
- 空输入防护不足：超时/回声后的空输入仍可能让 planner 进入异常路径。
- PulseAudio/蓝牙音频还不是完整后端。
- 日志治理未完成：历史 workflow/TTS 日志仍会记录完整文本和部分 payload，应避免长期落盘隐私语音、密钥、令牌和大体积原始输入输出。
- 真机导航、地图 `/home/unitree/test9.pcd`、DDS 网卡 `eno1`、机器人网络 `192.168.123.222/24` 现场可用性未验证。
- README「legacy 回退路径」仍引用 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`，该旧项目在本机不存在、真实位置未确认。

## 日志现状

- 项目 shell 彩色日志与 Python logging 混用；新增/调整关键流程应优先沿用当前模块日志系统。
- 默认级别保持 INFO 或更高；DEBUG 仅短时诊断并配合限量/轮转/降级。
- 关键日志位置：`logs/current_runtime.log`、`logs/nav_workflow_control/`、`logs/unified_runtime/`、`rabbitbot-dev-ros2-master/logs/unified_runtime/`。
- TTS 请求链路会记录完整提示文本，便于排障但不适合长期记录隐私输入。

## 建议下一步

1. 治理 QA/导览主链路：TTS 播放期间 STT 暂停/降权/门控，避免提示音回收。
2. planner 前加空输入与无效输入防护：空输入不进入 planner，记录原因并继续监听。
3. 把“开始导览”“返回起点”等控制词放到所有 STT 文本入口最高优先级。
4. 轻量验证：`docker compose config`、bash 语法检查、`tests.audio`/`tests.clients`、控制台测试。
5. 无机器人集成回归：启动 loop、注入 QA/开始导览、发 `arrive`、验证状态文件与日志。
6. 真机验证：nav bridge `28180`、地图加载、点位到达、返航、异常停止恢复。
7. 持续治理日志：保留阶段/耗时/设备/端口/状态/异常链，减少完整文本 payload 与隐私原文落盘。

## 近期工作

2026-07-03（闲聊 RAG）：给 workflow 闲聊(C)路径加入记忆 RAG——`chat_execute` 在调用 VLM 前先 `ctx.memory.query` 检索（neo4j 图谱 + markdown 文档，与导览/找物品同一检索），命中则把参考资料拼入用户输入交给 VLM 生成回答；未命中/异常/`RABBITBOT_CHAT_RAG=0` 时行为与原来完全一致。新增两个可选 env：`RABBITBOT_CHAT_RAG`(默认1)、`RABBITBOT_CHAT_RAG_GROUP`(默认“闲聊检索”，中文名→检索全部记忆)。实时验证：注入“介绍咖啡厅”→答“咖啡厅在二楼东侧”(neo4j)、注入“有免费wifi吗”→答“全区域覆盖免费WiFi”(markdown)，均与非 RAG 的通用回答不同。背景：此前 C/V 路径不查记忆，只有 N/G(导览/找物品)查；markdown 记忆内容自由，故让闲聊也走 RAG。
2026-07-03（内部解耦）：将导览上帝模块 `agno_agents/workflow.py`（3888 行）按关注点纯机械拆为 5 个同目录子模块（config/profiling/text/data/arm 共约 865 行迁出，主文件降至 3184 行），`workflow.py` 重导出全部 80 个符号；不改任何函数体、外部接口、docker 镜像/容器/环境。用「API 快照逐字节对比」（124 公开名 + 147 函数源码哈希零差异）+ 容器 import + 38 项 green 单测验证行为保持。
2026-07-03：拆分 TTS/STT 音频容器；Unitree 本体 TTS 默认改用设备当前音量（空 `RABBITBOT_UNITREE_TTS_VOLUME` 即不下发 `SetVolume(100)`）；STT 默认关闭启动播报（`RABBITBOT_STT_STARTUP_SPEECH=0`）；同步 README 运行架构表为 `rabbitbot-tts`/`rabbitbot-stt`（7 容器）并把项目默认路径统一为 `/mnt/disk1/gt/air_robot_gt_projects`；均通过 `tests.audio`/`tests.clients`（18 tests OK）与 `docker compose config` 验证。

## 注意事项

- `runtime/portable.env`、控制台 venv、模型目录、运行日志、容器卷属本机运行态，不进 Git。
- 修改代码优先遵守现有风格；关键流程/文件读写/网络/数据库/模型/脚本/配置/异常处理补充有诊断价值的 INFO 日志并保留原始异常链。
- 不在报告、日志、提交信息中记录密钥、令牌、完整隐私数据或大体积原始输入输出。

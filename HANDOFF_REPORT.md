# air_robot_gt_projects 项目交接报告

生成时间：2026-07-03 09:35（Asia/Singapore，CST +0800）  
当前主机：`new-orin`  
项目路径：`/mnt/disk1/gt/air_robot_gt_projects`  
当前分支：`refactor/rabbitbot-runtime-structure-stabilization`  
最新提交：`234853d 2026-07-02 22:01:53 +0800 拆分 TTS/STT 音频容器架构`  
本轮范围：按最新交接标准更新顶层 `HANDOFF_REPORT.md`，未修改运行代码。

## 项目整体描述

`air_robot_gt_projects` 是 RabbitBot 在 Orin 设备上的自主运行包，用于把导览 workflow、语音交互、视觉/记忆服务、Unitree 导航桥接和部署脚本组织成一套可迁移运行环境。项目当前同时保留 legacy 路径和 portable 路径；当前默认方向是 portable 解耦多容器栈。

核心功能包括：

- DOCX/JSON 剧本导览 workflow：进入 QA 状态，等待“开始导览”等控制词后按点位讲解、导航、返航。
- 语音链路：TTS 服务监听 `28185`，STT 服务监听 `28184`，当前已拆为独立容器并保留 `/exec` 协议兼容。
- 视觉与语义服务：VLM 服务监听 `8000`，Embedding 服务监听 `8005`。
- 记忆服务：Memory Agent 监听 `28182`，依赖 Neo4j 和 Embedding。
- 导航桥接：`humble_robot_agent_bridge.py` / nav portable 容器提供 `28180`，连接 Unitree 导航、地图和机器人侧 action。
- 控制台：`rabbitbot.control_console` 默认监听 `8080`，用于查看服务状态和发起控制动作。
- 部署交付：支持构建机生成 portable 镜像、全新 Orin 离线导入镜像、宿主初始化、自检、systemd 安装。

## 关键目录结构

- `README.md`：顶层 portable/legacy 部署说明。注意：其中运行架构表仍有旧 `rabbitbot-audio` 描述，当前实际 compose 已拆成 `rabbitbot-tts` 与 `rabbitbot-stt`。
- `HANDOFF_REPORT.md`：顶层交接报告，本文件。
- `deploy/`：宿主初始化、镜像构建/校验/导入导出、模型准备、自检、systemd 安装、portable 基础栈启动脚本。
- `rabbitbot-dev-ros2-master/`：RabbitBot 主项目源码、控制台、workflow、TTS/STT/VLM/Memory 应用、Docker 定义、测试。
- `rabbitbot-dev-ros2-master/docker/portable/`：portable core/nav Dockerfile 与解耦 compose 文件。
- `rabbitbot-dev-ros2-master/scripts_1/`：主循环、控制台、nav bridge、解耦/统一容器入口等现场运行脚本。
- `rabbitbot-dev-ros2-master/scripts/`：各服务独立启动脚本和旧工作流脚本。
- `rabbitbot-dev-ros2-master/rabbitbot/`：Python 包，包含上下文、provider、grounding、控制台、音频兼容层等模块。
- `rabbitbot-dev-ros2-master/tests/`：audio、clients、control_console、guide、memory、tasks、view、vln 等测试。
- `models/`：本机模型缓存，当前存在 Kokoro、Qwen2.5-VL、Qwen3-Embedding、SenseVoice、fsmn_vad。
- `custom_action_ws/`：ROS2 Humble 自定义 action 工作区。
- `unitree_slam_example_new/`：Unitree 导航、地图、手臂/nav bridge 相关源码和脚本。
- `unitree_sdk2/`、`vln/`、`pyorbbecsdk-v2-py310/`：portable 构建或运行所需外部依赖目录。
- `third_party/manifest.lock`：仓库外依赖、镜像和模型来源清单。
- `logs/`：当前运行日志、workflow 控制状态、解耦容器服务日志。

## 主要技术栈与外部依赖

- Python：主项目 `pyproject.toml` 声明 `requires-python >=3.10`，主要依赖包括 `qwen-agent[gui,rag,code_interpreter,mcp]`、`opencv-python-headless`、`PyGObject==3.42.1`、`numpy`、`graphiti-core`。
- Web/API：FastAPI/uvicorn 风格服务入口，TTS/STT/Memory/Robot Agent 均暴露 HTTP 接口。
- 容器：Docker / Docker Compose，host network，NVIDIA runtime，portable core/nav 镜像版本默认 `ghcr.io/aaronai/rabbitbot-*-portable:20260611`。
- 数据库：Neo4j 5.26 community，用于记忆/知识图谱。
- 机器人/导航：ROS2 Humble、Unitree SDK2、自定义 action、PCD 地图。
- 模型：Qwen2.5-VL-7B-Instruct-GPTQ-Int4、Qwen3-Embedding-0.6B、SenseVoiceSmall、fsmn_vad、Kokoro-82M。
- 音频：ALSA 为默认后端；PulseAudio/蓝牙目前只有探测和可选 compose override 入口，未实现完整播放/录音后端。
- 外部服务账号、远端 GitHub 仓库 URL、镜像发布凭据：未确认；本报告不记录任何密钥或令牌。

## 运行入口与核心数据流

### portable 默认基础栈

当前默认基础服务由 `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml` 定义，实际容器为：

- `neo4j`：Neo4j，健康检查依赖 cypher-shell。
- `rabbitbot-vlm`：VLM `8000` + Embedding `8005`。
- `rabbitbot-tts`：TTS `28185`。
- `rabbitbot-stt`：STT `28184`。
- `rabbitbot-memory`：Memory Agent `28182`，依赖 Neo4j 和 Embedding。
- `rabbitbot-workflow`：workflow 专用宿主容器，平时保活，由 loop 通过 `docker exec` 注入导览 workflow。
- `rabbitbot-navbridge`：nav bridge `28180`，在完整 loop 启动时由脚本/compose 管理；本轮只读核查时未运行。

所有服务使用 `network_mode: host`，服务间仍访问 `127.0.0.1:<port>`，以降低旧代码硬编码地址的迁移风险。

### 主循环数据流

1. systemd 或人工执行 `rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`。
2. 脚本读取 `rabbitbot-dev-ros2-master/runtime/portable.env`；不存在时回退 `portable.env.example`，但正式部署应先运行 `deploy/bootstrap_host.sh` 生成本机配置。
3. portable 模式下设置 `RABBITBOT_BASE_RUNTIME=compose`、`RABBITBOT_NAV_RUNTIME=compose`、地图路径、DDS 网卡、VLM/Embedding/STT 开关。
4. `scripts_1/start_nav_bridge_workflow_loop.sh` 准备模型、确保基础服务、启动/复用 nav bridge，再把 workflow 注入 `rabbitbot-workflow` 容器。
5. workflow 默认先进入 QA 状态，TTS 播放提示，STT 监听用户语音；识别到“开始导览”后进入剧本导览，点位到达/返航通过脚本或控制台触发。
6. 控制命令可通过 `scripts_1/send_nav_workflow_command.sh go/back/arrive` 或控制台发出。

## 重要配置文件

- `rabbitbot-dev-ros2-master/runtime/portable.env.example`：可迁移默认模板，进入 Git。
- `rabbitbot-dev-ros2-master/runtime/portable.env`：本机运行态配置，不应进入 Git；当前远端存在。
- `rabbitbot-dev-ros2-master/runtime/rabbitbot-loop.env`：loop 运行环境配置。
- `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml`：当前解耦栈主 compose。
- `rabbitbot-dev-ros2-master/docker/portable/docker-compose.audio-pulse.yaml`：可选 PulseAudio/蓝牙实验覆盖文件，默认不启用。
- `rabbitbot-dev-ros2-master/conf/dialogue_*.json`：导览点位、台词、地图配置。
- `third_party/manifest.lock`：外部依赖、镜像、模型来源与 blocker 清单。
- `.dockerignore`、`.gitignore`：控制 portable 构建上下文和 Git 提交边界。

## 常用命令

以下命令均在 `/mnt/disk1/gt/air_robot_gt_projects` 下执行：

```bash
# 查看 Git 状态
git status --short

# 构建机自检
PORTABLE_CHECK_MODE=builder bash deploy/check_air_project.sh

# 全新 Orin 自检
PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh

# 校验或构建 portable 镜像
MODE=check bash deploy/build_or_pull_images.sh
MODE=build bash deploy/build_or_pull_images.sh

# 启动 portable 基础服务
bash deploy/start_portable_stack.sh

# 启动控制台
sudo systemctl start rabbitbot-control-console.service

# 启动/停止导航主循环
sudo systemctl start rabbitbot-loop.service
sudo systemctl stop rabbitbot-loop.service

# 手工启动主循环入口
bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh

# workflow 控制命令
bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh go
bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh arrive
bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh back

# 运行核心单元测试示例
cd rabbitbot-dev-ros2-master
python3 -m unittest tests.audio.test_device_probe -v
python3 -m unittest tests.clients.test_audio_clients tests.clients.test_runtime_config -v
python3 -m unittest discover tests -v
```

## 当前状态

已确认事实：

- 远端路径 `/mnt/disk1/gt/air_robot_gt_projects` 是 Git 仓库，当前分支为 `refactor/rabbitbot-runtime-structure-stabilization`。
- 本轮开始前 `git status --short` 为空；本轮只计划修改顶层 `HANDOFF_REPORT.md`。
- 当前基础容器状态：`neo4j`、`rabbitbot-vlm`、`rabbitbot-tts`、`rabbitbot-stt`、`rabbitbot-memory` 均运行约 30 分钟且 healthy；`rabbitbot-workflow` 运行约 30 分钟但无健康检查标记。
- `docker compose -f rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml ps` 与 `docker ps` 一致显示基础服务在线。
- 本轮只读核查时没有看到 `rabbitbot-navbridge` 运行；因此不能据此确认 `28180` 当前在线。
- 最新 workflow 状态文件显示 `20260703_092006.status=running`；最新日志显示 workflow 处于 QA 等待语音输入循环，每 30 秒 STT 超时后再次 TTS 提示。
- 当前模型目录存在 `Kokoro-82M`、`Qwen2.5-VL-7B-Instruct-GPTQ-Int4`、`Qwen3-Embedding-0.6B`、`SenseVoiceSmall`、`fsmn_vad`。
- `rabbitbot-dev-ros2-master/tests/` 下存在 audio、clients、control_console、guide、memory、tasks、view、vln 等测试目录。

本轮未执行事项：

- 未启动或停止任何服务。
- 未运行完整自检、单元测试或 docker compose config。
- 未验证真机导航、返航、DOCX 完整导览闭环。
- 未检查远端 Git remote URL 和 CI/CD 配置；相关信息未确认。

## 已知阻塞与风险

- QA/导览链路未稳定闭环：最近日志显示 workflow 长时间停留在 QA 等待语音状态并反复超时提示；上一轮报告中提到的 TTS 播放期间 STT 回声/空输入触发 planner 异常仍应视为未完成风险。
- TTS/STT 互斥或门控未实现：TTS 播放期间 STT 仍可能收听到提示音或环境回声。
- 空输入防护不足：回声过滤或超时后若得到空输入，workflow planner 仍可能进入异常路径。
- PulseAudio/蓝牙音频还不是完整后端：当前只有探测、日志和 compose override 入口。
- 顶层 README 的运行架构表仍描述旧 `rabbitbot-audio` 容器，已与当前 compose 的 `rabbitbot-tts`/`rabbitbot-stt` 拆分不一致，后续应同步 README。
- 当前日志仍会记录完整 TTS 文本和部分 STT/任务 payload。新增设备探测日志较克制，但历史 workflow/TTS 日志治理未完成；后续日志改造应避免记录完整隐私语音文本、密钥、令牌和大体积原始输入输出。
- 真实机器人导航、地图 `/home/unitree/test9.pcd`、DDS 网卡 `eno1`、机器人网络 `192.168.123.222/24` 的现场可用性本轮未验证。

## 日志现状

- 项目已有 shell 彩色日志函数和 Python logging 混用；新增或调整关键流程时应优先沿用当前模块已有日志系统。
- 默认日志级别应保持 INFO 或更高；DEBUG 只应用于短时诊断，并配合限量/轮转/降级机制。
- 关键日志位置：
  - `logs/current_runtime.log`
  - `logs/nav_workflow_control/`
  - `logs/unified_runtime/`
  - `rabbitbot-dev-ros2-master/logs/unified_runtime/`
- 最近日志显示 TTS 请求链路会记录完整提示文本；这对排障有帮助，但不适合长期记录完整用户语音或隐私输入。

## 建议下一步

1. 先治理 QA/导览主链路：实现 TTS 播放期间 STT 暂停、降权或显式门控，避免提示音回收。
2. 给 workflow planner 前增加空输入和无效输入防护：空输入不进入 planner，记录原因并继续监听或返回可诊断状态。
3. 把“开始导览”“返回起点”等控制词放到所有 STT 文本入口的最高优先级，包括主听音、打断监听和 pending 用户输入。
4. 同步更新顶层 `README.md` 的运行架构表，替换旧 `rabbitbot-audio` 为 `rabbitbot-tts` 与 `rabbitbot-stt`。
5. 做一轮轻量验证：`docker compose config`、关键 bash 语法检查、`tests.audio.test_device_probe`、`tests.clients`、控制台测试可用性。
6. 做无机器人集成回归：启动 loop、注入 QA/开始导览、发送 `arrive`、验证状态文件和日志关键字。
7. 最后做真机验证：nav bridge `28180`、地图加载、点位到达、返航、异常停止恢复。
8. 持续治理日志：保留阶段、耗时、设备、端口、状态、异常链等诊断上下文；减少完整文本 payload 和隐私原文落盘。

## 本轮修改记录

- 仅更新顶层 `HANDOFF_REPORT.md`，将报告从上一轮音频拆分专项说明扩展为项目级交接文档。
- 本轮没有修改代码、配置、运行脚本或服务状态。
- 本轮未新增或调整日志点。
- 本轮完成后应提交一次中文 Git commit，提交范围仅包含本文件。

## 注意事项

- `runtime/portable.env`、控制台 venv、模型目录、运行日志和容器卷属于本机运行态，不应直接提交到 Git。
- 修改代码时必须优先遵守项目现有风格；涉及关键流程、文件读写、网络请求、数据库、模型训练/推理、命令行脚本、配置加载、异常处理时，应补充有诊断价值的 INFO 级别日志，并保留原始异常链。
- 不要在报告、日志或提交信息中记录密钥、令牌、完整隐私数据或大体积原始输入输出。
- 远端 README 默认路径仍写 `/mnt/ssd/navgation/projects/air_robot_gt_projects`，当前实际核查路径是 `/mnt/disk1/gt/air_robot_gt_projects`；是否需要统一部署文档路径未确认。

# rabbitbot-dev-ros2-master 交接报告

更新时间：2026-07-16（Asia/Singapore）
所属仓库：`/Users/firmiana/Desktop/RobotAbrainOffline`
子项目目录：`rabbitbot-dev-ros2-master`
本轮主题：自由问答和语音控制必须以“小智”作为句首称呼，默认导览口令改为“小智，开始导览”。

## 项目整体描述

`rabbitbot-dev-ros2-master` 是 RabbitBot 主运行项目，包含导览 workflow、TTS/STT/VLM/Memory HTTP 服务、控制台、部署脚本、portable Docker 配置和测试。它在上层 `air_robot_gt_projects` 仓库中承担机器人导览主业务：从语音或控制台接收指令，加载导览剧本和点位，调用语音播报、导航桥接、视觉/记忆服务与机械臂动作，完成问答、导览、返航和现场控制。

## 核心模块

- `rabbitbot/agno_agents/workflow.py`：导览 workflow 对外主入口；本轮合入后保留兼容入口并重导出拆分模块符号。
- `rabbitbot/agno_agents/workflow_config.py`：workflow 环境变量与开关。
- `rabbitbot/agno_agents/workflow_profiling.py`：插装、耗时统计、退出汇总。
- `rabbitbot/agno_agents/workflow_text.py`：语音文本和控制词解析。
- `rabbitbot/agno_agents/workflow_data.py`：DOCX/JSON 台词、实体、点位数据加载。
- `rabbitbot/agno_agents/workflow_arm.py`：机械臂动作与播报并发辅助。
- `rabbitbot/guide/`：导览控制、对话和路由纯逻辑。
- `rabbitbot/audio/`：音频设备探测、Unitree G1 TTS 后端和音量策略。
- `rabbitbot/clients/audio.py`：STT/TTS `/exec` HTTP 客户端。
- `rabbitbot/runtime/config.py`：运行配置读取与非法配置回退。
- `rabbitbot/control_console/`：控制台命令、状态、配置和 API。
- `docker/portable/`：portable compose 和镜像定义。
- `scripts/`、`scripts_1/`：单服务、解耦容器、统一容器和 workflow loop 启动脚本。
- `tests/`：audio、clients、control_console、guide 等测试。

## 技术栈与依赖

- Python `>=3.10`，包配置在 `pyproject.toml`。
- 主要依赖：`qwen-agent[gui,rag,code_interpreter,mcp]`、`opencv-python-headless`、`PyGObject==3.42.1`、`numpy`、`graphiti-core`。
- 测试依赖在 `project.optional-dependencies.test`：`pytest`、`fastapi`、`httpx`、`requests`。
- 服务协议：多个 FastAPI/HTTP 服务通过 `/exec` 交互。
- 容器：Docker Compose、host network、NVIDIA runtime。
- 外部服务：Neo4j、VLM、Embedding、Memory Agent、Unitree/ROS2 导航桥接。

## 运行入口

- 基础栈：上层目录执行 `bash deploy/start_portable_stack.sh`。
- 主循环：上层目录执行 `bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`。
- workflow 控制：`bash scripts_1/send_nav_workflow_command.sh go|arrive|back`。
- STT/TTS 单服务：`bash scripts/start_stt_funasr_app.bash`、`bash scripts/start_tts_app.bash`。
- 解耦角色容器入口：`scripts_1/unified_runtime/start_role_container.sh`。
- 统一容器入口：`scripts_1/unified_runtime/start_unified_container.sh`。

## 关键配置

- `runtime/portable.env.example`：portable 环境模板。
- `runtime/portable.env`：本机运行态配置，通常不提交；当前工作区有效性未确认。
- `docker/portable/docker-compose.decoupled.yaml`：解耦栈主 compose。
- `docker/portable/docker-compose.audio-pulse.yaml`：PulseAudio 可选覆盖。
- `conf/`：导览对话、点位和地图配置。
- `pyproject.toml`：包依赖和测试依赖入口。

## 核心数据流

1. 启动脚本读取 runtime 配置并拉起解耦服务。
2. TTS、STT、VLM/Embedding、Memory、Neo4j、workflow/navbridge 在 host network 下通过本机端口通信。
3. workflow 等待 STT 文本或控制命令，根据导览、闲聊、找物品、返航等路径分发。
4. 导览路径加载剧本和点位，调用 TTS 播报、导航桥接移动、机械臂动作，并写入状态和日志。
5. 闲聊路径可先检索 Memory RAG，再把参考资料交给 VLM/LLM 生成回答。

## 本轮状态

- 自由问答、连续追问、导览开场/途中提问和语音控制已增加“小智”称呼门控；剧本主动提问后的回答保持原逻辑。
- 默认导览注入口令和待命提示已同步更新；现场 `portable.env` 未覆盖相关默认值。
- 已随上层仓库合并 `refactor/service-internal-decoupling` 到 `master`。
- 合并无冲突，保留非快进合并提交，便于提交信息详细说明改动项。
- 子项目历史交接报告原有 2178 行，已压缩到 150 行以内。
- 本轮没有运行 Docker、机器人、音频设备或完整 pytest。

## 本轮主要改动

- `rabbitbot/guide/controls.py` 新增句首唤醒词校验和称呼剥离，支持 `RABBITBOT_GUIDE_WAKE_WORDS` 自定义称呼。
- `rabbitbot/agno_agents/workflow.py` 忽略未称呼“小智”的自由输入，命中后只将称呼后的请求交给模型；`scripts_1/start_nav_bridge_workflow_loop.sh` 默认注入“小智, 开始导览”。
- 拆分 `workflow.py` 上帝模块，降低单文件复杂度并保持外部入口兼容。
- 新增 `rabbitbot/guide` 纯逻辑模块和测试，覆盖导览控制、对话和路由。
- TTS/STT 从共享 `rabbitbot-audio` 容器拆成 `rabbitbot-tts` 与 `rabbitbot-stt`。
- 新增音频设备探测和 Unitree TTS 音量策略测试。
- 新增音频客户端，统一 HTTP 超时、异常、状态码、JSON 解析和缺字段处理。
- 新增 runtime 配置工具，集中处理 URL 和浮点配置回退。
- 控制台容器映射适配 TTS/STT 独立容器，并保留旧 `audio` 分组兼容。
- 更新 compose、env 示例、启动脚本和 unified role 入口。
- 扩展 `pyproject.toml` 测试可选依赖。

## 日志新增或调整

- 唤醒词匹配使用 INFO，记录称呼、文本长度、请求长度和匹配结果，不记录完整用户语音文本。
- 音频客户端初始化使用 INFO，网络超时、请求失败、异常状态、响应解析失败和缺字段使用 WARNING。
- runtime 配置读取对空 URL、非法浮点配置使用 WARNING 并记录变量名、回退值等必要上下文。
- 音频设备探测、TTS/STT 启动脚本和容器角色入口增加后端、设备、音量策略、启动参数等诊断信息。
- 日志不应记录密钥、令牌、完整隐私数据或大体积原始输入输出。

## 已验证事实

- 唤醒词新增用例 7/7、`tests/guide` 全量 `unittest` 23/23 通过；变更 Python 文件通过 `py_compile`，workflow loop 通过 `bash -n`。
- 合并前 `git merge-tree --write-tree master refactor/service-internal-decoupling` 通过。
- 合并前 `git diff --check master..refactor/service-internal-decoupling` 无空白错误。
- 合并阶段 `git merge --no-ff --no-commit refactor/service-internal-decoupling` 无冲突。
- `python3 -m py_compile` 覆盖变更 Python 文件，通过。
- `bash -n` 覆盖变更 shell 脚本，通过。
- `python` 命令不可用；`python3 -m pytest ...` 因缺少 `pytest` 未执行。

## 阻塞与风险

- 尚未用现场麦克风和真实 STT 验证“小智”识别及完整问答/导览触发链路。
- 需要在安装测试依赖的环境运行完整 pytest。
- 需要在目标机器验证 Docker Compose、GPU、模型缓存、Neo4j、TTS/STT、Memory、VLM/Embedding。
- 真机导航、地图、DDS 网卡、Unitree 网络和完整导览闭环未在本轮验证。
- PulseAudio/蓝牙为实验入口，完整后端能力未确认。

## 下一步

1. 安装测试依赖后运行 `python3 -m pytest tests/audio tests/clients tests/control_console tests/guide`。
2. 运行 `docker compose config` 并启动 portable 基础栈做健康检查。
3. 验证控制台“开始/关闭程序”、服务状态和容器映射。
4. 在无机器人模式验证 workflow 控制命令，在真机环境验证导航、返航和 TTS/STT 互斥。
5. 持续治理关键日志，保留诊断上下文和异常链，避免隐私与大体积 payload 落盘。

## 注意事项

- 遵守项目现有代码风格。
- 关键流程、网络请求、配置加载、命令脚本和异常处理应补充有诊断价值的 INFO/WARNING 日志。
- DEBUG/TRACE 只能短时诊断，并需采样、限时、限量、轮转或降级。
- 不提交本机运行态配置、密钥、令牌、模型缓存或运行日志。

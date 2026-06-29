# air_robot_gt_projects 交接报告

## 背景和目标

本项目是 RabbitBot 自主运行包，当前工作目录为 `/mnt/disk1/gt/air_robot_gt_projects`，主代码目录为 `rabbitbot-dev-ros2-master`，当前分支为 `feature/qa-vlm-workflow`。近期目标是在 ShuHao-orin 上收敛控制台、`rabbitbot-loop.service`、QA/导览 workflow、语音口令、返航、无机器人模式和运行状态可观测性。

本轮目标是按 Aaron 要求通过 SSH 阅读本交接报告和项目本身，核对项目结构、近期改动、运行入口、服务状态和当前风险；本轮不做业务代码修改，不主动重启服务或容器。

## 当前状态

已完成：

- `rabbitbot-loop.service` 默认进入 QA 状态，听到“开始导览”或收到前端 `go` 后才开始剧本导览。
- 导览期间保持 STT 监听，真实提问会暂停当前导览和正在播报的 TTS，回答后回到原导览步骤。
- 前端“导览”按钮发送 `go`，loop 在语音启动模式下向 STT `/exec` 注入“开始导览”。
- 前端“返航”按钮发送 `back`，loop 在语音启动模式下向 STT `/exec` 注入“返回起点”；导览完成后按 `back_points` 返回，没有 `back_points` 时按导览点位逆序返回。
- 前端已支持“开始程序(无机器人模式)”和“到达下一个点位(无机器人模式)”；中文称呼统一为“无机器人模式”，旧变量 `RABBITBOT_WORKFLOW_NON_INTEGRATION` 保留兼容。
- 前端“当前运行日志”会优先显示当前 workflow 日志；workflow 尚未创建时只显示本次 loop 启动生成的 `logs/current_runtime.log`，不再回退历史 journal。
- 前端“服务状态”面板位于“导览讲解词”上方，显示 Neo4j、TTS、STT、Memory、VLM、Embedding 的在线状态。
- loop QA 默认启用 VLM 和 Embedding；TTS 内置声卡回退默认允许，指定 `TTS_DEVICE_NAME=bt67` 不存在时会继续尝试内置声卡回退。
- 无机器人模式下手臂动作会在 `RobotAgent._post_arm_action()` 入口短路跳过，不再向未启动的 28180 机器人 Agent 发送请求并等待超时。
- `get_inst_chat` 已替换为精简现场对话提示词，避免聊天路径出现无端道歉或冗长铺陈。
- 控制台操作区按钮顺序已调整为：返航、刷新状态、开始程序、一键重启、关闭程序、开始程序(无机器人模式)、到达下一个点位(无机器人模式)。
- 本轮已通过 SSH 阅读交接报告、README、主项目 README、`pyproject.toml`、控制台 README、关键启动脚本、关键 Python 代码片段和项目文件结构。

未完成：

- 本轮未做机器人实机导航、返航、语音拾音、TTS 播报或动作验证。
- 本轮未读取 `runtime/portable.env` 或 `runtime/rabbitbot-loop.env` 内容；这些是现场运行配置，可能包含敏感或机器特定信息。
- 本轮未运行完整测试套件；只对关键 Python 文件执行了基础语法编译检查。
- 控制台 README 中仍提到 `scripts_1/systemd/...` 路径，但当前文件树未发现该目录，疑似文档滞后，尚未修正。

## 已验证的事实

- 当前 Git 根目录为 `/mnt/disk1/gt/air_robot_gt_projects`，分支为 `feature/qa-vlm-workflow`。
- 本轮阅读开始时工作区没有已跟踪文件改动；最新提交为 `080a224 调整控制台按钮顺序：无机器人模式按钮移到最后`。
- 根目录 README 说明项目包含 portable 和 legacy 两条运行路径；portable 路径通过自包含 core/nav 镜像离线交付。
- 主项目 Python 包名为 `rabbitbot`，`pyproject.toml` 要求 Python `>=3.10`，主要依赖包括 `qwen-agent[gui,rag,code_interpreter,mcp]`、`opencv-python-headless`、`PyGObject == 3.42.1`、`numpy`、`graphiti-core`。
- 主代码目录包括 `rabbitbot/agno_agents`、`rabbitbot/control_console`、`rabbitbot/audio`、`rabbitbot/memory`、`rabbitbot/robots`、`rabbitbot/tools`、`scripts_1`、`scripts`、`tests`、`docs`。
- `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 当前均为 active。
- 相关容器当前包括 `rabbitbot-portable-rabbitbot-nav-1` 和 `rabbitbot-unified-runtime`，二者均在运行。
- `python3 -m py_compile rabbitbot/control_console/app.py rabbitbot/control_console/status.py rabbitbot/provider.py rabbitbot/agno_agents/prompts.py` 通过。
- `rabbitbot/control_console/status.py` 将 Neo4j(7687)、TTS(28185)、STT(28184)、Memory(28182)、VLM(8000)、Embedding(8005) 都标记为必需服务。
- 远端未安装 `rg`，本轮用 `find`/`grep` 作为替代方式梳理文件和代码位置。
- 直接运行 `python3 -m pytest` 曾受远端 anyio/pytest 插件版本冲突影响；需要设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。

## 阻塞问题

- 现场实机链路仍依赖 `eno1`、机器人网络、Unitree DDS、导航核心、TTS/STT 设备和容器服务状态。
- 当前主要风险仍是 TTS 28185 在指定设备缺失并回退内置声卡后，现场实际声音是否从可听设备输出。
- 如果 Embedding 模型目录缺失或显存/端口资源不足，下一次启动会在 Embedding 8005 等待阶段暴露问题；可临时显式设置 `RABBITBOT_UNIFIED_START_EMBEDDING=0` 或 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING=0` 跳过。
- 如果 `rabbitbot-control-console.service` 运行用户没有写 `runtime/rabbitbot-loop.env` 的权限，前端启动模式写入会失败；需查看控制台服务日志确认权限。
- 控制台 README 中 systemd/sudoers 路径说明可能与当前文件树不一致，需要后续核实真实部署来源。

## 建议的下一步

- 从前端点击“开始程序(无机器人模式)”，确认“当前运行日志”显示本次 loop 启动日志，并确认 unified 基础服务启动到 Neo4j/TTS/STT/Memory/VLM/Embedding 的状态。
- 待 TTS/STT/Memory/VLM/Embedding 就绪后，在 QA 状态点击“导览”，确认效果等同于说“开始导览”。
- 无机器人模式下，每到一个剧本导航点时点击“到达下一个点位(无机器人模式)”，确认 workflow 日志出现等待和确认到达记录，并确认手臂动作不会再卡 28180 超时。
- 现场实机模式下验证返航、语音打断恢复、TTS 实际播报设备和机器人动作链路。
- 后续维护时优先修正控制台 README 中疑似过期的 `scripts_1/systemd/...` 路径说明。
- 若要临时降低启动成本，可在运行环境中显式设置 `RABBITBOT_UNIFIED_START_EMBEDDING=0` 或 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING=0`。

## 注意事项

- `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING` 是 loop 场景的默认开关，默认 `1`；`RABBITBOT_UNIFIED_START_EMBEDDING` 仍可直接覆盖最终传入容器的值。
- `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 是明确无机器人模式开关；`RABBITBOT_WORKFLOW_NON_INTEGRATION` 仍保留为兼容变量名。
- “到达下一个点位(无机器人模式)”按钮发送 `arrive`，只在无机器人模式下生效；真实机器人模式下 loop 会记录 warning 并忽略。
- “当前运行日志”默认请求 `/api/logs?target=runtime&lines=220`，打开后每 500ms 独立刷新；`target=workflow` 严格按当前 `run_id` 读取，不回退旧日志。
- 服务状态面板是短超时端口探测，不等同于 systemd 或 Docker 状态；Neo4j 7687 在线通常表示 `rabbitbot-unified-runtime` 容器仍在提供数据库。
- 本轮没有读取现场 env 文件内容，避免在交接报告或对话中泄露机器特定配置或潜在敏感信息。

## 本轮修改详情：阅读交接报告和项目现状

### 背景和目标

Aaron 要求 SSH 到 ShuHao-orin，阅读 `/mnt/disk1/gt/air_robot_gt_projects/HANDOFF_REPORT.md` 和项目本身。目标是形成当前可接手认知，并按工作规范更新交接报告。

### 已完成内容

- 已完整阅读根目录 `HANDOFF_REPORT.md`，并将超过 200 行的旧交接内容压缩为当前摘要、最近历史摘要和关键注意事项。
- 已阅读根目录 README、主项目 README、`pyproject.toml`、控制台 README、`scripts_1/start_loop_entry.sh`、`scripts_1/start_nav_bridge_workflow_loop.sh` 的关键入口说明。
- 已核对 `rabbitbot/provider.py` 中无机器人模式手臂动作短路、`rabbitbot/agno_agents/prompts.py` 中 `get_inst_chat` 精简提示词、`rabbitbot/control_console/app.py` 中按钮顺序和日志接口、`rabbitbot/control_console/status.py` 中必需服务列表。
- 已查看项目目录结构、关键源码/脚本/测试/文档文件清单、Git 分支和近期提交。
- 已确认当前两个 systemd 服务和两个相关容器处于运行状态。

### 已验证的事实

- 关键 Python 文件语法编译通过。
- 本轮开始时 Git 已跟踪文件干净；本轮只修改本交接报告。
- 远端缺少 `rg`，项目梳理使用 `find` 和 `grep` 完成。
- 现场 env 文件被视为敏感运行配置，本轮未读取其内容。

### 未完成 / 注意事项

- 未运行完整 pytest；如需运行控制台测试，沿用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/control_console/`。
- 未触发任何服务重启、容器重启或机器人运动。
- 控制台 README 的 systemd/sudoers 路径说明需要后续核实和修正。

### 新增或调整日志点

- 本轮为只读核查和交接报告整理，不涉及执行流程、外部依赖调用、文件读写业务逻辑或高频路径，未新增或调整代码日志点。

## 最近历史摘要

- `080a224 调整控制台按钮顺序：无机器人模式按钮移到最后`：前端操作区按钮调整为常规操作在前、两个无机器人按钮在最后，并重启相关服务/容器使前序改动生效。
- `6cd1543 将 get_inst_chat 替换为精简现场对话提示词`：聊天路径改为短答、直接、无画面规则，避免旧提示词导致无端道歉和冗长回复；不再输出动作标记。
- `74ed6bf 无机器人模式下跳过手臂动作并不再等待回执`：无机器人模式下 `do_arm_async` 等手臂动作在 provider 入口短路，避免因 28180 未启动导致台词推进卡住。
- `4b1867d 允许指定 TTS 设备缺失时回退内置声卡`：`TTS_DEVICE_NAME=bt67` 等指定设备不存在时，若允许内置回退则继续尝试 Orin/HDMI/APE 等候选设备。
- `8347c20 限制当前运行日志为本次运行`：loop 启动截断写入 `logs/current_runtime.log`，控制台 runtime 日志不再回退历史 journal，并提高日志刷新频率。
- `ced6f9a 默认允许 TTS 内置声卡回退`：unified/workflow/TTS 脚本默认开启 `RABBITBOT_TTS_ALLOW_BUILTIN=1`，失败提示同步更新。
- `37e8e8c 默认启用 Embedding 服务`：loop QA、unified 和 VLM QA 路径默认启用 Embedding，并在关键启动日志中输出开关。
- `073c7a3 默认启用 loop QA 所需 VLM`：loop QA 默认启用 VLM，服务状态面板将 VLM 标为必需。
- 更早工作已压缩：`back` 注入“返回起点”、`go` 注入“开始导览”、默认 QA 与语音打断恢复、portable core/nav 镜像、自包含部署、STT/TTS 音频链路和 systemd/sudoers 治理。

## 其它信息

- 本轮未启动或停止任何现场服务，未触发机器人运动。
- 生成时间：2026-06-29

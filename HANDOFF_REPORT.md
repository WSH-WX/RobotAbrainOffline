# air_robot_gt_projects 交接报告

## 背景和目标

本项目是 RabbitBot 自主运行包，当前工作目录为 `/mnt/disk1/gt/air_robot_gt_projects`，主代码仓库为 `rabbitbot-dev-ros2-master`，当前分支为 `feature/qa-vlm-workflow`。近期目标集中在 ShuHao-orin 上收敛控制台、`rabbitbot-loop.service`、QA/导览 workflow、语音口令、返航和无机器人模式的现场可用性。

## 当前状态

已完成：

- `rabbitbot-loop.service` 默认进入 QA 状态，听到“开始导览”或收到前端 `go` 后才开始剧本导览。
- 导览期间保持 STT 监听，真实提问会暂停当前导览和正在播报的 TTS，回答后回到原导览步骤。
- 前端“导览”按钮发送 `go`，loop 在语音启动模式下转换为向 STT `/exec` 注入“开始导览”。
- 前端“返航”按钮发送 `back`，loop 在语音启动模式下转换为向 STT `/exec` 注入“返回起点”。导览完成后按 `back_points` 返回；没有 `back_points` 时按导览点位逆序返回。
- 本轮新增前端“开始程序(无机器人模式)”和“到达下一个点位(无机器人模式)”按钮。
- 本轮将项目中文称呼从“非联调模式”统一为“无机器人模式”；旧环境变量 `RABBITBOT_WORKFLOW_NON_INTEGRATION` 保留为兼容实现名。
- 前端“当前 Workflow 最近日志”已改为读取当前 workflow `run_id` 对应日志，而不是固定显示导航桥接日志。
- 本轮新增前端“服务状态”面板，位于“导览讲解词”面板上方，显示 Neo4j、TTS、STT、Memory、VLM、Embedding 的在线状态。

未完成：

- 本轮未重启 `rabbitbot-loop.service`，未点击前端按钮做现场验证。
- 本轮未做机器人实机导航、返航、语音拾音、TTS 播报或动作验证。
- 无机器人模式下的完整 QA/导览体验仍需现场启动服务后走一轮。

## 已验证的事实

- 当前主仓库分支为 `feature/qa-vlm-workflow`。
- 已通过 Python 语法检查：`rabbitbot/control_console/app.py`、`commands.py`、`status.py`、`rabbitbot/agno_agents/workflow.py`。
- 已通过 shell 语法检查：`scripts_1/start_nav_bridge_workflow_loop.sh`、`send_nav_workflow_command.sh`、`start_loop_entry.sh`、`start_unified_integration_workflow.sh`、`start_unified_non_integration_workflow.sh`、`stop_unified_workflow.sh`。
- 已通过控制台目标测试：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/control_console/test_commands.py tests/control_console/test_app.py`，结果为 `47 passed`。
- 直接运行 `python3 -m pytest` 会受远端 anyio/pytest 插件版本冲突影响，需设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。
- `rabbitbot-loop.service` 的 systemd unit 会读取 `runtime/rabbitbot-loop.env` 和 `runtime/portable.env`。
- `runtime/rabbitbot-loop.env` 可由控制台写入 `NAV_PCD_PATH`、`RABBITBOT_NAV_WORKFLOW_NO_ROBOT`、`RABBITBOT_WORKFLOW_NON_INTEGRATION`。
- 无机器人模式下 loop 会跳过导航桥接启动和导航桥接健康检查，但仍启动 unified 基础服务、STT、TTS、Memory、Neo4j 和 workflow。
- workflow 手动到达确认优先等待 `RABBITBOT_WORKFLOW_MANUAL_ARRIVAL_FILE`；前端 `arrive` 命令会写该文件推进当前点位。

## 阻塞问题

- 现场实机链路仍依赖 `eno1`、机器人网络、Unitree DDS、导航核心、TTS/STT 设备和容器服务状态。
- 如果 `rabbitbot-control-console.service` 运行用户没有写 `runtime/rabbitbot-loop.env` 的权限，前端启动模式写入会失败；需查看控制台服务日志确认权限。
- 如果无机器人模式下 TTS 后端仍配置为机器人本体 TTS，离线无机器人环境可能无法听到播报；需按现场音频条件确认 `runtime/portable.env` 的 TTS 后端。

## 建议的下一步

- 从前端点击“开始程序(无机器人模式)”，确认状态显示“无机器人模式就绪”。
- 在 QA 状态点击“导览”，确认效果等同于说“开始导览”。
- 每到一个剧本导航点时点击“到达下一个点位(无机器人模式)”，确认 workflow 日志出现等待和确认到达记录，并继续下一段台词。
- 打开“当前 Workflow 最近日志”，确认显示的是 `logs/nav_workflow_control/rabbitbot_workflow_<run_id>.log`。
- 查看“服务状态”面板，确认 TTS(28185)、STT(28184)、Memory(28182)、Neo4j(7687) 与实际服务状态一致。
- 若要切回真实机器人模式，点击“开始程序”或“一键重启”，确认 `runtime/rabbitbot-loop.env` 中 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT="0"`。

## 注意事项

- `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 是本轮新增的明确无机器人模式开关。
- `RABBITBOT_WORKFLOW_NON_INTEGRATION` 仍保留，原因是代码和历史脚本已有该变量；中文说明统一改为“无机器人模式”。
- 无机器人模式只替代真实导航到点确认，不代表禁用 QA、STT、TTS、Memory 或剧本逻辑。
- “到达下一个点位(无机器人模式)”按钮发送 `arrive`，只在无机器人模式下生效；真实机器人模式下 loop 会记录 warning 并忽略。
- “最近日志”文字已改为“当前 Workflow 最近日志”，默认请求 `/api/logs?target=workflow&lines=160`。
- “服务状态”面板使用 `/api/status` 返回的 `services` 字段；VLM 和 Embedding 标记为可选服务，离线时不代表导览主流程必然不可用。

## 本轮修改详情：控制台无机器人模式和当前 workflow 日志

### 背景和目标

Aaron 说明之前项目中的“非联调模式”指无机器人导航、剧本走到导航点时按回车视为到达；现在统一称为“无机器人模式”。本轮目标是在前端增加无机器人模式启动和到达按钮，并修正“最近日志”显示的不是当前 workflow 日志的问题。

### 已完成内容

- 修改 `rabbitbot/control_console/app.py`：新增“开始程序(无机器人模式)”按钮，调用 `/api/start-no-robot`；新增“到达下一个点位(无机器人模式)”按钮，发送 `arrive` 命令；状态就绪判断在无机器人模式下不再要求导航桥接 ready；日志面板改为当前 workflow 日志。
- 修改 `rabbitbot/control_console/commands.py`：`ALLOWED_COMMANDS` 新增 `arrive`；新增运行环境文件读写函数，能保留地图配置并写入无机器人模式开关；无机器人启动使用 `systemctl restart rabbitbot-loop.service` 以确保 env 生效。
- 修改 `rabbitbot/control_console/status.py`：新增 `workflow_log_for_status()`，优先按当前 workflow `run_id` 找 `rabbitbot_workflow_<run_id>.log`，找不到才回退最新日志。
- 修改 `scripts_1/send_nav_workflow_command.sh`：支持 `arrive` 命令。
- 修改 `scripts_1/start_loop_entry.sh`：识别 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1`，进入无机器人模式时关闭真实 Robot Agent。
- 修改 `scripts_1/start_nav_bridge_workflow_loop.sh`：新增 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT`；无机器人模式跳过导航桥接启动、导航健康检查和真实返航导航；每轮 workflow 生成 `.arrive` 控制文件路径；收到 `arrive` 后写入该文件。
- 修改 `rabbitbot/agno_agents/workflow.py`：手动导航确认优先等待 `RABBITBOT_WORKFLOW_MANUAL_ARRIVAL_FILE`，收到文件后视为到达并记录耗时；终端按键兜底文案改为“无机器人模式”。
- 修改 `scripts_1/start_unified_integration_workflow.sh`、`scripts_1/start_unified_non_integration_workflow.sh`、`scripts_1/stop_unified_workflow.sh` 和 `docs/DOCX严格剧本workflow逻辑.md`：中文称呼改为“无机器人模式”。
- 修改控制台测试，覆盖 `arrive` 命令、无机器人启动、环境文件保留、当前 workflow 日志按 run_id 读取。

### 新增或调整日志点

- 控制台后端写入启动模式时记录 `env_file`、`no_robot_mode` 和手动确认开关，便于排查前端启动后模式未生效的问题。
- loop 启动和恢复阶段记录无机器人模式已启用、跳过真实导航桥接、跳过导航桥接恢复和跳过真实返航导航。
- loop 收到 `arrive` 时记录 `run_id` 与到达确认文件路径，便于确认前端按钮是否送达当前 workflow。
- workflow 等待到达确认时记录点位名、确认文件路径、清理旧文件失败、删除确认文件失败和确认耗时，便于排查剧本卡在某个导航点。
- 当前 workflow 日志选择按 `run_id` 命中或回退最新日志时使用 DEBUG 记录，便于排查页面日志来源。


## 本轮修改详情：控制台服务状态面板

### 背景和目标

Aaron 要求在前端增加“服务状态面板”，显示 TTS、STT、Memory 等服务是否在线，并放在“导览讲解词”面板上方。

### 已完成内容

- 修改 `rabbitbot/control_console/status.py`：新增 `ServiceStatus` 和 `get_runtime_service_statuses()`，短超时探测 Neo4j(7687)、TTS(28185)、STT(28184)、Memory(28182)、VLM(8000)、Embedding(8005)。
- 修改 `rabbitbot/control_console/app.py`：`/api/status` 新增 `services` 字段；前端新增“服务状态”面板，按在线/离线/可选离线显示服务卡片，并放在“导览讲解词”面板上方。
- 修改 `tests/control_console/test_app.py`：覆盖状态接口返回服务列表，以及页面包含服务状态面板且位置在导览讲解词之前。

### 新增或调整日志点

- `get_runtime_service_statuses()` 使用 DEBUG 记录服务探测摘要 `online/total`，默认 INFO 下不刷屏；用于需要排查控制台状态轮询时确认后端是否完成服务探测。

## 最近历史摘要

- `beb15ef 将 back 命令映射为返回起点口令`：前端返航按钮发送 `back` 后由 loop 注入“返回起点”，workflow 在导览完成后写返航请求文件，loop 按 `back_points` 或导览点逆序返航。
- `aedb292 将 go 命令映射为开始导览口令`：前端导览按钮发送 `go` 后由 loop 注入“开始导览”，避免绕过 QA 状态。
- `2010c40 支持导览默认 QA 与语音打断恢复`：启动后默认 QA，听到开始导览后推进剧本，导览中支持提问打断和恢复。
- `294ad4e 记录 ShuHao-orin 项目只读核查`：只读确认项目目录、分支、配置、容器/端口和 `eno1` 状态。
- 更早工作已压缩：portable core/nav 镜像、自包含部署、VLM QA、STT/TTS 音频链路、TTS auto 健康检查、systemd/sudoers 和模型目录治理。

## 其它信息

- 本轮未启动或停止任何现场服务，未触发机器人运动。
- 生成时间：2026-06-29

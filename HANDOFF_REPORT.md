# air_robot_gt_projects 交接报告

## 背景和目标

本项目是 RabbitBot 自主运行包，当前工作目录为 `/mnt/disk1/gt/air_robot_gt_projects`，主代码目录为 `rabbitbot-dev-ros2-master`，当前分支为 `feature/qa-vlm-workflow`。近期目标是在 ShuHao-orin 上收敛控制台、`rabbitbot-loop.service`、QA/导览 workflow、语音口令、返航、无机器人模式和运行状态可观测性。

## 当前状态

已完成：

- `rabbitbot-loop.service` 默认进入 QA 状态，听到“开始导览”或收到前端 `go` 后才开始剧本导览。
- 导览期间保持 STT 监听，真实提问会暂停当前导览和正在播报的 TTS，回答后回到原导览步骤。
- 前端“导览”按钮发送 `go`，loop 在语音启动模式下向 STT `/exec` 注入“开始导览”。
- 前端“返航”按钮发送 `back`，loop 在语音启动模式下向 STT `/exec` 注入“返回起点”；导览完成后按 `back_points` 返回，没有 `back_points` 时按导览点位逆序返回。
- 前端已支持“开始程序(无机器人模式)”和“到达下一个点位(无机器人模式)”；中文称呼统一为“无机器人模式”，旧变量 `RABBITBOT_WORKFLOW_NON_INTEGRATION` 保留兼容。
- 前端“当前运行日志”会优先显示当前 workflow 日志；workflow 尚未创建时只显示本次 loop 启动生成的 `logs/current_runtime.log`，不再回退历史 journal。
- 前端“服务状态”面板位于“导览讲解词”上方，显示 Neo4j、TTS、STT、Memory、VLM、Embedding 的在线状态。
- loop QA 默认启用 VLM 和 Embedding；本轮进一步把 TTS 内置声卡回退默认设为允许，确保没有外接声卡时 TTS 也能尽量启动。

未完成：

- 本轮未重启 `rabbitbot-loop.service`、未重启控制台、未停止或重建 `rabbitbot-unified-runtime`，以避免影响当前服务状态。
- 本轮未做机器人实机导航、返航、语音拾音、TTS 播报或动作验证。
- 本轮将 TTS 内置声卡回退默认打开，并修复指定 `TTS_DEVICE_NAME=bt67` 不存在时未继续回退内置声卡的问题；已按要求重启相关容器/服务。

## 已验证的事实

- 当前 Git 根目录为 `/mnt/disk1/gt/air_robot_gt_projects`，分支为 `feature/qa-vlm-workflow`。
- `rabbitbot-loop.service` 的 systemd unit 会读取 `runtime/rabbitbot-loop.env` 和 `runtime/portable.env`。
- `runtime/rabbitbot-loop.env` 可由控制台写入 `NAV_PCD_PATH`、`RABBITBOT_NAV_WORKFLOW_NO_ROBOT`、`RABBITBOT_WORKFLOW_NON_INTEGRATION`。
- 无机器人模式下 loop 会跳过导航桥接启动和导航桥接健康检查，但仍启动 unified 基础服务、STT、TTS、Memory、Neo4j、VLM、Embedding 和 workflow。
- workflow 手动到达确认优先等待 `RABBITBOT_WORKFLOW_MANUAL_ARRIVAL_FILE`；前端 `arrive` 命令会写该文件推进当前点位。
- Neo4j 在线不代表 loop 正在运行；它由 `rabbitbot-unified-runtime` 容器提供，停止 `rabbitbot-loop.service` 不会自动停止该容器。
- 最近现场日志显示 loop 卡在等待 TTS 28185：出现过 `TTS /exec 服务 (28185) 启动超时 (420 秒)`，提示可设置 `RABBITBOT_TTS_ALLOW_BUILTIN=1`。
- 直接运行 `python3 -m pytest` 会受远端 anyio/pytest 插件版本冲突影响，需设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。
- 本轮验证已通过：shell 语法检查、`rabbitbot/control_console/status.py` 语法检查、控制台目标测试 `51 passed`、`git diff --check`。

## 阻塞问题

- 现场实机链路仍依赖 `eno1`、机器人网络、Unitree DDS、导航核心、TTS/STT 设备和容器服务状态。
- 当前主要风险是 TTS 28185 是否能在内置声卡回退打开后正常启动；workflow 创建前会等待 unified 基础服务就绪。
- 如果 Embedding 模型目录缺失或显存/端口资源不足，下一次启动会在 Embedding 8005 等待阶段暴露问题；可临时显式设置 `RABBITBOT_UNIFIED_START_EMBEDDING=0` 或 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING=0` 跳过。
- 如果 `rabbitbot-control-console.service` 运行用户没有写 `runtime/rabbitbot-loop.env` 的权限，前端启动模式写入会失败；需查看控制台服务日志确认权限。

## 建议的下一步

- 重启后优先查看服务状态面板和 `logs/unified_runtime/rabbitbot_tts.log`，确认 TTS 28185 是否已就绪，以及实际选中的音频输出设备。
- 从前端点击“开始程序(无机器人模式)”，确认“当前运行日志”显示 unified 基础服务启动过程，并确认日志中出现 `embedding=1`。
- 待 TTS/STT/Memory/VLM/Embedding 就绪后，在 QA 状态点击“导览”，确认效果等同于说“开始导览”。
- 无机器人模式下，每到一个剧本导航点时点击“到达下一个点位(无机器人模式)”，确认 workflow 日志出现等待和确认到达记录。
- 若要临时降低启动成本，可在运行环境中显式设置 `RABBITBOT_UNIFIED_START_EMBEDDING=0` 或 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING=0`。

## 注意事项

- 本轮会按 Aaron 要求重启相关容器/服务；如 TTS 使用内置声卡回退启动成功，现场仍需确认实际播报声音是否从可听设备输出。
- `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING` 是 loop 场景的默认开关，默认 `1`；`RABBITBOT_UNIFIED_START_EMBEDDING` 仍可直接覆盖最终传入容器的值。
- `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 是明确无机器人模式开关；`RABBITBOT_WORKFLOW_NON_INTEGRATION` 仍保留为兼容变量名。
- “到达下一个点位(无机器人模式)”按钮发送 `arrive`，只在无机器人模式下生效；真实机器人模式下 loop 会记录 warning 并忽略。
- “当前运行日志”默认请求 `/api/logs?target=runtime&lines=220`，打开后每 500ms 独立刷新；`target=workflow` 仍严格按当前 `run_id` 读取，不回退旧日志。
- 服务状态面板是短超时端口探测，不等同于 systemd 或 Docker 状态；Neo4j 7687 在线通常表示 `rabbitbot-unified-runtime` 容器仍在提供数据库。




## 本轮修改详情：TTS 指定设备缺失时继续内置回退

### 背景和目标

重启后确认 `rabbitbot-unified-runtime` 已带有 `RABBITBOT_TTS_ALLOW_BUILTIN=1`，但 TTS 仍因 `TTS_DEVICE_NAME=bt67` 不存在而拒绝启动。目标是让指定设备缺失时仍能按默认内置声卡回退继续启动。

### 已完成内容

- 修改 `scripts/start_tts_app.bash`：当指定设备未匹配且 `RABBITBOT_TTS_ALLOW_BUILTIN=1` 时，把 Orin/HDMI/APE 等内置输出设备加入 fallback 候选。
- 调整扫描日志：指定设备缺失且允许回退时，日志明确写出“继续尝试内置声卡回退”。

### 新增或调整日志点

- TTS 设备扫描失败路径增加是否继续内置回退的说明，便于区分“指定设备缺失但可回退”和“指定设备缺失且禁止回退”。
- 没有新增高频日志，也没有开启 DEBUG/TRACE 持久化写盘。

## 本轮修改详情：当前运行日志只显示本次运行

### 背景和目标

Aaron 反馈“当前运行日志”仍可能显示历史内容，并且启动某个服务时因为一行尚未输出完毕导致页面看不见最新进度。本轮目标是让日志面板只读本次运行日志，并提高刷新频率。

### 已完成内容

- 修改 `scripts_1/start_loop_entry.sh`：每次 loop 启动都会截断并写入 `logs/current_runtime.log`，同时用 `tee` 保留 systemd stdout 和当前运行日志文件。
- 修改 `rabbitbot/control_console/config.py`：新增 `current_runtime_log` 配置，默认指向 `logs/current_runtime.log`，也可由 `RABBITBOT_CURRENT_RUNTIME_LOG` 覆盖。
- 修改 `rabbitbot/control_console/app.py`：点击“开始程序”“开始程序(无机器人模式)”和“一键重启”时先清空当前运行日志；`/api/logs?target=runtime` 在无当前 workflow 时只读当前运行日志文件，不再读取历史 journal。
- 修改前端日志刷新：日志面板打开后每 500ms 独立刷新一次，请求行数提高到 220 行，不再依赖 2 秒一次的状态轮询。
- 修改 `tests/control_console/test_app.py`：覆盖无当前 workflow 时读取当前运行日志、无当前运行日志时返回空、未换行尾行仍返回、页面包含 500ms 日志刷新定时器。

### 新增或调整日志点

- 控制台清空当前运行日志时记录 INFO，包含日志路径和启动原因；清空失败时记录 WARNING，包含异常类型和错误信息。
- loop 启动时在当前日志文件和 systemd stdout 中记录 `当前运行日志` 路径，便于确认前端读取来源。
- 没有新增高频后端日志；前端高频刷新只读取当前日志文件尾部。

## 本轮修改详情：默认允许 TTS 内置声卡回退

### 背景和目标

Aaron 反馈 TTS 日志提示“如需临时允许内置声卡回退，请设置 RABBITBOT_TTS_ALLOW_BUILTIN=1”，并要求无论如何启动程序都默认打开该开关，完成后重启相关容器/服务。

### 已完成内容

- 修改 `scripts_1/start_unified_integration_workflow.sh`：创建统一容器时默认传入 `RABBITBOT_TTS_ALLOW_BUILTIN=1`，仍允许调用方显式设为 `0`。
- 修改 `scripts/start_tts_app.bash`：TTS 脚本自身默认 `RABBITBOT_TTS_ALLOW_BUILTIN=1`，覆盖直接在容器内启动 TTS 的路径。
- 调整 TTS 启动失败提示：现在说明默认已允许内置声卡回退，如需强制外接声卡再显式设为 `0`。

### 新增或调整日志点

- TTS 音频设备扫描失败提示已同步更新，避免日志继续建议设置一个已经默认开启的变量。
- 没有新增高频日志，也没有开启 DEBUG/TRACE 持久化写盘。

## 本轮修改详情：默认启用 Embedding

### 背景和目标

Aaron 要求在不影响当前服务状态的情况下，把 Embedding 设为默认开启。本轮目标是只修改下次启动读取到的默认值，不重启 loop、控制台或容器。

### 已完成内容

- 修改 `scripts_1/start_loop_entry.sh`：新增 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING`，loop portable 主入口默认启用 Embedding，并在启动日志中打印 `embedding` 开关。
- 修改 `scripts_1/start_nav_bridge_workflow_loop.sh`：新增 loop 场景 Embedding 默认开关说明，默认传入 `RABBITBOT_UNIFIED_START_EMBEDDING=1`，并在 `ensure_unified_services()` 日志中打印 `vlm/embedding/stt`。
- 修改 `scripts_1/start_unified_integration_workflow.sh`：统一基础服务入口默认 `RABBITBOT_UNIFIED_START_EMBEDDING=1`，并更新说明文案为 Embedding 默认启动、显式设 `0` 才跳过。
- 修改 `scripts_1/unified_runtime/start_unified_container.sh`：容器内入口默认 `RABBITBOT_UNIFIED_START_EMBEDDING=1`，保持宿主传入 `0` 可覆盖。
- 修改 `scripts_1/start_unified_vlm_qa_workflow.sh`：VLM QA 入口默认启动 Embedding，并在启动日志中打印开关。
- 修改 `rabbitbot/control_console/status.py` 和 `tests/control_console/test_app.py`：控制台服务状态中 Embedding 从可选服务改为必需服务，并补充测试断言。

### 新增或调整日志点

- loop portable 启动日志增加 `embedding=${RABBITBOT_UNIFIED_START_EMBEDDING}`，便于从 systemd journal 判断本次启动是否默认启用 Embedding。
- `ensure_unified_services()` 日志增加 `embedding` 开关，便于在“当前运行日志”中确认传给 unified 基础服务的实际配置。
- VLM QA 入口启动日志增加 `embedding` 开关，便于排查问答底座是否带起 8005。
- 没有新增高频日志，也没有开启 DEBUG/TRACE 持久化写盘。

## 最近历史摘要

- `073c7a3 默认启用 loop QA 所需 VLM`：loop QA 默认启用 VLM，服务状态面板将 VLM 标为必需。
- `28fd87a 让日志面板显示当前运行日志`：workflow 尚未创建时显示 loop journal，定位到 TTS 28185 阻塞。
- `5391902 修正当前 workflow 日志回退旧文件`：没有当前 run 时不再显示历史 workflow 日志。
- `9740947 新增控制台服务状态面板`：前端显示 Neo4j/TTS/STT/Memory/VLM/Embedding 端口状态。
- `0486cc4 支持控制台无机器人模式`：新增无机器人启动和到达确认按钮，loop 支持 `arrive`。
- 更早工作已压缩：`back` 注入“返回起点”、`go` 注入“开始导览”、默认 QA 与语音打断恢复、portable core/nav 镜像、自包含部署、STT/TTS 音频链路和 systemd/sudoers 治理。

## 其它信息

- 本轮未启动或停止任何现场服务，未触发机器人运动。
- 生成时间：2026-06-29

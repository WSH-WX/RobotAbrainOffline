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

## 本轮修改详情：无机器人模式跳过手臂动作、不等待回执

### 背景和目标

Aaron 反馈：无机器人模式下导览调用动作时会卡住很久。`logs/current_runtime.log` 证实，无机器人模式下 workflow 仍以 sync 模式向 `http://127.0.0.1:28180/do_arm_async` 发送手臂动作（`shake_hand`、`face_wave` 等），而 28180 的机器人 Agent 由导航桥接提供、在无机器人模式下根本不会启动，于是每个动作都阻塞到 HTTP 读超时（动作默认 45 秒、release 默认 3 秒），导致台词推进被动作卡死。目标：无机器人模式下直接跳过手臂动作请求、不等待机器人回执。

### 已完成内容

- 修改 `rabbitbot-dev-ros2-master/rabbitbot/provider.py`：
  - 新增 `_arm_action_no_robot_skip()`：当 `RABBITBOT_WORKFLOW_NON_INTEGRATION=1` 或 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 时返回 True，表示应跳过手臂动作；可用 `RABBITBOT_ARM_ACTION_FORCE_WHEN_NO_ROBOT=1` 强制恢复发送。
  - 在 `RobotAgent._post_arm_action()` 入口（远程开关检查之后）增加无机器人模式短路：命中时记录链路日志后直接返回 `{"success": True, "skipped": True, ...}`，不再发起 HTTP 请求。
- 该拦截点是 sync `do_arm`、async `do_arm_async`、release 三类手臂动作的共同入口，故一处修改即覆盖全部手臂动作；workflow 侧的并发动作线程会瞬间返回，join 不再阻塞，台词按 TTS 节奏推进。
- 返回 `success=True` 可避免 workflow 把跳过误记为“动作回执失败”，链路日志中以 `no_robot_mode_skip` 明确区分“无机器人跳过”与真实失败。

### 已验证的事实

- `python3 -m py_compile rabbitbot/provider.py` 通过。
- 复刻 `_arm_action_no_robot_skip()` 的开关判定逻辑单测 6 个用例全部通过（默认关闭、两个开关分别开启、force 覆盖、true 值、显式 0）。
- 启动脚本确认：无机器人模式下 workflow 进程会收到 `RABBITBOT_WORKFLOW_NON_INTEGRATION=1`（`scripts_1/start_nav_bridge_workflow_loop.sh` 第 80 行由 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 转写，并经 -e 传入容器）。

### 未完成 / 注意事项

- 本轮未重启 `rabbitbot-loop.service`、控制台或 `rabbitbot-unified-runtime` 容器；改动需下次启动或重建容器后生效（provider.py 在 workflow/容器进程内加载）。
- 真实机器人模式不受影响：两个无机器人开关均未开启时行为不变，仍按原超时发送动作。
- 头部 / 手指 / 抓取等动作（`do_head_async`、`do_finger_async`、`do_grab_async` 等）走的是各自 timeout=10 的独立路径，未纳入本次短路；如无机器人模式下它们也造成卡顿，可后续按同样方式处理。

### 新增或调整日志点

- `RobotAgent._post_arm_action()` 命中无机器人短路时输出 `provider动作链路: stage=no_robot_mode_skip, action=..., mode=sync/async`，便于在“当前运行日志”中确认动作被有意跳过、而非真实失败或超时。
- 未新增高频日志：每个动作仅一行跳过日志，且替代了原本 33~45 秒的超时等待日志。

## 本轮修改详情：替换 get_inst_chat 为精简现场对话提示词

### 背景和目标

Aaron 反馈聊天路径出现"无端道歉/冗长"等异常（例：问"中国的首都是哪里"，模型先道歉再作答）。根因定位为 `get_inst_chat` 原提示词（机二角色 + 大量杭州/上海铺陈 + 动作标记规则）把 7B 模型带偏。目标：删除 `get_inst_chat` 原提示词，替换为 `vlm_qa_workflow.py` 中 `_build_prompt` 的精简现场对话提示词。

### 已完成内容

- 修改 `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/prompts.py`：`get_inst_chat` 整体替换为精简版"RabbitBot 现场对话助手"提示词。
- 适配（因 agno `instructions` 是系统提示词、用户问题由 `.run(text)` 单独传入）：
  - 删除 `用户问题：{user_text}` 行；
  - `{visual_rule}` 用无画面固定句"当前没有可用画面，请只根据用户问题回答。"（chat 路径不带摄像头图像）；
  - `{answer_max_chars}` 固定为 180（与 `RABBITBOT_QA_MAX_ANSWER_CHARS` 默认值一致）。
- 保留 `get_inst_chat(entity_lst)` 函数签名以兼容既有调用方（`workflow.py:1539`）；参数现未使用。
- 按 Aaron 确认：`vlm_qa_workflow.py` 保留不动，仅复制内容，不删除其提示词。

### 已验证的事实

- `python3 -m py_compile rabbitbot/agno_agents/prompts.py` 通过。
- 运行期渲染 `get_inst_chat(["机器狗","沙盘"])`：无 `{user_text}/{visual_rule}/{answer_max_chars}` 残留占位符，内容正确。
- `git status` 仅 `prompts.py` 变更，`vlm_qa_workflow.py` 无改动。

### 注意事项（行为变化）

- 新提示词不再包含 `[A:动作名称]` 动作标记规则，因此**聊天路径不再驱动机械臂手势动作**（原 get_inst_chat 才有动作标记）。导览剧本台词里的动作不受影响（走的是另一套 body 动作清单）。
- 新提示词不再包含"机二"角色设定、能力介绍话术、固定问候/夸奖应答、展厅板块引导、会议/杭州/上海背景知识等；如需保留其中部分（如能力介绍、固定问候），需另行补回。
- 本轮未重启 loop/控制台/容器；改动需下次启动或重建后生效。

### 新增或调整日志点

- 本轮为静态提示词文本替换，未涉及执行流程，未新增/调整日志点。

## 本轮修改详情：调整控制台前端按钮顺序并重启服务/容器

### 背景和目标

Aaron 要求把"开始程序(无机器人模式)"和"到达下一个点位(无机器人模式)"两个按钮移到操作区最后，避免与常规按钮混排。改完后重启两个系统服务与 unified-runtime 容器使全部改动生效。

### 已完成内容

- 修改 `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py`：操作区按钮重排为 返航 → 刷新状态 → 开始程序 → 一键重启 → 关闭程序 → 开始程序(无机器人模式) → 到达下一个点位(无机器人模式)；两个无机器人模式按钮移至末尾。
- 按钮 id/onclick/class 均未改，仅调整 DOM 顺序，不影响任何前端逻辑。
- 重启 `rabbitbot-unified-runtime` 容器、`rabbitbot-loop.service`、`rabbitbot-control-console.service`，使本轮及前几轮（无机器人跳过手臂动作、get_inst_chat 提示词替换）改动一并生效。

### 已验证的事实

- `python3 -m py_compile rabbitbot/control_console/app.py` 通过。
- 控制台测试 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/control_console/` 全部通过（66 passed）；测试仅断言按钮存在与"服务状态/导览讲解词"相对位置，不涉及本次重排按钮顺序。

### 注意事项

- 两个系统服务即 `rabbitbot-control-console.service`（前端，加载 app.py 改动）与 `rabbitbot-loop.service`（导览 workflow，加载 provider.py/prompts.py 改动）。`rabbitbot-loop.service` 重启前为 inactive，本次重启会将其启动。
- 工作区代码以挂载方式进入 `rabbitbot-unified-runtime` 容器（容器内路径 `/workspace/projects/rabbitbot-dev-ros2-master`），故重启容器即可让容器内 workflow 读到最新代码。

### 新增或调整日志点

- 本轮为前端 DOM 顺序调整，无执行流程变化，未新增/调整日志点。

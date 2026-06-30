# air_robot_gt_projects 交接报告

## 背景和目标

本项目是 RabbitBot 自主运行包，当前工作目录为 `/mnt/disk1/gt/air_robot_gt_projects`，主代码目录为 `rabbitbot-dev-ros2-master`，当前分支为 `feature/qa-vlm-workflow`。近期目标是在 ShuHao-orin 上收敛控制台、`rabbitbot-loop.service`、QA/导览 workflow、语音口令、返航、无机器人模式和运行状态可观测性。

本轮最新目标：Aaron 要求让前端“关闭程序”按钮在关闭导航主程序的同时重启 Docker 容器。

## 当前状态

已完成：

- `rabbitbot-loop.service` 默认进入 QA 状态，听到“开始导览”或收到前端 `go` 后才开始剧本导览。
- 导览期间保持 STT 监听，真实提问会暂停当前导览和正在播报的 TTS，回答后回到原导览步骤。
- 前端“导览”按钮发送 `go`，loop 在语音启动模式下向 STT `/exec` 注入“开始导览”。
- 前端“返航”按钮发送 `back`，loop 在语音启动模式下向 STT `/exec` 注入“返回起点”；导览完成后按 `back_points` 返回，没有 `back_points` 时按导览点位逆序返回。
- 前端已支持“开始程序(无机器人模式)”和“到达下一个点位(无机器人模式)”；中文称呼统一为“无机器人模式”。
- 前端“当前运行日志”会优先显示当前 workflow 日志；workflow 尚未创建时只显示本次 loop 启动生成的 `logs/current_runtime.log`。
- 前端“服务状态”面板显示 Neo4j、TTS、STT、Memory、VLM、Embedding 的在线状态。
- loop QA 默认启用 VLM 和 Embedding；TTS 内置声卡回退默认允许。
- 无机器人模式下手臂动作会在 `RobotAgent._post_arm_action()` 入口短路跳过，不再等待 28180 超时。
- `get_inst_chat` 已替换为精简现场对话提示词。
- 当前 Neo4j 默认 `neo4j` 数据库在线，但导览相关图数据为空：节点数 0，关系数 0。
- 当前日志中一次问答打断：`初步介绍` 段从 06:59:10.409 开始，06:59:15.631 标记 interrupt，打断发生在该段开始后约 5.22 秒；从 interrupt 到 06:59:22.935 恢复导览首句播报约 7.30 秒。
- 本轮已修改“关闭程序”后端：前端仍调用 `POST /api/stop`，后端现在依次执行关闭 `rabbitbot-loop.service` 和重启 `rabbitbot-unified-runtime` 容器。

未完成：

- 本轮未做机器人实机导航、返航、语音拾音、TTS 播报或动作验证。
- 本轮未读取 `runtime/portable.env` 或 `runtime/rabbitbot-loop.env` 内容，避免暴露现场运行配置。
- 控制台 README 中仍提到 `scripts_1/systemd/...` 路径，但当前文件树未发现该目录，疑似文档滞后，尚未修正。
- 本轮已通过受控终止旧控制台 MainPID 的方式触发 systemd 自动重启，`rabbitbot-control-console.service` 已加载新代码并保持 active。

## 已验证的事实

- Git 根目录为 `/mnt/disk1/gt/air_robot_gt_projects`，分支为 `feature/qa-vlm-workflow`。
- 主项目 Python 包名为 `rabbitbot`，要求 Python `>=3.10`。
- 主代码目录包括 `rabbitbot/agno_agents`、`rabbitbot/control_console`、`rabbitbot/audio`、`rabbitbot/memory`、`rabbitbot/robots`、`rabbitbot/tools`、`scripts_1`、`scripts`、`tests`、`docs`。
- `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 当前均可由 systemd 管理；控制台服务以 `nvidia` 用户运行。
- `nvidia` 用户属于 `docker` 组，具备直接执行 `/usr/bin/docker` 的权限。
- `/usr/bin/docker` 存在，`rabbitbot-unified-runtime` 是当前 unified 运行底座容器名。
- `rabbitbot/control_console/app.py` 中 `stopProgram()` 调用 `/api/stop`。
- `stop_loop_service()` 现在先执行 `/usr/bin/sudo -n /usr/bin/systemctl stop rabbitbot-loop.service`，再执行 `/usr/bin/docker restart rabbitbot-unified-runtime`。
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/control_console/` 通过，结果为 `66 passed`。
- `rabbitbot-control-console.service` 已重启加载新代码：MainPID 从 `525885` 变为 `1119447`，状态 active。
- `python3 -m py_compile rabbitbot/control_console/app.py rabbitbot/control_console/commands.py rabbitbot/control_console/config.py` 通过。
- `git diff --check` 通过。
- 远端未安装 `rg`，本轮继续用 `find`/`grep` 作为替代方式。

## 阻塞问题

- 现场实机链路仍依赖 `eno1`、机器人网络、Unitree DDS、导航核心、TTS/STT 设备和容器服务状态。
- 当前主要风险仍是 TTS 28185 在指定设备缺失并回退内置声卡后，现场实际声音是否从可听设备输出。
- 如果 Embedding 模型目录缺失或显存/端口资源不足，启动会在 Embedding 8005 等待阶段暴露问题；可临时设置 `RABBITBOT_UNIFIED_START_EMBEDDING=0` 或 `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING=0` 跳过。
- 如果后续希望“关闭程序”同时重启 nav bridge 容器，也需要明确加入 `rabbitbot-portable-rabbitbot-nav-1`；本轮只按“docker 容器”语境重启 `rabbitbot-unified-runtime`。

## 建议的下一步

- 从前端点击“关闭程序”，确认返回消息包含“已关闭导航主程序”和“已重启 Docker 容器 rabbitbot-unified-runtime”。
- 点击后查看 `rabbitbot-control-console.service` 日志，确认出现“准备重启 Docker 容器”和“Docker 容器重启完成”。
- 如关闭程序后要继续导览，需要再点击“开始程序”或“开始程序(无机器人模式)”重新启动 `rabbitbot-loop.service`。
- 后续维护时修正控制台 README 中疑似过期的 `scripts_1/systemd/...` 路径说明。

## 注意事项

- `RABBITBOT_NAV_WORKFLOW_START_EMBEDDING` 是 loop 场景的默认开关，默认 `1`；`RABBITBOT_UNIFIED_START_EMBEDDING` 可直接覆盖最终传入容器的值。
- `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1` 是明确无机器人模式开关；`RABBITBOT_WORKFLOW_NON_INTEGRATION` 保留为兼容变量名。
- “到达下一个点位(无机器人模式)”按钮发送 `arrive`，只在无机器人模式下生效。
- “当前运行日志”默认请求 `/api/logs?target=runtime&lines=220`，打开后每 500ms 独立刷新。
- 服务状态面板是短超时端口探测，不等同于 systemd 或 Docker 状态。
- “关闭程序”现在会影响 `rabbitbot-unified-runtime` 容器；这会重启 Neo4j/TTS/STT/Memory/VLM/Embedding 等 unified 底座进程。

## 本轮修改详情：关闭程序同时重启 Docker 容器

### 背景和目标

Aaron 要求让前端“关闭程序”按钮同时执行重启 Docker 容器。目标是在保留原有停止 `rabbitbot-loop.service` 行为的基础上，追加重启 unified 运行底座容器。

### 已完成内容

- 修改 `rabbitbot/control_console/commands.py`：新增 `RUNTIME_CONTAINER_NAME` 和 `_restart_runtime_container()`，`stop_loop_service()` 现在先 stop 主循环服务，再执行 Docker restart。
- 修改 `rabbitbot/control_console/config.py`：新增 `runtime_container_name` 和 `docker_path` 配置，默认分别为 `rabbitbot-unified-runtime` 和 `/usr/bin/docker`，支持 `RABBITBOT_UNIFIED_CONTAINER_NAME`、`CONTAINER_NAME`、`RABBITBOT_CONSOLE_DOCKER_PATH` 覆盖。
- 修改 `rabbitbot/control_console/app.py`：`/api/stop` 将 Docker 配置传给 `stop_loop_service()`。
- 修改 `tests/control_console/test_app.py` 和 `tests/control_console/test_commands.py`：覆盖 `/api/stop` 和 `stop_loop_service()` 同时执行 systemctl stop 与 docker restart。

### 已验证的事实

- 控制台语法检查通过。
- 控制台测试 `66 passed`。
- `git diff --check` 通过。
- `/usr/bin/docker` 存在，控制台运行用户 `nvidia` 属于 `docker` 组。

### 新增或调整日志点

- 新增 Docker 容器重启 INFO 日志：记录准备重启的容器名和 Docker 路径，便于确认按钮触发了容器重启阶段。
- 新增 Docker 容器重启完成 INFO 日志：记录容器名，便于确认 restart 成功。
- 新增 Docker 容器重启失败 ERROR 日志：记录容器名、退出码和输出，便于区分 systemd stop 成功后 Docker restart 失败的场景。
- 未新增 DEBUG/TRACE 持久化日志，也未增加高频日志。


## 本轮修改详情：核查 STT 未检测到讲话原因

Aaron 反馈虽然 STT 使用 DJI Mic Mini，但对着麦克风讲话后日志没有显示收到。本轮检查当前 STT 日志、STT 进程 fd、宿主 ALSA 状态、PortAudio 设备表、mixer 状态和内核日志。结论：设备选择没有错，当前 STT 使用 `DJI MIC MINI: USB Audio (hw:0,0)`，并持有 `/dev/snd/pcmC0D0c`；宿主 `card0` capture 为 RUNNING，硬件参数为 48000Hz、2ch、S24_3LE，Mic capture 为 100% 且 on。

已验证事实：当前 STT 日志只有一次 `Starting audio stream on device 0...`，但 `Speech detected`、`Recognizing`、`Recognized text`、`Audio too quiet`、`Audio too short` 计数均为 0；因此应用层从未进入“检测到语音/准备识别”分支。更可能的原因是 DJI 发射端未实际送出音频（未配对、静音、未开麦、输入源不对），或现场讲话电平未超过当前 `STT_MIN_RMS=0.022` 和 `STT_VAD_SPEECH_THRES=0.12` 门限。当前 `get_last_rms` 任务在 STT 服务中未实现，workflow 侧不能直接打印实时 RMS。

建议下一步：现场先确认 DJI 接收端/发射端配对、发射端未静音、接收端有电平指示；随后短时增加 STT 的实时 RMS/峰值日志或实现 `get_last_rms` 诊断接口，再根据真实电平决定是否调低 `STT_MIN_RMS` 或 `STT_VAD_SPEECH_THRES`。

新增或调整日志点：本轮为运行状态只读核查和交接报告整理，未修改业务代码，未新增或调整代码日志点。


## 本轮修改详情：通过电平判断 DJI 麦克风侧状态

Aaron 要求通过电平判断麦克风侧是否正常。本轮短暂停止 STT 释放 `/dev/snd/pcmC0D0c`，等待设备关闭后使用 `arecord -D hw:0,0 -f S24_3LE -r 48000 -c 2 -d 10` 独占采样 10 秒，并立即重启 STT。采样结果：左声道 RMS/Peak 均为 0，右声道 RMS 约 `0.00383`（`-48.34 dBFS`）、Peak 约 `0.01708`（`-35.35 dBFS`），混合单声道 RMS 约 `-54.36 dBFS`。

已验证事实：DJI Mic Mini 不是完全无信号，但信号只在右声道且电平偏低；当前 `stt_app_funasr.py` 配置 `INPUT_CHANNELS=1`，音频回调固定使用 `indata[:, 0]`，这会读取全 0 的左声道，因此 STT 日志不会出现 `Speech detected`。采样后已重启 STT，当前进程为 `bash scripts/start_stt_funasr_app.bash` 和 `python stt_app_funasr.py`。

建议下一步：优先修 STT 输入通道处理，改成双声道采集并选择 RMS 最大声道或做非零声道优先；同时现场确认 DJI 接收端是否能切换为单声道/混音输出到左声道。仅调低 VAD/RMS 门限无法解决“读到左声道全 0”的问题。

新增或调整日志点：本轮为运行状态诊断和交接报告整理，未修改业务代码，未新增或调整代码日志点。

## 本轮修改详情：修复 DJI Mic Mini 右声道 STT 输入

### 背景和目标

Aaron 要求执行修复建议，解决 DJI Mic Mini 有电平但 STT 不触发识别的问题。前序诊断确认 DJI 右声道有信号、左声道为 0，而 STT 旧逻辑固定读取左声道。

### 已完成内容

- 修改 `rabbitbot-dev-ros2-master/stt_app_funasr.py`：默认采集 2 声道，按 RMS 自动选择电平最大的声道；保留 `STT_INPUT_CHANNEL_SELECT_MODE` 和 `STT_INPUT_CHANNEL_INDEX` 以支持固定声道或混音模式。
- 增加 STT 最近输入电平状态，`/exec` 新增 `get_last_rms` 诊断任务，便于 workflow 或现场排查读取当前输入电平。
- 修改 `rabbitbot-dev-ros2-master/scripts/start_stt_funasr_app.bash`：默认 `STT_INPUT_GAIN` 从 `1.0` 调整为 `8.0`，用于补偿 DJI 现场约 -48 dBFS 的低电平输入，仍允许环境变量覆盖。
- 修改 `rabbitbot-dev-ros2-master/scripts_1/start_unified_integration_workflow.sh`：统一容器创建时记录 `/dev/snd` 音频挂载日志，便于确认 ALSA 字符设备已暴露给容器。
- 已重建 `rabbitbot-unified-runtime` 容器，使 `/dev/snd` 绑定刷新；当前 STT 已自然恢复运行。

### 已验证的事实

- `python3 -m py_compile stt_app_funasr.py` 通过。
- `bash -n scripts/start_stt_funasr_app.bash` 通过。
- `bash -n scripts_1/start_unified_integration_workflow.sh` 通过。
- STT 最新日志显示输入设备为 `DJI MIC MINI: USB Audio (hw:0,0)`，`input_channels=2`，`channel_select=max_rms`，`input_gain=8.0`。
- STT 最新日志显示 `device_max_channels=2, stream_channels=2`，并使用 48000Hz 输入重采样到 16000Hz。
- `curl http://127.0.0.1:28184/docs` 返回正常，`get_last_rms` 返回 `0.00738514`。
- TTS `/docs` 同步可达；统一启动循环已恢复基础服务。

### 新增或调整日志点

- STT 启动配置日志新增输入声道数、声道选择模式、固定声道索引和电平日志间隔，便于确认实际加载的音频策略。
- STT 麦克风配置日志新增设备最大输入声道、实际流声道数、声道选择模式和固定声道索引，便于定位设备枚举或声道降级问题。
- STT 录音中新增节流 INFO 电平日志，记录选中声道、RMS、Peak、各声道 RMS 和声道数，便于现场判断是否读到右声道。
- 统一容器创建流程新增 `/dev/snd` 挂载 INFO 日志，便于排查容器内音频设备不可见问题。
- 未新增 DEBUG/TRACE 持久化日志，电平日志仅在录音期间按 `STT_LEVEL_LOG_INTERVAL` 节流输出。

### 阻塞问题和未完成内容

- 已验证 STT 读到 DJI 设备和非零 RMS，但尚未由 Aaron 现场对着麦克风说话并确认完整语音识别文本输出。
- 尝试直接挂载 `/proc/asound` 到容器 `/proc/asound` 会被 Docker proc 安全策略拒绝；已回退该方案，实际可行路径是重建容器刷新 `/dev/snd` 绑定。

### 建议的下一步

- Aaron 对着 DJI Mic Mini 说话时，观察 `rabbitbot_stt.log` 是否出现 `STT 输入电平`、`Speech detected` 和识别文本。
- 若仍不触发识别，优先查看 `get_last_rms` 与 `STT 输入电平` 日志；如果 RMS 明显低于 `STT_MIN_RMS=0.022`，再考虑继续调低门限或提高接收端/发射端增益。
- 若容器重启后再次枚举不到 DJI，先重建 `rabbitbot-unified-runtime` 容器刷新 `/dev/snd`，不要使用 `/proc/asound` 挂载方案。

## 最近历史摘要

- `8672472 记录导览打断恢复耗时核查`：记录当前日志中提问打断和恢复导览耗时。
- `9b62af9 记录 Neo4j 导览数据核查结果`：确认 Neo4j 当前无节点和关系数据。
- `d881f32 更新项目阅读交接报告`：压缩交接报告并记录项目阅读结果。
- `080a224 调整控制台按钮顺序：无机器人模式按钮移到最后`：前端操作区按钮调整为常规操作在前、无机器人按钮在最后。
- `6cd1543 将 get_inst_chat 替换为精简现场对话提示词`：聊天路径改为短答、直接、无画面规则。
- `74ed6bf 无机器人模式下跳过手臂动作并不再等待回执`：无机器人模式下手臂动作在 provider 入口短路。
- 更早工作已压缩：TTS 内置声卡回退、当前运行日志、Embedding/VLM 默认启用、语音打断恢复、返航、portable core/nav 镜像和 systemd/sudoers 治理。

## 其它信息

- 本轮未点击真实前端“关闭程序”按钮，未主动停止 `rabbitbot-loop.service`。
- 本轮为刷新音频设备绑定，已删除并由启动循环重建 `rabbitbot-unified-runtime`；恢复过程曾短暂中断 Neo4j/TTS/STT/Memory/VLM/Embedding，最终基础服务已恢复。
- 本轮未修改 `rabbitbot-control-console.service` 代码，也未再次重启控制台服务。
- 生成时间：2026-06-29

## 本轮修改详情：解耦统一容器为多容器（docker-compose）

### 背景和目标

原 `rabbitbot-unified-runtime` 单容器内串行运行 Neo4j/VLM/Embedding/TTS/STT/Memory，存在一损俱损、串行启动相互阻塞、生命周期强耦合等问题。Aaron 要求按 neo4j / rabbitbot-vlm / rabbitbot-audio / rabbitbot-memory / rabbitbot-navbridge 五个名字解耦容器，并直接切换实测。

### 已完成内容

- 新增 `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml`：定义五个解耦容器，全部 `network_mode: host`（服务间仍走 127.0.0.1，无需改任何服务地址）。
  - `neo4j`：官方 `neo4j:5.26-community` 镜像，独立数据卷 `rabbitbot_neo4j_data`。
  - `rabbitbot-vlm` / `rabbitbot-audio` / `rabbitbot-memory`：复用 `core-portable` 镜像（本机已无原始最小镜像），各只启动自己的服务子集；GPU(`runtime: nvidia`)、`ipc: host`、源码 bind、py310/py38 依赖卷与原 unified 一致；audio 额外挂 `/dev/snd` + `device_cgroup_rules: c 116:* rwm`。
  - `rabbitbot-navbridge`：复用 nav 镜像，提供 28180。
  - 健康检查 + `depends_on`（memory 等 neo4j 与 vlm 健康）+ `restart: unless-stopped`。
- 新增 `rabbitbot-dev-ros2-master/scripts_1/unified_runtime/start_role_container.sh`：角色入口，按 `RABBITBOT_CONTAINER_ROLE`(vlm/audio/memory) 只启动对应服务。它 `source` 现有 `start_unified_container.sh` 复用全部 helper 与 start_* 函数，零重复。
- 修改 `rabbitbot-dev-ros2-master/scripts_1/unified_runtime/start_unified_container.sh`：给末尾 `main "$@"` 加“仅直接执行时运行”守卫（`BASH_SOURCE`==`$0`），使其可被 source 而不自动起全部服务；直接执行行为不变，向后兼容。

### 已验证的事实

- `bash -n` 两个脚本语法通过；`docker compose -f docker-compose.decoupled.yaml config` 通过。
- 直接切换：停掉旧 `rabbitbot-unified-runtime` 与旧 nav 容器后，`docker compose up -d` 起五容器，最终全部 healthy/up：neo4j(7687)、rabbitbot-vlm(8000+8005)、rabbitbot-audio(28184+28185)、rabbitbot-memory(28182)、rabbitbot-navbridge(28180)。
- 跨容器记忆功能实测通过：经 memory 容器(28182) 写入(→neo4j 容器)、语义查询(→vlm 容器 embedding 8005) 正确召回，清理后 0 节点。

### 注意事项 / 未完成

- 三个 rabbitbot 容器**共用 core-portable 镜像**（容器解耦、镜像未瘦身）；原始最小镜像在本机已不存在，真正拆分最小镜像需重建上游，留作后续。
- 旧 `rabbitbot-unified-runtime` 容器仅 stop 未删，作为回退；**切勿与解耦栈同时启动**（端口会冲突）。
- **loop 编排尚未对接解耦栈**：`start_unified_integration_workflow.sh` 仍会去创建/启动 unified 容器；若现在跑 `rabbitbot-loop.service` 会与解耦容器抢端口。后续需改 loop 的“确保基础服务”步骤改为依赖解耦 compose（本轮未改）。
- 回退方式：`docker compose -f docker/portable/docker-compose.decoupled.yaml down` 后 `docker start rabbitbot-unified-runtime` 与旧 nav 容器。

### 新增或调整日志点

- `start_role_container.sh` 启动时打印 role、project、models、log_dir；每个角色打印将启动哪些服务；依赖等待与就绪复用 `wait_until` 的 INFO/SUCCESS 日志，便于排查“某容器卡在等待依赖”。
- `start_unified_container.sh` 守卫为纯控制流，无新增运行日志。

## 本轮修改详情：loop 基础服务改为依赖解耦 compose，workflow 跑进专用容器

### 背景和目标

上一轮把 unified 单容器解耦为多容器，但 loop 仍创建 unified 容器、并把 workflow exec 进它。本轮目标：让 loop 的“确保基础服务”改为依赖解耦 compose，并让导览 workflow 真正跑在解耦栈上的专用容器内。

### 已完成内容

- `docker/portable/docker-compose.decoupled.yaml`：新增第 6 个服务 `rabbitbot-workflow`（导览 workflow 专用宿主，复用 core-portable，挂全部 5 个依赖卷 py310/py38/vln/pyorbbecsdk/unitree_sdk2 + 源码 + /models，host 网络，自身仅 `tail -f` 保活，待 loop 注入 workflow）；补齐对应 named volume 声明。
- `scripts_1/start_nav_bridge_workflow_loop.sh`：新增 `RABBITBOT_BASE_RUNTIME` 开关（unified=旧默认 / compose=解耦）。
  - compose 模式下 `CONTAINER_NAME` 指向 `rabbitbot-workflow`，所有 `docker exec`（启动/检查/终止 workflow、控制文件）自动指向它。
  - 新增 `ensure_decoupled_services()`：用 `docker compose up -d` 拉起 neo4j/vlm/audio/memory/workflow，替代创建 unified 单容器；并先停止仍在运行的旧 unified 容器避免端口冲突。
  - `ensure_unified_services()` 与 `restart_unified_services()` 入口加 compose 分支。
- 关键前提：无机器人模式（`RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1`）下 `main()` 本就跳过 nav 桥接，且手臂动作已被跳过（不需要 28180），故 compose 模式不必改 nav 逻辑。
- 激活方式：`runtime/portable.env` 增加 `RABBITBOT_BASE_RUNTIME="compose"`（机器本地配置，未入库；代码默认仍为 unified，向后兼容）。

### 已验证的事实

- `bash -n` 与 `docker compose config` 均通过。
- 修复了首次实测发现的 bug：`ensure_decoupled_services` 误用了本脚本未定义的 `log_success`，导致 `set -e` 下 loop 反复重启；已改为 `log_info`。
- 实测（compose 模式 + 无机器人模式）：loop 启动后 `ensure_decoupled_services` 拉起解耦栈（全部 healthy），workflow 约 20s 到 QA 待命；`docker exec rabbitbot-workflow pgrep` 确认 workflow 进程跑在 `rabbitbot-workflow` 容器内（PID 94 start_kuavo_agno_workflow.bash），旧 `rabbitbot-unified-runtime` 为 Exited 未参与；日志中 workflow 成功跨容器调用 audio 容器 TTS 播报问候（workflow_tts_request_done），证明跨容器解耦栈协作正常。

### 注意事项 / 未完成

- 本轮仅在无机器人模式下打通；真实机器人模式（需 nav 桥接 + 28180）下 compose 模式与 loop 的 nav 自管如何协同，尚未处理。
- 导览中导航类提问仍受上轮发现的 `random.sample(空 entity_lst)` 崩溃影响（展点数据为空所致），与本轮解耦无关，需另行修复 + 灌入展点数据。
- 回退：把 `runtime/portable.env` 的 `RABBITBOT_BASE_RUNTIME` 改回 `unified`（或删除）即恢复旧单容器路径。
- 当前 loop 已 stop（idle），6 个解耦容器保持运行。

### 新增或调整日志点

- `ensure_decoupled_services()` 打印 compose 文件路径、workflow 宿主容器名、停止旧 unified 的告警、就绪汇总，便于确认基础服务来源已切到解耦栈。

## 本轮修改详情：真实机器人模式下 nav 与解耦 compose 协同

### 背景和目标

上一轮 compose 解耦只在无机器人模式打通（该模式 main 跳过 nav）。真实机器人模式下 main 会调 start_nav_bridge，而旧 nav 路径（host 或 portable compose.yaml 的 rabbitbot-nav 容器）会与解耦 compose 的 rabbitbot-navbridge 抢 28180。目标：让 compose 模式下 nav 唯一由解耦栈的 rabbitbot-navbridge 提供。

### 已完成内容（仅改 scripts_1/start_nav_bridge_workflow_loop.sh）

- compose 基础运行方式配置块追加：`NAV_BRIDGE_RUNTIME="compose"`、`RABBITBOT_NAV_BRIDGE_CONTAINER_NAME=rabbitbot-navbridge`、`RABBITBOT_NAVBRIDGE_SERVICE=rabbitbot-navbridge`，使 nav 视为 compose 运行、容器名/服务名对齐解耦栈。
- start_nav_bridge 启动分支新增 `RABBITBOT_BASE_RUNTIME=compose` 分支：以前台 `docker compose -f docker-compose.decoupled.yaml up --force-recreate rabbitbot-navbridge` 作为进程组拉起 nav（传入 RABBITBOT_DDS_INTERFACE / RABBITBOT_NAV_MAP_PATH）。**复用既有 nav 生命周期**（nav_group_pid 即该前台 compose 进程，停止进程组=停止该容器；stop/restart/health/wait_nav_core_ready 全部既有逻辑无需改动），就绪判断由 wait_nav_core_ready 读取 rabbitbot-navbridge 容器日志。
- 设计取舍：选“前台进程组”模型而非“detached + docker restart”，以最小改动复用 loop 已有的 nav 健康/重启/就绪等待机制。

### 已验证的事实

- `bash -n` 通过。
- 真实机器人模式有界干跑（NO_ROBOT=0 + nav 就绪超时 10s，机器人离线）：loop 日志确认走 compose 分支——“28180 当前由已有 portable nav 容器占用；compose 启动会重建该容器并接管端口，继续”“启动导航桥接：runtime=compose”“导航桥接进程组已启动 pgid=…”“端口 28180 已就绪”“等待导航核心…container=rabbitbot-navbridge”“Container rabbitbot-navbridge Recreate”；容器 rabbitbot-navbridge 由 loop 重建并 Up，28180 在线。说明 nav 已唯一由解耦栈提供、无端口冲突、loop 正确对齐到该容器。
- 干跑后已还原：NO_ROBOT=1、移除临时短超时、停 loop、恢复 6 容器全 up。

### 注意事项 / 未完成

- 机器人离线，**nav 核心 Pose/Ready 无法端到端验证**（无机器人时按预期超时）；wiring 已就绪，待真机上线再验证完整导航/返航。
- 无机器人模式（默认）完全不受本改动影响：main 跳过 start_nav_bridge，新分支不会执行。
- 回退：runtime/portable.env 的 RABBITBOT_BASE_RUNTIME 改回 unified。

### 新增或调整日志点

- 复用既有 nav 日志（启动导航桥接 runtime、进程组 pgid、等待导航核心 container=… 等）；新分支未新增高频日志，仅让既有日志的 container 字段指向 rabbitbot-navbridge，便于现场确认 nav 来源是解耦栈。

## 本轮修改详情：控制台前端适配解耦栈（容器名/文案随运行方式更新）

### 背景和目标

后端已解耦为多容器，但控制台仍引用旧 `rabbitbot-unified-runtime`：例如“关闭程序”后显示“已关闭导航主程序；已重启 Docker 容器 rabbitbot-unified-runtime”，且 nav 日志读取也指向旧 nav 容器名。需让前端随运行方式自动显示/操作正确的容器。

### 已完成内容（仅改 rabbitbot/control_console/config.py）

- `ConsoleConfig.from_env()` 新增按 `RABBITBOT_BASE_RUNTIME` 区分运行容器与 nav 容器默认名：
  - compose（解耦栈）：`runtime_container_name` 默认 `rabbitbot-workflow`（可被 RABBITBOT_WORKFLOW_CONTAINER_NAME 覆盖）；`nav_container_name` 默认 `rabbitbot-navbridge`。
  - unified（旧，默认）：沿用 `rabbitbot-unified-runtime` 与 `rabbitbot-portable-rabbitbot-nav-1`。
- 控制台服务通过 systemd `EnvironmentFile=runtime/portable.env` 读到 `RABBITBOT_BASE_RUNTIME=compose`，故自动进入 compose 分支。
- 由于“关闭程序”文案是 `f"已重启 Docker 容器 {runtime_container_name}"`、且 app.py 已把 `config.runtime_container_name`/`config.nav_container_name` 传入相关逻辑，改 config 即让文案与操作（重启 workflow 宿主容器、读 navbridge 日志）一并更新，无需改 commands.py / app.py。

### 已验证的事实

- 行为单测：compose 模式解析为 runtime=rabbitbot-workflow、nav=rabbitbot-navbridge；unified 模式仍为旧名。
- 控制台测试 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/control_console/` 全过（66 passed）。
- 解耦模式下“关闭程序”将：停 loop 服务 + 重启 `rabbitbot-workflow` 容器（清掉 workflow 进程，base 服务不动），文案显示“…；已重启 Docker 容器 rabbitbot-workflow”。

### 注意事项 / 未完成

- 改动需重启 `rabbitbot-control-console.service` 生效（需 sudo 密码，非交互无法执行，须 Aaron 手动重启）；旧实例在重启前仍显示旧容器名。
- 服务状态面板按端口探测（host 网络端口不变），无需改动。

### 新增或调整日志点

- 本轮为前端配置解析逻辑调整，无执行流程变化，未新增/调整日志点。

## 本轮修改详情：日志清理与目录迁移到 air 根

### 背景和目标

日志散乱且分散在 `<project>/logs` 下多种命名。Aaron 要求：删除所有旧日志；把日志目录统一放到 air 根 `/mnt/disk1/gt/air_robot_gt_projects/logs`（容器内 `/workspace/projects/logs`，与现有挂载共享同一物理目录）。

### 已完成内容（6 个文件，仅改“日志根”少数定义点，其余路径派生）

- `scripts_1/start_loop_entry.sh`：current_runtime.log 落 air 根。
- `scripts_1/start_nav_bridge_workflow_loop.sh`：HOST_LOG_DIR→`${PROJECTS_DIR}/logs`(air 根)；容器侧 CONTAINER_LOG_DIR / CONTAINER_WORKFLOW_RUN_DIR→`/workspace/projects/logs/...`（用 `${CONTAINER_RABBITBOT_DIR%/*}` 取上级）。
- `scripts_1/unified_runtime/start_unified_container.sh`：容器内基础服务 LOG_DIR→`${PROJECT_DIR%/*}/logs/unified_runtime`。
- `rabbitbot/control_console/config.py`：控制台 nav_log_dir/workflow_log_dir/workflow_control_dir/current_runtime_log 由 `project_root`→`project_root.parent`(air 根)。
- `docker/portable/docker-compose.decoupled.yaml`：三处 RABBITBOT_LOG_DIR + navbridge 的 nav_workflow_control 挂载都改到 air 根。
- `rabbitbot/tools/logging.py`：Python 文件日志默认目录从相对 `logs`→air 根 `logs`（`os.path.normpath(__file__/../../../logs)`），可由 `RABBITBOT_PY_LOG_DIR` 覆盖。

### 已验证的事实

- bash/py 语法、compose config 均通过；控制台配置解析与 Python 日志默认目录均落 air 根。
- 重建解耦容器应用新 RABBITBOT_LOG_DIR；删除旧 `<project>/logs`（含 root 属主的 vlm_qa_workflow 用容器内 root 删除）；把 air 根/logs 属主修为 nvidia(1000:1000)，解决“容器 root 先建目录致 loop(nvidia) 无法写”的属主冲突。
- 启动 loop(compose+无机器人模式)实测：workflow 到 QA 待命，进程在 rabbitbot-workflow；运行期日志全部落新位置——current_runtime.log、unified_runtime/(基础服务)、nav_workflow_control/rabbitbot_workflow_*.log(工作流)、uvicorn_*.log 等(Python)；旧 `<project>/logs` 已不存在。

### 注意事项 / 未完成

- 属主顺序：正常 loop 启动时 prepare_runtime 先以 nvidia 建好日志目录再起容器，无冲突；若**手动 `docker compose up` 先于 loop**，docker 会以 root 创建 air 根/logs 子目录，需 `docker exec <core容器> chown -R 1000:1000 /workspace/projects/logs` 修正（本轮已处理）。
- 控制台 config.py 改动需重启 `rabbitbot-control-console.service` 生效（sudo，须 Aaron 手动）。
- 旧 unified 单容器路径(start_unified_integration_workflow.sh 等)未改（compose 模式不用）；core.Dockerfile 内 mkdir 的旧路径无害，不影响运行期。
- loop 已停(idle)；6 个解耦容器保持运行。

### 新增或调整日志点

- 未新增业务日志；本轮是日志“落盘位置”的统一迁移，所有既有日志改落 air 根 `/logs`，便于集中查看与清理。

## 本轮修改详情：修复“开始程序”按钮触发的 workflow 残留死循环

### 背景和目标

前端点击“开始程序(无机器人模式)”后，current_runtime.log 反复出现“检测到已有 workflow 正在运行，拒绝重复启动”“workflow 预启动命令发送失败，重新进入循环”，loop 卡在恢复死循环。

### 根因

按钮做的是 `systemctl restart rabbitbot-loop.service`。但上一轮 loop 是以 `docker exec -d`(detached/setsid) 在 rabbitbot-workflow 容器内启动 workflow 的，`systemctl stop loop` 杀不掉它，于是容器内残留 workflow 进程。新 loop 实例：
- `workflow_running()` 用 `pgrep -f` 能检测到该残留 → `launch_workflow_detached()` 拒绝；
- 但 `stop_current_workflow()` 只按本轮 `current_pid_file` 杀，新实例无此记录 → 不杀；
- 形成“检测得到却杀不掉、反复拒绝”的死循环。

### 已完成内容（scripts_1/start_nav_bridge_workflow_loop.sh）

- 新增 `kill_stale_workflow()`：按进程特征（`pkill -f` 三个 workflow 入口模式）在 CONTAINER_NAME 容器内清理任何残留 workflow（TERM→2s→KILL），并轮询确认清理完成；不依赖本轮 pid 记录。
- `launch_workflow_detached()`：检测到已有 workflow 时，不再直接拒绝，而是先 `kill_stale_workflow` 清理残留再启动；清理失败才拒绝。

### 已验证的事实

- `bash -n` 通过。
- 重启 loop（即“开始程序”按钮动作）实测：日志出现“清理残留 workflow / 已清理”2 次，workflow 约 20s 到 QA 待命；“拒绝重复启动 / 预启动命令发送失败”计数为 0（死循环消失）；容器内 workflow 进程数稳定为 1（不再累积残留）。

### 注意事项 / 未完成

- 这是 loop 行为修复；按钮本身（commands.py 的 systemctl restart）逻辑正确，无需改前端。
- 当前 loop 处于运行态（QA 待命，等“开始导览”）——因为 Aaron 点的是“开始程序”，保持运行符合意图。
- 解耦/日志迁移相关改动仍需重启控制台服务（sudo）生效。

### 新增或调整日志点

- `kill_stale_workflow()` 打印“清理残留 workflow 进程”“已清理/清理失败”，便于现场确认残留被清理而非反复拒绝。

## 本轮修改详情：修复注入文本被“低音量打断”忽略

### 背景和目标

用 curl 向 STT(28184) 注入语句(inject_text_async)后，日志反复出现“忽略低音量打断”，注入的口令被丢弃。

### 根因

打断有效性由 `rabbitbot/tools/sound_agno.py::is_interrupt_loud_enough()` 判断（在 workflow 进程）：当 `RABBITBOT_INTERRUPT_RMS_THRESHOLD>0` 时，调 STT 的 `get_last_rms` 取“最近一次音频 RMS”，低于阈值则“忽略低音量打断”。而注入文本无真实音频，`get_last_rms` 返回的是旧的/极低音频 RMS（实测基线 0.0032），于是被当作低音量忽略。

### 已完成内容（stt_app_funasr.py）

- 新增模块级 `injection_state = {"last_consumed_injected": False}`。
- `get_text_async`：从 injected_text_queue 取到注入文本时置 True；识别到真实音频文本时置 False。
- `get_last_rms`：当上次消费为注入文本时，返回高音量哨兵 `STT_INJECTED_RMS`（默认 1.0），否则照常返回真实音频 RMS。
- 该改法无竞态：打断流程恒为 get_text_async(置标记) → is_interrupt_loud_enough→get_last_rms(读标记)。

### 已验证的事实

- `python3 -m py_compile stt_app_funasr.py` 通过。
- 重建 rabbitbot-audio 加载新代码后，STT 层实测：注入前 get_last_rms=0.00317（即触发忽略的低值）；注入并 get_text_async 消费后 get_last_rms=1.00000000（高哨兵）。即注入文本现会无条件越过打断音量阈值。
- sound_agno.py 未改，运行中的 workflow 无需重启即生效（它只是查询 STT 的 get_last_rms）。

### 注意事项 / 未完成

- 真实麦克风打断不受影响：识别到真实音频文本时标记置 False，仍按真实 RMS 与阈值比较。
- 可用 STT_INJECTED_RMS 调整注入文本的哨兵音量值。

### 新增或调整日志点

- 未新增日志；既有“忽略低音量打断”不再对注入文本触发。

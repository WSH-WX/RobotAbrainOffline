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

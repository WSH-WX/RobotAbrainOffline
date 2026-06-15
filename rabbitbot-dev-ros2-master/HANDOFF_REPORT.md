# 交接报告

## 背景和目标

本轮目标是在六月六日 DOCX/PDF 剧本已对齐、过渡点和新地图坐标已更新的基础上，将导览台词从 `workflow.py` 抽离到独立 JSON 文件，便于现场直接修改文案；同时将默认称呼配置为台词文件中的 `variables.leader_calling` 键。项目主机 `AGX-orin-FX`，路径 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`，分支 `June6_workflow`。

## 当前状态

已完成：

- 已保持严格 DOCX 剧本开场逻辑：不在开场台词前额外导航点位1，直接从点位1开始台词。
- 已保持当前 DOCX 剧本步骤顺序：`1到2过渡`、`跟随步行到点位2`、`点咖啡`、`初步介绍`、`拿取咖啡`、`前往3到5过渡点`、`前往点位5`、`告别并指引小巴方向`。
- 已保持 `1->2过渡点位` 和 `3->5过渡点位` 为独立只导航、无台词步骤，避免在过渡点提前播报。
- 已按现场新采地图更新 DOCX 点位坐标：`点位1`、`1->2过渡点位`、`点位2`、`点位3`、`3->5过渡点位`、`点位5` 已写入 `DOCX_SCRIPT_POINTS`；其中本轮按最新反馈将点位1改为 `(1.9105, -1.6180, 0.0117, -0.0029, 0.0265, -0.2046, 0.9785)`。
- 已将导览台词文件命名格式改为 `conf/dialogue_<序号>.json`，当前默认文件为 `conf/dialogue_0.json`；不显式指定时默认加载 0 号台词；启动 workflow 时可通过 `RABBITBOT_DIALOGUE_INDEX=<序号>` 选择对应台词文件。
- 本轮核实并修复：`workflow.py` 已支持 `RABBITBOT_DIALOGUE_INDEX`，但 `start_nav_bridge_workflow_loop.sh` 原先没有向容器内 workflow 透传该变量，因此 loop 场景下不能可靠切换台词序号；现已补齐透传和启动日志。
- 本轮已将 `conf/dialogue*` 前缀台词文件加入 `.gitignore`，并从 Git 索引移除 `conf/dialogue_0.json`；Orin 本地文件仍保留，`conf` 目录本身和其它非 dialogue 配置文件不被整体忽略。
- 本轮已补齐 `workflow.py` 顶部运行环境变量速查注释，覆盖严格剧本、台词序号/文件覆盖、咖啡车后台命令、导航、动作、profile 和 mock 视觉相关变量。
- 本轮已将 `send_delivery_task.py` 纳入版本管理，并为脚本补充中文命令说明和 AIR 咖啡车接口调用日志。
- 本轮已按现场要求先停止当前 workflow 进程组，保留 unified 容器和 TTS/STT/Memory 后台服务继续运行。
- 本轮提交后发现现场仍有一次旧式外部 `docker exec ... bash scripts/start_kuavo_agno_workflow.bash | tee` 命令重新拉起 workflow；已再次只停止该旧 workflow 进程组，容器和后台服务仍保留。
- 本轮已改造 unified `start_workflow()`：workflow 现在以独立进程组启动，`^C`/TERM/EXIT 会触发清理逻辑，先 TERM 后按需 KILL 整个 workflow 进程组。
- 本轮已将 `0203788` 中 `workflow.py` 的 workflow 运行环境变量速查注释同步补充到联调和非联调两个 unified workflow 启动脚本，便于现场启动前直接查看台词、咖啡车、导航、动作和日志相关变量。
- 本轮新增 `scripts_1/start_nav_bridge_workflow_loop.sh`，用于合并启动导航桥接和 unified 基础服务，并通过外部 `go/back` 命令循环启动 workflow、剧本结束后返航到点位1、再等待下一次 `go`。
- 本轮已补齐 `scripts_1/start_nav_bridge_workflow_loop.sh` 的台词切换支持：启动 loop 时可通过 `RABBITBOT_DIALOGUE_INDEX=<序号>` 选择 `conf/dialogue_<序号>.json`，也可继续使用旧变量 `RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX` 或文件覆盖变量 `RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE`；脚本会在预启动 workflow 时打印本轮台词来源。
- 本轮修正 `start_nav_bridge_workflow_loop.sh` 的运行环境：导航控制日志默认改到普通用户可写的 `logs/nav_workflow_control`，并在启动导航桥接前显式 source Humble 和 `custom_action_ws`，避免普通用户写日志失败后改用 sudo 导致 ROS 动态库和 uvicorn 环境丢失。
- 本轮已将 `start_nav_bridge_workflow_loop.sh` 默认导航地图从 `/home/unitree/test.pcd` 改为 `/home/unitree/test1.pcd`；仍可通过 `NAV_PCD_PATH` 环境变量临时覆盖。
- 本轮修复 `start_nav_bridge_workflow_loop.sh` 的 `go/back` 控制体验：命令轮询默认从 1 秒降到 0.2 秒；workflow 运行期间提前收到 `back` 时会立即记录并排队，待 workflow 结束后自动返航。
- 本轮已移除 DOCX 剧本结束后的普通问答模式：严格 DOCX 剧本完成后 workflow 会结束，不再进入“你好，请问你需要我做什么吗”的 STT/TTS 循环；现场本地忽略文件 `examples/run_kuavo_agno.py` 的“流程测试完成”播报也已改为默认关闭。
- 本轮已修复 `back` 返航路径：`start_nav_bridge_workflow_loop.sh` 不再从点位5直接发送点位1单一目标，而是按 `3->5过渡点位 -> 点位3 -> 点位2 -> 1->2过渡点位 -> 点位1` 分段返航；每段都会重置导航状态、发送目标、轮询状态并打印分段耗时。
- 本轮已优化 `go` 后 workflow 启动延迟：`start_nav_bridge_workflow_loop.sh` 现在会先预启动 workflow，并让新 runner 在 AppContext 初始化完成后停在启动闸门；收到 `go` 时只写入闸门文件释放开场，避免现场再等待 Python/import/AppContext 初始化。
- 本轮新增可提交入口 `scripts/run_kuavo_agno_workflow.py`，`scripts/start_kuavo_agno_workflow.bash` 已从 ignored 的 `examples/run_kuavo_agno.py` 切到该入口；`scripts/start_all_services.sh` 和编排脚本的运行检测也已补充新 runner 匹配。
- 本轮修复启动脚本直接退出问题：根因是预启动 workflow 时宿主侧日志被写到 `logs/unified_runtime/rabbitbot_workflow_*.log`，该目录当前为 `root:root 755`，普通用户 `pc` 无法创建文件，`set -e` 触发脚本退出并清理导航桥接。现在宿主日志、ready/go 闸门和状态文件均改到普通用户可写的 `logs/nav_workflow_control`，容器内对应路径为 `/workspace/projects/rabbitbot-dev-ros2-master/logs/nav_workflow_control`。
- 本轮增强 `scripts/run_kuavo_agno_workflow.py`：启动时主动将项目根目录加入 `sys.path`，避免直接运行或容器内验证时因未设置 `PYTHONPATH` 找不到 `rabbitbot`。
- 本轮定位 `back` 无法返航的原因：当前脚本处于预启动 workflow 后等待 `go` 的阶段，旧逻辑只接受 `go`，收到 `back` 会被 `wait_command go` 读走并作为非当前阶段命令忽略，因此不会进入返航。
- 本轮同时发现预启动状态目录不一致：ready/go 闸门已在 `logs/nav_workflow_control`，但 runner 的 `status/pid/exit_code` 仍受 `RABBITBOT_LOG_DIR` 影响写入旧目录，主脚本可能看不到 workflow 完成状态。已将 docker exec 传入的 `RABBITBOT_LOG_DIR` 改为容器内 `logs/nav_workflow_control`，使 ready、go、status、pid、exit_code 统一。
- 本轮修复等待 `go` 阶段的 `back` 行为：新增 `wait_go_or_back`，等待 go 时收到 back 会停止当前预启动 workflow 和日志 tail，然后直接执行分段返航；同时检测 ready 文件存在但预启动进程已退出的 stale 状态，自动重新预启动。
- 本轮新增 `scripts_1/send_nav_workflow_command.sh`，供其它终端发送 `go`、`back` 或 `quit` 控制命令；命令通过 `/tmp/rabbitbot_nav_workflow_control/command` 文件传递，不依赖主终端 stdin。
- 已将默认称呼抽为 `variables.leader_calling`，台词中的 `{leader_calling}` 会在运行时替换；缺少该键时 workflow 会报出明确配置错误，不再静默使用代码内固定称呼。
- 本轮已按现场要求调整 `conf/dialogue_0.json`：开场问候句改为“{leader_calling}您好，我叫小智。”；点位5小巴引导合并为一个播报段，减少句间 TTS 停顿，最后“各位再会！”仍单独配合挥手动作。
- 本轮复查所有运行态称呼：严格 DOCX 台词中的个性化称呼均来自 `conf/dialogue_0.json` 的 `variables.leader_calling`；当前配置为 `姚区长`，格式化后会播报“姚区长您好，我叫小智。”、“对了，姚区长、各位...”、“姚区长，咖啡和饮料来了...”和“姚区长、各位领导...”。
- 本轮同步修正非严格剧本导览兜底称呼：普通 scripted tour 的转场介绍和结束语现在也优先使用 `ctx.leader_info.leader_calling` 或 `variables.leader_calling`，不再硬编码“各位领导”。
- 当前开场不再包含“第一次来园区”问答；第三段欢迎各位朋友的台词仍使用 `face_wave` 动作。
- 已调整 dialogue01/dialogue02 的握手动作时序：
  - `shake_hand` 现在从开场问候“{leader_calling}您好，我叫小智。”开始时启动。
  - dialogue02 “欢迎您来到滨湖复星人形机器人产业园。”仍在同一个握手动作窗口内播报。
  - `release` 收手仍复用 `_do_arm_during_speech` 的原有流程，在 dialogue02 播报结束后执行。
- 已将 TTS 默认启动路径切到 Unitree G1 本体音响：未显式设置 `RABBITBOT_TTS_BACKEND` 时默认使用 `unitree`，未显式设置 `RABBITBOT_UNITREE_TTS_VOLUME` 时默认音量为 `100`。
- 已新增 Unitree G1 本体 TTS 后端：
  - 新增 `scripts/unitree_g1_tts_bridge.cpp`，通过宇树 SDK2 `AudioClient.TtsMaker` 向 G1 发送播报文本。
  - 新增 `scripts/build_unitree_g1_tts_bridge.sh`，自动使用 `/mnt/ssd/navgation/projects/unitree_sdk2` 或 `/workspace/projects/unitree_sdk2` 构建桥接程序。
  - 新增 `rabbitbot/audio/unitree_g1_tts.py`，封装桥接程序调用、音量设置、网卡配置、等待估算和日志。
  - `tts_app.py` 新增 `RABBITBOT_TTS_BACKEND=unitree` 后端；默认仍为本地 TTS，不影响原外接音箱方案。
  - `scripts/start_tts_app.bash` 在 Unitree 模式下跳过 Orin 本地输出声卡扫描，避免因没有外接音箱导致 TTS 服务启动失败。
  - 统一容器脚本新增 Unitree TTS 相关环境变量，并在 TTS 后端或网卡配置变化时重建旧容器。

未完成：

- 尚未在完整 unified workflow 中验证 Unitree 本体 TTS 与 STT 打断、`tts_wait`、开场动作并发的整体节奏。
- 尚未在真机/完整 workflow 中验证提前伸手后的握手距离、收手时机、TTS 节奏和现场观感。

## 已验证的事实

- Orin 和 G1 通过有线网卡 `eno1` 通信，Orin 上 `eno1` 地址为 `192.168.123.222/24`。
- Orin 当前没有安装 Python 版 `unitree_sdk2py` 和 `cyclonedds`，因此本轮使用已有 C++ `unitree_sdk2` 实现桥接。
- `/mnt/ssd/navgation/projects/unitree_sdk2` 中存在 G1 `AudioClient`、`TtsMaker`、`SetVolume` 和 aarch64 SDK 库。
- `scripts/build_unitree_g1_tts_bridge.sh` 已成功构建 `build/unitree_g1_tts_bridge`。
- 直接运行桥接程序已成功返回：`SetVolume ret=0`，`TtsMaker ret=0`。
- 通过 `UnitreeG1TTS` Python 后端发送“后端测试”已成功返回 `ret=0`，并完成本地估算等待。
- 已通过检查：`bash -n`、`python3 -m py_compile`、桥接程序构建和帮助输出。
- 现有本体 TTS 日志会记录初始化、桥接程序构建、请求开始、返回码、耗时、音量、网卡、speaker id 和估算播放时长。
- 本轮只读调用 Unitree G1 `AudioClient.GetVolume` 查询当前机器人本体音量，返回 `ret=0`、`volume=85`，查询未触发播报，也未调用 `SetVolume`。
- 本轮已验证默认配置干运行初始化：默认后端为 `unitree`，默认网卡为 `eno1`，默认音量为 `100`；`bash -n` 和 `python3 -m py_compile` 均通过。
- 本轮核实机器人本体 TTS 变成女声的原因：当前 unified 容器环境为 `RABBITBOT_TTS_BACKEND=unitree`、`RABBITBOT_UNITREE_TTS_SPEAKER_ID=0`；宇树 G1 `TtsMaker(text, speaker_id)` 的 `speaker_id=0` 对应中文/自动 TTS，不是原 Orin 本地 TTS 音色选择，因此音色由 G1 内置语音服务决定。
- 本轮现场将 TTS 运行时切回 Orin 本地外接音响：宿主机识别到 USB 音响 `BT67`，`aplay -l` 为 `card 2, device 0`；使用 `RABBITBOT_TTS_BACKEND=local RECREATE_CONTAINER=1 RUN_WORKFLOW_AFTER_START=0` 重建统一容器基础服务，TTS 日志确认选中 `BT67: USB Audio (hw:2,0)`，`OUTPUT_DEVICE_INDEX=24`，HTTP `/docs` 返回 200。
- 本轮已通过当前 TTS 服务向 BT67 外接音响发送试播文本“测试测试”，`text_to_speech` 返回 `out_text=0`，随后 `wait_speech` 返回 `TTS finished`。
- 本轮已将 DOCX 剧本点咖啡环节的“我来给各位安排。”配置为播报开始时同步后台呼叫 AIR 咖啡车；后台命令默认解析为 `python3 /mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master/send_delivery_task.py run`，在 unified 容器内会自动改用 `/workspace/projects/rabbitbot-dev-ros2-master/send_delivery_task.py`。
- 本轮新增 DOCX 剧本总耗时终端打印：严格 DOCX 模式下从开场第一句实际 TTS 前开始计时；若开场被跳过，则从 DOCX 第一段台词前兜底开始；剧本完成时打印 `DOCX 剧本总耗时`，包含开始时间、结束时间和秒级耗时。
- 本轮按最新剧本删除两处问答交互：开场不再询问“是否第一次来园区”，改为直接播报“{leader_calling}，各位，请随我来，我简单的介绍一下园区。”；点咖啡不再等待领导回答，改为直接播报准备咖啡饮料并在“我来给各位安排。”开播时呼叫 AIR 咖啡车。
- 本轮已从 `拿取咖啡` 场景移除“我再给各位介绍一下产业园和清华创新中心的合作成果。”这句独立播报；该场景现在只保留咖啡和饮料自取提示，随后直接进入 `前往3到5过渡点`。
- 上一轮现场释放了导航桥接常用端口 `28180`：当时确认占用方为 `python3` 进程 PID `7283`，执行结束后复查 `ss -ltnp "sport = :28180"` 已无监听进程。
- 本轮处理旧导航桥接进程：先结束 `start_nav_arm_bridge.sh eno1 /home/unitree/test1.pcd` 的 PID `41946` 进程组；随后复查发现同命令又拉起 PID `42936` 进程组并占用 28180，已继续结束其 `goGoalNavigation66`、`humble_robot_agent_bridge`、`tail`、`tee` 子进程。最终复查 `ss -ltnp "sport = :28180"` 已无监听进程。
- 本轮同步更新了 `docs/DOCX严格剧本workflow逻辑.md` 和 `docs/直接导航命令.txt` 中的点位坐标说明，直接导航命令中的点位5路径已改为包含 `3->5过渡`。
- 本轮同步更新了 `docs/DOCX严格剧本workflow逻辑.md` 和 `docs/直接导航命令.txt` 中的点位1坐标，已与 workflow 和返航脚本默认点位1保持一致。
- 本轮已验证 `conf/dialogue_0.json` 可通过 `python3 -m json.tool` 解析，`rabbitbot/agno_agents/workflow.py` 可通过 `python3 -m py_compile` 语法检查；同时验证未设置环境变量时默认解析到 0 号台词，且 `RABBITBOT_DIALOGUE_INDEX=0` 路径可解析。
- 本轮已验证 `send_delivery_task.py --help` 可正常输出命令说明，`python3 -m py_compile rabbitbot/agno_agents/workflow.py send_delivery_task.py` 语法检查通过；未在本轮实际触发 `run`，避免误呼叫咖啡车。
- 本轮停止当前 workflow 后已复查：容器内不再存在 `run_kuavo_agno.py`、`start_kuavo_agno_workflow.bash` 或 workflow 日志 `tee` 进程；unified 容器仍运行，TTS/STT/Memory 服务进程仍在。
- 本轮对旧式外部 `docker exec` 重新拉起的 workflow 再次执行停止后复查：容器内已无 workflow 相关进程，TTS/STT/Memory 服务仍在，`rabbitbot-unified-runtime` 容器仍运行。
- 本轮已验证 `scripts_1/unified_runtime/start_unified_container.sh` 通过 `bash -n` 语法检查；未重新拉起完整 workflow，避免现场流程被误触发。
- 本轮已验证 `scripts_1/start_unified_integration_workflow.sh` 和 `scripts_1/start_unified_non_integration_workflow.sh` 通过 `bash -n` 语法检查；本轮未停止、重启或重新拉起 workflow。
- 本轮已验证 `scripts_1/start_nav_bridge_workflow_loop.sh` 和 `scripts_1/send_nav_workflow_command.sh` 通过 `bash -n` 语法检查；未实际启动导航桥接、未启动 workflow、未发送返航命令，避免影响现场运行。
- 本轮已验证普通用户 `pc` 对 `logs` 目录有写权限，但 `logs/unified_runtime` 当前为 `root:root 755`，这是直接运行编排脚本时创建导航控制日志失败的原因；同时验证 ROS 动态库缺失可通过 source Humble 和 `custom_action_ws` 修复。
- 本轮已验证 `scripts_1/start_nav_bridge_workflow_loop.sh` 通过 `bash -n` 语法检查；未实际启动导航桥接或 workflow。
- 本轮已验证本次返航修改后的 `scripts_1/start_nav_bridge_workflow_loop.sh` 通过 `bash -n`，`rabbitbot/agno_agents/workflow.py` 通过 `python3 -m py_compile`；未实际发送 `back` 或启动导航，避免影响现场运行。
- 本轮已验证预启动闸门相关静态检查：`scripts_1/start_nav_bridge_workflow_loop.sh`、`scripts/start_kuavo_agno_workflow.bash`、`scripts/start_all_services.sh` 均通过 `bash -n`，`scripts/run_kuavo_agno_workflow.py` 通过 `python3 -m py_compile`，`git diff --check` 通过。
- 本轮已验证当前权限事实：宿主 `logs/nav_workflow_control` 为 `pc:pc` 且可写，宿主 `logs/unified_runtime` 为 `root:root 755` 且 `pc` 不可写；这解释了启动脚本在创建 `rabbitbot_workflow_*.log` 时直接退出。
- 本轮已在当前运行的 `rabbitbot-unified-runtime` 容器内验证 `py310/bin/python scripts/run_kuavo_agno_workflow.py --help` 可正常导入并输出帮助，且容器内 `/workspace/projects/rabbitbot-dev-ros2-master/logs/nav_workflow_control` 可写；未实际启动 workflow。
- 本轮已验证当前现场状态：`start_nav_bridge_workflow_loop.sh` 仍在运行，28180 正常监听，最新 control 目录只有 `20260603_144523.ready`，无当前 `status/pid` 文件，容器内也无 `run_kuavo_agno_workflow.py` 进程；这说明当前实例已经处于等待 `go` 的旧逻辑阶段，发送 `back` 不会返航。
- 本轮已验证修复后的 `scripts_1/start_nav_bridge_workflow_loop.sh` 通过 `bash -n`，`git diff --check` 通过；未停止当前脚本实例，未实际触发返航。
- 本轮已验证 6 元组修复后的 `scripts_1/start_nav_bridge_workflow_loop.sh` 通过 `bash -n`，`git diff --check` 通过；未停止当前旧脚本实例，未重新触发返航。
- 本轮进一步按现场描述复查 `20260603_144523`：机器人已在点位5且 workflow 已结束，`status/finished_at/exit_code` 实际写在旧的 `logs/unified_runtime/workflow_control`，而当时主脚本预期从 `logs/nav_workflow_control/workflow_control` 读取状态；因此主脚本没有识别 workflow 完成，也不会进入 `wait_command back` 或返航流程，`back` 表现为无响应。
- 本轮复查前台未打印 workflow 日志问题：同一 run `20260603_144523` 中，主脚本前台 tail 的 `logs/nav_workflow_control/rabbitbot_workflow_20260603_144523.log` 为 0 字节，而实际 workflow 输出写入 `logs/unified_runtime/rabbitbot_workflow_20260603_144523.log`，大小约 81KB；因此前台只看到导航桥接日志。该问题与状态文件落点不一致同源，重启新版本脚本后 `RABBITBOT_LOG_DIR` 已改为容器内 `logs/nav_workflow_control`，前台 tail 应恢复 workflow 日志。
- 本轮只读复查现场状态：`back` 命令文件已写入但当前旧脚本实例仍在等待 workflow 结束，因此不会立即消费；本轮修复对已运行的旧脚本实例不热更新，需下次重启编排脚本生效。

## 阻塞问题

无代码层面的阻塞。本轮返航分段路径、go 预启动闸门和等待 go 阶段 back 返航尚未真机完整验证，且已运行的旧 `start_nav_bridge_workflow_loop.sh` 实例不会热更新，需要重启该编排脚本后新返航逻辑、低延迟 go 和等待 go 阶段 back 才生效。运行层面另有两个待恢复/验证事项：一是上一轮 BT67 外接音响已从 Orin 声卡列表消失且 TTS 当前未运行，需要现场恢复声卡后再启动；二是本轮 AIR 咖啡车呼叫逻辑未实际运行，避免误触发现场配送任务，需在真机 workflow 点咖啡环节验证。Unitree `TtsMaker` 只返回机器人接收状态，当前没有官方播放完成回调；`wait_speech` 使用文本长度估算等待时间，后续如发现台词衔接过快或过慢，需要调节 `UnitreeG1TTS._estimate_duration` 或新增更可靠的播放状态查询。

## 建议的下一步

- 用如下方式启动 unified 模式验证本体播报：`RECREATE_CONTAINER=1 bash scripts_1/start_unified_integration_workflow.sh`；默认会使用 Unitree G1 本体音响、`eno1` 网卡和音量 `100`。
- 真机跑一次完整开场，重点观察 `shake_hand` 是否从“{leader_calling}您好”开始伸手，并确认收手仍发生在“欢迎您来到滨湖复星人形机器人产业园”之后。
- 当前默认音量已改为 100；如现场觉得过响或破音，可通过 `RABBITBOT_UNITREE_TTS_VOLUME=85` 或更低值临时覆盖后重启 TTS/unified 流程。
- 若必须恢复原来的男声/本地音色，需要评估两条路线：一是回退 `RABBITBOT_TTS_BACKEND=local` 使用 Orin 外接音箱；二是改用 G1 `PlayStream` 播放 Orin 本地合成的 PCM 音频。仅调整 `RABBITBOT_UNITREE_TTS_SPEAKER_ID` 预计不能切换到中文男声。
- 如要继续使用 Orin 外接音响，需先让 Orin 重新识别 BT67，再用 `RABBITBOT_TTS_BACKEND=local RECREATE_CONTAINER=1` 重建/启动 unified；如不带 `RABBITBOT_TTS_BACKEND=local`，会按代码默认值回到机器人本体音响。
- 真机跑点咖啡环节时，重点观察“我来给各位安排。”开播时是否同时出现 `DOCX 后台命令已启动` 和 `DOCX 后台命令结束` 日志，并确认 stdout 中咖啡车接口返回 `success=true` 和运行时 `task_id`。
- 重新拉起导航桥接后，先用 `docs/直接导航命令.txt` 中的新坐标逐点验证 `1->2过渡`、`点位2`、`点位3`、`3->5过渡` 和 `点位5` 到点精度。
- 若使用新的导航 + workflow 编排脚本，主终端执行 `bash scripts_1/start_nav_bridge_workflow_loop.sh`，其它终端用 `bash scripts_1/send_nav_workflow_command.sh go` 启动 workflow，剧本完成后用 `bash scripts_1/send_nav_workflow_command.sh back` 返回点位1。
- 重启 `start_nav_bridge_workflow_loop.sh` 后，真机重点验证 `back` 是否按点位5、`3->5过渡点位`、点位3、点位2、`1->2过渡点位`、点位1的逆序路径行走，并观察每段日志中的 `返航分段 x/5` 状态和耗时。
- 重启 `start_nav_bridge_workflow_loop.sh` 后，先观察主终端是否出现 `workflow 已完成预启动并停在 go 闸门`，再发送 `go`，重点确认第一句台词是否在闸门释放后快速开始，并查看 `workflow启动闸门: stage=released` 与 TTS 请求日志的时间差。
- 如果再次出现启动后直接退出，优先看终端是否有 `Permission denied`，并确认脚本打印的 workflow 日志路径应位于 `logs/nav_workflow_control/rabbitbot_workflow_*.log`，不应再位于 `logs/unified_runtime`。
- 如果机器人已在点位5但主脚本显示正在等待 `go`，新版本允许直接发送 `back` 进入返航；旧运行实例不会具备该能力，需要重启 `start_nav_bridge_workflow_loop.sh` 后再试。
- 本轮确认最新 `start_nav_bridge_workflow_loop.sh` 已包含 `wait_go_or_back`：等待 `go` 阶段收到 `back` 会停止预启动 workflow 并直接执行 `return_to_start`，因此无需再增加“接近点位5才接收 back”的额外判断；当前未发现该编排脚本仍在运行。
- 本轮复查 2026-06-03 15:02 左右 back 不返航的新日志：脚本已经收到 `back` 并进入分段返航，但第一段目标发给 28180 时使用了 7 元组 `(x,y,z,ox,oy,oz,ow)`；28180 直接接口按 6 元组 `(x,y,ox,oy,oz,ow)` 解析，导致 `z=-0.1921` 被当成 `q_x`，姿态参数整体错位，底层导航返回 `Failed to obtain the current pose information`，机器人停在点位5不动。
- 本轮已将 `start_nav_bridge_workflow_loop.sh` 中直接发给 28180 的返航点位改为 6 元组，并新增 `normalize_go_to_task` 兼容转换：如外部环境变量仍传入 7 元组，会自动去掉 z 并打印 `任务格式已兼容转换` warning。
- 本轮按现场最新要求调整 back 返航路径：收到 back 后按 `原点位5 -> 返回点1 -> 返回点2 -> 点位1` 导航；返回点1 为 `(6.4327, 8.2585, 0.0505, 0.0827, 0.5996, -0.7944)`，返回点2 为 `(9.8023, -3.1366, -0.0442, 0.0674, 0.9944, 0.0684)`，均为 28180 直接接口使用的六元组格式。
- 本轮同步更新 `docs/直接导航命令.txt`，明确直接调用 28180 `/go_to_async` 使用 `(x, y, ox, oy, oz, ow)`，不包含 z。
- 如需现场修改称呼，直接改当前选中台词文件的 `variables.leader_calling`；如需修改台词，改对应 `opening` 键或 `steps[].segments[].text`。修改后重启 workflow 让进程重新读取台词文件。
- `conf/dialogue_<序号>.json` 文件已被 Git 忽略；新增或修改现场台词后不会出现在 `git status` 中。如需提交其它配置文件，请避免使用 `dialogue` 前缀。
- 完整跑完 DOCX 剧本后，确认终端出现 `DOCX 剧本总耗时`，并检查耗时是否覆盖开场第一句到最后一句“各位再会！”结束后的剧本完成时刻。
- 真机复测点位5时，重点听“移步门外，乘坐无人驾驶小巴车深入了解我们园区”是否已经作为同一段连续播报，确认没有明显句间停顿。
- 修改 `variables.leader_calling` 后需要重启 workflow；台词文件会在 workflow 进程内缓存，同一个进程运行期间不会自动热更新。
- 如需新增其它台词，复制 `conf/dialogue_0.json` 为 `conf/dialogue_1.json`、`conf/dialogue_2.json` 等并修改内容，再用 `RABBITBOT_DIALOGUE_INDEX=1` 或 `RABBITBOT_DIALOGUE_INDEX=2` 启动 workflow。
- 继续确认 dialogue01 中“上前靠近领导A一步”是否已有机器人动作或底盘接口；当前本轮未实现该靠近动作。
- 继续按上一轮建议清理重复 `entity` 字段。
- 明确是否有 OK 手势动作字段；如果有，再把点咖啡后的 `right_hand_up` 改为 OK 动作。

## 注意事项

- 默认 TTS 后端现在是 `unitree`，默认音量是 `100`；如需回退 Orin 本地外接音箱，需要显式设置 `RABBITBOT_TTS_BACKEND=local`。
- 当前 TTS 运行状态需现场恢复：上一轮重启 TTS 时 BT67 从 Orin 声卡列表消失，当前 `http://127.0.0.1:28185/docs` 返回 `000`，`/proc/asound/cards` 仅剩 HDA/APE；需重新插拔或恢复 BT67 后再启动 TTS。
- `send_delivery_task.py` 已纳入版本管理；默认模板 ID 保持现场已验证可用的 `delivery_1780402103401`，如 AIR 咖啡车任务模板变更，应优先通过脚本 `--template-id` 或 workflow 的 `RABBITBOT_COFFEE_DELIVERY_COMMAND` 覆盖后再固化。
- 上一轮观察到的旧容器 `RABBITBOT_UNITREE_TTS_VOLUME=85` 已不再是当前运行状态；当前默认 Unitree 音量仍为 `100`，但使用 `RABBITBOT_TTS_BACKEND=local` 时 Unitree 音量配置不参与本地外接音响播放。
- Unitree 本体 TTS 当前通过 C++ 桥接程序发命令，不依赖 Python 版宇树 SDK。
- unified 创建容器和容器内启动 TTS 时会打印后端、Unitree 网卡和音量，方便排查是否仍沿用旧容器或旧音量。
- unified 入口现在会在 workflow 启动时打印 workflow 进程组 PGID；按 `^C` 时应看到“收到 INT 信号，正在停止 workflow 进程组”和最终停止完成日志。如仍有残留，应优先按日志中的 PGID 排查。
- 新的 `^C` 清理逻辑只覆盖 `scripts_1/unified_runtime/start_unified_container.sh` 的 `start_workflow()` 路径；如果现场直接执行旧式 `docker exec ... bash scripts/start_kuavo_agno_workflow.bash | tee`，仍会绕过该 trap，需要改用 unified 入口或同步改造外部启动命令。
- 联调脚本和非联调脚本顶部的 workflow 环境变量速查注释需与 `workflow.py` 中对应注释保持同步；后续新增运行变量时应同步更新三处说明。
- `start_nav_bridge_workflow_loop.sh` 会独占启动 28180 导航桥接；如果 28180 已被旧桥接或其它服务占用，脚本会退出，不会自动 kill 旧进程。
- `start_nav_bridge_workflow_loop.sh` 默认使用 `/home/unitree/test1.pcd`；如果现场切回其它地图，可用 `NAV_PCD_PATH=/path/to/map.pcd bash scripts_1/start_nav_bridge_workflow_loop.sh` 覆盖。
- `start_nav_bridge_workflow_loop.sh` 运行期间如果提前发送 `back`，新版本会排队到 workflow 完成后返航；旧版本实例不会热更新，需重启脚本后才具备该能力。
- 严格 DOCX 剧本完成后现在默认不进入剧本后问答；现场本地忽略文件 `examples/run_kuavo_agno.py` 也默认不播报“流程测试完成”，如确需恢复结束播报，可临时设置 `RABBITBOT_WORKFLOW_FINISH_SPEECH=1`。
- 不建议用 `sudo` 启动 `start_nav_bridge_workflow_loop.sh`；sudo 会切换 Python 用户包和部分 ROS 环境，容易出现 `uvicorn` 或 ROS 动态库找不到的问题。
- `start_nav_bridge_workflow_loop.sh` 的返航现在是分段路径，默认顺序为 `3->5过渡点位 -> 点位3 -> 点位2 -> 1->2过渡点位 -> 点位1`；点位可分别通过 `RABBITBOT_NAV_WORKFLOW_POINT_3_TO_5_TRANSITION`、`RABBITBOT_NAV_WORKFLOW_POINT_3`、`RABBITBOT_NAV_WORKFLOW_POINT_2`、`RABBITBOT_NAV_WORKFLOW_POINT_1_TO_2_TRANSITION`、`RABBITBOT_NAV_WORKFLOW_POINT_1` 覆盖，最终点位1仍可用 `RABBITBOT_NAV_WORKFLOW_START_POINT` 兼容覆盖。返航状态通过 28180 `/go_to_status` 轮询，`status=3` 视为当前分段成功。
- `start_nav_bridge_workflow_loop.sh` 的 `go` 现在使用预启动闸门：可用 `RABBITBOT_NAV_WORKFLOW_GATE_READY_TIMEOUT_SECONDS` 调整等待预启动就绪超时，用 `RABBITBOT_WORKFLOW_START_GATE_POLL_SECONDS` 调整 workflow 内部闸门轮询间隔，用 `RABBITBOT_NAV_WORKFLOW_STATUS_POLL_SECONDS` 调整 workflow 运行期间状态和 back 预接收轮询间隔。
- `logs/unified_runtime` 当前由 root 拥有，普通用户不要在宿主侧直接写该目录；新的导航 workflow 编排运行日志和闸门控制文件默认放在 `logs/nav_workflow_control`，避免再次触发权限退出。
- 新版本中 workflow 预启动的 `ready/go/status/pid/exit_code` 都应位于 `logs/nav_workflow_control/workflow_control`；如果只看到 ready 而没有 status/pid，应优先检查是否仍在运行旧脚本实例或旧环境变量。
- 直接调用 28180 `/go_to_async` 与 workflow 内部点位格式不同：workflow `DOCX_SCRIPT_POINTS` 仍保留 `z`，但 curl 直接接口和 `start_nav_bridge_workflow_loop.sh` 返航目标应使用六元组；如果导航日志里出现 `q_x` 等于原 z 值，说明又发生了 7 元组误传。
- back 返航路径现在有 4 段：`原点位5 -> 返回点1 -> 返回点2 -> 点位1`；如需现场微调返回点，可覆盖 `RABBITBOT_NAV_WORKFLOW_BACK_POINT_1` 和 `RABBITBOT_NAV_WORKFLOW_BACK_POINT_2`。
- DOCX 后台命令日志会记录命令解析来源、启动 PID、超时时间、退出码、耗时、stdout/stderr 摘要，可用于排查 AIR 咖啡车接口是否被调用以及返回结果。
- `send_delivery_task.py` 现在会向 stderr 记录 AIR 咖啡车接口请求开始、HTTP 状态、耗时、返回字节数、运行任务 ID 以及失败原因；workflow 捕获后台命令 stderr 后可直接辅助定位网络、接口或模板问题。
- DOCX 剧本计时日志会在终端打印 `DOCX 剧本总计时开始` 和 `DOCX 剧本总耗时`，用于现场快速确认整段流程耗时。
- 当前 DOCX 剧本不再包含“第一次来园区”和“是否送咖啡饮料”的 STT 问答等待；如后续再恢复问答，需要重新配置 `listen_key`/`early_listen` 并验证监听超时。
- 当前 `拿取咖啡` 场景不再包含合作成果介绍台词；如后续要恢复相关内容，需要先确认正式文案，再重新加入独立播报 segment。
- `workflow.py` 现在只保留流程结构和台词文件加载/校验逻辑；六月六日 DOCX 导览具体台词应优先维护 `conf/dialogue_<序号>.json`，不要再直接写回 `DOCX_SCRIPT_STEPS`。
- 如果再次启动 `start_nav_arm_bridge.sh` 仍提示 28180 被占用，应优先现场复查当时的 `ss -ltnp "sport = :28180"` 输出；本轮结束旧桥接进程后该端口已经为空。
- 如果在容器内使用宿主机构建的桥接程序，`UnitreeG1TTS` 会自动设置 `LD_LIBRARY_PATH` 到 `/workspace/projects/unitree_sdk2/thirdparty/lib/aarch64` 或宿主机对应路径。
- 如果现场觉得伸手过早或动作时长影响话筒交接，可优先检查动作日志中的 `action=shake_hand` 耗时和随后的 `release` 耗时。

## 其它信息

如需同步到 `feature/unified-runtime-image`，可 cherry-pick 本轮提交。

## 本轮补充：旧日志归档

- 本轮已归档旧日志：将早于 2026-06-04 且未被进程打开、非 `latest` 链接、非 `latest` 目标的历史日志移动到 `logs/archive_20260604_083348_old_logs`。
- 当前正在写入的 `logs/nav_workflow_control/nav_bridge_20260604_083009.log` 保持原位；今天日志和无日期服务日志保持原位。
- 本轮归档前通过 `/proc/*/fd` 核实当前打开的项目日志；归档后复查当前打开日志仍在原路径。
- 旧日期日志剩余项仅为 `logs/unified_runtime/rabbitbot_workflow_20260603_144523.log`，该文件是 `rabbitbot_workflow_latest.log` 的目标文件，故保留以避免破坏 latest 链接。
- 归档目录内包含 `ARCHIVE_MANIFEST.txt` 和 `ARCHIVE_MANIFEST_ROOT.txt`，分别记录普通用户权限和容器 root 权限归档的文件清单。

## 本轮补充：workflow 开场后提前退出原因

- 本轮定位 2026-06-04 08:46 左右 workflow 提前退出：run_id 为 `20260604_084641`，退出码为 `1`，不是剧本正常结束。
- 直接原因是第三句开场欢迎语“各位朋友，也欢迎你们！”调用 TTS 时失败；workflow 日志中 `tts_index` 为空，旧逻辑随后执行 `int('')` 抛出 `ValueError`，loop 看到 workflow finished 后进入等待 `back` 阶段。
- TTS 服务端根因日志显示 Unitree G1 本体 TTS 桥接在该句执行 `SetVolume(100)` 时返回 `ret=3104`，随后 HTTP 返回 500；前两句 TTS 均正常返回。
- 本轮已修复 `rabbitbot/audio/unitree_g1_tts.py`：默认只在首次 Unitree TTS 请求时设置音量；如果设置音量失败或机器人音频服务忙，会记录 `tts_request_retry_without_volume` 并保留当前音量重试播报。
- 本轮已修复 `rabbitbot/tools/sound_agno.py`：当 TTS 返回空值或非法索引时记录 `workflow_tts_request_invalid_response`，并抛出带上下文的 `RuntimeError`，避免后续只看到难以定位的 `ValueError`。
- 已验证：Python 源码编译检查通过；模拟桥接返回验证第一句带 `--volume`、第二句不带；模拟 `SetVolume` 失败验证会不带音量重试并返回成功索引。
- 额外状态：复查时 `rabbitbot-unified-runtime` 容器已退出，Docker 状态为 `ExitCode=137`、`OOMKilled=false`，28185 TTS 端口不再监听；本轮未重新拉起容器或 workflow。

## 本轮补充：TTS 失败不再终止 workflow

- 本轮确认：上一版修复后，如果 Unitree TTS 重试后仍失败，`tts_sound` 仍可能抛出异常并导致 workflow 退出，这不满足现场导览“不能因单句 TTS 失败中断”的要求。
- 本轮已将 `rabbitbot/tools/sound_agno.py` 的 TTS 工具层改为默认可恢复：`text_to_speech` 异常、空 `tts_index`、非法 `tts_index`、`wait_speech` 异常、`get_wav_count/get_play` 异常都会记录 `TTS请求链路` 日志并返回可继续的默认值。
- 默认策略：单句 TTS 失败返回 `tts_index=-1`，后续台词和导航继续执行；与失败 TTS 绑定的动作会跳过，避免等待不存在的播放索引。
- 新增 `RABBITBOT_TTS_STRICT_FAILURE` 开关：默认 `0`，表示 TTS 失败只记录并继续；设为 `1/true/yes/on` 时恢复严格模式，把 TTS 失败视为致命错误。
- 已将 `RABBITBOT_TTS_STRICT_FAILURE` 写入 workflow、联调/非联调 unified 脚本和导航 loop 脚本注释；`start_nav_bridge_workflow_loop.sh` 和 `start_unified_integration_workflow.sh` 已透传该变量到容器内 workflow。
- 已验证：Python 源码编译检查通过，三个启动脚本 `bash -n` 通过；模拟 TTS 空返回、TTS 抛异常、等待失败、队列查询失败、非法 TTS 索引时均不会抛出到 workflow。

## 本轮补充：导航 workflow loop 系统服务

- 本轮新增 `scripts_1/systemd/rabbitbot-nav-workflow-loop.service`，用于将 `scripts_1/start_nav_bridge_workflow_loop.sh` 注册为 systemd 服务。
- 已将服务安装到 `/etc/systemd/system/rabbitbot-nav-workflow-loop.service`，并执行 `systemctl daemon-reload`。
- 已执行 `systemctl enable rabbitbot-nav-workflow-loop.service`，服务会在下次开机进入待命；本轮没有执行 `systemctl start`，因此没有启动第二个 loop 实例。
- 安装后验证：`systemctl status rabbitbot-nav-workflow-loop.service` 显示 `Loaded: enabled`、`Active: inactive (dead)`；当前手动运行的 `start_nav_bridge_workflow_loop.sh` 进程仍在，未被中断。
- 服务以 `pc` 用户运行，工作目录为 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`，异常退出时 `Restart=on-failure`，重启间隔 5 秒。
- 常用操作：启动 `sudo systemctl start rabbitbot-nav-workflow-loop.service`；停止 `sudo systemctl stop rabbitbot-nav-workflow-loop.service`；重启 `sudo systemctl restart rabbitbot-nav-workflow-loop.service`；查看日志 `journalctl -u rabbitbot-nav-workflow-loop.service -f`；取消开机自启 `sudo systemctl disable rabbitbot-nav-workflow-loop.service`。

## 本轮补充：系统服务重命名

- 本轮按现场要求将系统服务名从 `rabbitbot-nav-workflow-loop.service` 改为 `rabbitbot-loop.service`。
- 项目内服务模板同步重命名为 `scripts_1/systemd/rabbitbot-loop.service`，`SyslogIdentifier` 改为 `rabbitbot-loop`。
- 操作策略为先安装并启用新服务，再禁用并移除旧服务；全程没有执行 `systemctl start`，当前手动运行的 loop 进程未被中断。
- 新服务常用命令：`sudo systemctl start rabbitbot-loop.service`、`sudo systemctl stop rabbitbot-loop.service`、`sudo systemctl restart rabbitbot-loop.service`、`systemctl status rabbitbot-loop.service`、`journalctl -u rabbitbot-loop.service -f`。

## 本轮补充：systemd 下 go 不触发机器人移动原因

- 本轮定位 systemd 服务状态下发送 `send_nav_workflow_command.sh go` 后机器人不动：`rabbitbot-loop.service` 实际运行正常，导航桥接和统一容器基础服务均已启动，28180/28185/28184/28182 端口可用。
- 直接原因不是 go 命令未送达；日志显示 2026-06-04 15:35:52 已收到 `go` 并释放 workflow 闸门。
- workflow 随后立刻异常退出，run_id 为 `20260604_153323`，退出码为 `1`；根因是 systemd 默认环境没有设置台词序号，loop 脚本向容器透传了空字符串 `RABBITBOT_DIALOGUE_INDEX=''`，旧逻辑把空字符串视为非法序号而不是默认 0。
- workflow 异常退出后，loop 进入“等待 `back` 返回起点”阶段，因此后续再次发送 `go` 会被日志明确记录为 `当前阶段需要 back，忽略命令：go`。
- 本轮已修复 `rabbitbot/agno_agents/workflow.py`：`RABBITBOT_DIALOGUE_INDEX` 为空时视为未设置，继续读取旧变量 `RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX`；两个都为空时默认使用 `dialogue_0.json`。非法非数字序号仍会记录两个环境变量和最终生效值后报错。
- 已验证：Python 源码编译检查通过；空 `RABBITBOT_DIALOGUE_INDEX` 和空旧变量返回默认序号 `0`；显式 `RABBITBOT_DIALOGUE_INDEX=3` 返回 `3`；非法 `abc` 仍报 `DOCX 导览台词序号必须是数字`。
- 注意：当前正在运行的服务实例已经处于等待 `back` 阶段，本轮未自动发送 `back`、未重启服务、未中断现有 loop。要恢复现场可先发 `back` 完成本轮，或在确认安全后 `sudo systemctl restart rabbitbot-loop.service` 重新进入待命。

## 本轮补充：关闭 rabbitbot-loop 开机自启

- 本轮按现场要求将 `rabbitbot-loop.service` 设为不开机自启：已执行 `systemctl disable rabbitbot-loop.service`，并移除 `multi-user.target.wants` 下的启用链接。
- 已执行 `systemctl reset-failed rabbitbot-loop.service` 清理此前 TERM 退出留下的 failed 标记；最终状态验证为 `disabled / inactive (dead)`。
- 本轮没有执行 `systemctl start rabbitbot-loop.service`，系统服务不会在当前会话自动启动，也不会在下次开机自动启动。
- 复查发现 2026-06-04 15:39:22 有新的手动 `start_nav_bridge_workflow_loop.sh` 实例在运行，父进程不是 systemd；本轮未停止该手动实例。
- 如后续需要重新启用开机自启，可执行 `sudo systemctl enable rabbitbot-loop.service`；只临时启动则执行 `sudo systemctl start rabbitbot-loop.service`。

## 本轮补充：开场欢迎后长延迟定位

- 本轮只读排查 2026-06-05 运行中“各位朋友，也欢迎你们！”之后长时间停顿的问题，未修改代码。
- 最近几轮对比显示异常集中在 `logs/nav_workflow_control/rabbitbot_workflow_20260605_115910.log`：该轮 `face_wave` 动作耗时 `24.048s`，到下一句“各位领导，各位，请随我来...”开始间隔 `24.249s`；其它相邻轮次同一动作约 `4.1s`、到下一句约 `4.3s`。
- workflow 日志显示 TTS 请求本身正常：该句 TTS `elapsed=0.346s`，随后 `wait_speech` 约 3 秒完成；长延迟发生在等待并发动作 `face_wave` 的 action 线程 join。
- 导航桥接日志 `logs/nav_workflow_control/nav_bridge_20260605_115805.log` 显示 `/do_arm_async task=face_wave` 的 `goal_response=22.02ms`，但 `wait_result=24012.32ms`，说明 HTTP 和 ROS goal 接收很快，卡在等待手臂 action 结果。
- 手臂 action server 日志 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/run_logs/nav_arm_bridge_20260605_115806/02_g1ArmOfficialActionServer.log` 显示 `face_wave` 接收后约 20 秒才打印 `Executing official action [face_wave] at fsm_id=-1 fsm_mode=-1`，最终 `receive_to_success=23997.30ms`。
- 结合 `g1_arm_official_action_server.cpp` 执行顺序，`Executing official action` 之前会调用 `GetFsmId` 和 `GetFsmMode`；本轮推断约 20 秒耗在这两个 Unitree 状态查询超时/失败上，之后 `face_wave` 本体动作约 4 秒完成。
- 结论：该次长延迟不是 TTS 合成或播放导致，也不是导航目标导致，而是手臂官方动作服务在执行 `face_wave` 前查询机器人 FSM 状态异常超时。后续若要修复，可考虑减少/跳过动作前 FSM 查询、给查询单独加短超时，或让 workflow 对开场并发动作设置最大等待时间。

## 本轮补充：stop 脚本增强宿主机清理

- 本轮增强 `scripts_1/stop_unified_workflow.sh`，使其除停止统一容器 workflow 和容器内后台服务外，还会清理宿主机导航、手臂动作服务和 `28180` bridge。
- 新增宿主机清理顺序：先停止 `start_nav_bridge_workflow_loop.sh` 进程组，让 loop 自身 trap 清理；再停止 `start_nav_arm_bridge.sh`；最后按明确进程名兜底清理 `goGoalNavigation66`、`g1ArmOfficialActionServer`、`humble_robot_agent_bridge:app` 和导航日志 tail。
- 新增 pid 文件兜底清理：扫描 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/run_logs` 下历史启动脚本记录的 `.pid` 文件，并在命令行匹配预期进程名时才停止，避免 PID 复用导致误杀。
- 新增清理日志：脚本会打印每类宿主机进程的发现/停止情况、PID、命令行、强制停止原因，以及最终 `28180` 端口是否释放，便于排查停止不彻底的问题。
- 已验证 `bash -n scripts_1/stop_unified_workflow.sh` 通过；本轮未实际执行 stop 脚本，避免中断现场可能存在的服务。
- 当前已知未跟踪文件仍为 `conf/dialogue_1500.json`、`conf/dialogue_1600.json`、`conf/dialogue_2000.json`，本轮未处理这些现场台词文件。

## 本轮补充：增强导航 workflow loop 健壮性

- 本轮增强 `scripts_1/start_nav_bridge_workflow_loop.sh`，目标是在后续做成 systemd 开机服务前，先提升长期待命和异常恢复能力。
- 新增运行时健康检查配置：
  - `RABBITBOT_NAV_WORKFLOW_HEALTH_CHECK_INTERVAL_SECONDS`：等待命令和 workflow 运行期间的健康检查间隔，默认 5 秒。
  - `RABBITBOT_NAV_WORKFLOW_LOST_PROCESS_GRACE_SECONDS`：workflow 进程丢失但状态文件未落盘时的宽限时间，默认 5 秒。
  - `RABBITBOT_NAV_WORKFLOW_NAV_RESTART_WAIT_SECONDS`：重启导航桥接前等待时间，默认 3 秒。
  - `RABBITBOT_NAV_WORKFLOW_BACK_RETRY_LIMIT`：返航失败后自动恢复导航桥接并重试的次数，默认 1。
  - `RABBITBOT_NAV_WORKFLOW_RETURN_FAILURE_WAIT_SECONDS`：返航失败恢复间隔，默认 2 秒。
- 新增基础服务健康检查：定期检查 unified 容器、Neo4j `7687`、TTS `28185`、STT `28184` 和 Memory `28182`；如果基础服务不健康，会记录失败项并尝试通过统一入口恢复，运行中容器不健康时会先重启容器。
- 新增导航桥接健康检查：检查本脚本启动的导航桥接进程组、`28180` 端口和 `/go_to_status` 状态接口；失败时会记录具体原因并可重启导航桥接。
- 等待 `go/back` 阶段如果健康检查失败，会停止当前预启动 workflow，恢复基础服务或导航桥接后重新预启动，避免旧 ready 状态卡住。
- 等待普通 `back` 命令阶段也会做周期性健康检查，避免 workflow 已结束但返航前服务已经下线。
- workflow 运行期间如果健康检查失败，只记录并等待 workflow 自身收敛，不在导览过程中主动重启服务，避免中途干扰导航或播报。
- workflow 运行期间如果状态文件仍为 `running`，但当前 run 的 workflow 进程已经丢失，超过宽限时间后会写入 `exit_code=127`、`finished_at` 和 `status=finished`，避免 loop 无限等待。
- 返航失败不再直接让脚本因 `set -e` 退出；脚本会按重试上限恢复导航桥接并重试，超过上限后保持返航阶段，等待现场确认后再次发送 `back` 重试。
- workflow 预启动命令发送失败现在会进入恢复分支，不再直接退出 loop。
- 新增和调整的日志点覆盖：健康检查失败项、运行阶段、服务恢复原因、导航桥接重启原因、workflow 进程丢失宽限时间、异常状态落盘、返航失败分段、自动重试次数和返航重试等待。
- 已验证：`bash -n scripts_1/start_nav_bridge_workflow_loop.sh` 通过，`git diff --check` 通过。
- 本轮未启动 `start_nav_bridge_workflow_loop.sh`，未启动 systemd 服务，未发送 `go/back` 命令，未触发机器人移动或播报。
- 当前仍未处理现场未跟踪台词文件：`conf/dialogue_1500.json`、`conf/dialogue_1600.json`、`conf/dialogue_2000.json`。
- 下一步建议：更新并启用 `rabbitbot-loop.service` 前，先用当前脚本做一次短时手动启动验证，确认只进入待命；再验证 `go`、workflow 完成、`back` 和异常恢复路径。

## 本轮补充：台词 JSON 增加地图和点位配置

### 背景和目标

本轮目标是按现场要求调整 `conf/dialogue_<序号>.json` 台词配置：在台词文件中记录当前使用的地图文件名，并把 DOCX 严格剧本点位列表从 workflow 代码侧抽到台词 JSON 中；workflow 需要优先使用台词文件中的点位，同时保留旧代码点位作为兜底。

### 当前状态

已完成：

- 已在 `conf/dialogue_0.json`、`conf/dialogue_1.json`、`conf/dialogue_2.json`、`conf/dialogue_3.json` 顶层新增 `map_file`，当前值为 `test1.pcd`。
- 已在上述 4 个台词 JSON 顶层新增 `points`，包含 `point_1`、`point_1_to_2_transition`、`point_2`、`point_3`、`point_4`、`point_3_to_5_transition`、`point_5` 共 7 个点位。
- 已将点位条目统一为 `name`、`summary`、`description`、`location` 结构；`location` 中包含 workflow 使用的 `x/y/z/ox/oy/oz/ow/mode` 字段。
- 已适配 `rabbitbot/agno_agents/workflow.py`：加载台词 JSON 时会读取并校验 `map_file` 和 `points`；DOCX 严格剧本步骤解析 `entity_key` 时优先使用台词文件点位。
- 已保留 `DOCX_SCRIPT_POINTS` 代码兜底：如果台词文件没有配置对应点位，workflow 仍会尝试使用旧的代码内点位。
- 已更新 `conf/README.md`，说明 `map_file`、`points`、点位字段和重启 workflow 后生效的要求。

未完成：

- 本轮未启动 systemd 服务、导航桥接或 workflow，未进行真机移动验证，避免影响现场运行。
- `map_file` 当前用于配置记录和日志排查；导航桥接实际加载的地图仍由 `NAV_PCD_PATH` 控制，现场需要确认两者一致。

### 已验证的事实

- `conf/dialogue_0.json` 到 `conf/dialogue_3.json` 均可通过 `python3 -m json.tool` 解析。
- 4 个台词 JSON 均已通过结构校验：`map_file=test1.pcd`，每个文件 `points=7`，所有点位均包含完整 `x/y/z/ox/oy/oz/ow/mode` 坐标字段。
- `rabbitbot/agno_agents/workflow.py` 已通过 `python3 -m py_compile` 语法检查。
- `git diff --check` 已通过。

### 阻塞问题

无代码层面的阻塞。剩余风险是运行层面尚未实测：需要在重启 workflow 后确认台词文件点位被正确加载，并确认 `NAV_PCD_PATH` 与台词文件 `map_file` 指向同一张地图。

### 建议的下一步

- 重启 workflow 或 `rabbitbot-loop.service` 后观察日志中 `DOCX 导览台词文件加载完成`，确认 `map_file=test1.pcd`、`points=7`。
- 发送 `go` 前确认导航桥接启动参数中的 `NAV_PCD_PATH` 仍为 `/home/unitree/test1.pcd` 或其它与台词 `map_file` 一致的路径。
- 真机完整跑一遍 DOCX 严格剧本，重点观察各 `entity_key` 对应的点位是否从台词 JSON 加载，并确认返航和过渡点行为没有回退到旧配置。

### 注意事项

- 台词 JSON 修改后需要重启 workflow；当前 workflow 会缓存台词配置，同一进程内不会自动热更新。
- 若现场新增台词文件，应复制现有 `dialogue_<序号>.json` 并保留 `map_file` 与完整 `points` 结构，否则 workflow 可能回退到代码内旧点位或在配置校验阶段报错。
- 坐标校验会在点位加载阶段报出文件路径、点位 key、location 序号和缺失/非法字段，便于快速定位台词文件配置错误。

### 其它信息

- 本轮新增/调整的日志点包括：台词文件加载完成时输出 `map_file` 和 `points` 数量；点位加载时输出使用台词文件配置或代码兜底配置、点位名、坐标数量和地图文件名。
- 这些日志用于区分导航失败时到底是台词文件点位未生效、回退到了代码兜底，还是地图文件与导航桥接实际加载地图不一致。

## 本轮补充：dialogue_1 切换 test9 点位

### 背景和目标

本轮目标是按现场提供的 test9 地图点位，更新 `conf/dialogue_1.json` 中 DOCX 严格剧本实际使用的导航点位。现场已先将该台词文件的地图字段改为 `test9.pcd`，本轮保留该配置并更新对应点位坐标。

### 当前状态

已完成：

- 已确认 `conf/dialogue_1.json` 当前 `map_file` 为 `test9.pcd`。
- 已更新 `point_1_to_2_transition`、`point_2`、`point_3`、`point_3_to_5_transition`、`point_5` 的 `location` 坐标为 test9 图提供值。
- 已确认 `dialogue_1.json` 当前 steps 实际引用上述 5 个点位；未提供新坐标且未被 steps 引用的 `point_1`、`point_4` 本轮未改动。
- 已保留 `dialogue_1.json` 当前已有称呼配置 `variables.leader_calling=各位领导`。

未完成：

- 本轮未启动 workflow、导航桥接或 systemd 服务。
- 本轮未进行真机导航验证。

### 已验证的事实

- `conf/dialogue_1.json` 已通过 `python3 -m json.tool` JSON 格式校验。
- test9 的 5 个点位均已通过字段完整性校验，包含 `x/y/z/ox/oy/oz/ow/mode`。
- `rabbitbot/agno_agents/workflow.py` 已通过 `python3 -m py_compile` 语法检查。

### 阻塞问题

无代码层面阻塞。剩余风险是运行层面尚未验证：需要启动 workflow 后确认日志加载 `dialogue_1.json`、`map_file=test9.pcd`，并确认导航桥接实际使用 test9 对应地图。

### 建议的下一步

- 使用 `RABBITBOT_DIALOGUE_INDEX=1` 或等效配置启动 workflow，确认实际选中 `dialogue_1.json`。
- 启动导航桥接前确认 `NAV_PCD_PATH` 指向 test9 对应地图文件。
- 真机按完整 DOCX 严格剧本跑一遍，重点验证 `1到2过渡`、点位2、点位3、`3到5过渡` 和点位5 的到点精度。

### 注意事项

- `dialogue_1.json` 的 `point_1` 和 `point_4` 坐标仍保留旧值；当前 steps 未引用它们。如后续剧本增加引用或现场需要完整 test9 点位表，应补充这两个点位的新坐标。
- 台词 JSON 修改后需要重启 workflow 才会重新加载。

## 本轮补充：排查 workflow 启动后机器人未移动

### 背景和目标

本轮目标是排查现场刚启动 workflow 后机器人未移动的原因。现场使用 `dialogue_1.json`，该台词文件已配置 `map_file=test9.pcd` 和 test9 点位。

### 当前状态

已完成：

- 已查看最新运行日志：run_id 为 `20260609_110301`，导航桥接日志为 `logs/nav_workflow_control/nav_bridge_20260609_110145.log`，workflow 日志为 `logs/nav_workflow_control/rabbitbot_workflow_20260609_110301.log`。
- 已确认 workflow 侧加载的是 `dialogue_1.json` 的 test9 配置，日志显示 `map_file=test9.pcd`，点位来自台词文件。
- 已确认导航桥接实际启动时仍使用 `/home/unitree/test1.pcd`，与 `dialogue_1.json` 的 `test9.pcd` 不一致。
- 已确认第一段导航请求已发出，目标为 test9 的 `1->2过渡点位`：`x=0.1797, y=-0.1793, ox=0.0022, oy=0.1118, oz=0.0196, ow=0.9935`。
- 已确认导航底层返回 `statusCode=4`、`errorCode=4`、`info=Failed to obtain the current pose information.`，机器人因此没有开始移动，workflow 随后一直轮询到 `status=1, sub=navigating`。
- 已修复 `scripts_1/start_nav_bridge_workflow_loop.sh`：如果未显式设置 `NAV_PCD_PATH`，脚本会从当前台词 JSON 的 `map_file` 自动推导导航地图路径；例如 `RABBITBOT_DIALOGUE_INDEX=1` 会使用 `/home/unitree/test9.pcd`。
- 已保留显式覆盖能力：如果启动时设置了 `NAV_PCD_PATH`，脚本仍优先使用该显式路径。

未完成：

- 本轮未重新启动导航桥接、workflow 或 systemd 服务。
- 本轮未验证 `/home/unitree/test9.pcd` 在导航底层是否可成功重定位。
- 本轮未做真机移动复测。

### 已验证的事实

- `rabbitbot-loop.service` 当前为 `disabled / inactive`，本次不是 systemd 服务启动。
- 当前无 `start_nav_bridge_workflow_loop.sh`、workflow runner、`goGoalNavigation66` 或 28180 监听进程；28182、28184、28185 和 7687 基础服务端口仍在监听。
- 最新导航桥接启动日志显示使用 `/home/unitree/test1.pcd`，并在 test1 上重定位成功，当前位姿约为 `x=0.8586, y=0.1355`。
- 最新 workflow 日志显示加载 `dialogue_1.json` 的 `map_file=test9.pcd` 和 test9 点位。
- `bash -n scripts_1/start_nav_bridge_workflow_loop.sh` 已通过。
- `dialogue_1.json` 的 `map_file` 可解析为 `/home/unitree/test9.pcd`。

### 阻塞问题

无代码层面阻塞。剩余运行风险是：如果导航底层无法读取或重定位 `/home/unitree/test9.pcd`，机器人仍不会移动；需要现场用新脚本重新启动后观察导航桥接启动日志。

### 建议的下一步

- 重新启动 loop 时使用 `RABBITBOT_DIALOGUE_INDEX=1 bash scripts_1/start_nav_bridge_workflow_loop.sh`，不要额外设置旧的 `NAV_PCD_PATH=/home/unitree/test1.pcd`。
- 启动后先确认终端出现 `根据台词文件设置导航地图`，并显示 `map_file=test9.pcd, NAV_PCD_PATH=/home/unitree/test9.pcd`。
- 再确认导航桥接日志中 `Loading map` 和 `start relocation with map` 均为 `/home/unitree/test9.pcd`。
- 如仍出现 `Failed to obtain the current pose information`，优先检查 test9 地图是否可被导航底层读取、当前位置是否能在 test9 地图中完成重定位。

### 注意事项

- 台词文件 `map_file` 与导航桥接实际 `NAV_PCD_PATH` 必须一致；只修改台词 JSON 不会让旧版本脚本自动换地图。
- 新版本脚本只在 `NAV_PCD_PATH` 未显式设置时自动读取台词地图；显式设置仍会覆盖台词地图。
- 当前 workflow 状态文件仍显示 `20260609_110301.status=running`，但对应进程和 28180 已不存在，这是本次中途退出后的陈旧状态；重新启动新 run 时会生成新的 run_id。

### 其它信息

- 本轮新增日志点：loop 启动准备阶段会打印使用显式导航地图，或打印根据台词文件推导出的 `dialogue`、`map_file` 和最终 `NAV_PCD_PATH`。
- 该日志用于快速诊断台词点位与导航桥接地图是否一致。

## 本轮补充：禁用 STT 服务自动启动

### 背景和目标

当前 workflow 已不再需要 STT 语音识别服务（严格 DOCX 剧本已移除全部 STT 问答监听），现场要求 workflow 启动时不再自动拉起 STT 服务（28184），以减少资源占用和无关启动失败风险。

### 当前状态

已完成：

- 新增统一开关 `RABBITBOT_UNIFIED_START_STT`，默认 `0`（不启动 STT）；如确需启动，可显式设置 `RABBITBOT_UNIFIED_START_STT=1`。开关命名和接线方式与已有的 `RABBITBOT_UNIFIED_START_EMBEDDING` 保持一致。
- `scripts_1/unified_runtime/start_unified_container.sh`：新增开关默认值；`start_stt()` 顶部增加跳过守卫，开关非 `1` 时打印跳过日志并直接返回，不再启动 STT、不再等待 28184；同步更新文件头注释。
- `scripts_1/start_unified_integration_workflow.sh`：新增开关默认值与头部注释；基础服务等待阶段对 STT(28184) 改为条件等待，开关非 `1` 时打印跳过日志；`ensure_compatible_container` 新增 STT 开关比较项，开关变化时触发容器重建；docker run 时通过 `-e RABBITBOT_UNIFIED_START_STT` 透传到容器内。
- `scripts_1/start_nav_bridge_workflow_loop.sh`：新增开关默认值；基础服务健康检查 `base_services_health_ok` 中 STT(28184) 改为仅在开关为 `1` 时才检查，避免关闭 STT 后健康检查误判为不健康并触发误重启；调用集成脚本时透传 `RABBITBOT_UNIFIED_START_STT`。
- `scripts/start_all_services.sh`（旧版全量启动入口）：新增开关默认值；主流程 `start_stt` 调用改为条件执行，开关非 `1` 时打印跳过日志，避免 STT 从该旧入口回流。

未完成：

- 本轮只做脚本改造和静态检查，未在真机/容器中实际重启 workflow 验证（避免中断现场可能正在运行的服务）。

### 已验证的事实

- 已确认 workflow 不会因关闭 STT 服务而在初始化阶段失败：`rabbitbot/context.py` 中 `self.stt_agent = create_stt_agent()`，而 `rabbitbot/provider.py` 的 `create_stt_agent()` 仅构造 `STTAgent(host_url)` 对象、保存 URL，不在构造时连接 28184；STT 客户端为懒连接，只有真正触发监听时才请求服务，而严格 DOCX 剧本已不再触发监听。
- 4 个脚本均通过 `bash -n` 语法检查。
- 本轮补丁脚本对每处替换做命中次数断言（期望命中 1 次），全部精确命中：container 3 处、integration 7 处、navloop 3 处、all_services 2 处。

### 阻塞问题

无代码层面阻塞。当前运行中的容器若是在本次改动前创建并已启动 STT，本次脚本改动不会主动停止已在运行的 STT 进程；如需让已运行实例也不再有 STT，可用 `RECREATE_CONTAINER=1`（开关比较会因 STT 配置变化自动触发重建）重建容器，或手动停止 STT 进程。

### 建议的下一步

- 下次重启统一服务时无需额外设置即默认不启动 STT；如临时需要 STT，整链路设置 `RABBITBOT_UNIFIED_START_STT=1` 后再启动。
- 启动后确认终端出现 `RABBITBOT_UNIFIED_START_STT=0，跳过 STT` 日志，并确认 28184 未被监听、workflow 仍正常进入开场。

### 注意事项

- `RABBITBOT_UNIFIED_START_STT` 默认 `0`；该开关同时影响统一容器入口、联调编排脚本、导航 loop 健康检查和旧版全量启动脚本，四处行为一致。
- 关闭 STT 后，导航 loop 的基础服务健康检查不再包含 STT(28184)，因此 STT 缺失不会再触发健康检查失败或服务自动恢复。
- 本轮新增/调整日志点：四处启动路径在跳过 STT 时均打印 `RABBITBOT_UNIFIED_START_STT=0，跳过 STT ...` 或 `跳过等待 STT 服务 (28184)`，用于现场快速确认 STT 确实未启动且为预期行为。

## 本轮补充：back 返航点位支持台词文件配置

### 背景和目标

本轮目标是按现场要求让 `back` 返航点位也支持写入 `conf/dialogue_<序号>.json` 台词文件；如果台词文件没有显式配置返航点位，则导航 loop 按当前台词 `steps[].entity_key` 对应的 go 点位序列反向生成返航路线。

### 当前状态

已完成：

- 已在 `scripts_1/start_nav_bridge_workflow_loop.sh` 中新增 `read_dialogue_back_route()`，用于读取当前台词 JSON 的顶层 `back_points`。
- `back_points` 支持字符串数组引用 `points` 键，也支持对象数组直接写 `name` 和 `location`，或通过 `point_key` / `entity_key` 引用 `points`。
- 未配置或配置为空数组时，脚本会从 `steps[].entity_key` 提取 go 点位，去掉连续重复点位，再反向生成返航序列；如果 `points` 中存在 `point_1`，会补为最终起点。
- 返航发送给 28180 的坐标统一使用六元组 `(x, y, ox, oy, oz, ow)`，从台词 `location` 中自动忽略 `z` 和 `mode`。
- 如果读取台词返航配置失败，脚本会记录失败原因，并回退到原有环境变量返航点位 `POINT_5_TASK -> BACK_POINT_1_TASK -> BACK_POINT_2_TASK -> START_POINT_TASK`。
- 已更新 `conf/README.md`，说明 `back_points` 字段、两种配置写法、默认反序策略和 28180 六元组格式。

未完成：

- 本轮未启动导航桥接、workflow、systemd 服务或容器，未触发机器人移动。
- 本轮未在真机上验证实际 `back` 返航路径。

### 已验证的事实

- `bash -n scripts_1/start_nav_bridge_workflow_loop.sh` 通过。
- 使用当前 `conf/dialogue_1.json` 做只读解析验证时，未配置 `back_points` 会输出 `reverse_go_points`，路线为：点位5 -> 3->5过渡点位 -> 点位3 -> 点位2 -> 1->2过渡点位 -> 点位1。
- 使用临时台词 JSON 显式设置 `back_points=["point_5", "point_3", "point_1"]` 时，只读解析验证输出 `dialogue_back_points`，并按显式配置生成三段返航路线。

### 阻塞问题

无代码层面阻塞。剩余风险是运行层面尚未验证：需要现场重启新版本 loop 后发送 `back`，确认 28180 接收的目标点位、地图和机器人实际移动路线一致。

### 建议的下一步

- 如需自定义返航路线，可在当前台词 JSON 顶层增加 `back_points`，优先使用字符串数组引用 `points` 键，避免复制坐标造成 go/back 不一致。
- 现场重启 `scripts_1/start_nav_bridge_workflow_loop.sh` 后，观察返航开始日志中的 `source`、`dialogue`、`segments` 和 `route`，确认是 `dialogue_back_points` 还是 `reverse_go_points`。
- 真机验证时重点确认 `dialogue_1.json` / `test9.pcd` 下默认反序路线是否符合现场回程动线；如果默认反序不适合现场，可在 `dialogue_1.json` 中显式写 `back_points`。

### 注意事项

- `back_points` 修改后需要重启导航 loop 才会重新读取台词文件；已运行的旧 loop 实例不会热更新。
- 返航点位读取依赖台词文件 `points`，因此 `points` 中引用的 `location` 至少要有一组完整坐标。
- `back_points` 写错类型、引用不存在的 point key、坐标字段缺失或字段非数字时，脚本会记录错误并回退到原有环境变量兜底返航点。

### 其它信息

- 本轮新增/调整的日志点包括：返航开始时打印返航来源、台词文件路径、分段数和完整路线；读取台词返航配置失败时打印失败原因和兜底来源；最终目标日志打印最后一段返航目标。
- 这些日志用于排查现场到底使用了台词显式返航点、go 点位反序，还是因配置错误回退到了旧环境变量点位。

## 本轮补充：dialogue_fuxing 增加显式返航点位

### 背景和目标

本轮目标是按现场要求更新备份台词文件 `conf/dialogue_fuxing.json`：该文件由原始 0 号台词复制而来，用于复星原始路线备份；历史返航点位曾写在脚本环境变量中，但没有进入台词文件，本轮需要补入台词 JSON。

### 当前状态

已完成：

- 已在 `conf/dialogue_fuxing.json` 顶层新增 `back_points`。
- 返航路线配置为 `点位5 -> 返回点1 -> 返回点2 -> 点位1`。
- `返回点1` 坐标为 `(6.4327, 8.2585, 0.0505, 0.0827, 0.5996, -0.7944)`。
- `返回点2` 坐标为 `(9.8023, -3.1366, -0.0442, 0.0674, 0.9944, 0.0684)`。
- `点位5` 和 `点位1` 通过 `point_key` 引用台词文件已有 `points`，避免复制已有 go 点位坐标。

未完成：

- 本轮未启动 workflow、导航桥接、systemd 服务或容器。
- 本轮未发送 `go/back`，未触发机器人移动。

### 已验证的事实

- `python3 -m json.tool conf/dialogue_fuxing.json` 通过。
- 使用 `start_nav_bridge_workflow_loop.sh` 的 `read_dialogue_back_route` 只读解析 `conf/dialogue_fuxing.json`，输出来源为 `dialogue_back_points`，路线为点位5、返回点1、返回点2、点位1。
- `conf/dialogue_fuxing.json` 当前不被 Git 忽略，可纳入提交。

### 阻塞问题

无代码层面阻塞。剩余风险是运行层面尚未真机验证返航路线。

### 建议的下一步

- 如需使用该备份台词启动 workflow，设置 `RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE=/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master/conf/dialogue_fuxing.json` 或容器内对应路径。
- 真机验证时观察返航开始日志，确认 `source=dialogue_back_points` 且路线为 `点位5 -> 返回点1 -> 返回点2 -> 点位1`。

### 注意事项

- `back_points` 修改后需要重启导航 loop 才会被新预启动 workflow/返航逻辑读取。
- 返回点1、返回点2是 28180 直接接口六元组格式，不包含 workflow go 点位中的 `z` 和 `mode`。

## 本轮补充：接手阅读与状态确认

### 背景和目标

本轮目标是按 Aaron 要求读取 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master/HANDOFF_REPORT.md`，接手当前 `rabbitbot-dev-ros2-master` 项目状态，并确认后续应优先关注的运行风险。

### 当前状态

已完成：

- 已完整读取当前交接报告，确认最近工作集中在导航 workflow loop、台词 JSON 点位配置、test9 地图切换、默认关闭 STT、返航路线支持台词配置，以及 `dialogue_fuxing.json` 显式返航点位。
- 已确认远端 Git 分支为 `June6_workflow`，读取前工作区干净。
- 已确认最新提交为 `dc398ae fix: ignore future log files in console status`。

未完成：

- 本轮未启动 workflow、导航桥接、systemd 服务或容器。
- 本轮未发送 `go/back`，未触发机器人移动或语音播报。
- 本轮未修改业务代码或运行脚本。

### 已验证的事实

- 交接报告中最新风险点仍是运行验证类风险：`dialogue_1.json` 的 `map_file=test9.pcd` 需要与导航桥接实际 `NAV_PCD_PATH=/home/unitree/test9.pcd` 保持一致。
- `RABBITBOT_UNIFIED_START_STT` 当前默认应为 `0`，严格 DOCX 剧本不依赖 STT 服务启动。
- `back_points` 已支持从台词 JSON 读取；未配置时会按 go 点位反序生成返航路线。
- `conf/dialogue_fuxing.json` 已配置显式返航路线：点位5、返回点1、返回点2、点位1。

### 阻塞问题

无接手层面的阻塞。本轮未进行真机或服务重启验证，因此运行层面的剩余风险仍以原交接报告记录为准。

### 建议的下一步

- 如需继续验证 test9 路线，优先使用 `RABBITBOT_DIALOGUE_INDEX=1 bash scripts_1/start_nav_bridge_workflow_loop.sh`，并确认日志打印 `map_file=test9.pcd` 和 `NAV_PCD_PATH=/home/unitree/test9.pcd`。
- 如需验证返航，重启新版本 loop 后观察返航开始日志中的 `source`、`dialogue`、`segments` 和 `route`，确认实际使用台词显式返航点或 go 点位反序路线。
- 如需让当前运行实例关闭 STT，需要重建容器或手动停止旧 STT 进程；脚本改动不会热更新已运行容器。

### 注意事项

- 本轮只进行了只读接手和交接报告更新；没有更改日志逻辑、服务配置或台词内容。
- 后续任何台词 JSON、地图、导航脚本或服务启动逻辑变更后，仍需同步更新本交接报告并提交。

### 其它信息

- 本轮没有新增或调整代码日志点；仅确认已有交接报告中记录的关键日志点，包括台词文件地图/点位加载日志、导航 loop 地图推导日志、返航来源与路线日志、STT 跳过日志。

## 本轮补充：HaiSong-orin 迁移恢复完成

### 背景和目标

本轮目标是将 AGX-orin 通过移动硬盘准备好的 RabbitBot 离线迁移包恢复到 `HaiSong-orin`，使目标机具备运行 `rabbitbot-dev-ros2-master`、导航桥接、统一容器基础服务和控制台所需的项目目录与宿主运行时依赖。

### 当前状态

已完成：

- 已在 `HaiSong-orin` 上识别移动硬盘 `/dev/sda1`，文件系统为 exFAT，标签为 `PortableSSD`。
- 已通过 `exfat-fuse` 将移动硬盘挂载到 `/media/pc/PortableSSD`。
- 已定位迁移包目录：`/media/pc/PortableSSD/rabbitbot_orin_migration_20260609_125551`。
- 已在目标机移动硬盘挂载点执行 `sha256sum -c SHA256SUMS`，所有文件均为 `OK`。
- 已执行迁移包内 `restore_on_target.sh`，完成 `/mnt/ssd/navgation/projects`、`/opt/ros/humble`、`/home/pc/.local`、`/usr/local/lib/libddsc*`、`/usr/local/lib/libddscxx*` 和 rabbitbot systemd 服务文件恢复。
- 已执行恢复脚本中的 `sudo ldconfig` 和 `sudo systemctl daemon-reload`。
- 已确认 `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 均已加载，但保持 `disabled / inactive`，本轮未启动服务。
- 已安全卸载移动硬盘 `/media/pc/PortableSSD`，当前 `/dev/sda1` 无挂载点，可物理拔出。

未完成：

- 本轮未启动 `rabbitbot-loop.service`、`rabbitbot-control-console.service` 或统一容器，避免在未确认现场网络、地图和机器人连接前触发导航或播报。
- 本轮未迁移 AGX-orin 上的 Neo4j Docker 卷运行数据；该数据不是启动依赖，如需历史记忆数据需从 AGX-orin 停容器后单独打包迁移。
- 本轮未做真机导航、TTS、控制台访问或完整 workflow 验证。

### 已验证的事实

- `HaiSong-orin` 上 `/mnt/ssd/navgation/projects` 已恢复，大小约 12G。
- `/opt/ros/humble` 已恢复，大小约 190M。
- `/home/pc/.local` 已恢复，大小约 1.1G。
- `rabbitbot-unified-runtime:20260518` 镜像已存在。
- Python/ROS 导入检查通过：`uvicorn`、`fastapi`、`rclpy`、`custom_action_interfaces` 均可定位到恢复后的路径。
- DDS 动态库检查通过：`/usr/local/lib/libddsc.so`、`libddsc.so.0`、`libddscxx.so`、`libddscxx.so.0` 均存在，`ldconfig -p` 可查询到 `libddsc` 和 `libddscxx`。
- 导航和手臂二进制在 source `/opt/ros/humble/setup.bash` 与 `custom_action_ws/install/setup.bash` 后执行 `ldd`，未发现 `not found` 动态库。
- 脚本语法检查通过：`scripts_1/start_nav_bridge_workflow_loop.sh`、`scripts_1/start_control_console.sh`、`scripts_1/start_unified_integration_workflow.sh`、`scripts_1/unified_runtime/start_unified_container.sh`。
- Python 编译检查通过：`rabbitbot/agno_agents/workflow.py`、`rabbitbot/control_console/app.py`、`scripts/run_kuavo_agno_workflow.py`。
- 当前 28180、28182、28184、28185、8080、7687 等关键端口未监听，符合本轮未启动服务的预期。
- 目标机 `/mnt/ssd` 恢复后仍约有 688G 可用空间。

### 阻塞问题

无迁移恢复层面的阻塞。剩余工作是运行验证和现场配置确认，包括网卡、机器人连接、地图路径、音频设备和是否需要 Neo4j 历史数据。

### 建议的下一步

- 确认 HaiSong-orin 与机器人本体网络连通，尤其是导航和 Unitree G1 相关网卡名是否仍为 `eno1`。
- 确认现场期望使用的台词文件和地图：若使用 `dialogue_1.json`，需确认机器人本体侧 `/home/unitree/test9.pcd` 可用。
- 先手动启动或临时启动控制台服务验证页面与状态接口，再决定是否 `enable` 开机自启。
- 如需验证导览 loop，先保持服务 `disabled`，使用前台命令启动，观察日志确认只进入待命，再发送 `go/back`。
- 如需迁移 Neo4j 历史记忆数据，应回到 AGX-orin 停止 `rabbitbot-unified-runtime` 后打包并在 HaiSong-orin 恢复对应 Docker 卷。

### 注意事项

- 本轮恢复脚本默认不会自动启动服务，这是刻意保守处理，避免目标机一恢复就触发机器人动作或播报。
- `/home/unitree` 是机器人本体侧路径，不是 Orin 主机侧目录；HaiSong-orin 主机上没有该目录并不代表迁移缺文件。
- 当前仓库来自迁移包生成时的快照；AGX-orin 上迁移包生成后新增的“复制到移动硬盘”和“安全卸载”两条文档提交没有包含在 tar 内，本节已在目标机记录实际恢复结果。
- 如果后续要保持两台 Orin 的 Git 历史完全一致，可从 AGX-orin cherry-pick 或导入后续文档提交；当前目标机已具备运行所需文件和依赖。

### 其它信息

- 本轮没有修改业务代码或运行脚本，因此没有新增代码日志点。
- 本轮新增的交接信息记录了迁移恢复阶段、验证结果、服务未启动状态和剩余运行验证事项，可用于后续接手定位迁移完成范围。

## 本轮补充：HaiSong-orin rabbitbot 服务与 workflow loop 启动验证

### 背景和目标

本轮目标是在 `HaiSong-orin` 尚未接入机器人本体的情况下，尽可能验证迁移后的 `rabbitbot-control-console.service` 和 `rabbitbot-loop.service` 是否具备正常启动能力；验证过程中不发送 `go/back` 命令，避免触发导览剧本或机器人动作。

### 当前状态

已完成：

- 已实测 `rabbitbot-control-console.service`：systemd 可启动，`http://127.0.0.1:8080/api/status` 返回 HTTP 200；测试后已停止，当前保持 `inactive`。
- 首次启动 `rabbitbot-loop.service` 时发现根分区 `/` 100% 满，导致脚本无法创建 `/tmp/rabbitbot_nav_workflow_control`，报 `No space left on device`。
- 已定位根分区占用来源为旧 Docker 备份目录 `/var/lib/docker.bak`，约 16G；当前 Docker Root Dir 已是 `/mnt/ssd/docker-data`，该旧目录不再是 Docker 当前运行目录。
- 已将 `/var/lib/docker.bak` 移动到 `/mnt/ssd/docker.bak_from_root_20260610_101918` 保留备份，根分区从 100% 降到约 72%，`/tmp` 写入恢复正常。
- 第二次启动 `rabbitbot-loop.service` 时发现 ROS 运行时缺少系统动态库 `libspdlog.so.1` 和 `libfmt.so.8`；已从 AGX-orin 复制并安装到 `/usr/lib/aarch64-linux-gnu`，执行 `ldconfig` 后 `rclpy` 可导入。
- 第三次启动时发现 RMW 初始化缺少 `libtinyxml2.so.9`，导致 `librmw_fastrtps_cpp.so` 无法加载；已从 AGX-orin 复制并安装 `libtinyxml2.so*`，执行 `ldconfig` 后 `rclpy.init()` 和显式 `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` 初始化均通过。
- 最终复测 `rabbitbot-loop.service` 成功进入待命路径：28180 导航桥接启动，unified 容器基础服务启动，Neo4j(7687)、TTS(28185)、Memory(28182)、Robot Agent(28180) 均就绪，workflow 预启动并停在 `go` 闸门，run_id 为 `20260610_103325`。
- 本轮没有发送 `go` 或 `back` 命令。
- 测试结束后已停止 `rabbitbot-loop.service`，停止 `rabbitbot-unified-runtime` 容器，并确认 28180、28182、28184、28185、8080、7687、8000、8005 等关键端口均无监听。

未完成：

- 由于 HaiSong-orin 尚未接入机器人本体，未验证真实导航、重定位、Unitree DDS 通信、TTS 播报到机器人或动作执行。
- 未验证 `go` 后完整 workflow 运行，也未验证 `back` 返航。

### 已验证的事实

- `wlP1p1s0` 当前为管理网络，IP 为 `192.168.101.90/24`；`eno1` 当前 `DOWN`，尚未接机器人本体网络。
- loop 启动日志中 `goGoalNavigation66` 明确提示 `eno1: does not match an available interface`，这是未接机器人/网卡未起来导致；但 28180 FastAPI bridge 仍可启动并响应 `/go_to_status`。
- `rabbitbot-loop.service` 在修复主机依赖后能完成以下阶段：创建控制目录、启动导航桥接、启动 unified 基础服务、等待基础服务端口、预启动 workflow、等待 `go` 闸门。
- `RABBITBOT_UNIFIED_START_STT=0` 生效，STT(28184) 未被启动或等待。
- VLM(8000) 和 Embedding(8005) 默认跳过等待，符合当前脚本配置。
- 测试结束后的当前状态：`rabbitbot-loop.service inactive`、`rabbitbot-control-console.service inactive`、`rabbitbot-unified-runtime Exited`、关键端口无监听。

### 阻塞问题

无主机依赖层面的阻塞。剩余阻塞是现场硬件连接：`eno1` 未连接机器人本体网络时，导航节点会因 DDS 域创建失败或接口不可用而退出；接入机器人并确认 `eno1` UP 后需要重新验证。

### 建议的下一步

- 接入机器人本体后，先确认 `ip -br addr` 中 `eno1` 为 UP，并具有机器人通信网段地址。
- 前台启动 `rabbitbot-loop.service` 或直接运行 `scripts_1/start_nav_bridge_workflow_loop.sh`，观察是否还出现 `eno1: does not match an available interface`。
- 确认 28180 可用后，再验证 `go` 闸门释放、第一句 TTS、导航首段和 `back` 返航。
- 如果需要保留更干净的目标机，可后续确认 `/mnt/ssd/docker.bak_from_root_20260610_101918` 无用后再删除；本轮仅移动保留，未删除该旧 Docker 备份。

### 注意事项

- 本轮向 HaiSong-orin 补装了项目迁移包漏掉的宿主系统库：`libspdlog.so*`、`libfmt.so*` 和 `libtinyxml2.so*`，均来自 AGX-orin 的 `/usr/lib/aarch64-linux-gnu`。
- 本轮在 `/mnt/ssd` 留有小型临时库包和维护脚本：`rabbitbot_humble_extra_libs.tar`、`rabbitbot_tinyxml2_lib.tar`、`move_docker_backup_from_root.sh`；它们不是运行必需文件，可在确认不再需要后清理。
- 控制台 `/api/status` 可能显示迁移过来的旧 workflow/pose 日志快照，不能单独作为当前 loop 正在运行或已定位的证据，应结合 systemd、端口和最新日志判断。

### 其它信息

- 本轮没有修改业务代码或运行脚本，因此没有新增代码日志点。
- 本轮系统层面的关键诊断日志来自 systemd journal、loop 启动日志和导航桥接日志；这些日志已明确覆盖 `/tmp` 创建失败、ROS 动态库缺失、RMW 初始化失败、基础服务启动、workflow 预启动和最终清理状态。

## 本轮补充：判断 `/home/nvidia/rabbitbot-dev-ros2` 是否为旧项目

### 背景和目标

本轮目标是按 Aaron 要求判断 HaiSong-orin 根分区中的 `/home/nvidia/rabbitbot-dev-ros2` 是否为旧项目，避免误删当前迁移后的 RabbitBot 运行目录。

### 当前状态

已完成：

- 已只读检查 `/home/nvidia/rabbitbot-dev-ros2` 的目录结构、大小、Git 信息、大文件和系统引用。
- 已确认该目录大小约 18G，主要占用来自 `data/models` 下的 Qwen3 reranker 模型文件。
- 已确认该目录是 Git 仓库，分支为 `master`，远端为 `git@github.com:air-embodied-brain/rabbitbot-dev-ros2.git`。
- 已确认该目录最新提交为 `7c60570 feat(tools): add accuracy calculation script V2`，提交时间为 2026-03-22。
- 已确认该目录存在本地未提交改动：`rabbitbot/provider.py`、`scripts/prepare_vllm_docker.sh`、`scripts/start_stt_app.bash`、`scripts/start_tts_app.bash`，以及未跟踪目录 `docker_files/`。
- 已确认当前迁移后的运行项目为 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`，分支为 `June6_workflow`，最新提交为本轮 HaiSong 迁移与服务验证记录。
- 已确认当前 rabbitbot systemd 服务和统一容器不引用 `/home/nvidia/rabbitbot-dev-ros2`。
- 已确认仅有两个 6 周前退出的旧 Docker 容器引用该目录：`foxy-ros-cam-orb-ubuntu20` 和 `navid-vllm-cuda-mic`。

未完成：

- 本轮未删除、移动或归档 `/home/nvidia/rabbitbot-dev-ros2`。
- 本轮未删除引用该目录的旧 Docker 容器。

### 已验证的事实

- `/home/nvidia/rabbitbot-dev-ros2` 与当前项目路径、分支、提交历史和最近修改时间均不同。
- 该旧目录的代码主要停留在 2026-04-27 前后；当前迁移项目包含 2026-06 的 workflow loop、控制台、台词 JSON 点位和服务验证记录。
- 旧目录 `data/models/config.json` 显示模型架构为 `Qwen3ForCausalLM`，`model_type=qwen3`，README 指向 `Qwen3-Reranker-0.6B`。
- 旧目录中最大的文件为 `data/models/model-00001-of-00005.safetensors` 到 `model-00005-of-00005.safetensors` 以及 `model.safetensors`，合计约 17G。

### 阻塞问题

无判断层面的阻塞。是否清理该目录需要 Aaron 明确确认，因为它包含旧容器可能使用的模型和本地未提交改动。

### 建议的下一步

- 若确认不再需要旧 VLLM/旧容器环境，可先将 `/home/nvidia/rabbitbot-dev-ros2` 移到 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_YYYYMMDD` 归档，确认无问题后再删除。
- 在删除旧目录前，建议同步处理或记录旧容器 `foxy-ros-cam-orb-ubuntu20` 和 `navid-vllm-cuda-mic`，因为它们仍挂载该路径。
- 如果只想快速释放根分区空间，优先归档或删除该旧目录的 `data/models`，但删除前应确认 Qwen3 reranker 模型不再被旧容器或其它实验使用。

### 注意事项

- 当前 RabbitBot 正式运行目录是 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`，不要与 `/home/nvidia/rabbitbot-dev-ros2` 混用。
- `/home/nvidia/rabbitbot-dev-ros2` 不是本轮移动硬盘迁移恢复出来的目录，它是目标机原有旧内容。

### 其它信息

- 本轮没有修改业务代码或运行脚本，因此没有新增代码日志点。

## 本轮补充：旧 `/home/nvidia/rabbitbot-dev-ros2` 已归档并从根分区移除

### 背景和目标

本轮目标是按 Aaron 要求，将 HaiSong-orin 根分区中的旧项目 `/home/nvidia/rabbitbot-dev-ros2` 移动到 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322`，释放根分区空间，并确保当前正式项目不受影响。

### 当前状态

已完成：

- 已确认归档目标 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322` 原先不存在。
- 已使用 sudo 将 `/home/nvidia/rabbitbot-dev-ros2` 移动到 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322`。
- 已执行 `sync`，确保移动后的写入落盘。
- 已复查 `/home/nvidia/rabbitbot-dev-ros2` 当前已不存在。
- 已复查归档目录存在，大小约 18G，权限仍为 `nvidia:nvidia`。
- 根分区 `/` 使用率从约 71% 降到约 40%，可用空间约 33G。
- `/mnt/ssd` 使用率约 27%，可用空间约 637G。
- 已确认当前 `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 均为 `inactive`，关键端口无监听。

未完成：

- 本轮未删除归档目录 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322`。
- 本轮未删除仍引用旧路径的退出态旧 Docker 容器。

### 已验证的事实

- 当前正式 RabbitBot 项目仍为 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`。
- 旧目录移动后，两个 6 周前退出的旧容器 `foxy-ros-cam-orb-ubuntu20` 和 `navid-vllm-cuda-mic` 的 Docker 配置仍然挂载源路径 `/home/nvidia/rabbitbot-dev-ros2`。
- 因为旧源路径已不存在，后续如果直接启动这些旧容器，可能会失败，或由 Docker 自动创建空目录作为挂载源；如需继续使用旧容器，应先调整挂载路径到归档目录或重新创建容器。

### 阻塞问题

无当前正式项目运行层面的阻塞。唯一注意点是旧容器引用路径已失效，但这些旧容器不是当前 RabbitBot 正式服务链路的一部分。

### 建议的下一步

- 如果后续确认不再需要旧容器，可删除 `foxy-ros-cam-orb-ubuntu20` 和 `navid-vllm-cuda-mic`，避免误启动创建空目录。
- 如果后续确认旧模型和旧项目完全不需要，可再删除 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322` 释放 `/mnt/ssd` 空间。
- 当前不要再使用 `/home/nvidia/rabbitbot-dev-ros2` 作为项目路径；正式路径为 `/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master`。

### 注意事项

- 本轮执行的是移动归档，不是直接删除；旧项目和模型仍保留在 `/mnt/ssd/archive_home_nvidia_rabbitbot-dev-ros2_20260322`。
- 本轮没有修改业务代码或运行脚本，因此没有新增代码日志点。

### 其它信息

- 本轮使用的一次性维护脚本为 `/mnt/ssd/archive_old_home_nvidia_rabbitbot.sh`，可在确认不再需要后清理。

## 本轮补充：rabbitbot 系统服务保持非开机自启

### 背景和目标

本轮目标是按 Aaron 要求，将 HaiSong-orin 上 rabbitbot 相关 systemd 服务都先设为非开机自启，避免目标机开机后在未确认现场网络、地图和机器人连接前自动启动控制台或 workflow loop。

### 当前状态

已完成：

- 已列出 HaiSong-orin 上 rabbitbot 相关 unit files，当前仅有 `rabbitbot-loop.service` 和 `rabbitbot-control-console.service`。
- 已显式执行 `systemctl disable rabbitbot-loop.service rabbitbot-control-console.service`。
- 已执行 `systemctl daemon-reload`。
- 已复查两个服务均为 `disabled / inactive / inactive`。
- 已复查 `/etc/systemd/system/*wants*` 下没有 rabbitbot 相关开机自启链接。
- 已复查 28180、28182、28184、28185、8080、7687、8000、8005 等关键端口无监听。

未完成：

- 本轮未启动任何 rabbitbot 服务。
- 本轮未修改服务文件内容。

### 已验证的事实

- `rabbitbot-loop.service`：`is-enabled=disabled`、`is-active=inactive`、`is-failed=inactive`。
- `rabbitbot-control-console.service`：`is-enabled=disabled`、`is-active=inactive`、`is-failed=inactive`。

### 阻塞问题

无。

### 建议的下一步

- 接入机器人并确认现场条件后，如需临时测试，优先使用 `sudo systemctl start rabbitbot-control-console.service` 或前台手动运行脚本，不要先 enable 开机自启。
- 若后续确认需要开机自启，再显式执行 `sudo systemctl enable rabbitbot-loop.service rabbitbot-control-console.service`。

### 注意事项

- 本轮只是禁用开机自启和状态确认，不影响服务文件本身；服务仍可手动启动。
- 本轮没有修改业务代码或运行脚本，因此没有新增代码日志点。

## 本轮补充：导航桥接 DDS 接口失败诊断

### 背景和目标

Aaron 手动前台运行 `scripts_1/start_nav_bridge_workflow_loop.sh` 后，`goGoalNavigation66` 和 `g1ArmOfficialActionServer` 启动即崩溃，日志提示 `eno1: does not match an available interface`，因此本轮目标是判断导航桥接失败原因，不修改现场网络配置。

### 当前状态

已完成：

- 已查看本次运行目录 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/run_logs/nav_arm_bridge_20260610_144227`。
- 已确认 `01_goGoalNavigation66.log` 和 `02_g1ArmOfficialActionServer.log` 均在 CycloneDDS 创建 domain 时失败。
- 已确认 28180 的 `humble_robot_agent_bridge` 可以正常启动并监听；失败集中在直接连接 Unitree DDS 的两个原生节点。
- 已确认 `scripts_1/start_nav_bridge_workflow_loop.sh` 调用底层脚本时使用 `eno1` 和 `/home/unitree/test9.pcd`。
- 已确认底层 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/start_nav_arm_bridge.sh` 将 `eno1` 原样传给 `goGoalNavigation66` 与 `g1ArmOfficialActionServer`。
- 已查看 HaiSong-orin 当前网络状态：`eno1` 存在且内核链路状态为 `UP/LOWER_UP`，但没有 IPv4/IPv6 地址；NetworkManager 显示 `eno1` 为 `ethernet:disconnected`。
- 已确认 `/home/unitree/test9.pcd` 在 HaiSong 当前 shell 不可见，脚本也打印了对应 warning；但本次两个原生节点是在 DDS domain 创建阶段失败，早于地图文件实际使用路径，因此当前首要问题不是 PCD 文件读取。

未完成：

- 本轮未配置 `eno1` 静态 IP。
- 本轮未重启 workflow loop 或 systemd 服务。
- 本轮未接入机器人侧网络做联机验证。
- 因 AGX 当前未上电，本轮未能对比 AGX 原机的有线网口配置。

### 已验证的事实

- 失败日志完全一致：`eno1: does not match an available interface`，随后抛出 `unitree::common::DdsException`，CycloneDDS 报 `Failed to create domain explicitly`。
- HaiSong 当前只有 Wi-Fi `wlP1p1s0` 持有地址 `192.168.101.90/24`；`eno1` 无地址、无路由。
- `eno1` 虽然有 carrier，但没有被 NetworkManager 绑定到可用连接配置，CycloneDDS/Unitree SDK 因此没有把它作为可用 DDS 接口。
- `start_nav_arm_bridge.sh` 中 28180 bridge 与 DDS 原生节点是分开启动的；28180 端口 ready 只能说明 Python HTTP bridge 可用，不能说明 Unitree 导航和手臂 DDS 节点可用。

### 阻塞问题

当前阻塞是机器人 DDS 通信网口未就绪：`eno1` 没有地址且 NetworkManager 处于 disconnected，导致 Unitree DDS 节点无法在指定接口上创建 domain。HaiSong 未接入机器人或未配置机器人侧静态网段时，不能完成真实导航/手臂联机验证。

### 建议的下一步

- 将 HaiSong 接到机器人网络后，先确认 `eno1` 获得或配置为机器人 DDS 所需网段地址，再运行导航桥接。
- 如果机器人网络没有 DHCP，应按现场 Unitree/AGX 原配置为 `eno1` 添加静态 IPv4 地址；AGX 上电后可优先复制 AGX 的 NetworkManager 连接配置，避免猜测网段。
- 复测时先单独运行 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/start_nav_arm_bridge.sh eno1 /home/unitree/test9.pcd`，确认 `01_goGoalNavigation66.log` 与 `02_g1ArmOfficialActionServer.log` 不再出现 DDS domain 创建失败，再启动完整 workflow loop。
- 复测时不要只看 28180 是否 ready；还需要检查两个原生节点 pid 是否仍存活，以及对应日志中是否完成 DDS 初始化。

### 注意事项

- `/home/unitree/test9.pcd` 属于机器人侧目录。HaiSong 未接机器人时该路径不可见是预期现象之一，但本次崩溃发生在 DDS 接口选择阶段，优先处理网络接口。
- 本轮没有修改业务代码、脚本或服务文件，因此没有新增代码日志点；诊断信息已记录在交接报告中。

### 其它信息

- 本轮检查时 `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 仍保持非开机自启状态。
- 本轮未清理运行日志，后续可继续查看 `latest_nav_arm_bridge` 指向的失败日志目录。

## 本轮补充：清理手动启动遗留的统一容器

### 背景和目标

在诊断导航桥接问题后复查运行状态，发现 systemd 服务仍为 `disabled/inactive`，但 Aaron 手动运行 workflow loop 后遗留了 `rabbitbot-unified-runtime` 容器，容器内 Neo4j、TTS、Memory 和 Robot Agent 仍占用端口。因此本轮目标是恢复到不运行 rabbitbot 后台服务的状态。

### 当前状态

已完成：

- 已确认遗留进程来自 `rabbitbot-unified-runtime` 容器，不是 systemd 自启动。
- 已停止 `rabbitbot-unified-runtime` 容器。
- 已复查当前 `docker ps` 无运行容器。
- 已复查 `rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 仍为 `disabled/inactive`。
- 已复查 28180、28182、28184、28185、8080、7687、8000、8005 等关键端口无监听输出。

未完成：

- 本轮未删除容器、镜像或运行日志。
- 本轮未修改 systemd unit 文件。

### 已验证的事实

- 手动启动脚本即使被终止，也可能留下统一容器继续运行并占用基础服务端口。
- 停止容器后，当前 HaiSong-orin 上没有运行中的 rabbitbot 相关 systemd 服务或统一容器。

### 阻塞问题

无新增阻塞。导航桥接的真实阻塞仍是 `eno1` 未配置为可用 DDS 接口。

### 建议的下一步

- 后续手动测试 workflow loop 后，应复查 `docker ps` 和关键端口，必要时停止 `rabbitbot-unified-runtime`。
- 接入机器人网络并解决 `eno1` 地址配置后，再重新启动导航桥接验证。

### 注意事项

- 本轮没有修改业务代码，因此没有新增代码日志点。
- 本轮状态清理只停止运行中的容器，不影响已迁移镜像和项目文件。

## 本轮补充：修复 HaiSong 导航桥接断开问题

### 背景和目标

Aaron 在 HaiSong-orin 上手动运行 `scripts_1/start_nav_bridge_workflow_loop.sh` 时，底层导航桥接的 `goGoalNavigation66` 和 `g1ArmOfficialActionServer` 因 `eno1: does not match an available interface` 退出，完整 workflow loop 虽然能看到 28180 bridge ready，但原生 DDS 节点实际不可用。本轮目标是对比 AGX 原机配置并修复 HaiSong 的导航桥接启动链路。

### 当前状态

已完成：

- AGX 已上电后，已读取 AGX 原机 `Wired connection 1` 配置：绑定 `eno1`，IPv4 为手动 `192.168.123.222/24`，无网关。
- 已将 HaiSong-orin 的 `Wired connection 1` 修改为与 AGX 一致：绑定 `eno1`，IPv4 手动 `192.168.123.222/24`，无网关，开机自动连接。
- 已确认 HaiSong 当前 `eno1` 获得 `192.168.123.222/24`。
- 第一次底层复测后，DDS 接口错误消失，但暴露出 `goGoalNavigation66` 缺少 `librosidl_typesupport_cpp.so` 的动态库环境问题。
- 已修改 `/mnt/ssd/navgation/projects/unitree_slam_example_new/example/start_nav_arm_bridge.sh`：后台启动的 `goGoalNavigation66` 和 `g1ArmOfficialActionServer` 现在会先 source `/opt/ros/humble/setup.bash` 和 `/mnt/ssd/navgation/projects/custom_action_ws/install/setup.bash`，与前台 28180 bridge 使用同一 ROS/Humble 环境。
- 已为底层启动脚本补充启动日志，打印 `ros setup` 和 `ws setup` 路径，方便后续确认实际加载的环境。
- 已执行脚本语法检查：`bash -n start_nav_arm_bridge.sh` 通过。
- 已短时验证底层导航桥接：导航节点完成自动重定位并输出 `Navigation system ready for commands`，手臂 action server 进入等待 action goal 状态，28180 bridge 正常监听。
- 已短时验证完整 `start_nav_bridge_workflow_loop.sh`：导航自动重定位成功并持续输出位姿；Neo4j、TTS、Memory Agent、Robot Agent 均 ready；workflow 已预启动并停在 go 闸门。
- 测试结束后已停止测试进程组，并停止遗留的 `rabbitbot-unified-runtime` 容器，释放关键端口。

未完成：

- 本轮没有发送 `go` 或 `back` 命令，没有执行真实导览动作。
- 本轮没有删除测试日志。
- 底层脚本目录 `unitree_slam_example_new` 当前不是 Git 仓库，因此脚本修改不在该目录内形成 Git 提交；本轮通过主项目交接报告记录该变更。

### 已验证的事实

- 修复前 HaiSong 的 `Wired connection 1` 为 DHCP 自动获取，`eno1` 无 IPv4 地址，CycloneDDS/Unitree SDK 无法把 `eno1` 识别为可用接口。
- AGX 原机 `eno1` 静态地址为 `192.168.123.222/24`，该配置迁移到 HaiSong 后，`eno1: does not match an available interface` 不再出现。
- 原生节点缺少 ROS/Humble 环境时会找不到 `librosidl_typesupport_cpp.so`；为后台原生节点 source ROS 和工作区后，动态库问题消失。
- 完整 workflow loop 在 `RUN_WORKFLOW_AFTER_START=0` 模式下可以启动到底座 ready，并预启动 workflow 等待 go 闸门。
- 复测日志目录包括：`/mnt/ssd/navgation/projects/unitree_slam_example_new/example/run_logs/nav_arm_bridge_20260610_145350` 和 `nav_arm_bridge_20260610_145432`。

### 阻塞问题

无当前启动链路阻塞。真实导览仍需要 Aaron 在确认现场安全后发送 `go` 命令验证导航动作。

### 建议的下一步

- 后续正式测试前，先确认 HaiSong 的 `eno1` 仍为 `192.168.123.222/24`，并确认机器人侧网络连接正常。
- 先前台运行 `scripts_1/start_nav_bridge_workflow_loop.sh`，等待日志出现 `Navigation system ready for commands` 和 `workflow 已完成预启动并停在 go 闸门`。
- 现场安全确认后，再使用 `scripts_1/send_nav_workflow_command.sh go` 触发真实 workflow。
- 如果再次手动中断脚本，复查 `docker ps` 和 28180/28182/28185/7687 等端口，必要时停止 `rabbitbot-unified-runtime`。

### 注意事项

- HaiSong 的 `eno1` 已使用与 AGX 相同的静态地址；同一机器人网络内不要同时把 AGX 和 HaiSong 都接入并启用同样地址，避免 IP 冲突。
- `/home/unitree/test9.pcd` 在宿主 shell 仍可能显示不可见 warning，但本轮实测机器人侧重定位接口能返回成功，说明该路径由机器人/Unitree 侧使用，不应仅凭宿主 shell 可见性判断失败。
- 底层脚本修改位于非 Git 目录：`/mnt/ssd/navgation/projects/unitree_slam_example_new/example/start_nav_arm_bridge.sh`。

### 其它信息

- 本轮新增/调整的日志点：底层导航桥接启动时会打印 `ros setup` 与 `ws setup`，用于排查后台原生节点是否加载了正确 ROS/Humble 环境。
- 本轮未改动 systemd 自启动策略；`rabbitbot-loop.service` 和 `rabbitbot-control-console.service` 仍应保持非开机自启。

## 本轮补充：同步 AGX 控制台代码改动到 HaiSong

### 背景和目标

Aaron 说明 AGX-orin 上项目已有新的代码改动，要求同步到 HaiSong-orin。本轮目标是在保留 HaiSong 本地迁移记录和导航桥接修复的前提下，把 AGX `June6_workflow` 分支在 `be9011d` 之后的控制台代码改动同步过来。

### 当前状态

已完成：

- 已对比 AGX 与 HaiSong 的 Git 历史：两边共同祖先为 `be9011d`。
- 已确认 AGX 新增代码改动集中在控制台功能：`/api/start`、控制台“开始程序”按钮、启动后等待服务全部 ready 的页面提示、启动/停止/重启 `rabbitbot-loop.service` 的命令封装和测试。
- 已将 AGX 控制台相关改动同步到 HaiSong：`rabbitbot/control_console/README.md`、`app.py`、`commands.py`、`tests/control_console/test_app.py`、`tests/control_console/test_commands.py`。
- 已将 AGX 新增的 `scripts_1/systemd/rabbitbot-control-console.sudoers` 模板同步到 HaiSong，并按本项目规范把模板注释调整为中文。
- 已确认 sudoers 模板语法：`visudo -cf scripts_1/systemd/rabbitbot-control-console.sudoers` 通过。
- 已用系统 Python 执行 `py_compile`，覆盖控制台应用、命令模块和控制台测试文件。
- 已用系统 Python 验证 FastAPI 路由包含 `/api/start`、`/api/restart`、`/api/stop`，并验证 `start_loop_service` 会调用 `systemctl start rabbitbot-loop.service`，且拒绝非 `rabbitbot-loop.service`。

未完成：

- HaiSong 当前 Python 环境没有 `pytest`，因此未运行完整 `tests/control_console` pytest 测试集。
- 本轮没有安装 `/etc/sudoers.d/rabbitbot-control-console`。该操作属于持久 sudo 授权配置，当前未获得明确授权，因此只同步仓库模板，不写入系统 sudoers。
- 本轮没有启动 `rabbitbot-control-console.service` 或 `rabbitbot-loop.service`。
- `conf/dialogue_0.json` 当前存在未暂存的点位坐标改动，不属于本轮 AGX 控制台同步内容，本轮未提交该文件。

### 已验证的事实

- AGX 新提交中控制台代码改动来自 `1acdab4`、`40719bf`、`a889b05` 的合并结果。
- HaiSong 同步后，控制台应用能正常导入并暴露 `/api/start` 路由。
- `start_loop_service` 的白名单服务校验有效，只允许操作 `rabbitbot-loop.service`。
- sudoers 模板仅包含固定命令：`systemctl start/restart/stop rabbitbot-loop.service`。
- `scripts_1/systemd/rabbitbot-control-console.sudoers` 在仓库中被 `.gitignore` 忽略，本轮使用 `git add -f` 纳入提交，保证 AGX 新增模板在 HaiSong 仓库中可追踪。

### 阻塞问题

- 控制台网页上的“开始程序/一键重启/关闭程序”要在 systemd 服务用户下免密执行，需要后续明确授权安装 `/etc/sudoers.d/rabbitbot-control-console`。未安装前，相关按钮可能因 sudo 需要密码而失败。
- 完整 pytest 测试受缺少 pytest 依赖阻塞；本轮用编译和核心行为脚本验证替代。

### 建议的下一步

- 如果 Aaron 确认允许安装固定 sudoers 授权，执行：`sudo install -m 0440 scripts_1/systemd/rabbitbot-control-console.sudoers /etc/sudoers.d/rabbitbot-control-console && sudo visudo -cf /etc/sudoers.d/rabbitbot-control-console`。
- 如需完整测试，先在合适的项目环境补齐 pytest，再运行 `python3 -m pytest tests/control_console`。
- 在不影响现场任务的时间窗口，启动控制台服务后从网页点击“开始程序”，验证 `/api/start` 到 systemd 的完整链路。

### 注意事项

- 本轮没有改变 rabbitbot systemd 自启动策略；两个 rabbitbot 服务仍应保持非开机自启。
- 不要把 `conf/dialogue_0.json` 的现场点位改动误并入控制台同步提交，除非 Aaron 确认该点位配置就是本轮目标。

### 其它信息

- 本轮新增/调整的日志点：控制台前端在点击“开始程序”或“一键重启”后，会轮询 `/api/status` 并显示“正在等待所有服务加载完成...”以及“所有服务已加载成功，可执行相关操作”，用于区分 systemd 命令已发送和服务真正 ready 两个阶段。后端 `commands.py` 新增 workflow 命令发送、地图环境文件写入、主循环服务 start/restart/stop 的开始、成功和失败日志，失败日志包含 action、service、returncode 和输出摘要，便于排查 sudoers、systemctl 或脚本执行问题。

## 本轮补充：核查开场后首个导航目标

### 背景和目标

Aaron 反馈在 HaiSong 上启动 workflow 并发送 `go` 后，机器人讲完开场台词后前往了令人意外的位置，怀疑实际前往了点位1；按剧本预期，开场后第一段应前往 `1->2过渡点位`。本轮目标是只读检查代码、剧本配置和最近 workflow 日志，给出原因判断。

### 当前状态

已完成：

- 已查看当前 `conf/dialogue_0.json` 的点位配置：`point_1` 和 `point_1_to_2_transition` 当前坐标完全相同，均为 `x=0.1797, y=-0.1793, z=0.0481, ox=0.0022, oy=0.1118, oz=0.0196, ow=0.9935`。
- 已确认 `conf/dialogue_0.json` 当前有未提交改动：该改动将 `point_1` 从 Git 中原坐标改成与 `point_1_to_2_transition` 一致；Aaron 说明这是因为原点位1更危险，容易撞上障碍物。
- 已查看最近 workflow 日志 `logs/nav_workflow_control/rabbitbot_workflow_20260610_145907.log`。
- 日志确认严格 DOCX 剧本模式下，开场阶段不会预先执行点位1导航，而是“按 PDF 顺序直接在点位1开始台词”。
- 日志确认开场台词结束后的第一个 DOCX 剧本步骤为 `scene=1到2过渡`，加载的是 `point_1_to_2_transition` 对应实体 `1->2过渡点位`。
- 日志确认实际下发导航为 `go_to_async: (0.1797, -0.1793, 0.0022, 0.1118, 0.0196, 0.9935)`，即当前过渡点位坐标。
- 已查看 `rabbitbot/agno_agents/workflow.py`：`DOCX_SCRIPT_POINT_ENTITY` 将 `point_1_to_2_transition` 映射为 `1->2过渡点位`；`navigate_docx_script_step` 使用 step 的 `entity` 解析点位并下发 `location_points[0]`。

未完成：

- 本轮没有修改 workflow 逻辑。
- 本轮没有修改 `conf/dialogue_0.json` 的坐标。
- 本轮没有重跑 workflow 或发送 `go/back`。

### 已验证的事实

- 代码路径没有把开场后的第一跳误选为 `point_1`；它选择的是 `point_1_to_2_transition`。
- 现场观感像“去了点位1”的直接原因是当前配置中 `point_1` 和 `point_1_to_2_transition` 坐标相同。
- 如果这个坐标本身仍然不是期望的 1->2 过渡路径位置，需要重新采集或填写 `point_1_to_2_transition`；仅从代码看不会自动推导新的过渡点位。
- 当前日志只打印 entity 和 points 数量，关键坐标主要依赖后续 `go_to_async` 输出，排查时容易把“选了哪个点位 key”和“下发了哪个坐标”混在一起。

### 阻塞问题

无代码层面的阻塞。需要现场确认 `point_1_to_2_transition` 当前坐标是否真的是安全且正确的 1->2 过渡点；如果不是，问题在点位配置，而不是 workflow 选点逻辑。

### 建议的下一步

- 保留 `point_1` 改成安全坐标的策略没有问题，但应单独确认 `point_1_to_2_transition` 是否也应该使用同一个坐标；如果开场后应该去另一个过渡位置，需要只更新 `point_1_to_2_transition`。
- 建议在 `navigate_docx_script_step` 的导航日志中补充 point/entity 的首个坐标和 waypoint 数量，方便现场一眼确认“选中的点位 key”和“实际下发坐标”。
- 下次复测时，重点观察日志中的 `DOCX 导览点位使用台词文件配置`、`DOCX 剧本导航目标` 和 `go_to_async` 三行，三者应共同确认第一跳目标。

### 注意事项

- `conf/dialogue_0.json` 的点位改动当前仍未提交；如确认这是现场安全配置，应单独提交并在提交信息中说明点位1避障原因。
- 本轮未新增代码日志点；仅提出后续建议，可在确认需要后补充。

## 本轮补充：控制台无法启动导航主程序原因核查

### 背景和目标

Aaron 在浏览器控制台点击“开始程序”后，页面显示 `sudo: a password is required`，导航主程序未成功启动。本轮目标是检查 HaiSong-orin 上 control-console 服务、sudoers 授权和日志，确认失败原因。

### 当前状态

已完成：

- 已确认 `rabbitbot-control-console.service` 当前为 `active`，服务用户为 `pc`。
- 已确认 `rabbitbot-loop.service` 当前为 `inactive`。
- 已确认两个 rabbitbot 服务仍为 `disabled`，没有开机自启。
- 已确认 `/etc/sudoers.d/rabbitbot-control-console` 当前不存在。
- 已确认仓库内模板 `scripts_1/systemd/rabbitbot-control-console.sudoers` 存在，并只授权 `pc` 免密执行 `systemctl start/restart/stop rabbitbot-loop.service`。
- 已查看 `rabbitbot-control-console.service` 日志，点击“开始程序”时后端执行 `sudo -n /usr/bin/systemctl start rabbitbot-loop.service`，sudo 返回 `a password is required`，因此 `/api/start` 返回 400。

未完成：

- 本轮未安装 `/etc/sudoers.d/rabbitbot-control-console`。
- 本轮未启动 `rabbitbot-loop.service`。
- 本轮未修改控制台代码或 systemd unit 文件。

### 已验证的事实

- 失败原因不是导航桥接本身，也不是 workflow 脚本启动失败；请求在 systemd 启动前就被 sudo 权限拦住。
- 控制台服务以 `pc` 用户运行，网页无法输入 sudo 密码；后端使用 `sudo -n`，因此必须提前配置 NOPASSWD sudoers。
- 当前仓库模板已具备最小授权范围，但尚未安装到 `/etc/sudoers.d/`。

### 阻塞问题

控制台网页按钮要管理 `rabbitbot-loop.service`，需要安装固定 sudoers 授权。该操作属于持久系统权限变更，必须由 Aaron 明确授权后执行。

### 建议的下一步

- 若需要网页“开始程序 / 一键重启 / 关闭程序”可用，安装并校验 sudoers 模板：`sudo install -m 0440 scripts_1/systemd/rabbitbot-control-console.sudoers /etc/sudoers.d/rabbitbot-control-console && sudo visudo -cf /etc/sudoers.d/rabbitbot-control-console`。
- 在未安装 sudoers 前，可用终端手动执行 `sudo systemctl start rabbitbot-loop.service` 启动导航主程序。
- 安装 sudoers 后，再从网页点击“开始程序”验证 `/api/start` 到 systemd 的链路。

### 注意事项

- 本轮没有新增代码日志点；已利用上一轮补充的后端日志确认失败动作、service、returncode 和 sudo 输出。
- `conf/dialogue_0.json` 仍存在未提交的点位坐标改动，本轮未处理。

## 本轮补充：安装控制台 sudoers 授权

### 背景和目标

Aaron 明确授权安装 `/etc/sudoers.d/rabbitbot-control-console`，用于让网页控制台以 `pc` 用户免密启动、重启和停止 `rabbitbot-loop.service`。本轮目标是安装仓库模板并校验权限，同时不主动启动导航主程序。

### 当前状态

已完成：

- 已先校验仓库模板 `scripts_1/systemd/rabbitbot-control-console.sudoers`，`visudo -cf` 通过。
- 已安装模板到 `/etc/sudoers.d/rabbitbot-control-console`，权限为 `0440`，属主为 `root:root`。
- 已对安装后的 sudoers 文件执行 `visudo -cf /etc/sudoers.d/rabbitbot-control-console`，校验通过。
- 已通过 `sudo -l -U pc` 确认 `pc` 用户仅被授予以下固定命令的 NOPASSWD 权限：
  - `/usr/bin/systemctl start rabbitbot-loop.service`
  - `/usr/bin/systemctl restart rabbitbot-loop.service`
  - `/usr/bin/systemctl stop rabbitbot-loop.service`
- 已用 `sudo -u pc sudo -n -l ...` 验证上述三个命令可被非交互识别为允许命令。
- 已复查服务状态：`rabbitbot-control-console.service` 为 `active`，`rabbitbot-loop.service` 仍为 `inactive`。
- 已复查 8080 控制台端口在监听，导航主程序相关端口未因本轮操作启动。

未完成：

- 本轮没有点击网页“开始程序”。
- 本轮没有执行 `systemctl start rabbitbot-loop.service`，因此没有实际启动导航主程序。
- 本轮没有修改 systemd unit 文件或业务代码。

### 已验证的事实

- 之前网页报 `sudo: a password is required` 的原因已消除：`pc` 用户现在具备对 `rabbitbot-loop.service` 的固定 NOPASSWD 管理权限。
- 安装的 sudoers 范围很窄，只覆盖 start/restart/stop `rabbitbot-loop.service`，不授予通配 systemctl 或 shell 权限。
- 两个 rabbitbot 服务仍然保持 `disabled`，本轮没有改变开机自启策略。

### 阻塞问题

无当前权限层面的阻塞。下一次从网页点击“开始程序”时，应能越过 sudo 权限检查并进入 `rabbitbot-loop.service` 启动流程；若仍失败，应继续查看 `journalctl -u rabbitbot-loop.service` 和控制台页面日志。

### 建议的下一步

- 在现场确认机器人安全后，从控制台点击“开始程序”，观察页面是否从 `not_detected` 转为主循环运行，并等待导航桥接和 workflow ready。
- 若启动失败，优先查看：`journalctl -u rabbitbot-loop.service -n 120 --no-pager` 和 `logs/nav_workflow_control/nav_bridge_*.log`。
- 如需撤销网页控制台管理权限，可删除 `/etc/sudoers.d/rabbitbot-control-console` 并重新校验 sudoers。

### 注意事项

- 本轮没有新增代码日志点；本轮是系统权限配置安装。上一轮后端日志已能记录 `/api/start` 的 action、service、returncode 和 sudo/systemctl 输出。
- `conf/dialogue_0.json` 仍存在未提交的点位坐标改动，本轮未处理。

## 本轮补充：VLM 问答 workflow 时延测试

### 背景和目标

本轮目标是按 Aaron 要求，在无人现场对话的情况下测试 `feature/qa-vlm-workflow` 分支新增的 VLM 语音问答 workflow 是否能调用 Qwen2.5-VL 进行思考回答，并统计从 STT 命令发出到 TTS 进入回复播报请求的分阶段平均时延。

### 当前状态

已完成：

- 已启动 `rabbitbot-unified-runtime` 统一容器底座，显式启用 VLM 与 STT，并使用 `/mnt/disk1/models` 作为模型目录。
- 已确认 vLLM 成功加载 `/models/Qwen2.5-VL-7B-Instruct-GPTQ-Int4`，served model 为 `Qwen2.5-VL-7B-Instruct`，`/v1/models` ready。
- 已通过临时测试驱动复用 `VLMQAWorkflow` 主逻辑，关闭启动提示语和“让我想一想”提示语，避免干扰首个回复 TTS 统计。
- 已在 STT agent 层用同样 JSON 命令形式模拟 5 个问题输入；真实 STT 服务没有“文本注入异步识别结果”的 API，因此本轮没有走麦克风录音链路。
- 已调用真实 Qwen2.5-VL OpenAI 兼容接口并获得 5 次回答。
- 已在统一容器内临时启动标准 `tts_app.py` 到 `127.0.0.1:28186`，用于生成标准 `Unitree本体TTS` 日志。
- 测试完成后已停止临时 28186 TTS 进程，并停止本轮启动的 `rabbitbot-unified-runtime` 容器。
- 清理后已确认 28182、28184、28186、8000、7687 等本轮端口无监听；原有 caddy、redis、nav、air_vln_container、sound_docker 保持运行。

未完成：

- TTS 没有成功播报首字；标准 TTS app 调用 Unitree G1 TTS 时返回 `returncode=1`。
- 因 TTS 失败，无法得到真实“首个字已经播出”的硬件侧时间，只能统计到 TTS 服务收到回复播报请求的时间点。
- 本轮未进行摄像头图像输入测试，`RABBITBOT_QA_INCLUDE_IMAGE=0`，属于文本问答调用 Qwen2.5-VL。

### 已验证的事实

- Qwen2.5-VL 可被 workflow 调用，5 个问题均收到模型流式回答。
- 本轮 5 问平均时延如下：
  - STT 命令发出到文本可读：0.000062 秒。
  - 文本可读到 workflow 收到：0.000265 秒。
  - workflow 收到文本到发起 VLM 请求：0.000049 秒。
  - VLM 请求到 stream open：0.015098 秒。
  - VLM 请求到首 token：0.066295 秒。
  - VLM 首 token 到完整回答结束：0.590316 秒。
  - VLM 总耗时：0.656610 秒。
  - VLM 完成到 TTS 请求开始：0.000094 秒。
  - STT 命令发出到 TTS 回复请求开始：0.657080 秒。
  - TTS 请求开始到返回失败：0.040188 秒。
- 分轮结果已保存到 `logs/vlm_qa_workflow/latency_test_20260613_tts28186.json`。
- TTS 标准日志 `logs/vlm_qa_workflow/tts_test_28186.log` 显示每轮均到达 `Unitree本体TTS: stage=tts_request_start`，随后失败。
- TTS 失败根因为 Unitree DDS 接口不可用：日志中出现 `eno1: does not match an available interface` 和 `Failed to create domain explicitly`。
- 当前已有 28185 服务来自 `sound_docker`，只暴露 `POST /v1`，不是 workflow 默认 `TTSAgent` 使用的 `/exec` 接口；因此本轮没有用它作为正式 workflow TTS endpoint。

### 阻塞问题

- 真实 TTS 播报链路当前被 Unitree DDS 网卡问题阻塞。`tts_app.py` 使用 `RABBITBOT_UNITREE_TTS_INTERFACE=eno1` 调用 G1 音频服务时，CycloneDDS 不能在该接口创建 domain。
- 因上述问题，本轮无法给出真实“首字播报”平均时延；可给出的端到端值是“STT 命令发出到 TTS 回复请求开始”，平均 0.657080 秒。

### 建议的下一步

- 现场接入或恢复 Unitree DDS 网络后，先确认容器内也能看到可用 `eno1`，再单独测试 `build/unitree_g1_tts_bridge --network eno1 --text 测试`。
- 如果继续使用 portable 容器内标准 `tts_app.py`，需要确认容器网络/权限下的 `eno1` 与宿主配置一致，避免宿主可用但容器内 CycloneDDS 不可用。
- 若要在无人现场继续做纯链路时延压测，可临时将 TTS 设为 dry-run，但该结果不能代表真实首字播报时延。
- 如需测试真正视觉问答，应在下一轮设置 `RABBITBOT_QA_INCLUDE_IMAGE=1`，并优先用 `RABBITBOT_QA_IMAGE_SOURCE=mock` 验证图文输入路径，再切到机器人摄像头。

### 注意事项

- 本轮测试没有启动导览导航 workflow，没有发送 `go/back`，没有触发机器人移动。
- 本轮测试驱动没有提交为项目代码，仅生成运行日志和 JSON 结果。
- 本轮启动 VLM 时发现 `scripts_1/start_unified_integration_workflow.sh` 直接调用会误用 legacy `IMAGE_NAME=rabbitbot-unified-runtime:20260518`，本轮通过显式设置 `IMAGE_NAME=ghcr.io/aaronai/rabbitbot-core-portable:20260611` 和 `MODELS_DIR=/mnt/disk1/models` 绕过。

### 其它信息

本轮没有修改业务代码日志点；测试依赖已有日志。关键日志覆盖 VLM 启动、VLM 流式回答、workflow TTS 请求链路、Unitree TTS 请求开始/失败、服务清理状态。TTS 失败日志包含接口名、返回码、stdout/stderr 和 DDS 失败原因，足够定位到容器内 Unitree DDS 接口不可用问题。

## 本轮补充：复核 VLM 问答 TTS 重复提交问题

### 背景和目标

Aaron 要求先修复 VLM 问答 workflow 中可能存在的重复 `tts_sound()` 调用问题。本轮目标是确认当前 `feature/qa-vlm-workflow` 分支实际代码状态，并在必要时修复。

### 当前状态

已完成：

- 已检查 `rabbitbot/agno_agents/vlm_qa_workflow.py` 中 `_speak_answer()` 实现。
- 已用脚本断言 `_speak_answer()` 代码块内 `tts_sound(self.ctx.tts_agent, answer, "zh")` 只出现 1 次。
- 已执行 `python3 -m py_compile rabbitbot/agno_agents/vlm_qa_workflow.py`，语法检查通过。

未完成：

- 本轮未修改业务代码，因为当前远端文件已不存在重复 `tts_sound()` 调用。
- 本轮未启动 workflow、容器、VLM、STT 或 TTS 服务。

### 已验证的事实

- 当前 `_speak_answer()` 逻辑为：空回答兜底、超长截断、单次调用 `tts_sound()`、记录 `TTS 播报已提交` 日志、随后 `tts_wait()`。
- 当前文件不会因为该位置导致同一条完整回答被提交两次给 TTS。

### 阻塞问题

无。

### 建议的下一步

- 后续如仍观察到重复播报，应优先查看 TTS 服务端是否重复接收请求、前端/测试驱动是否重复触发同一轮问题，或是否有多个 workflow 实例并发运行。
- 若继续优化首字延迟，应另起改动实现按句流式提交 TTS，而不是在当前单次提交逻辑上继续排查重复调用。

### 注意事项

- 本轮只更新交接报告，不改变运行逻辑。
- 现有日志 `TTS 播报已提交` 与 `TTS请求链路` 足以确认单轮是否只提交一次 TTS 请求。

### 其它信息

本轮没有新增或调整代码日志点；已确认现有日志覆盖 TTS 提交流程。

## 本轮补充：VLM 问答按句流式 TTS 适配

### 背景和目标

Aaron 要求让 VLM 问答 workflow 具备“流式播报”能力：大模型生成的每一句话应尽快交给 TTS 播报，而不是等待完整回答全部生成后才提交 TTS，从而降低长回答时用户感知到的首字延迟。

### 当前状态

已完成：

- 已修改 `rabbitbot/agno_agents/vlm_qa_workflow.py`，新增 VLM 流式分句提交 TTS 的主路径。
- 已新增 `_pop_stream_tts_segment()`，用于从流式 token 缓冲中按句末标点提取可播报分段。
- 已新增 `_create_vlm_stream()`，统一纯文本和图文 VLM 的 OpenAI 兼容流式请求创建逻辑。
- 已新增 `_submit_stream_tts_segment()`，每个句子分段都会单独调用 `tts_sound()`，并记录分段索引、长度、哈希、TTS 返回索引和耗时。
- 已新增 `_call_vlm_with_stream_tts()`，在 VLM chunk 到达时持续累积文本，遇到 `。！？!?；;` 或换行即提交 TTS；流结束后提交最后残句；最后仅调用一次 `tts_wait()` 等待队列收敛。
- 已新增环境变量 `RABBITBOT_QA_STREAM_TTS`，默认 `1` 开启按句流式 TTS；设为 `0` 可回退旧的整段回答播报逻辑。
- 已更新 `scripts/start_vlm_qa_workflow.bash` 和 `scripts_1/start_unified_vlm_qa_workflow.sh` 的注释、环境变量透传和启动日志。

未完成：

- 本轮未启动真实 VLM、STT、TTS 或机器人硬件服务，未进行实机播报验证。
- 本轮未实现真正音频级流式合成；当前粒度为“按句文本分段提交 TTS”。

### 已验证的事实

- `python3 -m py_compile rabbitbot/agno_agents/vlm_qa_workflow.py` 通过。
- `bash -n scripts/start_vlm_qa_workflow.bash` 通过。
- `bash -n scripts_1/start_unified_vlm_qa_workflow.sh` 通过。
- `git diff --check` 通过。
- 已用依赖桩模拟 VLM chunk 流验证分句行为：输入 chunk 拼成 `第一句。第二句！最后残句` 时，TTS 提交顺序为 `第一句。`、`第二句！`、`最后残句`，并且只在末尾调用一次 `tts_wait()`。
- 当前实现保留回答最大长度约束；当分段超过 `RABBITBOT_QA_MAX_ANSWER_CHARS` 剩余长度时，会截断当前分段并记录日志，后续分段会跳过并记录原因。

### 阻塞问题

无代码层面的阻塞。运行层面仍需先解决上一轮记录的 Unitree TTS DDS 接口问题，否则真实播报仍会在 TTS 后端失败。

### 建议的下一步

- 在 Unitree TTS DDS 接口恢复后，启动 VLM 问答 workflow，观察日志中的 `VLM 首 token 到达`、`流式 TTS 分段已提交`、`流式 TTS 等待完成` 和 `VLM 流式问答完成`。
- 用一个包含多句长回答的问题复测首句提交时间，对比上一轮“完整回答后才 TTS”的 `STT 命令发出到 TTS 回复请求开始` 平均时延。
- 如需要更进一步降低延迟，可在当前按句方案基础上增加逗号/长度阈值分段，或改造 TTS 服务支持真正的音频流式播放。

### 注意事项

- 当前按句分段只在遇到句末标点后提交 TTS；如果模型长时间不输出句号，首句仍会等待到句末或流结束。
- `RABBITBOT_QA_STREAM_TTS=0` 可用于现场快速回退旧逻辑。
- 本轮没有启动导览导航 workflow，没有发送 `go/back`，没有触发机器人移动。

### 其它信息

本轮新增日志点包括：VLM 流式问答开始、VLM 首 token 到达、流式 TTS 分段提交、按最大长度截断/跳过、流式 TTS 等待完成、VLM 流式问答完成。日志中记录 turn、分段序号、文本长度、哈希、TTS 索引、耗时、首 token 耗时和首个 TTS 分段提交耗时，便于后续统计首字延迟和排查重复/漏播。

## 本轮补充：调整 VLM 问答开场语和回答风格提示词

### 背景和目标

Aaron 要求 VLM 问答 workflow 在最开始使用 TTS 问一句“你好，请问需要我做些什么吗”，并给大模型增加更贴近日常对话、避免冗长回答的系统提示词。

### 当前状态

已完成：

- 已将 `RABBITBOT_QA_STARTUP_SPEECH` 的默认值从“问答测试已启动，您可以直接向我提问。”改为“你好，请问需要我做些什么吗？”。
- 已调整 `_build_prompt()` 中的角色定位，从“现场问答测试助手”改为“现场对话助手，正在和用户面对面自然交流”。
- 已补充回答要求：中文口语化、适合直接播报、不要写成报告或长段说明、默认 1 到 2 句、简单问题直接短答、不确定时简短说明无法确认。
- 保留原有 `RABBITBOT_QA_STARTUP_SPEECH` 环境变量覆盖能力，现场仍可通过环境变量临时改开场语或置空。

未完成：

- 本轮未启动真实 workflow、VLM、STT、TTS 或机器人硬件服务。
- 本轮未做真实模型回答风格回归测试。

### 已验证的事实

- `python3 -m py_compile rabbitbot/agno_agents/vlm_qa_workflow.py` 通过。
- 依赖桩验证 `QAWorkflowConfig.from_env()` 默认 `startup_speech` 为“你好，请问需要我做些什么吗？”。
- 依赖桩验证 `_build_prompt()` 生成的提示词包含“日常聊天”和“默认回答 1 到 2 句”。
- `git diff --check` 通过。

### 阻塞问题

无代码层面的阻塞。运行层面仍需解决 Unitree TTS DDS 接口问题后才能现场验证真实播报。

### 建议的下一步

- TTS 链路恢复后，启动 VLM 问答 workflow，确认开场先播报“你好，请问需要我做些什么吗？”。
- 用几个开放式问题检查回答是否明显变短、更像日常对话；如仍偏长，可继续降低 `RABBITBOT_QA_MAX_ANSWER_CHARS` 或在提示词中加入更严格的字数限制。

### 注意事项

- 本轮只调整默认文案和 prompt，不改变流式 TTS 分句逻辑。
- 如果现场设置了 `RABBITBOT_QA_STARTUP_SPEECH`，环境变量会覆盖本次默认开场语。

### 其它信息

本轮没有新增代码日志点；沿用已有启动日志、VLM 流式问答日志和 TTS 提交日志即可验证开场语和回答播报链路。


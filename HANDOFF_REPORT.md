# air_robot_gt_projects 交接报告

## 背景和目标

本轮目标是将 RabbitBot 当前可运行项目整理为独立的 `air_robot_gt_projects` 自主运行包，避免继续依赖 `/mnt/ssd/navgation/projects` 下大量无关目录。目标路径为 `/mnt/ssd/navgation/projects/air_robot_gt_projects`。

## 当前状态

已完成：

- 已按 Aaron 要求清空旧 `air_robot_gt_projects` 后重建，不保留旧半成品目录内容。
- 已复制主项目、模型、ROS action 工作区、Unitree 导航示例、Unitree SDK2、VLN、Orbbec SDK、灵巧手服务源码和 Humble bridge。
- 已保留当前 `conf/dialogue_0.json` 的现场点位改动。
- 已将 air 副本中的主要运行路径改为从当前目录推导。
- 已生成 `deploy/check_air_project.sh` 和 `deploy/install_air_project.sh`。
- 已生成顶层 `README.md`。

未完成：

- 尚未在本报告生成时记录完整运行验证结果；后续应以实际执行日志为准补充。

## 已验证的事实

- 本包包含完整 `models` 目录。
- 本包包含 `rabbitbot-dev-ros2-master/py38` 和 `py310`，满足当前 workflow、Memory Agent 和 Robot Agent 的运行方式。
- 容器内路径仍设计为 `/workspace/projects/...`，由宿主 air 根整体挂载实现。
- Docker 镜像 `rabbitbot-unified-runtime:20260518` 仍作为宿主前置条件，不包含在本目录内。

## 阻塞问题

无当前打包层面的已知阻塞。运行层面仍依赖宿主系统已有 ROS、Docker 镜像、系统动态库和机器人网络。

## 建议的下一步

- 执行 `bash deploy/check_air_project.sh` 做静态和依赖检查。
- 执行 `bash deploy/install_air_project.sh` 安装 systemd unit 和 sudoers。
- 启动控制台，访问 `http://192.168.101.90:8080`。
- 现场安全确认后再从控制台启动导航主程序。

## 注意事项

- 两个 systemd 服务应保持非开机自启。
- `/home/unitree/test9.pcd` 是机器人本体侧地图路径，不应迁移到本目录。
- 如需离线迁移到另一台机器，还需要单独导出 Docker 镜像和宿主运行时依赖。

## 其它信息

- 生成时间：2026-06-10 15:50:21

## 历史压缩摘要（最近五轮之前）

### 背景和目标

早期工作围绕 `air_robot_gt_projects` 自主运行包展开：从 legacy air 自包含目录整理，到 portable core/nav 自包含镜像、全新 Orin 冷启动、控制台/systemd 安装、模型目录、Unitree 导航/TTS/STT/VLM QA 链路逐步收口。

### 当前状态摘要

已完成的历史工作：

- 完成 air 自包含运行包整理，保留 `legacy` 与 `portable` 两条路径，并明确 GitHub 轻量提交边界。
- 建立 portable 部署基础设施，包括 `third_party/manifest.lock`、`runtime/portable.env.example`、bootstrap/check/build/import/export/start 等部署脚本，以及 core/nav Docker 定义。
- 将全新 Orin 运行期依赖收敛到 `ghcr.io/aaronai/rabbitbot-core-portable:20260611` 与 `ghcr.io/aaronai/rabbitbot-nav-portable:20260611`，外部大依赖通过镜像或模型目录管理。
- 修复控制台状态误判、旧容器挂载复用、workflow ready/status 旧文件污染、28180 端口归属、runtime env 模板化和 sudoers/systemd 模板缺失等部署问题。
- 修复模型目录缺失与 `ensure_models.sh` 下载实现，当前模型运行态指向 `/mnt/disk1/models`，并用硬链接补齐 air 包模型入口。
- 多轮排查 Unitree DDS、`eno1`、TTS ret=3104、STT 设备、DJI MIC MINI capture、BT67 回退策略和 portable 服务收敛问题。
- 新增 VLM QA workflow，并完成语音问答链路的基础脚本、日志、端口和服务归属治理。
- VLM QA 所需模型目录已修复：运行态模型目录指向 `/mnt/disk1/models`，`ensure_models.sh` 已改用 `huggingface_hub.snapshot_download()`，并用硬链接补齐 air 包模型入口。

### 已验证的历史事实

- portable core/nav 镜像是当前主要迁移边界；全新 Orin 运行期不应依赖宿主 `py38/py310/vln/pyorbbecsdk/unitree_sdk2` 等目录。
- `runtime/portable.env` 是本机运行态配置，不进入 Git；可迁移默认值应改 `runtime/portable.env.example`。
- `eno1` 链路状态直接影响 Unitree DDS、导航核心和机器人本体 TTS。
- 28180 在 portable 模式下应归属 nav bridge；core 不应启动 `robot_app.py` 抢占该端口。
- TTS/STT/VLM QA 排查已经形成较完整日志链路，能区分容器归属、设备选择、TTS 后端选择、Unitree 返回码和 workflow 阶段耗时。
- TTS 历史排查已确认 SDK/桥接程序存在，`ret=3104` 更符合机器人网络链路或机器人侧音频服务问题；同时已梳理 Unitree、本地 Kokoro、workflow 调用层和 `/exec` 协议边界。

### 历史阻塞摘要

- 实机导航、机器人本体 TTS 和 DDS 验证依赖现场 `eno1` 链路、机器人侧网络和音频服务状态。
- VLM/STT/TTS 完整体验仍依赖现场音频设备、模型加载和机器人硬件状态；远程只能验证软件链路和日志返回。

### 历史建议

- 后续先按当前目标选择入口：portable 部署复核用 `deploy/check_air_project.sh`，VLM QA 用 `scripts_1/start_unified_vlm_qa_workflow.sh`，导览主循环用 `rabbitbot-loop.service`。
- 涉及服务归属问题时，优先确认 core/nav 容器、端口、`runtime/portable.env`、`eno1` 和日志最新 run_id。
- 不要把本机运行态配置、模型目录、虚

轮新增/调整的日志点：未新增业务日志。

、本地 `TTS服务链路` 阶段日志、workflow `TTS请求链路` 日志和 `/exec` 探活日志。后续优化时应优先围绕这些阶段补齐结构化状态与错误码。
- 生成时间：2026-06-16 13:45:00

## 本轮补充：TTS auto 后端健康检查加固

### 背景和目标

Aaron 指出 `RABBITBOT_TTS_BACKEND=auto` 只判断 Unitree 网卡名是否存在，不判断链路、IP、DDS 或机器人音频服务是否可用，导致 TTS 服务容易误选 Unitree 后端并在运行时才失败。本轮目标是让 auto 判定更健壮，并把成功/错误原因清楚写入启动日志，方便现场调试。

### 当前状态

已完成：

- 已修改 `rabbitbot-dev-ros2-master/scripts/start_tts_app.bash`，将 shebang 改为 bash，并新增 `TTS启动检查` 分阶段日志。
- `auto` 模式现在会依次检查：
  - Unitree 网卡是否存在。
  - `operstate` 与 `carrier`，默认要求接口 UP 且有物理载波。
  - IPv4 地址，默认要求能读取到接口 IPv4。
  - Unitree TTS 桥接程序是否存在；不存在时尝试构建并记录构建日志尾部。
  - Unitree 音频服务只读探测，默认调用桥接程序 `--probe get_volume`。
- 已新增可配置开关：
  - `RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER`，默认 `1`。
  - `RABBITBOT_UNITREE_TTS_REQUIRE_IPV4`，默认 `1`。
  - `RABBITBOT_UNITREE_TTS_AUTO_PROBE`，默认 `1`。
  - `RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT`，默认 `3` 秒。
- 已修改 `rabbitbot-dev-ros2-master/scripts/unitree_g1_tts_bridge.cpp`，新增 `--probe get_volume` 模式，使用 Unitree SDK2 `AudioClient.GetVolume()` 做只读探测，不触发 TTS 播报。

未完成：

- 本轮没有重启当前已经运行的 TTS 服务；新 auto 判定需要下次启动 `scripts/start_tts_app.bash` 或重建/重启 core 后生效。
- 当前现场 `eno1` 仍为 `down/carrier=0`，因此还无法验证链路恢复后的成功选择 Unitree 分支。

### 已验证的事实

- `bash -n rabbitbot-dev-ros2-master/scripts/start_tts_app.bash` 通过。
- `bash -n rabbitbot-dev-ros2-master/scripts/build_unitree_g1_tts_bridge.sh` 通过。
- 在 core 容器内用新源码编译桥接程序成功，`--help` 显示新增 `--probe get_volume`。
- 在 core 容器内运行 `bash scripts/build_unitree_g1_tts_bridge.sh` 成功，生成新的 `build/unitree_g1_tts_bridge`。
- 当前断链状态下直接执行 `./build/unitree_g1_tts_bridge --network eno1 --timeout 2 --probe get_volume` 返回 `ret=3104`，退出码为 32，说明只读探测可以捕获机器人音频接口不可用。
- 默认 auto 判定在当前现场状态下输出：`operstate=down, carrier=0`，随后记录“Unitree链路检查失败”并回退 `local`。
- 临时设置 `RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER=0` 后，脚本能继续走到 `GetVolume` 探测，并在日志中记录 `Unitree音频服务探测失败：returncode=32 ... ret=3104`，随后回退 `local`。

### 阻塞问题

无代码层面阻塞。现场层面仍需恢复 `eno1` 链路后才能验证成功路径：接口 UP、有 IPv4、`GetVolume` 返回 0、auto 选择 `unitree`。

### 建议的下一步

- 恢复机器人网络链路后，重启 TTS 所在 core 服务，让新的 auto 健康检查生效。
- 查看 `rabbitbot-dev-ros2-master/logs/unified_runtime/rabbitbot_tts.log`，确认是否出现 `TTS启动检查: TTS后端自动选择完成：effective=unitree`。
- 如果链路恢复后仍回退 `local`，优先看同一段日志里的失败阶段：接口、carrier、IPv4、桥接构建或 `GetVolume` 探测。

### 注意事项

- `GetVolume` 探测是只读接口，不发送 `TtsMaker`，不会产生播报声音。
- `RABBITBOT_UNITREE_TTS_AUTO_PROBE=0` 可临时跳过音频服务探测，但不建议现场常态使用；否则又会退回“链路看起来可用但机器人音频服务不可用”的不可靠状态。
- 本轮新增/调整日志点：`TTS启动检查` 会记录 auto 判定开始、接口状态、carrier/IP 检查结果、桥接程序构建状态、Unitree 音频服务探测开始/成功/失败、stdout/stderr 摘要和最终 effective 后端。这些日志用于快速定位 TTS 是因物理链路、IP、SDK/桥接构建还是机器人音频服务失败而回退。
- 生成时间：2026-06-16 13:55:00

## 本轮补充：ShuHao-orin 项目只读核查

### 背景和目标

Aaron 要求登录 `ShuHao-orin`，阅读 `/mnt/disk1/gt/air_robot_gt_projects/HANDOFF_REPORT.md` 以及该目录所属项目。本轮目标是只读梳理项目结构、交接报告、当前分支、运行配置和当前服务状态，不触发机器人动作，不重启服务，不修改业务代码。

### 当前状态

已完成：

- 已确认项目根目录为 `/mnt/disk1/gt/air_robot_gt_projects`，当前 Git 分支为 `feature/qa-vlm-workflow`。
- 已阅读顶层 `HANDOFF_REPORT.md` 的近期补充，重点包含 portable 部署、VLM QA workflow、模型目录修复、TTS/STT 音频链路、TTS auto 健康检查等内容。
- 已阅读顶层 `README.md`，确认该目录是 RabbitBot 自主运行包，保留 `legacy` 与 `portable` 两条运行路径。
- 已阅读主项目 `rabbitbot-dev-ros2-master/HANDOFF_REPORT.md` 的近期内容，确认最新工作集中在 VLM QA、portable core/nav 容器收敛、STT 设备选择解耦和 TTS auto 选择加固。
- 已查看 `third_party/manifest.lock`、`runtime/portable.env.example`、当前本机 `runtime/portable.env`、关键部署脚本和启动脚本清单。
- 已查看当前容器、关键端口和 `eno1` 网卡状态。

未完成：

- 本轮未执行 `deploy/check_air_project.sh`，未启动或重启任何 systemd 服务，未启动 VLM QA workflow。
- 本轮未做实机语音、TTS 播报、STT 拾音、导航或机器人动作验证。
- 本轮未修改业务代码。

### 已验证的事实

- 当前 Git 工作区在写入本节前是干净状态，分支为 `feature/qa-vlm-workflow`，最新提交为 `df67d94 加固 TTS auto 后端健康检查`。
- 顶层目录包含 `rabbitbot-dev-ros2-master`、`models`、`custom_action_ws`、`unitree_slam_example_new`、`unitree_sdk2`、`vln`、`pyorbbecsdk-v2-py310`、`deploy` 和 `third_party`。
- 当前 `runtime/portable.env` 设置：`RABBITBOT_RUNTIME_MODE=portable`，core 镜像为 `ghcr.io/aaronai/rabbitbot-core-portable:20260611`，nav 镜像为 `ghcr.io/aaronai/rabbitbot-nav-portable:20260611`，模型目录为 `/mnt/disk1/models`，`RABBITBOT_TTS_BACKEND=auto`，`RABBITBOT_UNITREE_TTS_SPEAKER_ID=1`。
- 当前运行容器只看到 `rabbitbot-portable-rabbitbot-nav-1`、`caddy`、`redis`；未看到 `rabbitbot-unified-runtime` core 容器正在运行。
- 当前关键端口只确认 `28180` 在监听；未看到 `8000`、`28182`、`28184`、`28185`、`7687` 监听。
- 当前 `eno1` 状态为 `DOWN`，这会阻塞 Unitree DDS、机器人本体 TTS 和导航实机链路。
- 当前顶层 README 仍说明 portable 默认通过 core/nav 两个自包含镜像运行，全新 Orin 运行期不再要求宿主存在 `py38/py310/vln/pyorbbecsdk/unitree_sdk2` 等目录。

### 阻塞问题

- 当前 `eno1` 为 `DOWN`，如果需要实机导航、Unitree 本体 TTS 或 DDS 相关验证，必须先恢复机器人网络链路。
- 当前 core 容器未运行，VLM、STT、TTS、Memory、Neo4j 等 core 侧服务当前不可用；如果要继续 VLM QA 或语音链路验证，需要按项目脚本重新拉起 core 基础服务或 workflow。

### 建议的下一步

- 若目标是恢复 VLM QA，先运行 `cd /mnt/disk1/gt/air_robot_gt_projects/rabbitbot-dev-ros2-master && bash scripts_1/start_unified_vlm_qa_workflow.sh`，再检查 `8000/28184/28185` 和 workflow 日志。
- 若目标是验证机器人本体 TTS 或导航，先恢复 `eno1` 链路，确认 `ip -brief addr show dev eno1` 不再是 `DOWN`，再启动相关服务。
- 若目标是做 portable 部署复核，先执行 `PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh` 或按当前机器角色选择 builder/clean_orin 模式。
- 后续修改业务代码时，应继续保持新增日志覆盖关键启动路径、设备选择、容器复用判断、网络/DDS 探测、TTS/STT/VLM 请求链路和失败原因。

### 注意事项

- 本轮只读核查未触发机器人移动、未发送 `go/back`、未启动或停止容器服务。
- 顶层 `HANDOFF_REPORT.md` 已经很长；后续若继续追加多轮记录，建议单独安排一次交接报告压缩，把最近五轮之前的历史内容折叠成摘要，避免继续膨胀。
- 本轮新增/调整日志点：未新增业务日志；本次只记录交接报告。已确认现有日志设计覆盖 TTS auto 后端选择、STT 设备选择、VLM QA workflow 阶段、TTS 请求返回、容器兼容性检查等关键排查路径。

### 其它信息

- 生成时间：2026-06-29

## 本轮补充：导览默认 QA 与语音打断恢复

### 背景和目标

Aaron 要求调整导览期间逻辑：启动 `rabbitbot-loop.service` 后默认进入 QA 状态；只有听到“开始导览”后，才按所选剧本开始导览；导览期间保持 STT 监听，听到提问后暂停当前导览流程和正在播报的话，先回答问题，回答结束后回到导览流程继续。

### 当前状态

已完成：

- 已修改 `scripts_1/start_nav_bridge_workflow_loop.sh`：默认 `RABBITBOT_NAV_WORKFLOW_VOICE_START=1`，workflow 启动后不再等待外部 `go` 文件闸门，而是进入 QA 状态等待语音口令。
- 已在语音启动导览模式下强制启用 `RABBITBOT_UNIFIED_START_STT=1`，避免 `portable.env` 默认关闭 STT 导致听不到“开始导览”。
- 已修改 `scripts/run_kuavo_agno_workflow.py`：当 `RABBITBOT_GUIDE_START_BY_VOICE=1` 时跳过旧的启动闸门和立即导览开场，记录 `voice_qa_mode` 后直接创建主 workflow。
- 已修改 `rabbitbot/agno_agents/workflow.py`：新增导览语音启动状态，默认识别“开始导览、开始讲解、开始参观、开始流程、启动导览”，可通过 `RABBITBOT_GUIDE_START_COMMANDS` 覆盖。
- 导览开始前，workflow 会持续进行 QA；普通问题走原有 chat/plan 路径，且 completion check 在导览未开始前不会自动结束 workflow。
- 听到开始导览口令后，workflow 会执行导览开场，然后按所选 `dialogue_<序号>.json` / 剧本继续推进。
- 严格 DOCX 剧本台词默认允许真实提问打断，继续确认词仍会被忽略；可通过 `RABBITBOT_DOCX_GUIDE_QA_INTERRUPT=0` 回退旧的严格忽略行为。
- 已为导航等待阶段新增 STT 监听：导航期间听到真实问题会停止当前 TTS 队列、返回 `interrupt`，保持剧本索引不前进，回答后继续原导览步骤。

未完成：

- 本轮未重启 `rabbitbot-loop.service`，未启动 core/nav 服务，未做现场实机导览验证。
- 本轮未验证真实麦克风听到“开始导览”的现场效果，也未验证机器人本体 TTS 的实际物理播报。
- 导航期间的“暂停导览流程”已实现为暂停剧本推进和停止 TTS；当前没有调用底层 `stop_nav`，机器人导航动作本身是否暂停仍取决于 28180/nav bridge 是否后续暴露停止接口。

### 已验证的事实

- `python3 -m py_compile scripts/run_kuavo_agno_workflow.py rabbitbot/agno_agents/workflow.py` 通过。
- `bash -n scripts_1/start_nav_bridge_workflow_loop.sh scripts_1/start_loop_entry.sh scripts_1/start_unified_integration_workflow.sh` 通过。
- `git diff --check` 通过。
- 关键开关和日志点已确认存在：`RABBITBOT_NAV_WORKFLOW_VOICE_START`、`RABBITBOT_GUIDE_START_BY_VOICE`、`RABBITBOT_DOCX_GUIDE_QA_INTERRUPT`、`RABBITBOT_GUIDE_NAV_STT_INTERRUPT`、`语音口令启动导览`、`导航期间启动 STT 监听`。

### 阻塞问题

- 当前未做实机验证；若 `eno1` 仍为 DOWN 或 core 容器未运行，无法验证 STT/TTS/导航真实链路。
- 当前导航暂停没有底层取消/暂停动作；如果现场要求机器人移动也立即停下，需要在 nav bridge/Robot Agent 层补充 `stop_nav` HTTP 接口并在 workflow 打断时调用。

### 建议的下一步

- 恢复现场网络和 core 服务后，重启 `rabbitbot-loop.service`，观察日志中是否出现“语音启动导览模式：workflow 已进入 QA 状态”。
- 对麦克风说普通问题，确认 workflow 在导览前能回答且不会退出；随后说“开始导览”，确认进入所选剧本。
- 导览台词播报期间和导航等待期间各问一个短问题，确认 TTS 被停止、问题被回答、回答后同一剧本步骤继续。
- 如需保持旧外部 `go/back` 启动模式，可设置 `RABBITBOT_NAV_WORKFLOW_VOICE_START=0`。

### 注意事项

- Python 侧 `RABBITBOT_GUIDE_START_BY_VOICE` 默认值保持为 0，避免直接手动运行 workflow 时改变旧行为；只有 loop 脚本默认显式传入 1。
- 新增日志点避免记录完整原始口令内容，只记录触发文本长度、阶段、scene、step_index、timeout、状态变化和异常类型，便于排查且避免过量日志。
- 本轮未修改模型、运行态 env、systemd unit 或 Docker 镜像。

### 其它信息

- 生成时间：2026-06-29

## 本轮补充：go 命令映射为开始导览口令

### 背景和目标

Aaron 明确要求前端“导览”按钮发送的 `go` 命令效果等同于 QA 状态下对麦克风说“开始导览”，即在默认 QA 状态中启动支持中途打断并恢复的导览流程，而不是沿用旧外部 go 闸门语义。

### 当前状态

已完成：

- 已修改 `rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_workflow_loop.sh`：在默认语音启动模式 `RABBITBOT_NAV_WORKFLOW_VOICE_START=1` 下，workflow 运行期间收到 `go` 命令时，不再忽略，而是调用 STT `/exec` 注入文本。
- 新增 `RABBITBOT_NAV_WORKFLOW_GO_TEXT`，默认值为 `开始导览`；如需改按钮注入文案，可通过该变量覆盖。
- 新增 `RABBITBOT_STT_EXEC_URL`，默认 `http://127.0.0.1:28184/exec`，用于调用 STT `inject_text_async`。
- 已修改 `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/workflow.py`：导览已经启动后再次收到“开始导览”类口令会被忽略并记录日志，避免重复点击按钮把口令当作普通问题打断当前导览。

未完成：

- 本轮未重启 `rabbitbot-loop.service`，未通过前端实际点击“导览”做现场验证。
- 本轮未验证 STT 服务运行态是否已经监听 28184；实际点击按钮前仍需保证 loop 已启动且 STT 服务就绪。

### 已验证的事实

- `python3 -m py_compile rabbitbot/agno_agents/workflow.py scripts/run_kuavo_agno_workflow.py` 通过。
- `bash -n scripts_1/start_nav_bridge_workflow_loop.sh scripts_1/send_nav_workflow_command.sh` 通过。
- `git diff --check` 通过。
- 当前后端“导览”按钮仍通过 `/api/task` 调用 `send_workflow_command("go")`；现在 loop 会把这个 `go` 转成 STT 注入的“开始导览”。

### 阻塞问题

- 无代码层面阻塞。现场验证仍依赖 `rabbitbot-loop.service`、core 容器、STT 28184、TTS 和导航服务正常。

### 建议的下一步

- 启动 `rabbitbot-loop.service` 后，在前端点击“导览”，检查 loop 日志是否出现“将 go 命令转换为开始导览口令”和“开始导览口令已注入 STT”。
- 确认 workflow 日志随后出现“语音口令启动导览”，并进入所选剧本。
- 如需恢复旧外部 go 闸门行为，设置 `RABBITBOT_NAV_WORKFLOW_VOICE_START=0`。

### 注意事项

- 新增日志不会记录完整原始口令，只记录文本长度、STT URL、STT 注入响应和重复口令忽略状态。
- 如果 STT 注入失败，loop 会记录 WARNING，但不会终止 workflow；这便于现场继续用麦克风说“开始导览”兜底。

### 其它信息

- 生成时间：2026-06-29

## 本轮补充：back 命令映射为返回起点口令

### 背景和目标

Aaron 要求“返航”按钮发送的 `back` 命令效果等同于向 STT 28184 注入“返回起点”；同时现场对麦克风说“返回起点”和点击“返航”按钮应统一触发同一逻辑：若机器人已经完成一轮导览并位于导览终点，则按照剧本 `back_points` 返回点序列返航；若没有 `back_points`，则按剧本导览点位顺序的逆序返航。

### 当前状态

已完成：

- 已修改 `rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_workflow_loop.sh`：在默认语音启动模式下，workflow 运行期间收到 `back` 命令时，不再直接排队旧返航命令，而是调用 STT `/exec` 注入“返回起点”。
- 新增 `RABBITBOT_NAV_WORKFLOW_BACK_TEXT`，默认值为 `返回起点`，可覆盖按钮注入文案。
- 复用 `RABBITBOT_STT_EXEC_URL`，默认 `http://127.0.0.1:28184/exec`，与 `go -> 开始导览` 使用同一 STT 注入通道。
- 已修改 `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/workflow.py`：导览完成后不再立刻退出，而是保持 QA 状态等待“返回起点/返航/回到起点/回起点/返回原点”等返航口令。
- workflow 收到返航口令且确认导览已完成后，会写入 `RABBITBOT_WORKFLOW_RETURN_REQUEST_FILE`；loop 监测到该文件后执行现有 `return_to_start`。
- 当前 `return_to_start` 已满足返航点序列规则：优先读取台词 JSON 顶层 `back_points`；未配置时按剧本导览点位顺序逆序生成返航路径。
- 如果导览尚未完成就收到“返回起点”，workflow 会记录并忽略，不会提前返航。

未完成：

- 本轮未重启 `rabbitbot-loop.service`，未在前端实际点击“返航”，也未用麦克风现场说“返回起点”验证实机链路。
- 本轮未验证 28180 导航桥接实机返航动作；仍依赖现场网络、定位和导航核心状态。

### 已验证的事实

- `python3 -m py_compile rabbitbot/agno_agents/workflow.py scripts/run_kuavo_agno_workflow.py` 通过。
- `bash -n scripts_1/start_nav_bridge_workflow_loop.sh scripts_1/send_nav_workflow_command.sh` 通过。
- `git diff --check` 通过。
- STT 服务已有 `inject_text_async` 队列，`get_text_async` 会优先消费注入文本；本轮复用该能力。

### 阻塞问题

- 无代码层面阻塞。现场验证仍要求 `rabbitbot-loop.service`、STT 28184、TTS、28180 nav bridge 和机器人网络状态正常。

### 建议的下一步

- 启动 `rabbitbot-loop.service`，完成一轮导览后点击前端“返航”，观察 loop 日志是否出现“将 返回起点 命令转换为 STT 注入口令”和 workflow 日志“已写入返航请求文件”。
- 完成一轮导览后对麦克风说“返回起点”，确认产生同样的返航请求文件并进入 `return_to_start`。
- 检查返航日志中的 `source`：若台词配置了 `back_points`，应为 `dialogue_back_points`；否则应为 `reverse_go_points`。

### 注意事项

- STT 注入日志只记录文本长度、STT URL、响应长度和状态，不打印完整口令文本或原始 STT 响应。
- 如果 STT 注入失败，loop 只记录 WARNING，不终止 workflow；现场仍可通过麦克风重试。
- 旧外部 go/back 闸门模式仍可通过 `RABBITBOT_NAV_WORKFLOW_VOICE_START=0` 回退。

### 其它信息

- 生成时间：2026-06-29


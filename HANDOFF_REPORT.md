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

## 本轮补充：打包后验证结果

### 背景和目标

本轮继续验证 `air_robot_gt_projects` 自主运行包，目标是确认静态检查、systemd 安装、控制台访问和导航桥接启动状态。

### 当前状态

已完成：

- 已执行 `bash deploy/check_air_project.sh`，目录结构、Docker 镜像存在性、核心脚本 `bash -n`、Python 编译、sudoers 模板和旧项目根硬编码检查全部通过。
- 已执行 `bash deploy/install_air_project.sh`，安装 air 路径的 `rabbitbot-loop.service`、`rabbitbot-control-console.service` 和 `/etc/sudoers.d/rabbitbot-control-console`。
- 已确认两个服务仍为 `disabled`，未设置开机自启。
- 已确认控制台服务已重启到 air 路径，`http://127.0.0.1:8080/api/status` 返回正常状态。
- 已短时启动 air 路径下的底层导航桥接，确认脚本使用 air 路径的 `custom_action_ws/install/setup.bash`，28180 Python bridge 能启动。

未完成：

- 底层 `goGoalNavigation66` 和 `g1ArmOfficialActionServer` 未能完成 DDS 初始化，因为当前 HaiSong `eno1` 为 `DOWN/unavailable`。
- 未执行完整 workflow loop 运行验证，因为当前机器人 DDS 网口不可用，继续启动会在同一处失败。
- 未发送 `go` 或执行真实导览动作。

### 已验证的事实

- 当前 `eno1` 状态为 `DOWN`，NetworkManager 显示 `ethernet:unavailable`；虽然 `Wired connection 1` 仍配置了 `192.168.123.222/24`，但接口没有可用载波/链路。
- air 路径改造后，底层桥接日志显示 `ws setup` 为 `/mnt/ssd/navgation/projects/air_robot_gt_projects/custom_action_ws/install/setup.bash`。
- 本次 DDS 失败原因是现场网口状态，不是 air 项目路径缺失。

### 阻塞问题

当前阻塞是机器人网络口 `eno1` 不可用，导致 Unitree DDS 节点报 `eno1: does not match an available interface`。需要接好机器人网络或恢复有线链路后，才能完成底层导航和完整 workflow 验证。

### 建议的下一步

- 恢复机器人网络连接后，先确认 `ip -brief addr show dev eno1` 显示 `192.168.123.222/24`。
- 再运行 `bash deploy/check_air_project.sh` 做快速复查。
- 然后从控制台点击“开始程序”，或手动运行 `sudo systemctl start rabbitbot-loop.service`，等待导航桥接和 workflow ready。
- 如果需要单独验证底层桥接，可运行：`/mnt/ssd/navgation/projects/air_robot_gt_projects/unitree_slam_example_new/example/start_nav_arm_bridge.sh eno1 /home/unitree/test9.pcd`。

### 注意事项

- 本轮没有新增业务代码日志点；但 air 检查脚本、安装脚本和桥接脚本会输出关键路径、服务状态和失败原因，足够用于部署排查。
- 生成时间：2026-06-10 15:54:42

## 本轮补充：Git 忽略规则确认

- 已确认顶层 `.gitignore` 会排除运行日志、Python 缓存、临时文件和备份目录。
- 已修正 `rabbitbot-dev-ros2-master/.gitignore`，避免 air 自主运行包漏提交 `py38/`、`py310/` 和日志目录占位文件。
- 已补充规则，使虚拟环境被纳入后仍排除其中的缓存字节码目录和 `.pyc` 文件。
- 已清理本轮导航试跑生成的 `unitree_slam_example_new/example/run_logs/nav_arm_bridge_*`，当前日志目录仅保留 `.gitkeep`。
- 已通过 `git check-ignore -v` 抽样验证：`py38/bin/python`、`py310/bin/python`、日志 `.gitkeep` 保留，普通日志文件排除。

## 本轮补充：GitHub 轻量提交策略

- 根据 Aaron 的判断，完整 air 目录包含模型、虚拟环境和构建产物，体积不适合直接提交到 GitHub。
- 已停止大体积 `git add`，删除中断提交留下的 `.git` 临时对象库，并重新初始化 Git 仓库。
- 已调整顶层 `.gitignore`：运行依赖继续留在 `/mnt/ssd/navgation/projects/air_robot_gt_projects`，但不进入 Git 提交。
- Git 提交边界改为代码、配置、部署脚本、检查脚本、README 和交接报告。
- 这意味着 GitHub 仓库不能单独恢复完整运行环境；迁移到新机器时仍需通过移动硬盘或离线依赖包同步被忽略的运行依赖目录。

## 本轮补充：外部示例工程构建产物排除

- 提交后复查发现 `unitree_slam_example_new` 下仍有历史 `build*`、`log` 和生成图片进入 Git 索引。
- 已补充顶层 `.gitignore`，排除 `unitree_slam_example_new/**/build*/`、`unitree_slam_example_new/**/log/`、生成的目标文件、静态库、动态库和 PNG 图片。
- 已使用 `git rm --cached` 仅从 Git 索引移除这些文件，磁盘上的运行依赖和构建产物仍保留在 air 目录中。
- 已补充 `*.bak_*` 忽略规则，并从 Git 索引移除外部示例工程中的历史备份脚本。

## 本轮补充：air 自包含运行复核

- 已复核 `workflow loop` 和控制台服务的 systemd 配置，`WorkingDirectory`、`ExecStart`、`EnvironmentFile` 均指向 `/mnt/ssd/navgation/projects/air_robot_gt_projects`。
- 已发现并修正 `custom_action_ws/install/setup.bash` 生成前缀问题：`start_nav_arm_bridge.sh` 和 `one_click_start.sh` 现在会显式设置 `COLCON_CURRENT_PREFIX` 到 air 目录，避免回退到旧 `/mnt/ssd/navgation/projects/custom_action_ws/install`。
- 已将 `one_click_start.sh` 额外需要的 `unitree_sdk2/build/bin/g1_loco_client` 和 `dfx_inspire_service/build/inspire_g1` 补入 air 目录，并修正 `setup_inspire_sudo_nopasswd.sh` 从 air 根目录推导 inspire 路径。
- 已补强 `deploy/check_air_project.sh`：新增 one-click 依赖检查、unitree 示例脚本语法检查、air ROS 工作区动态库解析检查、运行脚本旧路径硬编码检查。
- 已验证 `goGoalNavigation66` 在 source air 工作区后，`libcustom_action_interfaces__rosidl_typesupport_cpp.so` 解析到 `/mnt/ssd/navgation/projects/air_robot_gt_projects/custom_action_ws/install/custom_action_interfaces/lib/`。
- 当前控制台服务可访问 `http://127.0.0.1:8080/api/status`；`rabbitbot-loop.service` 保持 disabled，未设置开机自启。
- 仍需注意：完整实机导航验证依赖机器人网络口 `eno1` 可用，当前 `eno1` 显示 DOWN/unavailable 时不能完成导航 DDS 实机验证。


## 本轮补充：控制台显示服务未全部就绪排查

### 背景和目标

Aaron 在 HaiSong 上启动 `rabbitbot-control-console.service` 后，前端提示“服务仍未全部就绪，请查看状态或打开日志排查”。本轮目标是确认控制台、导航桥接和 workflow loop 的实际状态，并修复 air 项目启动链路中导致前端误报未就绪的问题。

### 当前状态

已完成：

- 已确认控制台服务本身可访问，`http://127.0.0.1:8080/api/status` 能返回状态。
- 已确认前端就绪条件包括主循环运行、28180 导航桥接端口就绪、workflow ready 文件存在且状态可读。
- 已定位根因：`rabbitbot-unified-runtime` 曾复用旧容器挂载，容器内 `/workspace/projects` 指向旧 `/mnt/ssd/navgation/projects`，导致 workflow 的 ready/status 文件写到旧路径，而 air 控制台读取 air 项目路径，因此前端持续显示服务未全部就绪。
- 已修复 `rabbitbot-dev-ros2-master/scripts_1/start_unified_integration_workflow.sh`：启动前检查既有统一容器的 `/workspace/projects` 和 `/models` 挂载源；若与当前 air 根目录不一致，则记录具体原因并重建容器。
- 已进一步修正 Docker 挂载解析方式，从 `println` 改为 `printf`，避免制表符两侧空格导致后续重启误判。
- 已重启 `rabbitbot-loop.service`，统一容器已按 air 根目录重建。

未完成：

- 本轮未发送 `go`，未执行真实导览动作。
- 本轮未停止 Aaron 已启动的 loop；当前 workflow 停在 `waiting_for_go` 闸门，等待现场操作。

### 已验证的事实

- 当前容器挂载为 `/mnt/ssd/navgation/projects/air_robot_gt_projects -> /workspace/projects`。
- 当前模型挂载为 `/mnt/ssd/navgation/projects/air_robot_gt_projects/models -> /models`。
- 当前控制台 API 返回 `main_loop=running`、`nav_bridge.ready=true`、`workflow.ready=true`、`workflow.status=waiting_for_go`。
- 当前定位状态为 `localized=true`，pose 来源为导航桥接日志。
- `bash deploy/check_air_project.sh` 通过，核心脚本语法、Python 编译、sudoers 模板、air 动态库解析和旧路径硬编码检查均正常。

### 阻塞问题

无当前前端就绪层面的阻塞。真实导览动作仍需现场确认机器人周围安全后再发送 `go`。

### 建议的下一步

- 浏览器刷新控制台页面，确认顶部状态不再提示服务未全部就绪。
- 如需开始导览，在现场安全确认后点击控制台的导览/开始流程按钮或发送 `go`。
- 若后续再次出现未就绪，优先查看 `rabbitbot-loop.service` 日志中是否出现“已有统一容器配置不匹配，将重建”以及 `/api/status` 的 `workflow.ready` 字段。

### 注意事项

- 这次问题不是前端页面故障，而是容器复用旧挂载后，workflow 状态文件写入路径与控制台读取路径不一致。
- 新增的挂载兼容性检查会输出具体不匹配原因，便于后续区分项目路径、模型路径和环境变量变更导致的容器重建。
- 生成时间：2026-06-10 18:15:00

## 本轮补充：控制台过快显示就绪与定位状态文案排查

### 背景和目标

Aaron 反馈：启动控制台后点击“开始程序”，页面很快显示就绪，但按实际启动流程不应这么快；同时定位状态长期显示“当前位姿已读取，定位状态待确认”。本轮目标是确认前端就绪判断是否读取了真实当前 workflow，并修正定位状态展示。

### 当前状态

已完成：

- 已确认控制台 API 曾读取到旧的 workflow ready/status 文件：页面显示 `run_id=20260610_181244`、`waiting_for_go`，但最新一次实际 workflow `20260610_181551` 已在 18:16:58 结束。
- 已确认根因是控制台状态选择逻辑优先选择历史 `running` 状态文件，导致旧 ready 文件盖过最新已结束的 run。
- 已修复 `rabbitbot/control_console/status.py`：workflow 状态改为选择最新状态文件；只有最新 run 仍为 `running`、存在 ready 文件且没有 `exit_code/finished_at` 时，才认为 `ready=true` 并显示 `waiting_for_go`。
- 已修复定位状态回退：没有解析到位姿时，不再显示“当前位姿已读取，定位状态待确认”，而是显示需要重定位的提示。
- 已修复前端导览按钮启用条件：只有主循环、导航桥接和 workflow 闸门全部 ready 时才允许发送导览 go。
- 已修复 `start_nav_bridge_workflow_loop.sh`：主循环启动准备阶段会清理历史 workflow 控制文件，防止服务启动早期被旧 ready 文件污染。
- 已重启 `rabbitbot-control-console.service` 让新状态逻辑生效。

未完成：

- 本轮未发送 `back`，也未重启 `rabbitbot-loop.service`，避免在现场不明确的情况下触发返航或重新拉起导航。
- 本轮未执行真实导览动作。

### 已验证的事实

- 当前 `/api/status` 返回最新 workflow：`run_id=20260610_181551`、`status=finished`、`ready=false`。
- 当前定位返回：`available=false`，状态文案为“定位未成功：程序会持续重定位，需要遥控机器人的位姿，帮助机器人完成定位”。
- 当前 `rabbitbot-loop.service` 仍在运行，但日志显示它停在“等待命令：back 返回起点”，因此此时点击“开始程序”只会执行 systemd start，不会新建 workflow。
- `bash deploy/check_air_project.sh` 已通过，核心脚本语法、Python 编译、sudoers 模板、air 动态库解析和旧路径硬编码检查正常。

### 阻塞问题

当前没有代码层面的阻塞。流程层面需要现场决定：是发送 `back` 完成返航并进入下一轮预启动，还是重启主程序清理当前等待状态。

### 建议的下一步

- 刷新控制台页面，确认不再秒变“全部就绪”，导览按钮在 workflow 未 ready 时不可点。
- 如果当前机器人应该返航，现场确认安全后发送 `back`。
- 如果不需要执行返航，可使用控制台“一键重启”或 `sudo systemctl restart rabbitbot-loop.service` 重建主循环，等待新的 workflow 进入 `waiting_for_go`。
- 若后续再出现秒变 ready，优先检查 `/api/status` 中 `workflow.run_id` 是否为最新控制文件，以及 `workflow.ready` 是否只在 `waiting_for_go` 阶段为 true。

### 注意事项

- “开始程序”按钮当前语义是启动 systemd 服务；如果 `rabbitbot-loop.service` 已经处于 active，systemd start 会立即返回，不会重启或清理当前流程状态。
- 新增日志点会记录启动时清理历史 workflow 控制文件的目录和数量；控制台状态解析对忽略非活动 ready 文件使用 DEBUG 日志，避免正常轮询产生过量日志。
- 生成时间：2026-06-10 18:22:00

## 本轮补充：定位持续未成功排查

### 背景和目标

Aaron 反馈控制台持续显示“定位未成功：程序会持续重定位，需要遥控机器人的位姿，帮助机器人完成定位”。本轮目标是确认定位失败的实际原因，并避免控制台只因 28180 Python bridge 存活而误判导航桥接就绪。

### 当前状态

已完成：

- 已确认最新导航日志为 `rabbitbot-dev-ros2-master/logs/nav_workflow_control/nav_bridge_20260610_182249.log`。
- 日志显示 `goGoalNavigation66` 启动后立即异常退出：`eno1: does not match an available interface`，随后抛出 `unitree::common::DdsException` 和 `Failed to create domain`。
- 已确认宿主网卡状态：`eno1` 为 `DOWN/NO-CARRIER`，NetworkManager 显示 `ethernet unavailable`。
- 已修复控制台 `/api/status` 的导航桥接判断：不再只看 28180 端口；会结合最新导航日志判断导航核心是否崩溃、是否网卡不可用、是否已经 ready/有位姿输出。
- 已修复前端导航桥接显示：现在会展示后端给出的具体原因，例如“导航核心未启动：Unitree DDS 网卡不可用，请检查 eno1 链路”。
- 已补强 `start_nav_bridge_workflow_loop.sh` 健康检查：识别导航日志中的 DDS、网卡和进程异常，避免导航核心已崩溃时仍把导航桥接视为健康。
- 已重启 `rabbitbot-control-console.service`，当前 API 已返回 `nav_bridge.ready=false` 和明确原因。

未完成：

- 本轮未重启 `rabbitbot-loop.service`，避免在现场链路未恢复时反复重启导航流程。
- 本轮未修复物理网络链路；需要现场接好机器人/Unitree DDS 所在的 `eno1` 网络。

### 已验证的事实

- 当前 `ip -brief addr show dev eno1` 显示 `eno1 DOWN`。
- 当前 `ip link show dev eno1` 显示 `NO-CARRIER`。
- 当前 `/api/status` 中 `nav_bridge.ready=false`，message 为“导航核心未启动：Unitree DDS 网卡不可用，请检查 eno1 链路”。
- 当前 workflow 虽然可停在 `waiting_for_go`，但导航核心未启动，不能执行真实导航。
- `bash deploy/check_air_project.sh` 已通过；核心脚本语法、Python 编译、sudoers 模板、air 动态库解析和旧路径硬编码检查正常。

### 阻塞问题

物理/网络层阻塞：`eno1` 没有载波，Unitree DDS 不能创建 domain，导致 `goGoalNavigation66` 崩溃，定位和导航都不会成功。

### 建议的下一步

- 现场恢复机器人网络连接，确保 `eno1` 有载波并处于可用状态。
- 确认 `ip -brief addr show dev eno1` 不再是 `DOWN`，并有正确的 Unitree 网络地址。
- 恢复链路后重启主程序：`sudo systemctl restart rabbitbot-loop.service`。
- 刷新控制台，等待导航桥接显示“导航核心已就绪”，定位状态显示“定位成功”后再发送 `go`。

### 注意事项

- 当前 28180 端口在线只代表 Humble Python bridge 还活着，不代表 Unitree 导航核心可用。
- 新增日志点：loop 健康检查会在导航核心日志不可读、DDS/网卡/进程异常、尚未完成定位时输出 WARNING，便于区分端口在线和核心导航可用性。
- 控制台状态解析对导航日志读取失败和核心异常使用 DEBUG 日志，避免常规状态轮询造成过量日志。
- 生成时间：2026-06-10 18:25:00

## 本轮补充：portable 可迁移化基础设施第一版

### 背景和目标

Aaron 这轮要求先为“全新 Orin 仅靠 GitHub 源码 + 镜像 + 最小宿主初始化完成 RabbitBot 冷启动”建立独立实施分支和第一版落地基础设施，同时保留现有现场可回退的 legacy 路径。

### 当前状态

已完成：

- 已从当前 `master` 切出独立分支 `feature/portable-deploy`。
- 已新增 `third_party/manifest.lock`，显式记录 Git 之外的运行依赖、镜像来源和模型下载策略。
- 已新增 `rabbitbot-dev-ros2-master/runtime/portable.env`，集中管理 portable 运行模式、DDS 网卡、地图路径、镜像和模型开关。
- 已新增 portable 相关脚本：
  - `deploy/bootstrap_host.sh`
  - `deploy/setup_robot_network.sh`
  - `deploy/ensure_models.sh`
  - `deploy/build_or_pull_images.sh`
  - `deploy/start_portable_stack.sh`
- 已新增 portable Docker 定义：
  - `rabbitbot-dev-ros2-master/docker/portable/core.Dockerfile`
  - `rabbitbot-dev-ros2-master/docker/portable/nav.Dockerfile`
  - `rabbitbot-dev-ros2-master/docker/portable/compose.yaml`
  - `rabbitbot-dev-ros2-master/docker/portable/nav_entrypoint.sh`
- 已新增 portable 入口脚本：
  - `rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`
  - `rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_portable.sh`
- 已修改主循环 `start_nav_bridge_workflow_loop.sh`，支持通过 `RABBITBOT_NAV_RUNTIME=compose` 切换到 portable nav。
- 已修改控制台启动脚本，使其优先使用 `runtime/control_console_venv`，并支持从 `runtime/portable.env` 读取地图路径。
- 已把 `start_kuavo_agno_workflow.bash`、`start_robot_app.bash`、`start_nav_arm_bridge.sh` 的关键固定 IP / 网卡配置改为环境变量优先。
- 已修改控制台配置与状态解析：控制台地图默认值支持 `RABBITBOT_NAV_MAP_PATH`，主循环进程检测兼容 `start_loop_entry.sh`。
- 已升级顶层 `README.md` 为 portable 主线说明，同时保留 legacy 回退章节。
- 已升级 `deploy/check_air_project.sh` 和 `deploy/install_air_project.sh`，使其同时识别 legacy / portable。

未完成：

- portable core 目前仍基于 `rabbitbot-unified-runtime:20260518` 基础镜像，尚未把其历史上游构建链完全公开重建。
- 本轮尚未执行 portable nav Docker 实际构建，也未在“干净新 Orin”环境完成端到端冷启动验证。
- 本轮没有把 `pyorbbecsdk-v2-py310`、`vln` 等目录真正转成仓库内可自动恢复制品，只是先通过 manifest 明确了它们必须被显式管理。

### 已验证的事实

- 所有新增/修改的 shell 脚本已通过 `bash -n` 语法检查。
- `rabbitbot/control_console/config.py`、`status.py` 与现有关键 Python 文件编译检查可通过。
- portable 基础文件已落盘，`runtime/portable.env`、`third_party/manifest.lock`、portable Docker 定义和 deploy 脚本都在仓库中可见。
- 主循环现在支持两种导航桥接运行方式：
  - `host`：原 `start_nav_arm_bridge.sh`
  - `compose`：新的 `start_nav_bridge_portable.sh`
- `deploy/check_air_project.sh` 现在会额外检查：
  - manifest 关键条目
  - portable env 关键键
  - portable Docker 文件与脚本
  - 关键运行脚本中未环境变量化的固定 IP / 网卡硬编码

### 阻塞问题

- 当前最大未完成阻塞仍是 portable core 的完全可重建性：它现在默认依赖 `rabbitbot-unified-runtime:20260518` 作为基础镜像，而不是完全由公开 Dockerfile 从零构建。
- 第二个阻塞是制品供应链还未真正接通：manifest 已有，但 `unitree_sdk2`、`vln`、`pyorbbecsdk-v2-py310` 等目录的远程制品源还没落地。
- 第三个阻塞是尚未在干净 Orin 上做完整演练，因此还不能宣称“只靠 GitHub + 镜像即可稳定冷启动成功”。

### 建议的下一步

- 优先在当前 HaiSong 上尝试执行：
  - `bash deploy/check_air_project.sh`
  - `bash deploy/build_or_pull_images.sh MODE=build`
  - `bash deploy/start_portable_stack.sh`
- 如果 portable nav 镜像构建失败，先逐项补齐 nav Dockerfile 的系统依赖，再继续。
- 如果 portable core 运行依旧依赖 `rabbitbot-unified-runtime:20260518`，下一轮应继续拆解该镜像来源，逐步把上游历史镜像改成仓库内可重建或镜像仓库可拉取的显式基础镜像。
- 在确认 portable 基础服务可启动后，再安排一次“干净 Orin”冷启动演练。

### 注意事项

- 本轮为了保证现场回退能力，没有删除 legacy 逻辑；因此仓库现在是“双路径并存”，不要把存在 legacy 代码误解为 portable 改造失败。
- 新增日志点主要在 `bootstrap_host.sh`、`setup_robot_network.sh`、`ensure_models.sh`、`build_or_pull_images.sh`、`start_portable_stack.sh` 和 `start_nav_bridge_portable.sh`，覆盖了宿主初始化、网卡配置、模型下载、镜像准备和 portable nav 启动的关键阶段、输入摘要、失败原因和结果摘要。
- 当前 root README 已改成 portable 主线说明；后续如再改部署方式，应先同步 README 与本交接报告，再继续提交代码。
- 生成时间：2026-06-11 18:00:00

## 本轮补充：portable 镜像构建收口与上下文治理

### 背景和目标

本轮继续推进 `feature/portable-deploy` 分支上的 RabbitBot 可迁移化改造，目标是让 portable 路径不仅具备脚本、清单和 compose 入口，还能够在当前 Orin 上实际完成 `rabbitbot-nav` 镜像构建，并避免宿主历史构建产物和大体积运行目录再次污染 Docker 构建上下文。

### 当前状态

已完成：

- 已在 `feature/portable-deploy` 分支上修复 `rabbitbot-dev-ros2-master/docker/portable/nav.Dockerfile`，在编译 `unitree_slam_example_new/example` 前显式清理宿主遗留的 `build/` 和 `run_logs/`。
- 已新增顶层 `.dockerignore`，排除 `models/`、`py38/`、`py310/`、ROS build/install 缓存、导航示例 build 目录和无关外部依赖，避免它们进入 portable 镜像构建上下文。
- 已补强 `deploy/check_air_project.sh`，新增 `.dockerignore` 存在性和关键规则检查，防止后续回归导致大目录重新进入构建上下文。
- 已重新执行 `MODE=build RABBITBOT_PORTABLE_BUILD_CORE=0 RABBITBOT_PORTABLE_BUILD_NAV=1 bash deploy/build_or_pull_images.sh`，确认 `ghcr.io/aaronai/rabbitbot-nav-portable:20260611` 构建成功。
- 已确认本次 `docker build` 的上下文传输量降到约 `103.31kB`，不再把 `models/`、历史虚拟环境和宿主 build 目录打进镜像构建上下文。
- 已再次执行 `bash deploy/check_air_project.sh` 和 `docker compose -f rabbitbot-dev-ros2-master/docker/portable/compose.yaml config -q`，检查通过。

未完成：

- 本轮没有实际启动 portable stack；原因是当前主机仍可能承担现场控制任务，不适合在未确认现场状态时直接拉起新容器拓扑。
- `portable core` 仍默认基于 `rabbitbot-unified-runtime:20260518`，后续仍需继续拆解或发布可拉取成品镜像，才能彻底消除该基础镜像依赖。

### 已验证的事实

- `rabbitbot-nav` portable 镜像当前已成功生成：`ghcr.io/aaronai/rabbitbot-nav-portable:20260611`，镜像 ID 为 `sha256:d25e6527186e175be19d5e9bf26ec19fd680ae4fe0bb4feb3872a6ac56eb55c1`。
- 之前导致构建失败的直接原因已确认是宿主 `unitree_slam_example_new/example/build/CMakeCache.txt` 被复制进容器，路径与容器内目录不一致。
- 新增 `.dockerignore` 后，Docker 构建上下文已显著收敛，说明大体积目录已被成功排除。
- 当前 portable 自检脚本已经覆盖：依赖清单、portable env、`.dockerignore`、关键脚本语法、Python 编译、旧路径硬编码和固定网卡/IP 硬编码。

### 阻塞问题

当前主要阻塞已从 `rabbitbot-nav` 构建失败转移为 `portable core` 仍依赖 legacy unified 基础镜像；如果新 Orin 上既没有本地该镜像，也没有可拉取的成品镜像，就还不能完成真正意义上的“只靠 GitHub + 镜像仓库冷启动”。

### 建议的下一步

- 继续拆解 `portable core`，优先识别 `rabbitbot-unified-runtime:20260518` 中必须前置固化进 Dockerfile 的系统依赖与 Python 运行时。
- 在镜像仓库发布 `rabbitbot-core-portable` 与 `rabbitbot-nav-portable` 的可拉取版本，并把拉取地址与版本锁回写到 `third_party/manifest.lock`。
- 选择一个不影响现场运行的窗口，按 `bootstrap_host.sh -> build_or_pull_images.sh -> start_portable_stack.sh` 路径做一次完整 portable 冷启动演练。
- 在具备机器人链路的条件下，再补做 `workflow -> waiting_for_go` 与 28180 就绪的整链验证。

### 注意事项

- 本轮新增/调整的日志主要集中在 portable 脚本与检查链路：镜像准备、模型下载、宿主初始化、网络配置、compose 启动和导航入口都会记录开始、关键参数、完成状态和失败原因，便于后续在新 Orin 上排查冷启动问题。
- `.dockerignore` 仅用于镜像构建上下文治理，不影响 Git 跟踪规则；Git 侧是否提交仍以顶层 `.gitignore` 为准。
- 生成时间：2026-06-11 11:30:00

## 本轮补充：portable 自包含镜像化冷启动落地

### 背景和目标

按 Aaron 的「全新 Orin 镜像化冷启动」计划，把 `core` 与 `nav` 做成包含全部运行时依赖的本地自包含镜像，使全新 Orin 只需 GitHub 拉源码、导入镜像、最小宿主初始化即可冷启动，运行期不再要求宿主存在 `py38/py310/vln/pyorbbecsdk/unitree_sdk2` 等目录。

### 关键现实约束（已核实）

- 本机现存镜像中，`unified_runtime/Dockerfile` 引用的四个上游镜像里**只剩 `neo4j:5.26-community`**；`navid-rabbitbot:stt-tts-audio-ct2cuda-20260511`、`rabbitbot-vllm:20260511`、`foxy-ros-cam-orb-ubuntu20:rabbitbot-20260511` 这三个 tag 已不在本机。因此**无法在本机从零重建 core**。
- `rabbitbot-unified-runtime:20260518`（49.8GB）本身即这四个镜像的合并产物，已包含 Neo4j/Java/ROS Foxy/Python3.8/STT/TTS/VLM venv。
- 结论：core 只能以 unified-runtime 为基础镜像，再把宿主 gitignore 的重型依赖与源码烤进镜像。该折中已在 `third_party/manifest.lock` 的 `images.portable_core.notes` 与 README 中如实记录。

### 当前状态

已完成：

- **改写 `docker/portable/core.Dockerfile` 为自包含镜像**：`FROM rabbitbot-unified-runtime:20260518`，烤入 `rabbitbot-dev-ros2-master`（含 `py38/py310`）、`vln`、`pyorbbecsdk-v2-py310`、`humble_robot_agent_bridge.py` 到 `/workspace/projects/...`，并从烤入源码安装统一入口与冒烟脚本到 `/usr/local/bin`。
- **改写 `deploy/build_or_pull_images.sh`**：
  - 新增 `MODE=build|check|none`（保留 `pull|both`）；`RABBITBOT_IMAGE_SOURCE=local` 时默认 `check`。
  - core 构建使用 `rsync` 生成的专用上下文 `.portable_core_ctx`，绕过顶层 `.dockerignore` 对 `py38/py310/vln/pyorbbecsdk` 的排除（早期 `cp -al` 方案因宿主 root 文件触发 `protected_hardlinks` 失败，已弃用）。
  - 记录镜像 tag、image id、耗时。
- **新增 `deploy/export_portable_images.sh` / `deploy/import_portable_images.sh`**：以 `docker save/load` 离线交付，导出 `*.tar`、`images.sha256`、`images.lock.json`；导入前校验 sha256，并确认 load 后 tag 与 `runtime/portable.env` 一致；均记录 tag、id、路径、sha256、耗时。
- **改写 `scripts_1/start_unified_integration_workflow.sh`**：portable 模式（`RABBITBOT_RUNTIME_MODE=portable`）新建容器时，为 `py38/py310/vln/pyorbbecsdk` 注入从 core 镜像 seed 的 named volume（`rabbitbot_portable_*`）；新建前重置这些卷以从当前镜像重新 seed；并新增「容器镜像与期望镜像不一致即重建」判定，保证导入新镜像后重启即生效。
- **改写 `deploy/check_air_project.sh` 为两模式**：`PORTABLE_CHECK_MODE=builder|clean_orin`。`clean_orin` 允许外部构建目录缺失，转而要求已导入的 core/nav 镜像、控制台 venv、`RABBITBOT_NAV_MAP_PATH` 配置；manifest 检查新增「无未解决 blocker」。
- **更新 `third_party/manifest.lock`**：`unitree_sdk2`/`custom_action_ws_install` → `baked_into_image`(nav)；`vln`/`pyorbbecsdk-v2-py310` → `baked_into_image`(core)；`legacy_python_envs` → `not_required_for_portable`；`dfx_inspire_service` 保持 `legacy_optional`；`blockers` 清空并移入 `resolved_blockers`；新增 `image_source=local`、`image_delivery=offline_docker_save_load`。
- **更新 `runtime/portable.env`**：`RABBITBOT_PORTABLE_BUILD_CORE=1`、新增 `RABBITBOT_IMAGE_SOURCE=local`、`RABBITBOT_PORTABLE_INJECT_DEPS=1`；并在 `rabbitbot-dev-ros2-master/.gitignore` 增加 `!runtime/portable.env`，使该模板能随仓库迁移（此前被 `*` 规则忽略）。
- **更新 `start_portable_stack.sh`**：以 portable 模式启动，默认走 `check`（不访问远端仓库）。
- **更新 `README.md`**：拆为「流程 A 构建机生成镜像」「流程 B 全新 Orin 导入镜像冷启动」两条明确流程，并更新自检/注意事项。

### 已验证的事实（本机实测）

- `PORTABLE_CHECK_MODE=builder bash deploy/check_air_project.sh` 通过。
- `MODE=build bash deploy/build_or_pull_images.sh` 成功：`ghcr.io/aaronai/rabbitbot-core-portable:20260611`（id `sha256:683425716fd5...`，50.8GB，耗时 29s）；nav 命中缓存（id `d25e6527186e`）。
- **自包含冒烟（无任何挂载）通过**：`docker run --rm --entrypoint rabbitbot-unified-smoke-check` 返回 `audio_runtime_ok / vllm_runtime_ok / workflow_runtime_ok / robot_python38_runtime_ok / neo4j_java_runtime_ok`，exit=0。证明 workflow(py310)、Robot Agent(系统 py3.8 + 烤入 py38 site-packages)、VLM、音频、Neo4j Java 全部在镜像内可用。
- **干净 Orin 运行链路通过（throwaway 容器模拟）**：用 `git archive HEAD` 生成只含 git 跟踪文件、缺 `py38/py310/vln/pyorbbecsdk` 的源码树 bind 到 `/workspace/projects`，再挂 4 个新建 named volume；容器内这 4 个依赖均从 core 镜像 seed 出来并在 bind mount 之上可见，`py310/bin/python` 成功 `import agno` 与 `from rabbitbot.agno_agents.workflow import create_main_workflow`（exit=0）。证明「named volume 在父 bind mount 之下仍能从镜像 seed」这一关键机制成立。
- `PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh` 通过（exit=0）；两个 WARN 为预期：本机尚无 `control_console_venv`、地图文件为机器人本体侧路径。

### 未完成 / 阻塞

- **未切换正在服务的 live core 容器**：当前 `rabbitbot-unified-runtime` 容器已运行约 16h、控制台 active、workflow 停在 `waiting_for_go`。因 `eno1` 当前为 DOWN，Unitree TTS / Robot Agent 基础服务在全新容器中无法完整初始化，此时执行 `start_portable_stack.sh` 重建会用「不可验证的新容器」替换「当前可用的待命容器」且不易回滚。已通过 throwaway 容器完整验证镜像与 seed 机制，**实际 live 切换建议在 `eno1` 恢复的维护窗口执行**。
- **未在真正的「干净新 Orin」整机演练**：本机仍是构建机；干净链路已用容器级模拟覆盖，但端到端整机冷启动（导入 tar → bootstrap → start_portable_stack → 控制台/28180/waiting_for_go）需在另一台干净 Orin 上完成。
- 离线导出 `deploy/export_portable_images.sh` 正在后台运行生成 `outputs/portable-images/`（core ~50GB tar + nav + sha256 + lock）；本报告生成时可能尚未结束，结果以 `outputs/portable-images/images.lock.json` 与 `/tmp/export.log` 为准。

### 建议的下一步

- `eno1` 恢复后，在维护窗口执行：`bash deploy/start_portable_stack.sh`（portable 模式会自动检测镜像变化并以 core-portable 镜像 + 依赖卷重建 core 容器），等待基础服务就绪后再验证控制台、28180 与 `waiting_for_go`。
- 准备一台干净 Orin，按 README「流程 B」整机演练：导入镜像 → `bootstrap_host.sh` → `PORTABLE_CHECK_MODE=clean_orin` 自检 → `MODE=check` 校验 → `start_portable_stack.sh`。
- 将 `outputs/portable-images/` 整目录交付到目标 Orin 作为离线镜像来源。

### 注意事项

- core 镜像 50.8GB，`docker save` tar 约同量级；导出/导入耗时较长，`outputs/` 已被 `.gitignore` 排除，不进入提交。
- portable 依赖卷 `rabbitbot_portable_{py38,py310,vln,pyorbbecsdk}` 在「新建 core 容器」时会被重置并从当前 core 镜像重新 seed；导入新版 core 镜像后首次 `start_portable_stack.sh` 即会刷新它们。
- 本轮新增/调整的日志点：core 构建（上下文准备、镜像 id、耗时）、镜像 check/none 分支、导出/导入（tag/id/路径/sha256/耗时）、portable 依赖卷重置与注入、容器镜像不一致重建原因、clean_orin 自检的镜像/初始化/地图校验，均覆盖关键阶段、输入摘要、状态变化、失败原因。
- 生成时间：2026-06-11 11:05:00

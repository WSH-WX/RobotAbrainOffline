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

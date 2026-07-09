# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：在 new-orin 上使用 `build_grid_map.py` 将两份 PCD 点云转换为二维占据地图。

## 项目整体描述

`RobotAbrainOffline` 是 RabbitBot/Unitree 导览机器人离线部署项目集合，用于在 Orin/ROS2 环境中运行导览 workflow、语音交互、视觉识别、记忆检索、导航桥接、Web 控制台和 portable 容器化服务。核心链路是：控制台或 systemd 启动主循环，workflow 加载 JSON 台词与点位，STT/命令触发导览、返航或无机器人模式到点确认，导航桥接连接 Unitree 导航，TTS 播报讲解，VLM/Embedding/Memory/Neo4j 提供扩展问答能力。

## 主要模块与目录

- `deploy/`：宿主初始化、portable 栈启动、自检、systemd 安装脚本。
- `rabbitbot-dev-ros2-master/conf/`：导览台词、点位、地图等运行配置；本轮运行台词为 `dialogue_0.json`。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/`：FastAPI 控制台后端、静态页面、台词热更新逻辑、服务状态与命令执行。
- `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/`：导览 workflow 编排、数据加载、机械臂动作、日志和 profiling。
- `rabbitbot-dev-ros2-master/rabbitbot/guide/`：导览台词、控制命令和路由等纯逻辑。
- `rabbitbot-dev-ros2-master/docker/portable/`：portable core/nav 镜像与解耦 compose；本项目保持单个 portable core 镜像复用为多容器角色，另配 nav 镜像和 Neo4j。
- `rabbitbot-dev-ros2-master/scripts/`、`scripts_1/`：workflow 启动、主循环入口、控制命令脚本。
- `models/`：模型缓存目录；现场部署要求实体复制，不使用符号链接。
- `custom_action_ws/`、`unitree_slam_example_new/`：ROS2/Unitree 导航相关代码。

## 技术栈与运行入口

- Python `>=3.10`，FastAPI 控制台，Docker Compose host network，NVIDIA runtime，ROS2 Humble，Neo4j。
- 常用入口：
  - portable 基础服务：`bash deploy/start_portable_stack.sh`
  - 主循环：`bash rabbitbot-dev-ros2-master/scripts_1/start_loop_entry.sh`
  - workflow 控制：`bash rabbitbot-dev-ros2-master/scripts_1/send_nav_workflow_command.sh go|arrive|back`
  - 控制台：`rabbitbot.control_console` 或 systemd `rabbitbot-control-console.service`
- 关键配置：
  - `rabbitbot-dev-ros2-master/runtime/portable.env.example`
  - `rabbitbot-dev-ros2-master/runtime/portable.env`（运行态，通常不提交）
  - `rabbitbot-dev-ros2-master/docker/portable/docker-compose.decoupled.yaml`
  - `rabbitbot-dev-ros2-master/conf/dialogue_0.json`

## 本轮修改摘要

- `unitree_slam_example_new/global_nav/build_grid_map.py` 新增 PCD 直接读取路径：对 `.pcd` 使用 `numpy` 解析 PCD 头和 `binary/ascii` 点数据；非 PCD 仍沿用原有 `open3d` 读取。
- 远端 `new-orin:/mnt/disk1/gt/RobotAbrainOffline/unitree_slam_example_new/global_nav/build_grid_map.py` 已同步该脚本。
- 已在 `new-orin` 生成两份二维占据地图：
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_grid.npz`
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_edited_grid.npz`
- 脚本自动生成了两份调试图：
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_grid.png`
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_edited_grid.png`
- 转换参数均为：`resolution=0.10`、`z_min=-0.20`、`z_max=1.50`、`inflation_radius=0.45`。
- 控制台任务控制页左侧“运动状态”板块已改为动态“服务状态”板块，显示 Neo4j、VLM、Embedding、TTS、STT、Memory、Workflow、NavBridge 的在线状态和用户友好的服务作用说明。
- 控制台原“模型服务”页面已改名为“服务状态管理”，继续提供详细服务状态与服务重启入口。

## 日志新增或调整

- `build_grid_map.py` 新增 `logging`，默认 INFO 级别。
- 转换开始时记录输入文件、输出文件、分辨率、高度过滤范围和膨胀半径。
- 读取 PCD 时记录文件路径、声明点数和数据格式；不记录原始点云数据。
- 非 PCD 且缺少 `open3d` 时保留原始导入异常链，便于诊断依赖问题。
- 本轮控制台服务状态板块复用既有 `/api/status` 数据和前端渲染逻辑，未新增后端日志。

## 已验证事实

- 本地 `python3 -m py_compile unitree_slam_example_new/global_nav/build_grid_map.py` 通过。
- 本地 `python3 -m py_compile rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py rabbitbot-dev-ros2-master/tests/control_console/test_app.py` 通过。
- 远端 `python3 -m py_compile unitree_slam_example_new/global_nav/build_grid_map.py` 通过。
- `new-orin` 缺少 `open3d`，但存在 `numpy 1.26.4` 和 `Pillow 9.0.1`；本轮 PCD 读取不依赖 `open3d`。
- `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133.pcd` 声明点数为 `243037`，已转换为 `global_map_20260708_124133_grid.npz`；栅格形状 `(914, 747)`，占据单元 `83076`，原点 `[-45.643035888671875, -28.656492233276367]`，分辨率 `[0.1]`。
- `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_edited.pcd` 声明点数为 `79074`，已转换为 `global_map_20260708_124133_edited_grid.npz`；栅格形状 `(629, 434)`，占据单元 `26551`，原点 `[-24.151477813720703, -19.83965492248535]`，分辨率 `[0.1]`。
- 两个 `.npz` 均已用 `numpy.load` 读取并确认包含 `occupancy`、`origin`、`resolution`。
- 本地 `pytest` 未运行：`/Applications/Xcode.app/Contents/Developer/usr/bin/python3` 缺少 `pytest`。

## 阻塞与风险

- 本轮未验证规划器是否能直接消费新生成的 `.npz`，只验证了地图文件可生成并可读取。
- `maps/` 在远端 Git 状态中仍为未跟踪目录，包含输入 PCD 和输出地图；本轮不提交这些地图产物，避免把现场大文件纳入代码提交。
- 非 PCD 点云仍需要 `open3d`；`new-orin` 当前未安装该依赖。
- 控制台服务状态板块尚未在 new-orin 浏览器视觉截图验证；需同步后通过控制台页面检查。

## 下一步

1. 如需导航规划，使用新生成的 `.npz` 作为 `plan_nav_2d.py` 或动态规划脚本的 `--map` 输入做路径验证。
2. 如需长期支持 PLY 或其它点云格式，在 `new-orin` 安装 `open3d` 或补充对应格式的直接解析逻辑。
3. 如地图产物需要纳入发布流程，先确认仓库是否应追踪 `maps/` 及其文件大小策略。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

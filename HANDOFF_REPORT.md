# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：将 `global_nav` 点云转二维占据地图的高度截断改为相对估计地面高度。

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

- `unitree_slam_example_new/global_nav/build_grid_map.py` 新增 `estimate_ground_z()`：按 0.20m XY 网格取每格最低 z，再用最低包络的 5cm 直方图众数估计地面高度。
- `unitree_slam_example_new/global_nav/build_grid_map.cpp` 新增同等地面估计逻辑，C++ 文本地图输出路径也将 `--z-min/--z-max` 解释为相对地面的高度。
- Python/C++ 两个入口的 `--z-min/--z-max` 已从“地图坐标系绝对 z”改为“相对估计地面高度”；实际过滤范围为 `ground_z + z_min` 到 `ground_z + z_max`。
- Python 输出 `.npz` 额外写入 `ground_z`、`z_filter_absolute`、`z_filter_relative` 元数据；现有规划脚本只读取 `occupancy/origin/resolution`，兼容不受影响。
- 已同步代码到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline/unitree_slam_example_new/global_nav/`。
- 已用相对地面高度 `--z-min 0.20 --z-max 1.80` 重算两份地图、路径和可视化：
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_z020_z180_grid.npz`
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/global_map_20260708_124133_edited_z020_z180_grid.npz`
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/path_global_map_20260708_124133_z020_z180_start_to_goal.json`
  - `/mnt/disk1/gt/RobotAbrainOffline/maps/path_global_map_20260708_124133_edited_z020_z180_start_to_goal.json`
  - 对应 `*_world_view.png` 和 `*_grid_view.png` 可视化图已生成。

## 日志新增或调整

- `build_grid_map.py` 保持 `logging` 默认 INFO 级别。
- 转换开始时记录输入文件、输出文件、分辨率、相对高度过滤范围和膨胀半径。
- 读取 PCD 时记录文件路径、声明点数和数据格式；不记录原始点云数据。
- Python/C++ 都新增地面估计 INFO 日志，记录 `ground_z`、最低包络网格数量、候选数量、众数 bin。
- Python/C++ 都新增相对高度到绝对 z 范围的换算日志，便于现场确认过滤含义。
- 非 PCD 且缺少 `open3d` 时保留原始导入异常链，便于诊断依赖问题。

## 已验证事实

- 本地 `python3 -m py_compile unitree_slam_example_new/global_nav/build_grid_map.py` 通过。
- 远端 `python3 -m py_compile unitree_slam_example_new/global_nav/build_grid_map.py` 通过。
- `new-orin` 缺少 `open3d`，但存在 `numpy 1.26.4` 和 `Pillow 9.0.1`；本轮 PCD 读取不依赖 `open3d`。
- 原始点云 `global_map_20260708_124133.pcd` 估计 `ground_z=-1.316023349761963`，`--z-min 0.20 --z-max 1.80` 换算为绝对 z `[-1.116023349761963, 0.48397665023803715]`；生成栅格形状 `(932, 677)`，占据单元 `105377`。
- edited 点云 `global_map_20260708_124133_edited.pcd` 估计 `ground_z=-1.413818895816803`，`--z-min 0.20 --z-max 1.80` 换算为绝对 z `[-1.213818895816803, 0.38618110418319707]`；生成栅格形状 `(627, 400)`，占据单元 `37619`。
- 两个新 `.npz` 均已用 `numpy.load` 读取并确认包含 `occupancy`、`origin`、`resolution`、`ground_z`、`z_filter_absolute`、`z_filter_relative`。
- 使用起点 `(-1.0852, -0.2571)`、终点 `(-14.7038, 32.9859)`、目标 yaw `-0.16826904606068796` 重新规划成功：原始地图 `31` 个稀疏点、路径约 `67.399m`；edited 地图 `7` 个稀疏点、路径约 `37.118m`。
- 已用 `visualize_grid_map.py` 和 `visualize_map_and_path.py` 重新生成两套可视化图；本地已打开 edited world view 快速确认路径叠加正常。

## 阻塞与风险

- `maps/` 在远端 Git 状态中仍为未跟踪目录，包含输入 PCD 和输出地图；本轮不提交这些地图产物，避免把现场大文件纳入代码提交。
- 非 PCD 点云仍需要 `open3d`；`new-orin` 当前未安装该依赖。
- C++ 版未完成实际编译验证：`new-orin` 缺少 PCL 开发包，`cmake ..` 仍失败于找不到 `PCLConfig.cmake`/`pcl-config.cmake`。
- 地面估计使用最低包络众数，适合当前室内近似平地地图；多楼层、坡面或大面积台阶场景需要进一步加局部地面估计或人工指定地面高度。

## 下一步

1. 如需启用 C++ 转换入口，先在 `new-orin` 安装或配置 PCL 开发包，再运行 `cmake .. && make -j` 验证。
2. 如需长期支持 PLY 或其它点云格式，在 `new-orin` 安装 `open3d` 或补充对应格式的直接解析逻辑。
3. 如地图产物需要纳入发布流程，先确认仓库是否应追踪 `maps/` 及其文件大小策略。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

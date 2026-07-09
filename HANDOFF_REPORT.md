# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：移除控制台任务控制页顶部状态栏和标题栏网络电量块。

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

- `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py` 移除主内容区顶部白色状态栏，包括“RabbitBot 控制台”、顶部地图、控制台状态、主循环、导航桥接和当前模式。
- 移除任务控制页标题栏右侧的“网络正常 电量 92%”状态块。
- 调整任务控制页高度和标题栏布局，让移除顶部区域后页面继续铺满视口。
- 将前端 `setText()` 改为缺失元素容错，避免状态刷新继续写入已删除的顶部状态 DOM 时抛错。
- `rabbitbot-dev-ros2-master/tests/control_console/test_app.py` 增加页面模板断言，防止顶部状态栏和网络电量块被误加回来。

## 日志新增或调整

- 本轮仅调整前端页面结构和 DOM 容错，没有新增或调整运行时日志。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `1d320a9`，分支 `air_robot_gt_projects-master`。
- `python3 -m py_compile rabbitbot/agno_agents/workflow.py rabbitbot/control_console/app.py rabbitbot/control_console/status.py` 通过。
- `bash -n rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_workflow_loop.sh` 通过。
- `git diff --check` 通过。
- 轻量脚本确认控制台页面模板不再包含 `<header class="topbar">`、`<div class="tech-status">` 和“网络正常 电量 92%”文案。
- 轻量脚本确认 `setText()` 已改为缺失元素容错，页面仍保留主标题“双足机器人导览系统”。
- 本机系统 Python 缺少 `pytest`，因此未能在本机完整运行 `python3 -m pytest tests/control_console -q`。

## 阻塞与风险

- 本机缺少测试依赖，完整控制台 pytest 尚未在本机执行；服务器同步后可在具备项目运行环境的机器上补跑。
- 顶部地图和主循环/导航桥接状态入口被移除后，这些信息仍可通过服务状态管理、开发人员日志和状态接口查看；任务控制页不再展示顶部摘要。

## 下一步

1. 完成本轮提交后同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 并重启 `rabbitbot-control-console.service`。
2. 在控制台任务控制页刷新后确认顶部白色状态栏和“网络正常 电量 92%”块均已消失。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

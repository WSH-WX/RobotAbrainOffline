# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：将控制台任务控制页“机器人状态”板块改为显示真实 DDS 电量和机器人在线状态。

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

- `rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py` 新增 `RobotStatus` 和后台 DDS BMS 订阅缓存，订阅 `rt/lf/bmsstate` 的 `BmsState_` 并读取 `soc` 作为电量百分比。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/config.py` 新增 `dds_interface` 配置，优先读取 `RABBITBOT_DDS_INTERFACE` / `NAV_INTERFACE`，默认 `eno1`。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py` 的 `/api/status` 新增 `robot_status` 字段；任务控制页“机器人状态”板块改为真实电量、可视化电量条和在线/离线状态，移除“当前模式”。
- `rabbitbot-dev-ros2-master/tests/control_console/test_status.py` 增加机器人状态缓存单元测试；`test_app.py` 增加状态接口和页面模板断言。

## 日志新增或调整

- DDS BMS 订阅启动时记录 `INFO`，首次读到机器人 BMS 数据时记录 `INFO`，包含网卡、topic 和电量文本。
- 缺少 `unitree_sdk2py` 或 DDS 订阅异常时记录有上下文的 `WARNING`/异常日志；状态接口本身读取缓存，不在每次轮询时刷日志。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `9f60859`，分支 `air_robot_gt_projects-master`。
- `python3 -m py_compile rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py rabbitbot-dev-ros2-master/rabbitbot/control_console/config.py` 通过。
- `git diff --check` 通过。
- 轻量脚本确认 `get_robot_status()` 对最近 BMS 缓存返回在线和电量百分比，对过期缓存返回离线和 `N/A`。
- 轻量脚本确认控制台页面模板包含 `robotBatteryText`、`robotBatteryBar`、`robotStateText` 和 `renderRobotStatus`，且不再包含“当前模式”和“自主导览”。
- 本机系统 Python 缺少 `pytest`，因此未能在本机完整运行 `python3 -m pytest tests/control_console -q`。
- 本机系统 Python 缺少 `fastapi`，因此未能在本机用 `TestClient` 导入控制台应用做完整接口 smoke；改用文件文本检查页面模板。
- 服务器同步、服务重启和线上状态接口验证：待完成。

## 阻塞与风险

- 本机缺少测试依赖，完整控制台 pytest 和 FastAPI TestClient smoke 尚未在本机执行；服务器同步后可在具备项目运行环境的机器上补跑。
- 真实 DDS 订阅需要服务器控制台运行环境能导入 `unitree_sdk2py`，并且 `RABBITBOT_DDS_INTERFACE` / `NAV_INTERFACE` 指向连接机器人 DDS 的网卡。
- 当前以最近 `rt/lf/bmsstate` 消息作为机器人在线判据；超过 `RABBITBOT_ROBOT_STATUS_STALE_SECONDS`（默认 6 秒）未收到 BMS 数据即显示离线和 `N/A`。

## 下一步

1. 提交本轮代码，随后同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline`。
2. 重启 `rabbitbot-control-console.service`，请求 `/api/status` 确认返回 `robot_status` 字段。
3. 在真机 DDS 网络下刷新任务控制页，确认电量显示真实百分比、状态显示在线；断开或未读到 BMS 时显示 `N/A` 和离线。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

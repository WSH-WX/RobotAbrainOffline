# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：将“机器人状态”独立页面内容迁移到“任务控制”页面的机器人状态板块，并删除独立页面入口。

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

- 已把 `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py` 中原“机器人状态”页面的三项内容（开机自启动、定位状态、当前位姿）迁入“任务控制”页面左侧的“机器人状态”板块。
- 已移除侧边栏“机器人状态”导航按钮和独立 `page-status` 页面。
- 已替换“任务控制”页面机器人状态板块原有固定展示内容（92% 电量、空闲运行状态、自主导览模式）。
- 已调整 `rabbitbot-dev-ros2-master/tests/control_console/test_app.py` 页面断言，覆盖独立页面入口删除和旧固定内容移除。

## 日志新增或调整

- 本轮为前端页面结构调整，没有新增或调整运行时日志。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `3d42446e725353261525b68b91e6b7a79f2fff32`，分支 `air_robot_gt_projects-master`。
- 本机与服务器均相对 `origin/air_robot_gt_projects-master` ahead 11。
- 已执行 `python3 -m py_compile rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py rabbitbot-dev-ros2-master/tests/control_console/test_app.py`，语法检查通过。
- 尝试执行 `python -m pytest rabbitbot-dev-ros2-master/tests/control_console -q` 失败，因为本机没有 `python` 命令。
- 尝试执行 `python3 -m pytest rabbitbot-dev-ros2-master/tests/control_console -q` 失败，因为本机 Python 环境未安装 `pytest`。

## 阻塞与风险

- 本机缺少 `pytest`，未能运行完整控制台测试套件；只完成语法检查。
- 本轮未在浏览器或服务器运行态控制台中做视觉验收；部署后若服务已运行，需要重启或重新加载控制台服务才能看到页面变更。

## 下一步

1. 完成本轮 Git 提交。
2. 同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline`，保持本机与服务器同一提交。
3. 如需现场立即生效，在服务器上重启 `rabbitbot-control-console.service` 或让控制台进程重新加载新代码。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

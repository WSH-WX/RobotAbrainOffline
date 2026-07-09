# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：让控制台任务控制页显示真实导览任务进度，并移除“开发中”标识。

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

- `rabbitbot-dev-ros2-master/rabbitbot/agno_agents/workflow.py` 新增导览任务进度写出：每个 workflow run 在控制目录生成 `<run_id>.task_progress.json`，记录是否有活动任务、当前/下一站点、已完成点位数、总点位数和更新时间。
- 严格 DOCX 导览路径在导览开始、前往点位、到达点位、点位失败/跳过和导览结束时更新进度；旧脚本化导览路径也同步写出基本进度。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/status.py` 新增任务进度读取，缺失、损坏或读取失败时回退为空进度并记录诊断日志。
- `rabbitbot-dev-ros2-master/rabbitbot/control_console/app.py` 的 `/api/status` 返回 `task_progress`，任务控制页“任务信息”板块改为动态渲染：工作流未启动、待命、展厅导览、前往下一站点、当前站点、下一站点和真实进度条。
- 删除任务控制页所有可见“开发中”标签，并删除“预计状态”行；服务状态摘要保留为“读取中/在线数量”样式。
- `rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_workflow_loop.sh` 清理 workflow 控制目录时同步删除旧任务进度 JSON。
- 新增控制台状态相关测试，覆盖任务进度文件读取和 `/api/status` 返回任务进度。

## 日志新增或调整

- workflow 写任务进度成功时记录 INFO 级诊断日志，包含状态、完成点位数、当前/下一站点和进度文件路径。
- workflow 写任务进度失败时记录路径、状态和原始异常类型/消息，导览流程继续运行。
- 控制台读取任务进度 JSON 失败或格式非法时记录 warning/debug 级诊断日志，并回退为空进度，避免页面异常。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `a0dddc8`，分支 `air_robot_gt_projects-master`，工作区干净。
- `python3 -m py_compile rabbitbot/agno_agents/workflow.py rabbitbot/control_console/app.py rabbitbot/control_console/status.py` 通过。
- `bash -n rabbitbot-dev-ros2-master/scripts_1/start_nav_bridge_workflow_loop.sh` 通过。
- `git diff --check` 通过。
- 轻量脚本验证 `get_task_progress()` 可读取当前 run 的任务进度 JSON。
- 轻量脚本确认控制台页面模板不再包含“开发中”和“预计状态”，并包含任务进度所需 DOM id。
- 本机系统 Python 缺少 `fastapi` 和 `pytest`，因此未能在本机完整运行 `python3 -m pytest tests/control_console -q`。

## 阻塞与风险

- 本机缺少测试依赖，完整控制台 pytest 尚未在本机执行；服务器同步后可在具备项目运行环境的机器上补跑。
- 任务进度依赖 workflow 正常写出 `<run_id>.task_progress.json`；若 workflow 未启动或尚未开始导览，控制台按需求显示“工作流未启动”或“待命”并保持空进度条。
- 当前总点位数按 workflow 加载的导览步骤数计算，严格 DOCX 路径包含中转点位。

## 下一步

1. 完成本轮 Git 提交并同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline`。
2. 重启 `new-orin` 上的 `rabbitbot-control-console.service`。
3. 现场启动导览后，在任务控制页确认当前任务、进度条、当前站点和下一站点随 workflow 变化。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

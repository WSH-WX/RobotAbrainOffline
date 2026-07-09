# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：停止“机器人状态真实 DDS 电量”改造，回退已写入仓库的功能代码。

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

- 已按用户最新要求停止继续实现真实机器人状态功能：该功能需要控制台运行环境具备 `unitree_sdk2py` / CycloneDDS 依赖，属于环境变更范畴。
- 已回退本轮先前提交的机器人状态功能代码，当前仓库不保留 `robot_status` 接口、DDS BMS 订阅缓存、机器人状态面板改造或相关测试。
- 服务器上曾短暂安装 `cyclonedds-dev` 及其依赖以验证 Python SDK 安装路径；收到停止指令后已卸载这些包并执行 `apt autoremove`，未继续安装 `unitree-sdk2` Python 包。
- 未更改镜像，未重启 `rabbitbot-control-console.service`，运行中的控制台服务仍保持上一轮已部署状态。

## 日志新增或调整

- 本轮最终没有保留运行时代码改动，因此没有新增或调整运行时日志。

## 已验证事实

- 本轮开始前本机与 `new-orin:/mnt/disk1/gt/RobotAbrainOffline` 均为提交 `9f60859`，分支 `air_robot_gt_projects-master`。
- 先前机器人状态功能提交 `640c6f2` 已通过 `git revert` 回退，回退提交为 `7a808c5`。
- 服务器控制台虚拟环境与系统 Python 均无法导入 `unitree_sdk2py`；当前项目内 `unitree_sdk2` 目录为空，未发现可直接复用的 Python DDS SDK。
- 尝试安装 `unitree-sdk2` Python 包时失败，原因是构建依赖 `cyclonedds==0.10.2` 需要本机 CycloneDDS；这确认该功能涉及环境依赖变更。
- 已卸载本轮临时安装的 `cyclonedds-dev`、`cyclonedds-tools`、`libddsc0`、`libcycloneddsidl0` 和相关 iceoryx 包，并执行 `apt autoremove`。
- `rabbitbot-control-console.service` 当前仍为 active；本轮停止后未重启服务。

## 阻塞与风险

- 真实 DDS 电量读取需要在控制台运行环境中提供 `unitree_sdk2py` 与 CycloneDDS，或改为由已有机器人/导航运行环境暴露一个轻量状态接口；当前用户要求不做环境或镜像变更，因此功能停止。
- 如果未来允许改环境，需决定依赖放在宿主控制台虚拟环境、portable 镜像，还是由已有 nav/workflow 容器提供转发接口。

## 下一步

1. 将回退和本交接报告更新同步到 `new-orin:/mnt/disk1/gt/RobotAbrainOffline`，保持本机与服务器同一提交。
2. 不继续实现机器人真实电量功能，除非后续明确允许环境/镜像依赖调整，或提供一个现成可调用的机器人状态数据源。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

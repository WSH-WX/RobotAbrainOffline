# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：将控制台封面图替换为宇树 G1 正面抠图。

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

- 替换 `rabbitbot-dev-ros2-master/rabbitbot/control_console/static/unitree-g1-dashboard.png`。
- 新图为宇树 G1 正面机器人本体抠图，透明背景，保持原资源路径和 `1024x1536` 画布尺寸，避免修改控制台 HTML/CSS 引用。
- 控制台首页图片引用增加 `?v=20260709-g1-front` 版本参数，用于绕过浏览器旧图缓存。
- 素材来自网络检索到的 G1 正面产品图，白底来源页为 RoboStore 的 Unitree G1 商品页；另核对过 Unitree 官方 G1 页面作为产品外观参考。
- 本轮未修改控制台后端逻辑、部署脚本或运行配置。

## 日志新增或调整

- 本轮仅替换静态图片资源，没有新增或调整运行时日志。

## 已验证事实

- 本地已用 Pillow 打开新封面图，确认路径为 `rabbitbot-dev-ros2-master/rabbitbot/control_console/static/unitree-g1-dashboard.png`，尺寸 `(1024, 1536)`，模式 `RGBA`。
- 本地已人工预览抠图效果：机器人主体居中，背景透明，适配现有控制台封面图槽位。
- 已确认 `new-orin` 和 `http://192.168.101.121:8080/static/control_console/unitree-g1-dashboard.png` 返回的新图 SHA256 均为 `42a30a3e5cdc75aa0fe66ffe0620d0d6426bc86495e41995b462266b62b95590`。
- 本轮修改前本地 Git 工作区为空。

## 阻塞与风险

- 新图来自第三方商品页的白底产品图，并非项目自有拍摄素材；如现场有版权或品牌素材要求，应替换为授权图片。
- 透明抠图由本地脚本基于白底阈值生成，边缘在深色背景下已做收紧处理，但不是专业人工精修。
- 如果浏览器仍显示旧图，优先确认页面 HTML 中图片地址是否包含 `?v=20260709-g1-front`，其次再清理浏览器缓存。

## 下一步

1. 同步提交到 GitHub 后，在 `new-orin` 拉取更新并重启控制台服务。
2. 在控制台页面刷新缓存后确认封面图显示为 G1 正面透明抠图。
3. 如后续获得现场拍摄或官方授权透明图，可继续替换同一路径静态资源。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

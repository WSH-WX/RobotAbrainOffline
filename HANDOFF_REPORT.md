# RobotAbrainOffline 交接报告

生成时间：2026-07-09（Asia/Singapore）
本轮工作目录：`/Users/firmiana/Desktop/RobotAbrainOffline`
本轮主题：同步 fuxing 控制台能力与台词配置，保留本项目 portable 单镜像多容器部署结构。

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

- 控制台页面以 fuxing 为基准同步深色任务控制页、点位台词热更新、嘉宾称呼、当前位置回填、开机自启动按钮和静态机器人图展示。
- 控制台后端新增/合并 `/api/dialogue/leader-calling`、`/api/dialogue/hot-rows`、`/api/autostart`，并保留本项目 `/api/start-no-robot`、`/api/service/restart`、portable 服务状态和当前运行日志接口。
- `rabbitbot-dev-ros2-master/conf/dialogue_0.json` 已替换为 fuxing 台词；`dialogue_fuxing.json` 同步为同内容备份留档。
- workflow 数据层新增 `reload_docx_guide_dialogue()`，`run_kuavo_agno_workflow.py` 在 go 闸门释放后刷新台词缓存，确保热更新在下一次导览读取最新台词。
- `deploy/install_air_project.sh` 生成的 sudoers 增加 `enable/disable/is-enabled rabbitbot-loop.service` 权限，未引入 fuxing 旧路径 unit。
- 控制台测试补充 leader-calling、hot-rows、autostart、静态图和页面断言。

## 日志新增或调整

- `rabbitbot.control_console.commands` 新增开机自启动查询/设置 INFO 日志，失败记录 ERROR 并保留命令上下文。
- `rabbitbot.control_console.dialogue` 同步 fuxing 的台词读写、备份、嘉宾称呼校验、点位热更新读写日志；不记录完整台词正文。
- `rabbitbot.control_console.app` 对当前运行日志清空、服务容器后台重启提交/失败、开机自启动查询失败降级返回增加诊断日志。
- `rabbitbot.agno_agents.workflow_data` 在台词缓存刷新时记录 reason、台词文件路径、steps/points 数量。

## 已验证事实

- `python3 -m json.tool rabbitbot-dev-ros2-master/conf/dialogue_0.json` 通过。
- `python3 -m json.tool rabbitbot-dev-ros2-master/conf/dialogue_fuxing.json` 通过。
- `python3 -m py_compile` 已覆盖控制台、dialogue、commands、workflow 数据加载、workflow 入口和测试文件，通过。
- `bash -n deploy/install_air_project.sh rabbitbot-dev-ros2-master/scripts/run_kuavo_agno_workflow.py` 通过。
- 本机 `/Applications/Xcode.app/Contents/Developer/usr/bin/python3` 缺少 `pytest`，完整控制台 pytest 未运行。
- 本机缺少 FastAPI 运行依赖，无法用 `TestClient` 做手工路由调用；仅完成语法/JSON/shell 静态验证。
- GitHub `origin/air_robot_gt_projects-master` 已更新到本轮提交；new-orin 已通过 git bundle 同步到同一提交。
- new-orin 上 `docker compose config --services` 显示 `neo4j,rabbitbot-vlm,rabbitbot-memory,rabbitbot-navbridge,rabbitbot-stt,rabbitbot-tts,rabbitbot-workflow`，配置中旧路径 `/mnt/ssd/navgation`、`/mnt/disk1/gt/air_robot_gt_projects` 和 `fuxing` 计数为 0。
- new-orin 已重新安装正式 systemd unit/sudoers；`rabbitbot-control-console.service` 指向 `/mnt/disk1/gt/RobotAbrainOffline/rabbitbot-dev-ros2-master` 并处于 active。
- new-orin 正式控制台 `127.0.0.1:8080` 页面包含“双足机器人导览系统”“点位台词热更新”和 `unitree-g1-dashboard.png`；静态图 HEAD 返回 `200 OK image/png`；`/api/status` 返回 `200 OK`。
- new-orin `/api/start-no-robot` 短跑通过：`workflow.status=waiting_for_go`、`ready=true`、`no_robot_mode=true`；验证后已停止 `rabbitbot-loop.service`。

## 阻塞与风险

- 本地 Python 缺少 `pytest`、FastAPI 等测试依赖，`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest rabbitbot-dev-ros2-master/tests/control_console` 未能运行。
- 真机移动闭环、DDS 网卡、真实地图 `/home/unitree/test9.pcd`、TTS/STT/VLM/Memory 健康状态未在本轮本机验证。
- `runtime/portable.env` 和模型缓存完整性未做逐项审计；现场基础服务在控制台状态接口中为在线。

## 下一步

1. 在可用 Python 环境安装测试依赖后运行 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest rabbitbot-dev-ros2-master/tests/control_console`。
2. 在 new-orin 继续验证 leader-calling、hot-rows 和 autostart API 的实际页面操作。
3. 按现场需要再做真机环境验证；不做真实机器人移动闭环，除非另行要求。

## 注意事项

- 修改代码优先遵守现有风格。
- 关键流程、文件读写、网络请求、数据库、模型推理、命令脚本、配置加载和异常处理应保留有诊断价值的日志。
- 默认日志级别不得低于 INFO；DEBUG/TRACE 仅可短时诊断并必须有限量、限时、采样、轮转或降级机制。
- 不要提交运行态配置、密钥、令牌、模型缓存或大体积日志。

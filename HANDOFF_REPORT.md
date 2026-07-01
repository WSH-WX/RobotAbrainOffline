# air_robot_gt_projects 交接报告

> 本报告是“当前状态快照”，逐轮改动细节见 Git 历史；本轮已按规范压缩冗长的逐轮记录。

## 背景和目标

RabbitBot 自主运行包，部署在 ShuHao-orin。Git 根 `/mnt/disk1/gt/air_robot_gt_projects`，主代码 `rabbitbot-dev-ros2-master`，分支 `feature/qa-vlm-workflow`，Python 包 `rabbitbot`（>=3.10）。系统由 `rabbitbot-control-console.service`（控制台，nvidia 用户，8080）+ `rabbitbot-loop.service`（导览主循环）+ 一组容器化基础服务组成，支持 QA/导览 workflow、语音口令、返航、无机器人模式。

近期主线：把原来挤在单个 `rabbitbot-unified-runtime` 容器内的服务**解耦为多容器（docker-compose）**，并让导览 workflow 跑在专用容器上；配套修复前端、日志、TTS、STT、启动等问题。

## 当前运行架构（解耦栈，已上线）

由 `docker/portable/docker-compose.decoupled.yaml` 定义，全部 `network_mode: host`（服务间走 127.0.0.1，无需改服务地址）：

| 容器 | 镜像 | 端口/职责 |
|---|---|---|
| neo4j | 官方 neo4j:5.26-community | 7687 图数据库 |
| rabbitbot-vlm | core-portable | 8000 VLM + 8005 Embedding |
| rabbitbot-audio | core-portable | 28185 TTS(Kokoro) + 28184 STT(SenseVoice) |
| rabbitbot-memory | core-portable | 28182 Memory Agent(Graphiti) |
| rabbitbot-navbridge | nav-portable | 28180 导航桥接/Robot Agent |
| rabbitbot-workflow | core-portable | 导览 workflow 专用宿主（loop 经 docker exec 注入） |

- vlm/audio/memory/workflow 共用 core-portable 镜像，各只跑自己服务子集（`scripts_1/unified_runtime/start_role_container.sh`，按 `RABBITBOT_CONTAINER_ROLE` 分派；它 source `start_unified_container.sh` 复用启动函数）。
- loop 通过 `RABBITBOT_BASE_RUNTIME=compose`（写在 `runtime/portable.env`）切到解耦栈：`ensure_decoupled_services()` 用 `docker compose up` 拉起基础服务+workflow 宿主；`CONTAINER_NAME=rabbitbot-workflow`，所有 workflow 的 docker exec 指向它。真实机器人模式下 nav 唯一由 `rabbitbot-navbridge` 提供（前台 compose up 作进程组，复用既有 nav 生命周期）。
- 镜像未瘦身：3 个 rabbitbot 容器共用 core-portable（本机已无原始最小镜像）；容器层面已完全解耦。

## 当前状态

实测（截至生成时间）：6 容器全部运行（neo4j/vlm/audio/memory healthy，navbridge/workflow 无 healthcheck 但 Up），7 端口（7687/8000/8005/28182/28184/28185/28180）全 up，`rabbitbot-loop.service` 按需启停（当前 inactive，compose 基础服务持续在线），`RABBITBOT_BASE_RUNTIME=compose`、`RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1`。

已完成（本会话）：
- 解耦多容器 + loop 对接解耦栈 + 真机模式 nav 协同（见上）。
- 日志统一搬到 air 根 `/mnt/disk1/gt/air_robot_gt_projects/logs`（容器内 `/workspace/projects/logs`），旧 `<project>/logs` 已删除；6 处“日志根”定义点统一改造（loop 入口/主循环/容器入口/控制台 config/compose/`rabbitbot/tools/logging.py`）。
- 控制台前端：无机器人按钮移到操作区最后；`config.py` 的运行容器名/nav 容器名随 `RABBITBOT_BASE_RUNTIME` 切换（compose→`rabbitbot-workflow`/`rabbitbot-navbridge`），“关闭程序”文案与操作随之正确。
- `get_inst_chat` 换成精简现场对话提示词；无机器人模式手臂动作在 `provider.py::_post_arm_action` 入口短路跳过（不再等 28180 超时）。
- 修复：①“开始程序”按钮触发的 workflow 残留死循环（`kill_stale_workflow` 按进程特征清理残留再启动）；②curl 注入文本被“低音量打断”忽略（STT 记录“上次消费是否注入”，注入时 `get_last_rms` 返回高哨兵 1.0）；③TTS(Kokoro) 本地模型路径错误致离线下载崩溃（默认改用 `RABBITBOT_MODELS_DIR`=`/models` 下的 `Kokoro-82M`）。
- 导览开场白被打断后**继续(resume)剩余开场白**：被打断→回答提问→重播本句→继续后续开场白，不再吞词（开场回答回调由调用点注入，因 guide_opening_speech 为模块级、取不到嵌套的 chat_execute）。
- 控制台服务状态面板：新增“启动中”黄色态（主循环启动 180s 窗口内、端口未就绪的服务显示“启动中”，窗口外才“离线”；后端 `ServiceStatus` 增 `state` 字段，按主循环进程 `/proc starttime` 判定启动窗口 `SERVICE_STARTUP_GRACE_SECONDS=180`）；并去除“开始程序”等待超时弹出的“服务仍未全部就绪”聚合提示（面板已逐服务展示状态）。新增 3 个状态判定测试，控制台测试 69 passed。
- 控制台“一键重启”按钮改名为“一键重启主循环”；`/api/restart` 不再硬编码真机模式，改为读取并沿用重启前的运行模式（无机器人模式则仍以无机器人模式重启 loop，避免一键重启把模式覆盖成真机），新增 `test_restart_preserves_no_robot_mode`，控制台测试 70 passed。
- 控制台服务状态面板为每个服务加“重启”按钮：弹“是否确认重启…服务？”确认框，同容器服务(TTS/STT、VLM/Embedding)额外提示一并重启；新增 `POST /api/service/restart`(按服务解析容器并 `docker restart -t 20`，免 sudo)，`ServiceStatus` 增 `container` 字段与 `resolve_service_container` 映射(随 `RABBITBOT_BASE_RUNTIME` 切换)，刚重启的容器在宽限期内其服务显示“启动中”。新增 5 个测试，控制台测试 75 passed。
- 修复服务重启按钮反馈延迟：端点改为先打“启动中”标记 + 后台异步 `docker restart` 并立即返回（不再被优雅停止 ~20s 阻塞 HTTP）；新增“强制启动中”窗口 `SERVICE_RESTART_FORCE_STARTING_SECONDS=22`（重启发起后即使旧端口仍开也优先显示“启动中”，覆盖 `docker stop` 时长）；前端点击确认后乐观地立即把同容器卡片标“启动中”。新增 force-starting 测试，控制台测试 76 passed。
- 进一步修复“重启后短暂闪回在线”：实测确认后端 `/api/status` 重启后 0~35s 全程返回“启动中”（后端无问题），根因是前端每 2s 轮询会重建卡片，而“点击前已在途、携带在线数据的轮询响应”在乐观标黄后才返回、重绘时盖回绿色；前端新增 `pendingRestartUntil`，点击后 22s 内该容器强制显示“启动中”、不被任何轮询响应覆盖（与后端 force 窗口对齐）。提醒：浏览器需硬刷新页面才能加载最新前端 JS。
- 部署链路适配解耦栈（原先解耦只在运行层，deploy/README 仍是单容器）：`README.md` 增「运行架构：解耦多容器栈」总览并修订端口拓扑/流程 B 启动/模型要求/env 约定；`runtime/portable.env.example` 补 `RABBITBOT_BASE_RUNTIME=compose` 与 `RABBITBOT_NEO4J_IMAGE`（全新 Orin 从模板生成的 env 默认即解耦栈）；`deploy/start_portable_stack.sh` 按 `RABBITBOT_BASE_RUNTIME` 分流（compose→`docker compose up docker-compose.decoupled.yaml`）；`deploy/export|import_portable_images.sh` 纳入 neo4j 官方镜像离线交付；`deploy/check_air_project.sh` 增 `docker-compose.decoupled.yaml` 存在性检查。`install_air_project.sh` 无需改（只装 systemd，容器由 loop 按 env 拉起）。已实测 compose 分支幂等启动 5 容器 healthy、neo4j 镜像就位、脚本 `bash -n` 通过；**全新 Orin 端到端冷启动未验证（本机为已部署机）**。
- 会前已完成：DJI Mic Mini 右声道 STT 输入修复（双声道按 RMS 选道、`STT_INPUT_GAIN=8.0`、新增 `get_last_rms` 诊断接口）。

未完成 / 待办：
- **控制台改动（`config.py` 容器名/日志路径、`status.py`/`app.py` 服务状态“启动中”态与去除聚合提示）需重启 `rabbitbot-control-console.service`（sudo）才生效，尚未重启。**
- 机器人离线：真机导航/返航、nav 核心 Pose/Ready 未端到端验证。
- 导览数据为空：`combined_data.json` 缺失 + Neo4j 展点 0 节点 → 导览中导航/检测类提问会命中“异常结点”。
- 已知未修 bug：`workflow.py::navi_execute` 的 `random.sample(ctx.entity_lst, 1)` 在展点为空时崩溃（“Sample larger than population”），挡住导览导航/检测路径；与解耦无关，需修 + 灌入展点数据。

## 已验证的事实

- nvidia 用户在 docker 组（免 sudo 跑 docker）；sudoers **仅** `systemctl start/restart/stop rabbitbot-loop.service` 免密；`rabbitbot-control-console.service` 重启需 sudo 密码（非交互无法执行，须 Aaron 手动）。
- Neo4j 凭据 `neo4j/neo4j_pass`；模型挂载 `/mnt/disk1/models` → 容器 `/models`；TTS 模型 = 本地 Kokoro-82M（中文音色 zm_yunxi，`/models/Kokoro-82M`）。
- 解耦栈实测通过：跨容器记忆写入/查询召回正确；loop(compose+无机器人)→workflow 在 `rabbitbot-workflow` 容器到 QA 待命、跨容器调 audio 容器 TTS 成功；TTS 本地模型加载无下载错误、`text_to_speech` 合成成功；STT 注入后 `get_last_rms` 由 0.0032 变 1.0；控制台测试 `66 passed`。
- STT 端口 28184，注入口令用 `/exec` 的 `inject_text_async`（与“对麦克风说话”同路径，被 `get_text_async` 消费）。

## 阻塞问题

- 机器人离线：实机链路（eno1、Unitree DDS、导航核心、28180）无法端到端验证。
- 导览点位数据缺失（`combined_data.json` + Neo4j 展点），叠加 `random.sample` 空列表崩溃，导致导览导航/检测路径走不通。

## 建议的下一步

1. 重启控制台服务使 `config.py` 改动（容器名/日志路径）生效：`sudo systemctl restart rabbitbot-control-console.service`。
2. 修 `navi_execute` 的 `random.sample` 空列表崩溃；准备 `combined_data.json` 或用 importer 把展点导入 Neo4j，再验证导览“带我去找 X”端到端（记忆+导航）。
3. 机器人上线后：验证 `rabbitbot-navbridge` 输出 Pose/Ready、loop 进入真机导览与返航。

## 注意事项

- `RABBITBOT_BASE_RUNTIME=compose` 在 `runtime/portable.env`（本机配置，未入库；代码默认仍 `unified`）。回退旧单容器路径：改回 `unified`。
- 解耦栈与旧 `rabbitbot-unified-runtime` **互斥，勿同时启动**（host 网络端口冲突）；旧 unified 仅停未删，作回退。
- 日志属主：正常 loop 启动会先以 nvidia 建日志目录再起容器；若**手动 `docker compose up` 先于 loop**，docker 会以 root 建 air 根/logs 子目录致 loop(nvidia) 无法写，需 `docker exec <core 容器> chown -R 1000:1000 /workspace/projects/logs`。
- 无机器人开关 `RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1`（兼容名 `RABBITBOT_WORKFLOW_NON_INTEGRATION`）；无机器人模式下手臂动作被跳过、不需 28180，可用 `RABBITBOT_ARM_ACTION_FORCE_WHEN_NO_ROBOT=1` 强制发送。
- 可调环境变量：`KOKORO_MODEL_DIR`（TTS 模型目录）、`STT_INJECTED_RMS`（注入哨兵音量，默认 1.0）、`STT_INPUT_GAIN`、`RABBITBOT_INTERRUPT_RMS_THRESHOLD`、`RABBITBOT_WORKFLOW_CONTAINER_NAME`。
- 服务状态面板是短超时端口探测，不等同于 systemd/Docker 状态。远端无 `rg`，用 `find`/`grep`。

## 关键文件与端口

- 解耦栈：`docker/portable/docker-compose.decoupled.yaml`、`scripts_1/unified_runtime/start_role_container.sh`、`start_unified_container.sh`。
- 编排：`scripts_1/start_loop_entry.sh`、`scripts_1/start_nav_bridge_workflow_loop.sh`。
- 控制台：`rabbitbot/control_console/{app,commands,config,status,dialogue}.py`。
- 业务：`rabbitbot/agno_agents/{workflow,prompts}.py`、`rabbitbot/provider.py`、`stt_app_funasr.py`、`tts_app.py`、`rabbitbot/audio/run_tts_espnet.py`、`rabbitbot/tools/{sound_agno,logging}.py`。
- 端口：Neo4j 7687 / VLM 8000 / Embedding 8005 / Memory 28182 / STT 28184 / TTS 28185 / Robot Agent·nav 28180 / 控制台 8080。

## 最近历史摘要（提交）

- 部署链路适配容器解耦：README + portable.env.example + start_portable_stack.sh + export/import + check 改用 compose 解耦栈（本轮提交）
- `97ef15a` 修复“重启后前端短暂闪回在线”：前端加本地强制启动中窗口 `pendingRestartUntil`，不被在途轮询响应覆盖
- `02e5dcd` 修复服务重启按钮反馈延迟：先标记+后台异步重启+立即返回，新增强制启动中窗口与前端乐观更新
- `73982f0` 控制台服务状态面板每服务加“重启”按钮（重启对应容器/服务，TTS/STT 等同容器提示一并重启）
- `6761317` “一键重启”改名“一键重启主循环”并沿用重启前运行模式（无机器人模式不再被覆盖成真机）
- `c0bda9e` 控制台服务状态新增“启动中”黄色态、去除“服务仍未全部就绪”提示（含 3 个状态测试）
- `3a9e05d` 开场打断回答失败(NameError)修复：回答回调由调用点注入
- `33c6bb7` 开场白被打断后继续剩余开场白(resume)，不再吞词
- `e396078` TTS(Kokoro) 本地模型路径修复（离线本地加载）
- `dbf6f6b` 注入文本被“低音量打断”忽略修复
- `1f03820` “开始程序”按钮 workflow 残留死循环修复
- `dedea04` 日志统一迁移到 air 根并清理旧日志
- `adef602` 控制台前端适配解耦栈（容器名/文案随运行方式）
- `4d14a51` 真实机器人模式 nav 与解耦 compose 协同
- `4f156b3` loop 基础服务依赖解耦 compose、workflow 专用容器
- `64c4cdd` 解耦统一容器为五个独立容器(docker-compose)
- 更早：`6cd1543` get_inst_chat 精简提示词；`74ed6bf` 无机器人跳过手臂动作；`080a224` 控制台按钮顺序；`e67ee72` DJI 右声道 STT 修复；以及 TTS 声卡回退、Embedding/VLM 默认启用、当前运行日志面板、返航、portable core/nav 镜像、systemd/sudoers 治理（均已压缩，详见 git log）。

生成时间：2026-06-30

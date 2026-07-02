# RabbitBot 重构与回归测试交接报告

生成时间：2026-07-02 21:05（Asia/Singapore）
当前分支：`refactor/rabbitbot-runtime-structure-stabilization`
当前范围：`rabbitbot-dev-ros2-master` 主链路重构与无机器人模式回归测试

## 背景和目标

Aaron 已完成三轮小步重构，本轮目标不是继续改业务代码，而是在无机器人模式下做运行回归：

- 确认 loop 开启后是否还能进行问答。
- 确认 DOCX 导览流程是否能正常启动、推进并走完。
- 确认 STT/TTS 音频设备和服务是否能连接成功。
- 补跑三轮重构相关单元测试，判断重构是否引入基础回归。

## 当前状态

已完成的三轮重构提交：

- `46aee17 启动主链路稳定性重构`：抽出音频 `/exec` 客户端和运行配置读取，保留 `provider.py` 兼容入口。
- `eccef40 抽出 workflow 纯逻辑模块`：新增 `rabbitbot.guide.controls` 与 `rabbitbot.guide.dialogue`，承载控制词、DOCX dialogue、点位解析等纯逻辑。
- `c8a607d 抽出 workflow 导航文本规则`：新增 `rabbitbot.guide.routing`，承载导航文本归一化、意图规则和实体模糊匹配。

本轮运行测试状态：

- 基础栈已启动并保持在线：`neo4j`、`rabbitbot-vlm`、`rabbitbot-audio`、`rabbitbot-memory`、`rabbitbot-workflow` 均运行，带 healthcheck 的容器为 healthy。
- `runtime/rabbitbot-loop.env` 当前为无机器人模式：`RABBITBOT_NAV_WORKFLOW_NO_ROBOT=1`、`RABBITBOT_WORKFLOW_NON_INTEGRATION=1`。
- 本轮 loop 测试已结束，未留下 `start_loop_entry`、`start_nav_bridge_workflow_loop` 或 workflow 残留进程。
- 本轮未修改业务代码，只更新本交接报告。

## 本轮测试结果

### 音频设备与服务

结论：音频服务和设备连接成功。

- STT 文档接口 `http://127.0.0.1:28184/docs` 可访问。
- TTS 文档接口 `http://127.0.0.1:28185/docs` 可访问。
- TTS 短文本请求返回 200，服务端日志完整经过 `tts_enqueue_text`、`tts_generate_done`、`tts_play_start`、`tts_play_done`。
- TTS 当前后端为 `local`，原因是 `eno1` Unitree 链路无物理载波，自动回退本地外接输出设备。
- TTS 当前选中输出设备：`REDMI Speaker 2-4550: USB Audio (hw:3,0)`，index=25，reason=`non_hda_external`。
- STT 当前选中输入设备：`DJI MIC MINI: USB Audio (hw:1,0)`，index=4。
- `rabbitbot-audio` 当前为 healthy。

### loop 问答

结论：loop 开启后可以进入 QA 状态，可以完成一次模型问答并触发 TTS 输出；但回声打断问题仍存在。

- loop 按无机器人模式启动，跳过真实导航桥接。
- workflow 进入默认 QA 状态，日志显示 `voice_qa_mode` 和“等待用户说话”。
- 通过 STT `inject_text_async` 注入一条短问，STT 返回相同文本和 `utterance_id`，说明注入/消费链路可用。
- workflow 调用模型接口成功，随后连续向 TTS 发送回答片段，TTS 服务端也记录了播放完成。
- 问答后 STT 多次把 TTS 输出听成用户输入，例如把回答内容截成后续问题，触发“用户打断”或继续追问。这不是本轮三次纯逻辑重构引入的导入错误，但仍是当前运行态稳定性问题。

### DOCX 导览流程

结论：导览可以被开始口令触发，开场和前两个无机器人到点确认能推进；但完整导览未走完，卡在剧本段落被 TTS 回声反复打断。

- 干净启动第二轮 loop 后，语音口令触发成功，日志显示 `语音口令启动导览: trigger_len=4, opening_enabled=1`。
- 无机器人模式动作跳过正常，日志显示 `provider动作链路: stage=no_robot_mode_skip`。
- DOCX dialogue 加载成功：默认 `dialogue_0.json`，points=7、steps=8、segments=6。
- 开场白能够播放并继续推进；部分低音量回声被正确忽略。
- 剧本进入 `1到2过渡`，等待 `arrive`；发送到达确认后推进到 `点位2`。
- 剧本进入 `跟随步行到点位2`，再次发送到达确认后推进到 `点咖啡`。
- 在 `点咖啡` 段，TTS 输出反复被 STT 识别成打断文本，workflow 反复回到同一段重播，未能走完整个导览。
- 第一轮在普通问答后再注入“开始导览”时，口令被处于打断监听路径的 STT 当作普通用户输入，未切入剧本导览，并最终出现 `list index out of range`；这说明“从问答中切导览”的状态机边界仍有 bug。

## 已验证的事实

- 编译检查通过：`PYTHONPYCACHEPREFIX=/tmp/rabbitbot_refactor_pycache python3 -m py_compile rabbitbot/guide/*.py rabbitbot/agno_agents/workflow.py tests/guide/*.py`。
- guide 单元测试通过：`python3 -m unittest discover tests/guide -v`，20 tests OK。
- 客户端/运行配置测试通过：`python3 -m unittest tests.clients.test_audio_clients tests.clients.test_runtime_config -v`，9 tests OK。
- 当前三轮重构新增的纯逻辑边界没有基础编译或单元测试回归。
- 本轮运行验证确认至少 3 类此前高风险链路已可工作：音频容器重建与设备选择、无机器人 loop 启动并进入 QA、无机器人 `arrive` 到点确认推进。
- 本轮仍确认 2 个影响现场流程的 bug：TTS 回声被 STT 当成用户打断；问答状态中注入开始导览时可能走入普通聊天/错误路径。

## 阻塞问题

- 完整导览流程未通过，主要阻塞是 TTS 播放期间 STT 仍能听到自身声音并触发导览打断；在 `点咖啡` 段已复现多次重复打断。
- 问答后切导览的状态机路径不稳：当开始口令进入 `audio_input_stop_chat` 打断路径时，没有优先识别为导览控制词。
- 机器人真机链路未验证，本轮全程无机器人模式，不代表 28180、导航核心、Unitree DDS 或真实返航可用。

## 建议的下一步

1. 优先修 TTS/STT 回声打断：TTS 播放期间暂停或门控 STT、加强回声文本过滤、或把“正在播放的 TTS 文本片段”作为打断过滤上下文。
2. 修状态机控制词优先级：无论文本来自主听音、打断监听还是 pending 用户输入，只要匹配“开始导览/返回起点”等控制词，应先走控制逻辑而不是普通聊天。
3. 增加一条集成级无机器人脚本测试：启动 loop、注入开始导览、自动发送 `arrive`、断言进入若干剧本步骤或完成，用于后续回归。
4. 在真实设备环境中复测 STT 麦克风和 TTS 输出的物理声学位置；如果必须同房间外放，建议降低麦克风监听期间的扬声器串音或改用更稳定的声学回声消除方案。
5. 真机上线后再单独验证导航桥接、实际到点、返航与机器人动作，不要把本轮无机器人结果外推到真机链路。

## 注意事项

- 本轮测试使用的运行日志：`logs/current_runtime_refactor_test.log`、`logs/current_runtime_refactor_guide_only.log`、`logs/nav_workflow_control/rabbitbot_workflow_20260702_204955.log`、`logs/nav_workflow_control/rabbitbot_workflow_20260702_205251.log`。
- STT/TTS 日志在 `logs/unified_runtime/rabbitbot_stt.log`、`logs/unified_runtime/rabbitbot_tts.log`。
- 无机器人到点确认使用 `bash scripts_1/send_nav_workflow_command.sh arrive`。
- 停止本轮 loop 使用 `bash scripts_1/send_nav_workflow_command.sh quit`，已执行。
- 本轮未新增代码日志点；本轮结论依赖已有日志点，包括音频客户端初始化、TTS 服务链路、workflow TTS 请求链路、DOCX dialogue 加载、无机器人到达确认、no-robot 动作跳过和导览打断日志。

## 历史摘要

- 已完成容器解耦、portable stack、模型按需检查、控制台状态面板、音频设备自动选择、markdown/Neo4j 记忆合并等多轮工作。
- 旧报告超过 200 行的详细历史已压缩；需要逐项追溯时以 Git 历史为准。
- 近期关键提交还包括 `cb97945 调整TTS音频设备选择顺序为auto`、`f9f4a4d 调整 TTS 本地输出设备优先级`、`4edd961 调整 Kokoro TTS 模型默认路径`、`a707775 修复控制台服务状态启动中判定遗漏整机重启场景`、`3e135c6 修复关闭程序的多容器重启逻辑`。

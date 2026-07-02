# RabbitBot 重构交接报告

生成时间：2026-07-02 22:15（Asia/Singapore）
当前分支：`refactor/rabbitbot-runtime-structure-stabilization`
当前范围：TTS/STT 音频架构解耦与设备兼容层

## 背景和目标

Aaron 关注 TTS 与 STT 的互相干扰、各自可靠性差，以及后续可能增加蓝牙音频设备支持。本轮目标是先从架构上解耦，不改 TTS 合成、STT 识别、VAD、播放队列等核心逻辑：

- 将原 `rabbitbot-audio` 拆为独立 `rabbitbot-tts` 与 `rabbitbot-stt`。
- 保持 `/exec` 协议和端口 `28185/28184` 兼容。
- 新增统一音频设备探测/选择层，为 ALSA、PulseAudio、Bluetooth 设备诊断和后续蓝牙支持预留入口。
- 保持默认无机器人模式下的 ALSA USB 输出和 DJI MIC MINI 输入路径可用。

## 当前状态

已完成内容：

- `docker/portable/docker-compose.decoupled.yaml` 已拆出 `rabbitbot-tts` 与 `rabbitbot-stt`，`rabbitbot-workflow` 改为等待两个服务分别 healthy。
- `scripts_1/unified_runtime/start_role_container.sh` 新增 `tts`、`stt` 角色；保留 `audio` 兼容入口，当前会同时启动 TTS 与 STT。
- 新增 `rabbitbot/audio/device_probe.py`，统一探测 ALSA playback/capture、PulseAudio sinks/sources、Bluetooth 设备，并输出 `kind/device_name/device_index/reason/available`。
- `scripts/start_tts_app.bash` 与 `scripts/start_stt_funasr_app.bash` 已改为调用统一探测层，TTS/STT 核心服务逻辑未改。
- 新增 `docker/portable/docker-compose.audio-pulse.yaml`，显式启用时才挂载 PulseAudio socket；默认关闭，避免 socket 不存在阻断容器启动。
- 控制台容器映射已更新为 `rabbitbot-tts`、`rabbitbot-stt`，TTS/STT 可分别重启。
- 便携拆分栈默认 `RABBITBOT_TTS_BACKEND=local`，避免无机器人模式被旧 `auto/unitree` 环境误导；真机联调仍可显式设置 `unitree` 或 `auto`。
- 本轮测试后已清理临时 loop/workflow 测试进程，保留基础容器运行。

未完成内容：

- 未实现 PulseAudio 或 Bluetooth 播放/录音后端，只完成探测、日志和 compose override 入口。
- 未修 TTS 播放期间 STT 误收回声的问题。
- 未修 workflow QA 空输入进入计划步骤后 `list index out of range` 的状态机问题。
- 未做真机、导航桥接、实际返航验证。

## 已验证的事实

静态与单元测试：

- `bash -n` 覆盖启动脚本、角色入口、loop 入口和顶层便携启动脚本，通过。
- `docker compose -f docker/portable/docker-compose.decoupled.yaml config` 通过。
- `docker compose -f docker/portable/docker-compose.decoupled.yaml -f docker/portable/docker-compose.audio-pulse.yaml config` 通过。
- `PYTHONPYCACHEPREFIX=/tmp/rabbitbot_refactor_pycache python3 -m py_compile ...` 覆盖新增探测模块、控制台映射和相关测试，通过。
- `python3 -m unittest tests.audio.test_device_probe -v`：7 tests OK。
- `python3 -m unittest tests.clients.test_audio_clients tests.clients.test_runtime_config -v`：9 tests OK。
- 控制台 pytest 用例未执行：当前系统 Python 缺少 `pytest`，报 `/usr/bin/python3: No module named pytest`；相关文件已通过 `py_compile`。

运行验证：

- 已用 compose 启动拆分栈，`rabbitbot-tts` 与 `rabbitbot-stt` 均达到 healthy。
- TTS 设备探测选择 `REDMI Speaker 2-4550: USB Audio (hw:3,0)`，reason=`non_hda_external`。
- STT 设备探测选择 `DJI MIC MINI: USB Audio (hw:1,0)`，reason=`external_microphone`。
- `POST http://127.0.0.1:28185/exec` 的 `wait_speech` 返回 200。
- `POST http://127.0.0.1:28185/exec` 的 `text_to_speech` 返回 200，协议兼容。
- `POST http://127.0.0.1:28184/exec` 的 `inject_text_async` 与 `get_text_async` 返回 200，注入链路兼容。
- 单独重启 `rabbitbot-tts` 时，`rabbitbot-stt` 仍可响应；单独重启 `rabbitbot-stt` 时，`rabbitbot-tts` 仍可响应；最终两个服务都 healthy。
- 无机器人 loop 能启动，能进入默认 QA 状态，基础服务依赖 healthy，TTS 能播出 QA 提示。

## 阻塞问题

- 无机器人 QA 未稳定通过：workflow 进入 QA 后，STT 先收到 TTS 提示音回声，回声清理后得到空输入，随后 `plan_step` 出现 `list index out of range`。这不是容器拆分导致的端口或设备问题，而是当前 TTS/STT 互相干扰与 workflow 空输入防护不足共同暴露的问题。
- 本轮没有继续推进完整 DOCX 导览流程，因为 QA 阶段已经复现上述阻塞；此前报告中“点咖啡段被 TTS 回声反复打断”的问题仍视为未解决。
- 启动日志仍有旧路径会记录完整 TTS 文本或 STT 注入文本，本轮新增的设备探测日志没有记录完整用户语音原文，但历史 workflow/TTS 日志点仍需后续治理。

## 建议的下一步

1. 先做 TTS/STT 运行期互斥或门控：TTS 播放期间暂停 STT 监听、降低 STT 权重，或让 STT 服务显式知道当前 TTS 播放状态。
2. 给 workflow 增加空输入防护：回声过滤后为空时不要进入 planner，应继续监听或返回可诊断的跳过状态。
3. 把“开始导览/返回起点”等控制词提升到所有 STT 文本入口的最高优先级，包括主听音、打断监听和 pending 用户输入。
4. 在本轮 `device_probe.py` 基础上继续抽象播放/录音后端接口，再接 PulseAudio 输出，最后再接蓝牙设备。
5. 增加集成级无机器人回归脚本：启动 loop、注入 QA、注入开始导览、发送 arrive，自动断言状态和日志关键字。

## 注意事项

- 新增设备探测日志使用 Python `logging`，默认 INFO 只记录探测摘要、选中设备、候选数量、Pulse/蓝牙候选数量、等待和超时原因；候选设备明细降到 DEBUG。
- TTS/STT 启动脚本记录音频后端、Pulse 开关、Pulse server、设备等待参数、最终选中设备和原因，便于排查 USB 枚举慢或误选内置声卡。
- 首次拆分启动时曾短暂复现外接声卡枚举慢导致内置声卡回退，本轮已改为在只看到 `builtin_fallback` 时继续等待外接设备，TTS/STT 都有单测覆盖。
- 默认不启用 PulseAudio，只有叠加 `docker-compose.audio-pulse.yaml` 并设置相关环境变量时才挂载 Pulse socket。
- 真机使用 Unitree TTS 时需要显式设置 `RABBITBOT_TTS_BACKEND=unitree` 或 `auto`；无机器人便携拆分栈默认 `local`。
- 本轮临时验证日志：`/tmp/rabbitbot_loop_audio_refactor.log`、`/tmp/rabbitbot_loop_audio_refactor.nohup`、`logs/unified_runtime/rabbitbot_tts.log`、`logs/unified_runtime/rabbitbot_stt.log`。

## 历史摘要

- 近期已完成：音频 `/exec` 客户端抽出、workflow DOCX/控制词纯逻辑抽出、workflow 导航文本规则抽出、无机器人模式回归测试记录。
- 上一轮运行回归已经确认：音频设备和服务能连接，loop 能进入 QA，导览能被开始口令触发并推进部分点位，但 TTS 回声打断仍阻塞完整流程。
- 旧报告详细历史已压缩；需要逐项追溯时以 Git 历史为准。

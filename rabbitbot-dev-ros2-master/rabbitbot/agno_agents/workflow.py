
import time
import json
import random
import asyncio
import threading
import os
import subprocess
import shlex
from pathlib import Path
from datetime import datetime
import difflib
import re
import ast
import atexit
from agno.workflow.v2 import (
    Workflow,
    Loop,
    Router,
    StepInput,
    Step,
    StepOutput,
    Workflow
)
from agno.run.v2.workflow import WorkflowRunResponseEvent
from agno.agent import Agent
from rabbitbot.agno_agents.sound import RealtimeSTT, RealtimeTTS
from rabbitbot.tools.logging import logger as file_logger

from .models import (
    CompletionCheckModel,
    StaticOrDynamicNavigationModel,
    SimpleDelegationTaskModel,
    DelegationTaskModel,
    #ActionModel,
)
from .prompts import (
    get_inst_plan,
    get_inst_navi_check,
    get_inst_chat,
    get_inst_post_docx_chat,
    get_inst_search_check,
    get_inst_ctoe_translate
)
from .chat import ChatQueue
from rabbitbot.robots.constants import MoveType, NavigationStatus
from rabbitbot.tools.navi_agno import NavigationToolkit, NavigationQuery, is_navigating
from rabbitbot.tools.sound_agno import (
    tts_sound, tts_wait, tts_stop, tts_fast, tts_get_wav_count,
    tts_long_text_with_stt_stop,
    tts_long_text,
    action_with_tts, wait_with_tts,
    audio_input_execute,
    audio_input_execute_timeout,
    audio_input_execute_timeout_navi,
    tts_ask_with_early_stt,
    audio_input_yes_or_no,
    audio_input_yes_or_no_ignore_echo,
    audio_input_stop_chat,
    yes_or_no_quick_match,
    identify_think_type,
    build_guide_go_to_text,
    build_stt_prompt_by_list
)
from rabbitbot.tools.detect_agno import DetectToolkit

from typing import Any, List, AsyncIterator, Union
from textwrap import dedent
from rich.console import Console
from rich.pretty import pprint
from rich.prompt import Prompt
from agno.exceptions import StopAgentRun
import numpy as np
import cv2
from rabbitbot.provider import create_general_vlm_openai
from rabbitbot.guide.controls import (
    DEFAULT_CONTINUE_TEXTS,
    build_control_commands,
    is_continue_text,
    matches_control_command,
    normalize_control_text,
)
from rabbitbot.guide.routing import (
    classify_task_by_rule as guide_classify_task_by_rule,
    has_any as guide_has_any,
    has_navigation_action as guide_has_navigation_action,
    is_chat_info_request as guide_is_chat_info_request,
    is_direct_navigation_request as guide_is_direct_navigation_request,
    is_next_board_request as guide_is_next_board_request,
    is_visual_request as guide_is_visual_request,
    normalize_nav_text as guide_normalize_nav_text,
    resolve_navigation_entity_by_fuzzy as guide_resolve_navigation_entity_by_fuzzy,
)
from rabbitbot.guide.dialogue import (
    dialogue_index as guide_dialogue_index,
    dialogue_path as guide_dialogue_path,
    extract_location_points as guide_extract_location_points,
    format_guide_text as guide_format_text,
    guide_leader_calling as guide_dialogue_leader_calling,
    guide_map_file as guide_dialogue_map_file,
    guide_variables as guide_dialogue_variables,
    load_dialogue as guide_load_dialogue,
    load_script_steps as guide_load_script_steps,
    normalize_point_entity as guide_normalize_point_entity,
    opening_text as guide_opening_text,
    point_entities as guide_point_entities,
)

# ==== 关注点模块拆分：以下符号已迁出到同目录子模块，此处重导出以保持原命名空间不变 ====
from .workflow_config import (
    _env_enabled,
    _workflow_verbose_enabled,
    _workflow_non_integration_enabled,
    _strict_docx_script_enabled,
    _docx_guide_qa_interrupt_enabled,
    _workflow_log,
    _workflow_profile_enabled,
    _workflow_profile_path,
    _workflow_profile_summary_enabled,
    _should_speak_with_action,
    _env_float,
)
from .workflow_profiling import (
    WorkflowTimePoints,
    _profile_lock,
    _profile_span_id,
    _profile_summary_lock,
    _profile_summary,
    _workflow_timestamp,
    _format_log_fields,
    _workflow_action_log,
    _profile_json_safe,
    _profile_write,
    _profile_next_span_id,
    _profile_start,
    _profile_end,
    _profile_instant,
    _profile_summary_reset,
    _profile_summary_start_if_needed,
    _profile_summary_label,
    _profile_summary_record,
    _profile_summary_line,
    _profile_summary_print,
    _profile_summary_print_at_exit,
)
from .workflow_text import (
    COMMON_SURNAMES,
    _find_common_surname,
    _extract_leader_calling,
    _parse_first_visit_answer,
    _is_empty_stt_text,
)
from .workflow_data import (
    DOCX_GUIDE_DIALOGUE_DIR,
    DOCX_GUIDE_DIALOGUE_DEFAULT_INDEX,
    _DOCX_GUIDE_DIALOGUE_CACHE,
    _docx_guide_dialogue_index,
    _docx_guide_dialogue_path,
    _load_docx_guide_dialogue,
    reload_docx_guide_dialogue,
    _docx_guide_variables,
    _docx_guide_leader_calling,
    _docx_guide_map_file,
    _normalize_docx_point_entity,
    _docx_guide_point_entities,
    _format_docx_guide_text,
    _docx_opening_text,
    _load_docx_script_steps,
    DOCX_SCRIPT_POINTS,
    _load_docx_point_entity,
    _ensure_start_position,
    _wait_manual_navigation_success,
    _load_combined_data,
    _load_json_entity_order,
    _load_json_entity,
    _extract_first_location_point,
    _extract_location_points,
    _prefer_json_entity_location,
    JSON_ENTITY_ORDER,
)
from .workflow_arm import (
    ARM_ACTIONS_NEED_RELEASE_BEFORE_SPEECH,
    ARM_ACTIONS_NEED_RELEASE_AFTER_SPEECH,
    ARM_RELEASE_ACTION,
    ARM_BEFORE_RELEASE_DELAYS,
    ARM_BEFORE_RELEASE_DELAY_ENV,
    HAND_GESTURE_COMMANDS,
    _get_hand_gesture_command,
    _publish_hand_gesture_for_arm_action,
    _format_arm_action_success,
    _log_arm_action_latency,
    _do_arm_async_timed,
    _send_release_arm,
    _send_release_arm_sync,
    _do_arm_before_speech,
    _do_arm_sync,
    _do_arm_during_speech,
    _release_arm_after_concurrent_speech,
    _release_arm_after_speech,
)
# ==== 关注点模块重导出结束 ====




workflow_configs = {
    "max_chat_history": 5,
    "max_chat_steps": 1
}

PLAN_SESSION_ID = 0
NAVI_CHECK_SESSION_ID = 1
CHAT_SESSION_ID = 2
last_chat_text = ""
chat_queue = ChatQueue(10)
before_text = ""
pending_user_text = ""














# workflow 运行环境变量速查：
# - RABBITBOT_STRICT_DOCX_SCRIPT：是否启用严格 DOCX 剧本模式，默认启用。
# - RABBITBOT_SCRIPTED_TOUR：是否启用脚本化导览推进，默认启用。
# - RABBITBOT_WORKFLOW_NON_INTEGRATION：是否使用无机器人手动确认导航模式（兼容旧变量名）。
# - RABBITBOT_WORKFLOW_VERBOSE：是否打印调试级 workflow 过程日志。
# - RABBITBOT_WORKFLOW_PROFILE：是否写入 workflow profile JSONL，默认启用。
# - RABBITBOT_WORKFLOW_PROFILE_LOG：显式指定 workflow profile JSONL 路径。
# - RABBITBOT_LOG_DIR：未指定 profile 路径时的日志目录。
# - RABBITBOT_WORKFLOW_SUMMARY：是否在退出时打印 workflow 耗时汇总，默认启用。
# - RABBITBOT_TTS_STRICT_FAILURE：TTS 请求失败时是否按致命错误终止 workflow，默认 0，即记录错误并继续导览。
# - RABBITBOT_DIALOGUE_INDEX：选择 conf/dialogue_<序号>.json，未设置时默认 0。
# - RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX：旧版台词序号变量，仅在 RABBITBOT_DIALOGUE_INDEX 未设置时兜底。
# - RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE：直接指定台词 JSON 文件完整路径，优先级高于序号。
# - RABBITBOT_COFFEE_DELIVERY_COMMAND：覆盖“呼叫咖啡车”的后台命令。
# - RABBITBOT_COFFEE_DELIVERY_COMMAND_TIMEOUT：呼叫咖啡车后台命令等待超时时间，单位秒。
# - RABBITBOT_OPENING_MODE：控制开场流程，full 为完整开场，skip/0/false/off 为跳过。
# - RABBITBOT_ENABLE_NAVI：是否真实执行导航，设为 0/false/no/off 时跳过导航。
# - RABBITBOT_HAND_GESTURE_<ACTION>：为指定手臂动作配置灵巧手 ROS 字符串命令。
# - RABBITBOT_HAND_GESTURE_TOPIC：灵巧手命令发布 topic，默认 /gesture_cmd。
# - RABBITBOT_HAND_GESTURE_PUB_TIMEOUT：灵巧手命令发布超时，单位秒。
# - RABBITBOT_HANDSHAKE_BEFORE_RELEASE_DELAY：握手动作收手前等待时间，单位秒。
# - RABBITBOT_ARM_BEFORE_RELEASE_DELAY：其它前置动作收手前默认等待时间，单位秒。
# - RABBITBOT_ARM_AFTER_SPEECH_RELEASE_DELAY：台词后收手动作的等待时间，单位秒。
# - RABBITBOT_ARM_CONCURRENT_RELEASE_DELAY：动作与台词并发时收手前等待时间，单位秒。
# - RABBITBOT_ARM_RELEASE_WAIT_SECONDS：发送 release 后额外等待时间，单位秒。
# - RABBITBOT_VIEW_MODE：视觉问答来源，robot 使用机器人视觉，其它值使用 mock。
# - RABBITBOT_MOCK_IMAGE：mock 视觉问答使用的本地图片路径。
# - RABBITBOT_CHAT_RAG：闲聊(C 路径)是否启用记忆 RAG（先检索 neo4j+markdown，命中则作为参考资料交给 VLM 生成回答），默认启用。
# - RABBITBOT_CHAT_RAG_GROUP：闲聊 RAG 检索使用的 group_name，默认“闲聊检索”（中文名会跳过 neo4j 分组过滤，检索全部图谱节点+markdown 文档）。














DOCX_POINT_LOCATION_REQUIRED_FIELDS = ("x", "y", "z", "ox", "oy", "oz", "ow", "mode")
DOCX_POINT_LOCATION_FLOAT_FIELDS = ("x", "y", "z", "ox", "oy", "oz", "ow")

















































































































def _start_docx_script_elapsed_timer(ctx, reason="speech_start"):
    if getattr(ctx, "docx_script_elapsed_start_perf", None) is not None:
        return
    ctx.docx_script_elapsed_start_perf = time.perf_counter()
    ctx.docx_script_elapsed_start_ts = _workflow_timestamp()
    ctx.docx_script_elapsed_finish_printed = False
    print(f"DOCX 剧本总计时开始: reason={reason}, start={ctx.docx_script_elapsed_start_ts}")


def _finish_docx_script_elapsed_timer(ctx, reason="script_finished"):
    start_perf = getattr(ctx, "docx_script_elapsed_start_perf", None)
    if start_perf is None:
        print(f"DOCX 剧本总计时无法结束: reason={reason}, start_missing=True")
        return
    if getattr(ctx, "docx_script_elapsed_finish_printed", False):
        return
    elapsed_seconds = time.perf_counter() - start_perf
    ctx.docx_script_elapsed_finish_printed = True
    ctx.docx_script_elapsed_seconds = elapsed_seconds
    start_ts = getattr(ctx, "docx_script_elapsed_start_ts", "")
    print(
        "DOCX 剧本总耗时: "
        f"reason={reason}, start={start_ts}, "
        f"end={_workflow_timestamp()}, elapsed={elapsed_seconds:.3f}s"
    )


async def guide_opening_speech(ctx: Any, answer_interrupt=None):
    """Run the speech-only opening guide flow before the main workflow."""

    def set_opening_pending_text(text):
        global pending_user_text
        if _is_empty_stt_text(text):
            return False
        pending_user_text = text.strip()
        print("设置导览开场打断后的下一轮用户输入: " + pending_user_text)
        return True

    def say(text, interruptible=True):
        if _strict_docx_script_enabled():
            _start_docx_script_elapsed_timer(ctx, reason="opening_speech")
        if _strict_docx_script_enabled() and interruptible and not _docx_guide_qa_interrupt_enabled():
            tts_sound(ctx.tts_agent, text, "zh")
            tts_wait(ctx.tts_agent)
            return False
        if interruptible:
            interrupt_text = tts_long_text_with_stt_stop(ctx.tts_agent, text, ctx.stt_agent, ctx.robot, before_text=None)
            return set_opening_pending_text(interrupt_text)
        tts_sound(ctx.tts_agent, text, "zh")
        tts_wait(ctx.tts_agent)
        return False

    if _strict_docx_script_enabled():
        # PDF 剧本的开场发生在点位1现场；严格剧本模式不在开场前额外导航，避免台词被起点导航阻塞。
        ctx.start_position_confirmed = True
        ctx.current_entity_name = "点位1"
        _workflow_log("严格 DOCX 剧本开场：按 PDF 顺序直接在点位1开始台词，不预先执行起点导航")

    opening_mode = os.getenv("RABBITBOT_OPENING_MODE", "full").strip().lower()
    if opening_mode in {"0", "false", "no", "off", "skip"}:
        print(f"跳过导览开场: RABBITBOT_OPENING_MODE={opening_mode}")
        default_leader_calling = _docx_guide_leader_calling()
        return {
            "leader_calling": default_leader_calling,
            "raw_name_text": "",
            "raw_visit_text": "",
            "first_visit": True,
            "start_entity_name": None,
        }

    if opening_mode != "full":
        short_leader_calling = _docx_opening_text("short_mode_leader_calling")
        if say(_docx_opening_text("short_mode_intro", {"leader_calling": short_leader_calling})):
            return {
                "leader_calling": short_leader_calling,
                "raw_name_text": pending_user_text,
                "raw_visit_text": "",
                "first_visit": True,
                "start_entity_name": None,
            }
        say(_docx_opening_text("short_mode_ready", {"leader_calling": short_leader_calling}), interruptible=False)
        leader_info = {
            "leader_calling": short_leader_calling,
            "raw_name_text": "",
            "raw_visit_text": "",
            "first_visit": True,
            "start_entity_name": None,
        }
        ctx.leader_info = leader_info
        return leader_info

    leader_calling = _docx_guide_leader_calling()
    raw_name_text = leader_calling

    async def _answer_opening_interrupt():
        # 开场白被打断：取出打断提问，复用 chat 回答后继续(resume)剩余开场白。
        global pending_user_text
        question = (pending_user_text or "").strip()
        pending_user_text = ""
        if not question:
            return
        if answer_interrupt is None:
            print(f"开场白被打断但未配置回答回调，跳过回答继续开场白: {question}")
            return
        print(f"开场白被打断，先回答用户提问后继续开场白: {question}")
        try:
            await answer_interrupt(question)
        except Exception as exc:
            print(f"开场打断提问回答失败，继续开场白: error_type={type(exc).__name__}, error={exc}")

    async def _play_opening_line(speech_thunk, action=None):
        # 播放一句开场白；被打断则回答提问后重播本句(动作不重复)，确保完整播完再继续下一句。
        current_action = action
        while True:
            if current_action:
                interrupted = await _do_arm_during_speech(ctx.robot, current_action, speech_thunk)
            else:
                interrupted = speech_thunk()
            if not interrupted:
                return
            await _answer_opening_interrupt()
            current_action = None

    # 开场白逐句播报：握手问候、欢迎、群体欢迎、跟随介绍；任一句被打断都回答后继续，不再吞词。
    await _play_opening_line(
        lambda: say(_docx_opening_text("handshake_greeting", {"leader_calling": leader_calling})),
        action="shake_hand",
    )
    await _play_opening_line(
        lambda: say(_docx_opening_text("handshake_welcome", {"leader_calling": leader_calling})),
    )
    await _play_opening_line(
        lambda: say(_docx_opening_text("group_welcome", {"leader_calling": leader_calling})),
        action="face_wave",
    )
    raw_visit_text = ""
    first_visit = True
    await _play_opening_line(
        lambda: say(_docx_opening_text("follow_intro", {"leader_calling": leader_calling})),
    )

    start_entity_name = "点位1"
    start_description = ""
    start_entity = _load_json_entity(start_entity_name)
    if start_entity is not None:
        start_description = start_entity.get("description", "")
    else:
        try:
            start_nodes = await ctx.memory.query(query=start_entity_name, group_name="展点", limit=1)
        except Exception as exc:
            print(f"查询起始板块失败: {exc}")
            start_nodes = []
        start_node = start_nodes[0] if start_nodes else None
        if start_node is not None:
            start_description = start_node.attributes.get("description", "") or start_node.attributes.get("describtion", "") or start_node.summary or ""

    if not _strict_docx_script_enabled() and say("好的，我们现在去" + start_entity_name):
        return {"leader_calling": leader_calling, "raw_name_text": raw_name_text, "raw_visit_text": raw_visit_text, "first_visit": first_visit, "start_entity_name": start_entity_name}

    start_navi_status = NavigationStatus.SUCCEEDED
    start_points = _extract_location_points(start_entity)
    start_point = start_points[0] if start_points else None
    enable_navi = os.getenv("RABBITBOT_ENABLE_NAVI", "1").strip().lower() not in {"0", "false", "no", "off"}
    _workflow_log(f"开场导航配置: enable_navi={enable_navi}", verbose=True)
    if _strict_docx_script_enabled():
        _workflow_log("严格 DOCX 剧本已在开场前确认起始板块，跳过重复起始点导航", verbose=True)
    elif enable_navi:
        start_navi_status = NavigationStatus.ABORTED
        if start_point is None:
            _workflow_log(f"起始板块缺少可用导航点位: {start_entity}")
        elif _wait_manual_navigation_success(start_entity_name):
            start_navi_status = NavigationStatus.SUCCEEDED
        else:
            navi_tools = NavigationToolkit(ctx)
            navi_query = NavigationQuery()
            x, y, ox, oy, oz, ow = start_point
            await navi_tools.go_to_async(
                x, y, ox, oy, oz, ow, navi_query,
                waypoints=start_points if len(start_points) > 1 else None,
            )
            while await is_navigating(navi_tools):
                await asyncio.sleep(0.5)
            start_navi_status = await navi_tools.go_to_status()
            _workflow_log(f"开场导航完成: status={start_navi_status}")

    ctx.current_entity_name = start_entity_name
    if start_entity_name in getattr(ctx, "entity_lst", []):
        ctx.current_entity_index = ctx.entity_lst.index(start_entity_name)
    if start_navi_status == NavigationStatus.SUCCEEDED and start_description and not _strict_docx_script_enabled():
        interrupt_text = tts_long_text_with_stt_stop(ctx.tts_agent, start_description, ctx.stt_agent, ctx.robot, before_text)
        set_opening_pending_text(interrupt_text)
    elif start_navi_status != NavigationStatus.SUCCEEDED:
        print(f"起始板块导航未完成，跳过开场介绍: {start_navi_status}")

    leader_info = {
        "leader_calling": leader_calling,
        "raw_name_text": raw_name_text,
        "raw_visit_text": raw_visit_text,
        "first_visit": first_visit,
        "start_entity_name": start_entity_name,
    }
    ctx.leader_info = leader_info
    return leader_info


def create_main_workflow(ctx: Any) -> Workflow:
    """
    Create the main workflow for the RabbitBot agents.
    """
    # Initialize toolkits
    navi_tools = NavigationToolkit(ctx)
    detect_tools = DetectToolkit(ctx)
    # Define agents
    model = ctx.agno_model
    quant_model =  ctx.agno_quant_model
    plan_agent = Agent(
        name='Plan Agent',
        role='Planner',
        instructions=get_inst_plan(ctx.entity_lst),
        # instructions=dedent(f"""\
        #     你是智元机器人公司的具身机器人规划智能体。
        #     给定一个任务，你必须规划完成该任务的下一步操作。
        #     每个子任务应该是以下之一：
        #     - navigation: 寻找或前往某个位置/房间/实体
        #     - chat: 与用户聊天对话，特别是介绍智元公司相关信息
        #     如果任务是寻找或前往某个位置/房间/实体或者需要你介绍智元公司相关的信息，你应该输出"navigation"并输出subtask_description："<位置/房间/实体的名称>"。
        #     如果任务是与用户聊天、询问问题，你应该输出"chat"。
        #     如果子任务无法由任何智能体完成，你应该向用户寻求帮助。
        #     """),
        #response_model=SimpleDelegationTaskModel,
        model=model,
        debug_mode=False,
        add_history_to_messages=False,
        num_history_runs=4,
    )

    navi_check_agent = Agent(
        name='Navigation Plan Agent',
        role='Planner',
        instructions=get_inst_navi_check(ctx.entity_lst),
        model=model,
        debug_mode=False,
        add_history_to_messages=True,
        num_history_runs=5,
    )

    entity_check_agent = Agent(
        name='Entity Check Agent',
        role='Entity checker',
        instructions=dedent("""\
            你是一个实体检查智能体。请根据用户给定的查询请求，从实体列表中选择最相关的实体。实体列表是一个字典类型的数据，包含"""),
        model=model,
    )

    location_name="教育场景"
    node_names= ctx.education_entity_lst
    node_summary=ctx.education_summary_lst
    search_check_agent = Agent(
        name='Search Check Agent',
        role='Search Checker',
        instructions=get_inst_search_check(node_names,node_summary),
        model=model,
        debug_mode=True,
    )

    ctoe_translate_agent = Agent(
        name='English to Chinese Translate Agent',
        role='Translator',
        instructions=get_inst_ctoe_translate(),
        model=model,
        debug_mode=False,
    )

    entity_reranker_agent = Agent(
        name='Entity Reranker Agent',
        role='Entity reranker',
        instructions=dedent("""\
            You are an entity reranker agent.
            Given a task and a list of entities:
                - if there is not any relevant entity, you should output "nothing relevant".
                - if there are multiple relevant entities, you should output the name of the most relevant one.
            Taken the name and description of the entity into account."""),
        model=model,
    )

    task_completion_check_agent = Agent(
        name='Task Completion Check Agent',
        role='Task completion checker',
        instructions=dedent("""\
            You are a task completion checker agent.
            Given the task and all previous step outputs, you must determine if the task is completed"""),
        response_model=CompletionCheckModel,
        model=model,
    )

    #stt_agent = Agent(
    #    name="STT Agent",
    #    model=RealtimeSTT(id="base", modalities=["text"]),
    #)
    #stt_agent = None

    stt_agent = ctx.stt_agent

    #tts_agent = Agent(
    #    name="TTS Agent",
    #    model=RealtimeTTS(id="base", modalities=["text"]),
    #)
    tts_agent = ctx.tts_agent

    chat_bot_name = "机二机器人"

    max_chat_history = workflow_configs["max_chat_history"]
    chat_agent = Agent(
        name='Chat Agent',
        role='Assistant',
        instructions=get_inst_chat(ctx.entity_lst),
        model=model,
        #model=quant_model,
        read_chat_history=False,
        add_history_to_messages=True,
        num_history_runs=max_chat_history,
    )
    post_docx_chat_agent = Agent(
        name='Post DOCX Chat Agent',
        role='Assistant',
        instructions=get_inst_post_docx_chat(),
        model=model,
        read_chat_history=False,
        add_history_to_messages=True,
        num_history_runs=max_chat_history,
    )
    general_vlm_openai = create_general_vlm_openai()

    DOCX_SCRIPT_CONTINUE_TEXTS = DEFAULT_CONTINUE_TEXTS

    def normalize_docx_script_control_text(text):
        return normalize_control_text(text)

    def is_docx_script_continue_text(text):
        return is_continue_text(text, DOCX_SCRIPT_CONTINUE_TEXTS)

    def docx_script_in_progress():
        return (
            _strict_docx_script_enabled()
            and hasattr(ctx, "docx_script_step_index")
            and not getattr(ctx, "docx_script_done", False)
        )

    def set_pending_user_text(text):
        global pending_user_text
        if text is None:
            return False
        text = text.strip()
        if text == "":
            return False
        if docx_script_in_progress() and is_docx_script_continue_text(text):
            print(f"忽略剧本继续确认词: {text}")
            return False
        pending_user_text = text
        print(f"设置打断后的下一轮用户输入: {pending_user_text}")
        return True

    def pop_pending_user_text():
        global pending_user_text
        text = pending_user_text
        pending_user_text = ""
        return text

    def set_current_entity_name(name):
        if not name:
            return
        ctx.current_entity_name = name
        entity_order = getattr(ctx, 'json_entity_order', None) or JSON_ENTITY_ORDER or getattr(ctx, 'entity_lst', [])
        if name in entity_order:
            ctx.current_entity_index = entity_order.index(name)
        elif hasattr(ctx, 'entity_lst') and name in ctx.entity_lst:
            ctx.current_entity_index = ctx.entity_lst.index(name)

    def get_next_entity_name():
        entity_order = getattr(ctx, 'json_entity_order', None) or JSON_ENTITY_ORDER or getattr(ctx, 'entity_lst', [])
        if not entity_order:
            return None
        current_name = getattr(ctx, 'current_entity_name', None)
        current_index = getattr(ctx, 'current_entity_index', None)
        if current_index is None:
            if current_name not in entity_order:
                return None
            current_index = entity_order.index(current_name)
        next_index = current_index + 1
        if next_index >= len(entity_order):
            return None
        return entity_order[next_index]

    SCRIPTED_TOUR_STEP_DONE = "<SCRIPTED_TOUR_STEP_DONE>"
    SCRIPTED_TOUR_FINISHED = "<SCRIPTED_TOUR_FINISHED>"
    SCRIPTED_TOUR_RETURN_TO_START = "<SCRIPTED_TOUR_RETURN_TO_START>"
    SCRIPTED_TOUR_ORDER = [
        "起始板块",
        "多功能展示区",
        "园区历史板块",
        "复星集团板块",
        "园区布局板块",
        "园区介绍板块",
        "园区企业介绍板块",
        "智慧园区板块",
        "合影板块",
    ]
    SCRIPTED_TOUR_ACTIONS = {
        "起始板块": "face_wave",
        "多功能展示区": "right_hand_up",
        "园区历史板块": "right_hand_up",
        "复星集团板块": "right_hand_up",
        "园区布局板块": "right_hand_up",
        "园区介绍板块": "right_hand_up",
        "园区企业介绍板块": "right_hand_up",
        "智慧园区板块": "right_hand_up",
        "合影板块": "high_wave",
    }
    DOCX_SCRIPT_POINT_ENTITY = {
        "point_1_to_2_transition": "1->2过渡点位",
        "point_2": "点位2",
        "point_3": "点位3",
        "point_4": "点位4",
        "point_3_to_5_transition": "3->5过渡点位",
        "point_5": "点位5",
    }
    DOCX_SCRIPT_STEPS = _load_docx_script_steps(DOCX_SCRIPT_POINT_ENTITY)

    def _task_progress_path():
        explicit_path = os.getenv("RABBITBOT_WORKFLOW_TASK_PROGRESS_FILE", "").strip()
        if explicit_path:
            return Path(explicit_path)
        run_id = os.getenv("RABBITBOT_WORKFLOW_RUN_ID", "").strip()
        if not run_id:
            return None
        log_dir = Path(os.getenv("RABBITBOT_LOG_DIR", Path.cwd() / "logs"))
        return log_dir / "workflow_control" / f"{run_id}.task_progress.json"

    def _docx_step_site_name(step, index):
        if not isinstance(step, dict):
            return f"步骤{index + 1}"
        return str(step.get("scene") or step.get("entity") or f"步骤{index + 1}").strip() or f"步骤{index + 1}"

    def _docx_next_site(index):
        next_index = index + 1
        if next_index >= len(DOCX_SCRIPT_STEPS):
            return None
        return _docx_step_site_name(DOCX_SCRIPT_STEPS[next_index], next_index)

    def write_task_progress(status, current_site=None, next_site=None, completed_points=0, total_points=None, active=True):
        progress_path = _task_progress_path()
        if progress_path is None:
            _workflow_log("任务进度未写入：缺少 RABBITBOT_WORKFLOW_RUN_ID")
            return
        if total_points is None:
            total_points = len(DOCX_SCRIPT_STEPS)
        try:
            total_points = max(0, int(total_points or 0))
            completed_points = max(0, min(int(completed_points or 0), total_points)) if total_points else 0
        except (TypeError, ValueError):
            total_points = 0
            completed_points = 0
        payload = {
            "active": bool(active),
            "task_name": "展厅导览" if active else "待命",
            "status": str(status or "idle"),
            "current_site": current_site or "",
            "next_site": next_site or "",
            "completed_points": completed_points,
            "total_points": total_points,
            "run_id": os.getenv("RABBITBOT_WORKFLOW_RUN_ID", "").strip(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        tmp_path = progress_path.with_suffix(progress_path.suffix + ".tmp")
        try:
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp_path, progress_path)
            _workflow_log(
                "任务进度已更新: "
                f"status={payload['status']}, completed={completed_points}/{total_points}, "
                f"current={payload['current_site'] or '未知'}, next={payload['next_site'] or '未知'}, path={progress_path}"
            )
        except OSError as exc:
            _workflow_log(
                "任务进度写入失败: "
                f"status={payload['status']}, path={progress_path}, error_type={type(exc).__name__}, error={exc}"
            )

    def scripted_tour_enabled():
        value = os.getenv("RABBITBOT_SCRIPTED_TOUR", "1").strip().lower()
        return value not in {"0", "false", "no", "off", "skip"}

    def guide_start_by_voice_enabled():
        return scripted_tour_enabled() and _env_enabled("RABBITBOT_GUIDE_START_BY_VOICE", "0")

    def guide_started():
        return not guide_start_by_voice_enabled() or bool(getattr(ctx, "scripted_tour_started", False))

    def normalize_guide_start_text(text):
        return normalize_control_text(text)

    def guide_start_commands():
        raw_value = os.getenv("RABBITBOT_GUIDE_START_COMMANDS", "开始导览,开始讲解,开始参观,开始流程,启动导览")
        return build_control_commands(raw_value, ["开始导览"])

    def is_guide_start_command(text):
        return matches_control_command(text, guide_start_commands())

    def guide_return_commands():
        raw_value = os.getenv("RABBITBOT_GUIDE_RETURN_COMMANDS", "返回起点,返航,回到起点,回起点,返回原点")
        return build_control_commands(raw_value, ["返回起点"])

    def is_guide_return_command(text):
        return matches_control_command(text, guide_return_commands())

    def guide_tour_completed_for_return():
        return bool(
            guide_started()
            and (
                getattr(ctx, "guide_tour_completed_wait_return", False)
                or getattr(ctx, "docx_script_done", False)
                or getattr(ctx, "scripted_tour_done", False)
            )
        )

    def write_return_request_file(trigger_text):
        request_file = os.getenv("RABBITBOT_WORKFLOW_RETURN_REQUEST_FILE", "").strip()
        trigger_len = len((trigger_text or "").strip())
        if not request_file:
            _workflow_log(f"收到返回起点口令但缺少返航请求文件配置: trigger_len={trigger_len}")
            return False
        request_path = Path(request_file)
        try:
            request_path.parent.mkdir(parents=True, exist_ok=True)
            request_path.write_text(
                f"return_to_start\n"
                f"pid={os.getpid()}\n"
                f"time={datetime.now().isoformat()}\n"
                f"trigger_len={trigger_len}\n",
                encoding="utf-8",
            )
            _workflow_log(f"已写入返航请求文件: path={request_path}, trigger_len={trigger_len}")
            return True
        except OSError as exc:
            _workflow_log(f"返航请求文件写入失败: path={request_path}, error_type={type(exc).__name__}, error={exc}")
            return False

    async def start_scripted_tour_by_voice(trigger_text):
        if getattr(ctx, "scripted_tour_started", False):
            return
        ctx.scripted_tour_started = True
        ctx.pre_guide_qa_mode = False
        write_task_progress("guide_running", current_site=getattr(ctx, "current_entity_name", None), next_site=_docx_next_site(-1), completed_points=0, active=True)
        trigger_len = len((trigger_text or "").strip())
        opening_enabled = os.getenv("RABBITBOT_ENABLE_GUIDE_OPENING", "1")
        _workflow_log(f"语音口令启动导览: trigger_len={trigger_len}, opening_enabled={opening_enabled}")
        if opening_enabled == "1":
            await guide_opening_speech(ctx, answer_interrupt=lambda q: chat_execute(q, ChatSessionInfo.sess_idx))
        else:
            tts_sound(ctx.tts_agent, f"{before_text}好的，开始导览。", "zh")
            tts_wait(ctx.tts_agent)
        ctx.scripted_tour_opening_done = True
        _workflow_log("语音口令导览开场完成，准备按所选剧本推进")

    def init_scripted_tour_state():
        if hasattr(ctx, "scripted_tour_index"):
            return
        entity_order = [name for name in SCRIPTED_TOUR_ORDER if _load_json_entity(name) is not None]
        if not entity_order:
            entity_order = getattr(ctx, "json_entity_order", None) or JSON_ENTITY_ORDER or getattr(ctx, "entity_lst", [])
        ctx.scripted_tour_order = list(entity_order)
        current_name = getattr(ctx, "current_entity_name", None)
        if current_name in ctx.scripted_tour_order:
            ctx.scripted_tour_index = ctx.scripted_tour_order.index(current_name) + 1
        else:
            ctx.scripted_tour_index = 0
        ctx.scripted_tour_arrived_index = None
        ctx.scripted_tour_done = False
        _workflow_log(f"初始化剧本导览状态: index={ctx.scripted_tour_index}, order={ctx.scripted_tour_order}", verbose=True)

    def build_scripted_intro(entity_name):
        leader_info = getattr(ctx, "leader_info", {}) or {}
        leader_calling = leader_info.get("leader_calling") or _docx_guide_leader_calling()
        if entity_name == "合影板块":
            return f"{leader_calling}，请各位移步合影区。"
        return f"{leader_calling}，下面请随我来到{entity_name}。"

    def init_docx_script_state():
        if hasattr(ctx, "docx_script_step_index"):
            return
        ctx.docx_script_step_index = 0
        ctx.docx_script_segment_index = 0
        ctx.docx_script_nav_done_step = None
        ctx.docx_script_done = False
        ctx.docx_script_answers = {}
        ctx.docx_background_commands_started = set()
        if not hasattr(ctx, "docx_script_elapsed_start_perf"):
            ctx.docx_script_elapsed_start_perf = None
            ctx.docx_script_elapsed_start_ts = ""
            ctx.docx_script_elapsed_finish_printed = False
            ctx.docx_script_elapsed_seconds = None
        ctx.docx_total_profile_span = _profile_start("docx_total")
        write_task_progress("guide_running", current_site=getattr(ctx, "current_entity_name", None), next_site=_docx_next_site(-1), completed_points=0, active=True)
        _workflow_log("初始化 DOCX 剧本演出状态", verbose=True)

    def format_docx_script_text(text):
        leader_info = getattr(ctx, "leader_info", {}) or {}
        leader_calling = leader_info.get("leader_calling") or _docx_guide_leader_calling()
        coffee_order = getattr(ctx, "docx_script_answers", {}).get("coffee_order", "")
        return _format_docx_guide_text(text, {"leader_calling": leader_calling, "coffee_order": coffee_order})

    def _format_command_for_log(command):
        try:
            return shlex.join([str(item) for item in command])
        except Exception:
            return " ".join(str(item) for item in command)

    def _resolve_coffee_delivery_command():
        configured_command = os.getenv("RABBITBOT_COFFEE_DELIVERY_COMMAND", "").strip()
        if configured_command:
            return shlex.split(configured_command), "env"

        candidates = [
            Path(__file__).resolve().parents[2] / "send_delivery_task.py",
            Path("/workspace/projects/rabbitbot-dev-ros2-master/send_delivery_task.py"),
        ]
        for script_path in candidates:
            if script_path.exists():
                return ["python3", str(script_path), "run"], str(script_path)

        return ["python3", str(candidates[0]), "run"], "host_default_missing"

    def _resolve_docx_background_command(command_spec):
        if command_spec == "coffee_delivery_run":
            return _resolve_coffee_delivery_command()
        if isinstance(command_spec, (list, tuple)):
            return [str(item) for item in command_spec], "segment_list"
        if isinstance(command_spec, str):
            return shlex.split(command_spec), "segment_string"
        raise ValueError(f"不支持的后台命令配置: {command_spec!r}")

    def start_docx_segment_background_command(segment, scene, segment_index, formatted_text):
        command_spec = segment.get("background_command")
        if not command_spec:
            return

        command_name = segment.get("background_command_name") or str(command_spec)
        once_key = segment.get("background_command_once_key")
        started_commands = getattr(ctx, "docx_background_commands_started", set())
        if once_key and once_key in started_commands:
            print(f"DOCX 后台命令跳过重复启动: name={command_name}, scene={scene}, segment={segment_index}, once_key={once_key}")
            return

        try:
            command, source = _resolve_docx_background_command(command_spec)
        except Exception as exc:
            print(f"DOCX 后台命令解析失败: name={command_name}, scene={scene}, segment={segment_index}, error={type(exc).__name__}: {exc}")
            _profile_instant(
                "docx_background_command_resolve_error",
                span="docx_background_command",
                name=command_name,
                scene=scene,
                segment=segment_index,
                error=f"{type(exc).__name__}: {exc}",
            )
            return

        command_timeout = float(segment.get("background_command_timeout") or os.getenv("RABBITBOT_COFFEE_DELIVERY_COMMAND_TIMEOUT", "15"))
        command_text = _format_command_for_log(command)
        span_token = _profile_start(
            "docx_background_command",
            name=command_name,
            scene=scene,
            segment=segment_index,
            command=command_text,
            source=source,
            timeout=command_timeout,
        )
        start_time = time.perf_counter()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            elapsed_seconds = time.perf_counter() - start_time
            print(f"DOCX 后台命令启动失败: name={command_name}, scene={scene}, segment={segment_index}, command={command_text}, error={type(exc).__name__}: {exc}")
            _profile_end(
                span_token,
                name=command_name,
                scene=scene,
                segment=segment_index,
                status="start_error",
                elapsed=round(elapsed_seconds, 6),
                error=f"{type(exc).__name__}: {exc}",
            )
            return

        if once_key:
            started_commands.add(once_key)
            ctx.docx_background_commands_started = started_commands

        print(f"DOCX 后台命令已启动: name={command_name}, scene={scene}, segment={segment_index}, pid={process.pid}, command={command_text}, source={source}, timeout={command_timeout}")

        def wait_background_command():
            try:
                stdout, stderr = process.communicate(timeout=command_timeout)
                status = "success" if process.returncode == 0 else "error"
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                status = "timeout"
            elapsed_seconds = time.perf_counter() - start_time
            stdout_tail = (stdout or "")[-1000:]
            stderr_tail = (stderr or "")[-1000:]
            print(
                "DOCX 后台命令结束: "
                f"name={command_name}, scene={scene}, segment={segment_index}, "
                f"pid={process.pid}, status={status}, returncode={process.returncode}, "
                f"elapsed={elapsed_seconds:.3f}s, stdout={stdout_tail!r}, stderr={stderr_tail!r}"
            )
            _profile_end(
                span_token,
                name=command_name,
                scene=scene,
                segment=segment_index,
                status=status,
                returncode=process.returncode,
                elapsed=round(elapsed_seconds, 6),
                stdout=stdout_tail,
                stderr=stderr_tail,
            )

        threading.Thread(target=wait_background_command, daemon=True).start()

    def make_docx_interaction_trace(listen_key, scene, segment_index, trace_id=None):
        trace_id = trace_id or f"{listen_key}-{scene}-{segment_index}-{int(time.time() * 1000)}"

        def emit_trace(**fields):
            fields = dict(fields)
            fields.pop("trace_id", None)
            phase = fields.get("phase")
            _profile_instant(
                "interaction_latency",
                span="interaction_latency",
                trace_id=trace_id,
                listen_key=listen_key,
                scene=scene,
                segment=segment_index,
                **fields,
            )
            print(
                f"[{_workflow_timestamp()}] 用户到TTS链路: "
                f"trace_id={trace_id}, listen_key={listen_key}, "
                f"scene={scene}, segment={segment_index}, "
                f"phase={phase}, elapsed_from_listen_start={fields.get('elapsed_from_listen_start')}, "
                f"text={fields.get('text')}, status={fields.get('status')}, "
                f"tts_index={fields.get('tts_index')}"
            )

        return trace_id, emit_trace

    def mark_docx_answer_received(listen_key, scene, segment_index, answer, trace_id=None):
        span_token = _profile_start(
            "answer_to_feedback",
            listen_key=listen_key,
            answer_scene=scene,
            answer_segment=segment_index,
            answer=answer,
            trace_id=trace_id,
        )
        pending_latency = {
            "listen_key": listen_key,
            "scene": scene,
            "segment": segment_index,
            "answer": answer,
            "trace_id": trace_id,
            "received_perf": time.perf_counter(),
            "received_at": _workflow_timestamp(),
            "profile_span": span_token,
        }
        ctx.docx_pending_answer_latency = pending_latency
        _profile_instant(
            "human_answer_received",
            span="listen_answer",
            listen_key=listen_key,
            scene=scene,
            segment=segment_index,
            answer=answer,
            trace_id=trace_id,
        )
        _profile_instant(
            "interaction_latency",
            span="interaction_latency",
            phase="human_answer_accepted",
            trace_id=trace_id,
            listen_key=listen_key,
            scene=scene,
            segment=segment_index,
            answer=answer,
        )
        print(
            f"[{pending_latency['received_at']}] DOCX应答延迟: "
            f"stage=human_answer_received, trace_id={trace_id}, listen_key={listen_key}, "
            f"scene={scene}, segment={segment_index}, answer={answer}"
        )

    def log_docx_feedback_start(scene, segment_index, text):
        pending_latency = getattr(ctx, "docx_pending_answer_latency", None)
        if not pending_latency:
            return
        elapsed_seconds = time.perf_counter() - pending_latency["received_perf"]
        feedback_at = _workflow_timestamp()
        print(
            f"[{feedback_at}] DOCX应答延迟: stage=robot_feedback_tts_start, "
            f"trace_id={pending_latency.get('trace_id')}, "
            f"listen_key={pending_latency['listen_key']}, "
            f"answer_scene={pending_latency['scene']}, answer_segment={pending_latency['segment']}, "
            f"feedback_scene={scene}, feedback_segment={segment_index}, "
            f"elapsed={elapsed_seconds:.3f}s, answer={pending_latency['answer']}, feedback_text={text}"
        )
        _profile_instant(
            "interaction_latency",
            span="interaction_latency",
            phase="feedback_tts_start",
            trace_id=pending_latency.get("trace_id"),
            listen_key=pending_latency["listen_key"],
            answer_scene=pending_latency["scene"],
            answer_segment=pending_latency["segment"],
            feedback_scene=scene,
            feedback_segment=segment_index,
            elapsed_from_answer=round(elapsed_seconds, 6),
            answer=pending_latency["answer"],
            feedback_text=text,
        )
        _profile_end(
            pending_latency.get("profile_span"),
            listen_key=pending_latency["listen_key"],
            answer_scene=pending_latency["scene"],
            answer_segment=pending_latency["segment"],
            feedback_scene=scene,
            feedback_segment=segment_index,
            answer=pending_latency["answer"],
            feedback_text=text,
            trace_id=pending_latency.get("trace_id"),
        )
        ctx.docx_pending_answer_latency = None

    def normalize_coffee_answer(text):
        answer = (text or "").strip()
        for wrong_text in ["老铁", "拿贴", "拿帖", "拿跌"]:
            answer = answer.replace(wrong_text, "拿铁")
        return answer

    def is_valid_coffee_answer(text):
        normalized_text = re.sub(r"[\s，。！？?、,.!；;：:\"'“”‘’（）()\[\]【】]+", "", text or "").lower()
        if normalized_text == "":
            return False

        coffee_keywords = [
            "咖啡", "拿铁", "美式", "热拿铁", "冰拿铁", "热美式", "冰美式",
            "老铁", "拿贴", "拿帖", "拿跌",
            "都可以", "随便", "任选", "一样", "都行", "可以",
        ]
        no_coffee_keywords = [
            "不喝", "不用", "不要", "不需要", "免了", "算了", "不用了", "不要了",
        ]
        return any(keyword in normalized_text for keyword in coffee_keywords + no_coffee_keywords)

    def accept_docx_listen_answer(listen_key, scene, segment_index, answer, trace_id=None):
        if _is_empty_stt_text(answer):
            return False

        answer = answer.strip()
        if listen_key == "coffee_order":
            answer = normalize_coffee_answer(answer)
        elif listen_key == "dog_show_confirmation" and not is_valid_dog_show_confirmation(answer):
            print(f"忽略非机器狗表演确认回答: {answer}")
            return False

        ctx.docx_script_answers[listen_key] = answer
        mark_docx_answer_received(listen_key, scene, segment_index, answer, trace_id=trace_id)
        return True

    def is_valid_dog_show_confirmation(text):
        normalized_text = normalize_docx_script_control_text(text)
        if normalized_text == "":
            return False

        negative_keywords = [
            "不看", "不用", "不要", "不需要", "算了", "别", "先不", "不等",
            "不表演", "不用表演", "别表演", "不可以", "不行", "不是",
        ]
        if any(keyword in normalized_text for keyword in negative_keywords):
            return False

        positive_keywords = [
            "是", "是的", "对", "对的", "好", "好的", "好啊", "好呀",
            "可以", "行", "行的", "没问题", "看", "看看", "看吧",
            "看个节目", "表演", "动起来", "开始吧", "来吧",
        ]
        return any(keyword in normalized_text for keyword in positive_keywords)

    def load_docx_script_entity(entity_name):
        return _load_docx_point_entity(entity_name) or _load_json_entity(entity_name)

    async def speak_docx_script_navigation_segments(step, scene):
        if not step.get("speak_during_navigation"):
            return None

        segments = step.get("segments", [])
        segment_index = getattr(ctx, "docx_script_segment_index", 0)
        segment_count = int(step.get("speak_during_navigation_segments", 0) or 0)
        end_index = min(segment_index + segment_count, len(segments))
        while segment_index < end_index:
            segment = segments[segment_index]
            action_name = segment.get("action")
            speak_with_action = _should_speak_with_action(action_name, segment.get("speak_with_action"))
            if action_name and not speak_with_action:
                await _do_arm_before_speech(ctx.robot, action_name)

            text = segment.get("text", "")
            listen_key = segment.get("listen_key")
            listen_timeout = int(segment.get("listen_timeout", 8))
            early_listen = bool(segment.get("early_listen")) and listen_key
            interrupt_text = None
            listen_answer_handled = False
            if text:
                def speak_segment():
                    _start_docx_script_elapsed_timer(ctx, reason="docx_segment_speech")
                    formatted_text = format_docx_script_text(text)
                    start_docx_segment_background_command(segment, scene, segment_index, formatted_text)
                    log_docx_feedback_start(scene, segment_index, formatted_text)
                    span_token = _profile_start("tts_segment", scene=scene, segment=segment_index, text=formatted_text)
                    try:
                        if early_listen:
                            listen_span = _profile_start("listen_answer", listen_key=listen_key, scene=scene, segment=segment_index, timeout=listen_timeout, early=True)
                            answer = ""
                            trace_id, trace_event = make_docx_interaction_trace(listen_key, scene, segment_index)
                            try:
                                answer = tts_ask_with_early_stt(
                                    tts_agent,
                                    formatted_text,
                                    stt_agent,
                                    timeout=listen_timeout,
                                    stop_tts_on_answer=True,
                                    trace_event=trace_event,
                                    trace_id=trace_id,
                                )
                            finally:
                                _profile_end(listen_span, listen_key=listen_key, scene=scene, segment=segment_index, early=True, answer=answer, trace_id=trace_id)
                            return ("__DOCX_LISTEN_ANSWER__", answer, trace_id)
                        return tts_long_text_with_stt_stop(
                            tts_agent,
                            formatted_text,
                            stt_agent,
                            ctx.robot,
                            before_text,
                            ignored_interrupt_texts=DOCX_SCRIPT_CONTINUE_TEXTS,
                            ignore_unlisted_interrupts=not _docx_guide_qa_interrupt_enabled(),
                        )
                    finally:
                        _profile_end(span_token, scene=scene, segment=segment_index, text=formatted_text)

                if speak_with_action:
                    interrupt_text = await _do_arm_during_speech(ctx.robot, action_name, speak_segment)
                else:
                    interrupt_text = speak_segment()

                if isinstance(interrupt_text, tuple) and interrupt_text[0] == "__DOCX_LISTEN_ANSWER__":
                    listen_answer_handled = True
                    accept_docx_listen_answer(
                        listen_key,
                        scene,
                        segment_index,
                        interrupt_text[1],
                        trace_id=interrupt_text[2] if len(interrupt_text) > 2 else None,
                    )
                    interrupt_text = None

            if not speak_with_action:
                await _release_arm_after_speech(ctx.robot, action_name)
            if not _is_empty_stt_text(interrupt_text):
                if is_docx_script_continue_text(interrupt_text):
                    print(f"忽略剧本继续确认词: {interrupt_text}")
                else:
                    print(f"DOCX 剧本被用户打断: scene={scene}, segment={segment_index}, text={interrupt_text}")
                    ctx.docx_script_segment_index = segment_index
                    return "interrupt", interrupt_text.strip()

            segment_index += 1
            ctx.docx_script_segment_index = segment_index
        return None

    async def wait_navigation_with_stt_interrupt(navi_tools, scene, step_index=None):
        if not _env_enabled("RABBITBOT_GUIDE_NAV_STT_INTERRUPT", "1"):
            while await is_navigating(navi_tools):
                await asyncio.sleep(0.5)
            return None
        listen_timeout = int(os.getenv("RABBITBOT_GUIDE_NAV_STT_TIMEOUT_SECONDS", "3600"))
        _workflow_log(f"导航期间启动 STT 监听: scene={scene}, step_index={step_index}, timeout={listen_timeout}s")
        while await is_navigating(navi_tools):
            span_token = _profile_start("audio_input", source="guide_navigation", scene=scene, step_index=step_index, timeout=listen_timeout)
            try:
                out_text = await audio_input_execute_timeout_navi(stt_agent, listen_timeout, navi_tools)
            finally:
                _profile_end(span_token, source="guide_navigation", scene=scene, step_index=step_index, timeout=listen_timeout)
            if _is_empty_stt_text(out_text) or out_text == "<NAVI_REACH>":
                _workflow_log(f"导航期间 STT 监听结束: scene={scene}, result={out_text}", verbose=True)
                return None
            if is_docx_script_continue_text(out_text):
                _workflow_log(f"导航期间忽略剧本继续确认词并继续等待导航: scene={scene}, text={out_text}")
                continue
            _workflow_log(f"导航期间收到用户提问，暂停导览流程: scene={scene}, step_index={step_index}, text_len={len(out_text)}")
            try:
                tts_stop(tts_agent)
            except Exception as exc:
                _workflow_log(f"导航期间停止 TTS 失败: scene={scene}, error_type={type(exc).__name__}, error={exc}")
            return out_text.strip()
        _workflow_log(f"导航期间 STT 监听结束: scene={scene}, result=navigation_not_active", verbose=True)
        return None

    async def navigate_docx_script_step(step, step_index):
        entity_name = step.get("entity")
        scene = step.get("scene", entity_name)
        site_name = _docx_step_site_name(step, step_index)
        span_token = _profile_start("navigation", step_index=step_index, scene=scene, entity=entity_name)
        if not entity_name:
            write_task_progress("arrived", current_site=site_name, next_site=_docx_next_site(step_index), completed_points=step_index + 1, active=True)
            _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status=NavigationStatus.SUCCEEDED)
            return NavigationStatus.SUCCEEDED

        if step.get("skip_navigation_if_current") and getattr(ctx, "current_entity_name", None) == entity_name:
            write_task_progress("arrived", current_site=site_name, next_site=_docx_next_site(step_index), completed_points=step_index + 1, active=True)
            _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status=NavigationStatus.SUCCEEDED, skipped=True)
            return NavigationStatus.SUCCEEDED

        entity = load_docx_script_entity(entity_name)
        if entity is None:
            print(f"DOCX 剧本展点不存在或缺少点位配置: {entity_name}")
            write_task_progress("guide_running", current_site=getattr(ctx, "current_entity_name", None), next_site=site_name, completed_points=step_index, active=True)
            _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status=NavigationStatus.ABORTED, error="entity_missing")
            return NavigationStatus.ABORTED

        location_points = _extract_location_points(entity)
        if not location_points:
            print(f"DOCX 剧本展点缺少可用导航点位: {entity_name}")
            write_task_progress("guide_running", current_site=getattr(ctx, "current_entity_name", None), next_site=site_name, completed_points=step_index, active=True)
            _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status=NavigationStatus.ABORTED, error="location_missing")
            return NavigationStatus.ABORTED
        _workflow_log(f"DOCX 剧本导航目标: step={step_index}, scene={scene}, entity={entity_name}, points={len(location_points)}")

        guide_text = step.get("guide")
        if guide_text:
            formatted_guide_text = format_docx_script_text(guide_text)
            guide_span = _profile_start("tts_segment", scene=step.get("scene", entity_name), segment="guide", text=formatted_guide_text)
            interrupt_text = tts_long_text_with_stt_stop(
                tts_agent,
                formatted_guide_text,
                stt_agent,
                ctx.robot,
                before_text,
                ignored_interrupt_texts=DOCX_SCRIPT_CONTINUE_TEXTS,
                ignore_unlisted_interrupts=not _docx_guide_qa_interrupt_enabled(),
            )
            _profile_end(guide_span, scene=step.get("scene", entity_name), segment="guide", text=formatted_guide_text)
            if not _is_empty_stt_text(interrupt_text):
                _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status="interrupt")
                return ("interrupt", interrupt_text.strip())

        enable_navi = os.getenv("RABBITBOT_ENABLE_NAVI", "1").strip().lower() not in {"0", "false", "no", "off"}
        navi_status = NavigationStatus.SUCCEEDED
        if enable_navi:
            write_task_progress("navigating", current_site=getattr(ctx, "current_entity_name", None), next_site=site_name, completed_points=step_index, active=True)
            if _workflow_non_integration_enabled():
                speech_result = await speak_docx_script_navigation_segments(step, step.get("scene", entity_name))
                if speech_result:
                    _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status="interrupt")
                    return speech_result
                if _wait_manual_navigation_success(entity_name):
                    navi_status = NavigationStatus.SUCCEEDED
            else:
                navi_query = NavigationQuery()
                x, y, ox, oy, oz, ow = location_points[0]
                await navi_tools.go_to_async(
                    x, y, ox, oy, oz, ow, navi_query,
                    waypoints=location_points if len(location_points) > 1 else None,
                )
                speech_result = await speak_docx_script_navigation_segments(step, step.get("scene", entity_name))
                if speech_result:
                    _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status="interrupt")
                    return speech_result
                nav_interrupt_text = await wait_navigation_with_stt_interrupt(navi_tools, scene, step_index)
                if not _is_empty_stt_text(nav_interrupt_text):
                    _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status="interrupt")
                    return ("interrupt", nav_interrupt_text)
                navi_status = await navi_tools.go_to_status()
                await navi_tools.reset_go_to_status()

        if navi_status == NavigationStatus.SUCCEEDED:
            set_current_entity_name(entity_name)
            ctx.docx_script_nav_done_step = step_index
            write_task_progress("arrived", current_site=site_name, next_site=_docx_next_site(step_index), completed_points=step_index + 1, active=True)
        else:
            write_task_progress("guide_running", current_site=getattr(ctx, "current_entity_name", None), next_site=site_name, completed_points=step_index, active=True)
        _profile_end(span_token, step_index=step_index, scene=scene, entity=entity_name, status=navi_status)
        return navi_status

    async def run_docx_scripted_tour_next_step():
        if not guide_started():
            return None, None
        if pending_user_text:
            return None, None

        init_docx_script_state()
        if getattr(ctx, "docx_script_done", False):
            return None, None

        step_index = getattr(ctx, "docx_script_step_index", 0)
        if step_index >= len(DOCX_SCRIPT_STEPS):
            ctx.docx_script_done = True
            write_task_progress("finished", current_site=getattr(ctx, "current_entity_name", None), next_site=None, completed_points=len(DOCX_SCRIPT_STEPS), active=False)
            _profile_end(getattr(ctx, "docx_total_profile_span", None), status="finished")
            ctx.docx_total_profile_span = None
            _finish_docx_script_elapsed_timer(ctx, reason="script_index_finished")
            return "done", SCRIPTED_TOUR_FINISHED

        step = DOCX_SCRIPT_STEPS[step_index]
        scene = step.get("scene", f"步骤{step_index + 1}")
        step_span = _profile_start("docx_step", step_index=step_index, scene=scene)
        _workflow_log(f"DOCX 剧本步骤开始: index={step_index}, scene={scene}")

        if getattr(ctx, "docx_script_nav_done_step", None) != step_index:
            nav_result = await navigate_docx_script_step(step, step_index)
            if isinstance(nav_result, tuple) and nav_result[0] == "interrupt":
                _profile_end(step_span, step_index=step_index, scene=scene, status="interrupt")
                return nav_result
            if nav_result != NavigationStatus.SUCCEEDED:
                tts_sound(tts_agent, f"{before_text}很抱歉，我暂时无法到达{step.get('entity', scene)}。", "zh")
                tts_wait(tts_agent)
                ctx.docx_script_step_index = step_index + 1
                ctx.docx_script_segment_index = 0
                ctx.docx_script_nav_done_step = None
                _profile_end(step_span, step_index=step_index, scene=scene, status=nav_result)
                return "done", SCRIPTED_TOUR_STEP_DONE

        segments = step.get("segments", [])
        segment_index = getattr(ctx, "docx_script_segment_index", 0)
        while segment_index < len(segments):
            segment = segments[segment_index]
            action_name = segment.get("action")
            speak_with_action = _should_speak_with_action(action_name, segment.get("speak_with_action"))
            if action_name and not speak_with_action:
                await _do_arm_before_speech(ctx.robot, action_name)

            text = segment.get("text", "")
            listen_key = segment.get("listen_key")
            listen_timeout = int(segment.get("listen_timeout", 8))
            early_listen = bool(segment.get("early_listen")) and listen_key
            interrupt_text = None
            listen_answer_handled = False
            if text:
                def speak_segment():
                    _start_docx_script_elapsed_timer(ctx, reason="docx_segment_speech")
                    formatted_text = format_docx_script_text(text)
                    start_docx_segment_background_command(segment, scene, segment_index, formatted_text)
                    log_docx_feedback_start(scene, segment_index, formatted_text)
                    span_token = _profile_start("tts_segment", scene=scene, segment=segment_index, text=formatted_text)
                    try:
                        if early_listen:
                            listen_span = _profile_start("listen_answer", listen_key=listen_key, scene=scene, segment=segment_index, timeout=listen_timeout, early=True)
                            answer = ""
                            trace_id, trace_event = make_docx_interaction_trace(listen_key, scene, segment_index)
                            try:
                                answer = tts_ask_with_early_stt(
                                    tts_agent,
                                    formatted_text,
                                    stt_agent,
                                    timeout=listen_timeout,
                                    stop_tts_on_answer=True,
                                    trace_event=trace_event,
                                    trace_id=trace_id,
                                )
                            finally:
                                _profile_end(listen_span, listen_key=listen_key, scene=scene, segment=segment_index, early=True, answer=answer, trace_id=trace_id)
                            return ("__DOCX_LISTEN_ANSWER__", answer, trace_id)
                        return tts_long_text_with_stt_stop(
                            tts_agent,
                            formatted_text,
                            stt_agent,
                            ctx.robot,
                            before_text,
                            ignored_interrupt_texts=DOCX_SCRIPT_CONTINUE_TEXTS,
                            ignore_unlisted_interrupts=not _docx_guide_qa_interrupt_enabled(),
                        )
                    finally:
                        _profile_end(span_token, scene=scene, segment=segment_index, text=formatted_text)

                if speak_with_action:
                    interrupt_text = await _do_arm_during_speech(ctx.robot, action_name, speak_segment)
                else:
                    interrupt_text = speak_segment()

                if isinstance(interrupt_text, tuple) and interrupt_text[0] == "__DOCX_LISTEN_ANSWER__":
                    listen_answer_handled = True
                    accept_docx_listen_answer(
                        listen_key,
                        scene,
                        segment_index,
                        interrupt_text[1],
                        trace_id=interrupt_text[2] if len(interrupt_text) > 2 else None,
                    )
                    interrupt_text = None

            if not speak_with_action:
                await _release_arm_after_speech(ctx.robot, action_name)
            if not _is_empty_stt_text(interrupt_text):
                if is_docx_script_continue_text(interrupt_text):
                    print(f"忽略剧本继续确认词: {interrupt_text}")
                    segment_index += 1
                    ctx.docx_script_segment_index = segment_index
                    continue
                print(f"DOCX 剧本被用户打断: scene={scene}, segment={segment_index}, text={interrupt_text}")
                ctx.docx_script_segment_index = segment_index
                _profile_end(step_span, step_index=step_index, scene=scene, status="interrupt")
                return "interrupt", interrupt_text.strip()

            if listen_key and not listen_answer_handled:
                listen_span = _profile_start("listen_answer", listen_key=listen_key, scene=scene, segment=segment_index, timeout=listen_timeout)
                answer = audio_input_execute_timeout(stt_agent, timeout=listen_timeout, text="")
                _profile_end(listen_span, listen_key=listen_key, scene=scene, segment=segment_index, answer=answer)
                accept_docx_listen_answer(listen_key, scene, segment_index, answer)

            post_wait_seconds = float(segment.get("post_wait_seconds", 0) or 0)
            if post_wait_seconds > 0:
                await asyncio.sleep(post_wait_seconds)

            segment_index += 1
            ctx.docx_script_segment_index = segment_index

        ctx.docx_script_step_index = step_index + 1
        ctx.docx_script_segment_index = 0
        ctx.docx_script_nav_done_step = None
        _profile_end(step_span, step_index=step_index, scene=scene, status="done")
        _workflow_log(f"DOCX 剧本步骤完成: scene={scene}, next_index={ctx.docx_script_step_index}")
        if ctx.docx_script_step_index >= len(DOCX_SCRIPT_STEPS):
            ctx.docx_script_done = True
            ctx.post_docx_chat_mode = False
            write_task_progress("finished", current_site=scene, next_site=None, completed_points=len(DOCX_SCRIPT_STEPS), active=False)
            _profile_end(getattr(ctx, "docx_total_profile_span", None), status="finished")
            ctx.docx_total_profile_span = None
            _finish_docx_script_elapsed_timer(ctx, reason="script_finished")
            _workflow_log("DOCX 剧本全部完成，结束 workflow，不进入剧本后问答")
            return "done", SCRIPTED_TOUR_FINISHED
        return "done", SCRIPTED_TOUR_STEP_DONE

    async def run_scripted_tour_next_step():
        if not scripted_tour_enabled():
            return None, None
        if not guide_started():
            return None, None
        if pending_user_text:
            return None, None
        if _strict_docx_script_enabled():
            return await run_docx_scripted_tour_next_step()

        init_scripted_tour_state()
        if getattr(ctx, "scripted_tour_done", False):
            return None, None

        entity_order = getattr(ctx, "scripted_tour_order", [])
        index = getattr(ctx, "scripted_tour_index", 0)
        if index >= len(entity_order):
            ctx.scripted_tour_done = True
            write_task_progress("finished", current_site=getattr(ctx, "current_entity_name", None), next_site=None, completed_points=len(entity_order), total_points=len(entity_order), active=False)
            await _do_arm_async_timed(ctx.robot, "high_wave")
            leader_info = getattr(ctx, "leader_info", {}) or {}
            leader_calling = leader_info.get("leader_calling") or _docx_guide_leader_calling()
            tts_sound(tts_agent, f"{before_text}{leader_calling}、各位领导再会，欢迎您再次来到我们人形机器人产业园。", "zh")
            tts_wait(tts_agent)
            return "done", SCRIPTED_TOUR_FINISHED

        entity_name = entity_order[index]
        entity = _load_json_entity(entity_name)
        if entity is None:
            print(f"剧本导览跳过未知展点: {entity_name}")
            ctx.scripted_tour_index = index + 1
            return "done", SCRIPTED_TOUR_STEP_DONE

        _workflow_log(f"剧本导览步骤开始: index={index}, entity={entity_name}")
        already_arrived = (
            getattr(ctx, "scripted_tour_arrived_index", None) == index
            and getattr(ctx, "current_entity_name", None) == entity_name
        )
        if not already_arrived:
            write_task_progress("navigating", current_site=getattr(ctx, "current_entity_name", None), next_site=entity_name, completed_points=index, total_points=len(entity_order), active=True)
            guide_text = build_scripted_intro(entity_name)
            tts_sound(tts_agent, f"{before_text}{guide_text}", "zh")
            tts_wait(tts_agent)

            location_points = _extract_location_points(entity)
            if not location_points:
                print(f"剧本导览展点缺少可用导航点位: {entity}")
                ctx.scripted_tour_index = index + 1
                return "done", SCRIPTED_TOUR_STEP_DONE

            enable_navi = os.getenv("RABBITBOT_ENABLE_NAVI", "1").strip().lower() not in {"0", "false", "no", "off"}
            navi_status = NavigationStatus.SUCCEEDED
            if enable_navi:
                if _wait_manual_navigation_success(entity_name):
                    navi_status = NavigationStatus.SUCCEEDED
                else:
                    navi_query = NavigationQuery()
                    x, y, ox, oy, oz, ow = location_points[0]
                    await navi_tools.go_to_async(
                        x, y, ox, oy, oz, ow, navi_query,
                        waypoints=location_points if len(location_points) > 1 else None,
                    )
                    nav_interrupt_text = await wait_navigation_with_stt_interrupt(navi_tools, entity_name, index)
                    if not _is_empty_stt_text(nav_interrupt_text):
                        return "interrupt", nav_interrupt_text
                    navi_status = await navi_tools.go_to_status()
                    await navi_tools.reset_go_to_status()
                _workflow_log(f"剧本导览导航完成: entity={entity_name}, status={navi_status}")

            if navi_status != NavigationStatus.SUCCEEDED:
                tts_sound(tts_agent, f"{before_text}很抱歉，我暂时无法到达{entity_name}。", "zh")
                tts_wait(tts_agent)
                return "done", SCRIPTED_TOUR_STEP_DONE

            set_current_entity_name(entity_name)
            ctx.scripted_tour_arrived_index = index
            next_entity_name = entity_order[index + 1] if index + 1 < len(entity_order) else None
            write_task_progress("arrived", current_site=entity_name, next_site=next_entity_name, completed_points=index + 1, total_points=len(entity_order), active=True)
        else:
            next_entity_name = entity_order[index + 1] if index + 1 < len(entity_order) else None
            write_task_progress("arrived", current_site=entity_name, next_site=next_entity_name, completed_points=index + 1, total_points=len(entity_order), active=True)
            tts_sound(tts_agent, f"{before_text}我们继续刚才的介绍。", "zh")
            tts_wait(tts_agent)

        action_name = SCRIPTED_TOUR_ACTIONS.get(entity_name)
        interrupt_text = None
        description = entity.get("description", "")
        if description:
            def speak_entity_description():
                return tts_long_text_with_stt_stop(tts_agent, description, stt_agent, ctx.robot, before_text)

            if _should_speak_with_action(action_name):
                interrupt_text = await _do_arm_during_speech(ctx.robot, action_name, speak_entity_description)
            else:
                if action_name:
                    await _do_arm_before_speech(ctx.robot, action_name)
                interrupt_text = speak_entity_description()
                await _release_arm_after_speech(ctx.robot, action_name)
        elif action_name:
            await _do_arm_before_speech(ctx.robot, action_name)
            await _release_arm_after_speech(ctx.robot, action_name)
        if not _is_empty_stt_text(interrupt_text):
            print(f"剧本导览被用户打断: entity={entity_name}, text={interrupt_text}")
            return "interrupt", interrupt_text.strip()

        ctx.scripted_tour_index = index + 1
        ctx.scripted_tour_arrived_index = None
        _workflow_log(f"剧本导览步骤完成: entity={entity_name}, next_index={ctx.scripted_tour_index}")
        return "done", SCRIPTED_TOUR_STEP_DONE

    async def listen_user_input_for_workflow(source, prompt_on_timeout=True):
        audio_span = _profile_start("audio_input", source=source, timeout=30)
        try:
            out_text = audio_input_execute_timeout(stt_agent, timeout=30, text="")
        finally:
            _profile_end(audio_span, source=source, timeout=30)
        while out_text == "<REC_TIMEOUT>" or out_text == "<REC_DUPLICATE>":
            if prompt_on_timeout:
                prompt_text = os.getenv("RABBITBOT_PRE_GUIDE_QA_PROMPT", "你好，请问你需要我做什么吗？听到开始导览后，我会开始讲解。")
                tts_sound(tts_agent, f"{before_text}{prompt_text}", "zh")
            audio_span = _profile_start("audio_input", source=f"{source}_retry", timeout=30)
            try:
                out_text = audio_input_execute_timeout(stt_agent, timeout=30, text="")
            finally:
                _profile_end(audio_span, source=f"{source}_retry", timeout=30)
        return out_text

    async def audio_input_executor(step_input):
        original_task = step_input.message or ''
        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"original_task: {original_task}", verbose=True)
        _workflow_log(f"previous_steps: {previous_steps}", verbose=True)

        loop_span = _profile_start("loop_iteration", step="audio_input_step")
        text = original_task
        #text = previous_steps.split("===")[-1]
        #text = text[1:]
        _workflow_log(f"text: {text}", verbose=True)

        #tts_sound(tts_agent, f"{before_text}我准备好了，您需要帮助吗？", "zh")
        #tts_sound(tts_agent, "You can chat with me now", "en")
        #tts_fast(tts_agent, "ready")

        text = "请介绍一下深圳这座城市"
        pending_text = pop_pending_user_text()
        if pending_text and docx_script_in_progress() and is_docx_script_continue_text(pending_text):
            print(f"忽略剧本继续确认词: {pending_text}")
            pending_text = ""
        if pending_text:
            out_text = pending_text
            print(f"使用打断输入作为下一轮用户输入: {out_text}")
        else:
            if guide_start_by_voice_enabled() and not guide_started():
                ctx.pre_guide_qa_mode = True
                out_text = await listen_user_input_for_workflow("pre_guide_qa")
                if is_guide_start_command(out_text):
                    await start_scripted_tour_by_voice(out_text)
                    WorkflowTimePoints.PLAN_START = time.time()
                    _profile_end(loop_span, step="audio_input_step", result="guide_started_by_voice")
                    return StepOutput(content=f"{SCRIPTED_TOUR_STEP_DONE}")
            else:
                script_kind, script_text = await run_scripted_tour_next_step()
                if script_kind == "done":
                    WorkflowTimePoints.PLAN_START = time.time()
                    if script_text == SCRIPTED_TOUR_FINISHED and guide_start_by_voice_enabled():
                        ctx.guide_tour_completed_wait_return = True
                        _profile_summary_print(reason="docx_finished_wait_return")
                        _workflow_log("导览已完成，保持 QA 状态等待返回起点口令")
                        _profile_end(loop_span, step="audio_input_step", result="script_done_wait_return")
                        return StepOutput(content=f"{SCRIPTED_TOUR_STEP_DONE}")
                    _profile_end(loop_span, step="audio_input_step", result="script_done")
                    if script_text == SCRIPTED_TOUR_FINISHED:
                        _profile_summary_print(reason="docx_finished")
                    return StepOutput(content=f"{script_text}")
                if script_kind == "interrupt":
                    out_text = script_text
                    print(f"使用剧本导览打断输入作为用户输入: {out_text}")
                else:
                    time.sleep(1)
                    #out_text = audio_input_execute(stt_agent, "speech_to_text", timeout=300)
                    out_text = await listen_user_input_for_workflow("main_loop")
        if guide_started() and is_guide_start_command(out_text):
            _workflow_log(f"忽略重复开始导览口令: text_len={len(out_text or '')}")
            WorkflowTimePoints.PLAN_START = time.time()
            _profile_end(loop_span, step="audio_input_step", result="duplicate_guide_start_ignored")
            return StepOutput(content=f"{SCRIPTED_TOUR_STEP_DONE}")
        if guide_started() and is_guide_return_command(out_text):
            if guide_tour_completed_for_return():
                if write_return_request_file(out_text):
                    WorkflowTimePoints.PLAN_START = time.time()
                    _profile_end(loop_span, step="audio_input_step", result="return_to_start_requested")
                    return StepOutput(content=f"{SCRIPTED_TOUR_RETURN_TO_START}")
                WorkflowTimePoints.PLAN_START = time.time()
                _profile_end(loop_span, step="audio_input_step", result="return_request_file_error")
                return StepOutput(content=f"{SCRIPTED_TOUR_STEP_DONE}")
            _workflow_log(f"导览尚未完成，忽略返回起点口令: text_len={len(out_text or '')}")
            WorkflowTimePoints.PLAN_START = time.time()
            _profile_end(loop_span, step="audio_input_step", result="return_to_start_ignored_before_finished")
            return StepOutput(content=f"{SCRIPTED_TOUR_STEP_DONE}")

        chat_queue.put(out_text, "用户")

        #tts_sound(tts_agent, f"{before_text}我听到了，但是可能要思考一会。请稍等片刻", "zh")
        think_type = identify_think_type(out_text)
        tts_fast(tts_agent, think_type)

        WorkflowTimePoints.PLAN_START = time.time()

        _profile_end(loop_span, step="audio_input_step", result="user_input")
        return StepOutput(content=f"{out_text}")

    audio_input_step = Step(
        name='audio_input_step',
        description='Audio input from the user.',
        executor=audio_input_executor,
    )

    plan_step = Step(
        name='plan_step',
        agent=plan_agent,
        description='Plan the next step to complete the task.',
    )

    async def plan_executor(step_input):
        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"previous_steps: {previous_steps}", verbose=True)
        text_lst = previous_steps.split("===")
        assert text_lst[1].replace(" ", "") == "audio_input_step"
        text = text_lst[2].replace("\n", "")

        _workflow_log(f"in_text: {text}", verbose=True)
        if text in {SCRIPTED_TOUR_STEP_DONE, SCRIPTED_TOUR_FINISHED, SCRIPTED_TOUR_RETURN_TO_START}:
            _workflow_log(f"plan_executor: scripted tour control token {text}, skip planner", verbose=True)
            return StepOutput(content=text)
        if getattr(ctx, "post_docx_chat_mode", False):
            _workflow_log("plan_executor: post DOCX chat mode, skip guide planner", verbose=True)
            return await chat_executor(step_input)
        history_text = chat_queue.build_history()
        text =  history_text
        _workflow_log(f"in_text: {text}", verbose=True)
        rule_task = classify_task_by_rule(text_lst[2].replace("\n", ""))
        if rule_task == "C":
            _workflow_log("plan_executor: rule classified as chat", verbose=True)
            return await chat_executor(step_input)
        if rule_task == "N":
            _workflow_log("plan_executor: rule classified as navigation", verbose=True)
            return await navi_check_executor(step_input)
        if rule_task == "V":
            _workflow_log("plan_executor: rule classified as view", verbose=True)
            return await view_executor(step_input)

        start_time = time.time()
        plan_llm_span = _profile_start("plan_llm")
        #run_response = plan_agent.run(text, session_id=str(PLAN_SESSION_ID))
        #out_text = run_response.content
        response_stream = plan_agent.run(
            text, stream=True, stream_intermediate_steps=False,
            session_id=str(PLAN_SESSION_ID)
        )
        out_text = ""
        for event in response_stream:
            if event.event == "RunResponseContent":
                #print(f"Content: {event.content}")
                out_text += event.content
            elif event.event == "ToolCallStarted":
                _workflow_log(f"Tool call started: {event.tool}", verbose=True)
            elif event.event == "ReasoningStep":
                _workflow_log(f"Reasoning step: {event.content}", verbose=True)
            if len(out_text) > 0:
                break
        duration  = time.time() - start_time
        _workflow_log(f"out_text: {out_text}", verbose=True)
        log_text = f"plan_executor: plan_duration {duration:.3f}, text {out_text}"
        _workflow_log(log_text, verbose=True)
        file_logger.debug(log_text)
        _profile_end(plan_llm_span, output=out_text)

        planner_choice = (out_text or "").strip()[:1].upper()
        if planner_choice == "C":
            response = await chat_executor(step_input)
        elif planner_choice == "N":
            response = await navi_check_executor(step_input)
        elif planner_choice == "V":
            response = await view_executor(step_input)
        else:
            # The planner is intentionally conservative: ordinary dialogue should
            # remain usable even if the routing model returns an empty or noisy token.
            print(f"plan_executor: invalid planner output {out_text!r}, fallback to chat")
            response = await chat_executor(step_input)

        return response

    plan_step_v2 = Step(
        name='plan_step',
        description='Plan the next step to complete the task.',
        executor=plan_executor,
    )

    def is_chinese(s):
        #return all('\u4e00' <= ch <= '\u9fff' for ch in s)
        return '\u4e00' <= s[0] <= '\u9fff'

    def is_english(s):
        #return all('a' <= ch.lower() <= 'z' for ch in s if ch.isalpha())
        return 'a' <= s[0].lower() <= 'z'

    async def retrieve_chat_rag_reference(text):
        """闲聊 RAG：用用户问题检索记忆(neo4j 图谱 + markdown 文档)，命中则返回可作参考资料的文本，未命中返回空串。

        由 RABBITBOT_CHAT_RAG 控制（默认启用）；检索走 ctx.memory.query，复用与导览/找物品一致的
        neo4j+markdown 合并检索。命中"异常结点"(低于相似度阈值)或异常时降级为通用回答，不改变原有行为。
        """
        if not _env_enabled("RABBITBOT_CHAT_RAG", "1"):
            return ""
        query_text = (text or "").strip()
        if not query_text or query_text in ("<REC_TIMEOUT>", "<REC_STOP>", "<REC_DUPLICATE>"):
            return ""
        if getattr(ctx, "memory", None) is None:
            return ""
        rag_group = os.getenv("RABBITBOT_CHAT_RAG_GROUP", "闲聊检索")
        try:
            nodes = await ctx.memory.query(query=query_text, group_name=rag_group, limit=1)
        except Exception as exc:
            file_logger.warning(
                f"闲聊RAG记忆检索异常，降级为通用回答: query_len={len(query_text)}, error={exc}"
            )
            return ""
        if not nodes or getattr(nodes[0], "name", "") == "异常结点":
            file_logger.info(f"闲聊RAG未命中记忆，使用通用回答: query_len={len(query_text)}")
            return ""
        node = nodes[0]
        description = (getattr(node, "attributes", None) or {}).get("description", "") or ""
        reference_body = (description or getattr(node, "summary", "") or "").strip()
        if not reference_body:
            return ""
        reference = f"{node.name}：{reference_body}"
        file_logger.info(
            f"闲聊RAG命中记忆: name={node.name}, reference_len={len(reference)}, query_len={len(query_text)}"
        )
        return reference

    def build_chat_rag_input(text, reference):
        """把检索到的参考资料与用户问题拼成 RAG 提示，交给闲聊 VLM 生成回答。"""
        return (
            "请参考以下资料回答用户的问题。若资料与问题相关，请依据资料自然口语化作答；"
            "若资料与问题无关，请忽略资料，用你已知的信息回答。\n"
            f"【参考资料】{reference}\n"
            f"【用户问题】{text}"
        )

    async def chat_execute(text, sess_idx=None, navi_tools=None):
        _workflow_log(f"chat_execute: text {text}", verbose=True)
        if is_chinese(text): lang = "zh"
        elif is_english(text): lang = "en"
        else:
            lang = "zh"
            #print(f"Unkown lanugage")
            #out_text = "<CHAT_UNKOWN_LANG>"
            #return StepOutput(content=f"{out_text}")
        _workflow_log(f"lang: {lang}", verbose=True)
        if text == "<REC_TIMEOUT>":
            out_text = text
            return StepOutput(content=f"{out_text}")

        # 闲聊 RAG：先检索记忆(neo4j 图谱 + markdown 文档)，命中则把参考资料一并交给 VLM 生成回答；
        # 未命中或异常时 chat_input_text 保持为原始 text，行为与原来完全一致。
        chat_input_text = text
        rag_reference = await retrieve_chat_rag_reference(text)
        if rag_reference:
            chat_input_text = build_chat_rag_input(text, rag_reference)

        tts_wait(tts_agent)

        WorkflowTimePoints.CHAT_START = time.time()
        chat_llm_span = _profile_start("chat_llm")
        chat_tts_span = None
        active_chat_agent = post_docx_chat_agent if getattr(ctx, "post_docx_chat_mode", False) else chat_agent
        if sess_idx is not None:
            _workflow_log(f"chat_agent: session_id {str(sess_idx)}", verbose=True)
            _workflow_log(f"chat_agent: text {text}", verbose=True)
            response_stream = active_chat_agent.run(
                chat_input_text, stream=True, stream_intermediate_steps=False,
                session_id=str(sess_idx)
            )
        else:
            response_stream = active_chat_agent.run(
                chat_input_text, stream=True, stream_intermediate_steps=False,
            )

        speecher_start_event = threading.Event()
        speecher_stop_event = threading.Event()
        listener_stop_event = threading.Event()
        interrupt_text_holder = {"text": ""}

        def stop_task():
            while True:
                time.sleep(1)
                while not speecher_start_event.is_set():
                    time.sleep(1)
                print("聊天正式开始，可以输入停止命令了") if lang == "zh" else print("You can say stop now")
                if False:
                    #text = "停止说话"
                    #input_dict = {"task": "speech_to_text_async", "lang": lang, "text": "", "timeout": 60}

                    #run_response = stt_agent.run(
                    #   json.dumps(input_dict), stream=False, stream_intermediate_steps=False,
                    #)
                    #out_text = run_response.content

                    #out_text = stt_agent.run(json.dumps(input_dict))

                    out_text = audio_input_execute_timeout(stt_agent, timeout=30)
                    #out_text = ""

                    print("收到命令：", out_text) if lang == "zh" else print("Got command:", out_text)
                    if out_text.startswith("停止") or "停" in out_text or "stop" in out_text.lower():
                        speecher_stop_event.set()
                        break
                if listener_stop_event.is_set():
                    _workflow_log("监听线程收到信号量，退出", verbose=True)
                    break
                if True:
                    resp_msg = audio_input_stop_chat(stt_agent)
                    if resp_msg == "<STOP_CHAT>":
                        print("收到停止口令，退出")
                        speecher_stop_event.set()
                        break
                    elif resp_msg != "<UNKNOWN_MSG>":
                        print("收到用户打断输入，退出当前回答：", resp_msg)
                        interrupt_text_holder["text"] = resp_msg
                        speecher_stop_event.set()
                        break
                if listener_stop_event.is_set():
                    _workflow_log("监听线程收到信号量，退出", verbose=True)
                    break

        speecher_stop_thread = threading.Thread(target=stop_task)
        speecher_stop_thread.start()

        global last_chat_text
        out_text = ""
        last_chat_text = ""
        num_setence = 0
        for event in response_stream:
            if event.event == "RunResponseContent":
                #print(f"Content: {event.content}")
                out_text += event.content
            elif event.event == "ToolCallStarted":
                _workflow_log(f"Tool call started: {event.tool}", verbose=True)
            elif event.event == "ReasoningStep":
                _workflow_log(f"Reasoning step: {event.content}", verbose=True)

            if speecher_stop_event.is_set():
                tts_stop(tts_agent)
                time.sleep(0.5)
                _workflow_log("已经停止说话了" if lang == "zh" else "Chatting stopped", verbose=True)
                break
            if navi_tools is not None:
                if not await is_navigating(navi_tools):
                    _workflow_log("导航达到，停止生成文本", verbose=True)
                    break

            #print(f"OutText: {out_text}")
            out_text = out_text
            if out_text.endswith("，") or out_text.endswith("；") or \
                out_text.endswith("。") or out_text.endswith("？") or out_text.endswith("！") or \
                out_text.endswith(".") or out_text.endswith("!") or out_text.endswith("\n"):
                _workflow_log(f"out_text: {out_text}", verbose=True)
                action_name = None

                if out_text.startswith("[A:"):
                    ei = out_text.index("]")
                    text_len = len(out_text[ei+1:])
                else:
                    text_len = len(out_text)

                _workflow_log(f"text_len: {text_len}", verbose=True)
                if text_len < 8:
                    continue

                if out_text.startswith("[A:"):
                    ei = out_text.index("]")
                    _workflow_log(f"ei: {ei}", verbose=True)
                    action_name = out_text[3:ei]
                    _workflow_log(f"action_name: {action_name}", verbose=True)
                    out_text = out_text[ei+1:]
                    _workflow_log(f"out_text: {out_text}", verbose=True)
                #time.sleep(10)

                if is_chinese(out_text):
                    lang = "zh"
                elif is_english(out_text):
                    lang = "en"
                else:
                    lang = "zh"
                    print(f"Unkown lanugage: {lang}")
                WorkflowTimePoints.CHAT_FIRST_TEXT_START = time.time()
                first_infer_time = WorkflowTimePoints.CHAT_FIRST_TEXT_START - WorkflowTimePoints.CHAT_START
                WorkflowTimePoints.CHAT_START = WorkflowTimePoints.CHAT_FIRST_TEXT_START
                log_text = f"chat_executor: seq_idx {num_setence}, infer_time {first_infer_time:.3f}, text {out_text}"
                _workflow_log(log_text, verbose=True)
                file_logger.debug(log_text)
                #tts_index = tts_sound(tts_agent, f"{before_text}" + out_text.strip(), lang)
                if chat_tts_span is None:
                    chat_tts_span = _profile_start("chat_tts")
                tts_index = tts_sound(tts_agent, out_text.strip(), lang)
                speecher_start_event.set()
                if navi_tools is not None:
                    go_to_status = await navi_tools.go_to_status()
                    if go_to_status == NavigationStatus.PENDING or go_to_status == NavigationStatus.SUCCEEDED:
                        if action_name is not None:
                            if action_name == "shake_hand":
                                #await handshake_execute_v2(ctx)
                                action_with_tts(ctx.robot, action_name, tts_agent, tts_index)
                            else:
                                action_with_tts(ctx.robot, action_name, tts_agent, tts_index)
                else:
                    if action_name is not None:
                        if action_name == "shake_hand":
                            #await handshake_execute_v2(ctx)
                            action_with_tts(ctx.robot, action_name, tts_agent, tts_index)
                        else:
                            action_with_tts(ctx.robot, action_name, tts_agent, tts_index)
                last_chat_text += out_text
                out_text = ""
                num_setence += 1
                #if num_setence > 3:
                #    break

        _profile_end(chat_llm_span, sentence_count=num_setence)

        remaining_text = out_text.strip()
        if remaining_text and not speecher_stop_event.is_set():
            _workflow_log(f"remaining out_text: {remaining_text}", verbose=True)
            action_name = None
            if remaining_text.startswith("[A:") and "]" in remaining_text:
                ei = remaining_text.index("]")
                action_name = remaining_text[3:ei]
                remaining_text = remaining_text[ei+1:].strip()
                _workflow_log(f"remaining action_name: {action_name}", verbose=True)

            if remaining_text:
                if is_chinese(remaining_text):
                    lang = "zh"
                elif is_english(remaining_text):
                    lang = "en"
                else:
                    lang = "zh"
                    print(f"Unkown lanugage: {lang}")
                WorkflowTimePoints.CHAT_FIRST_TEXT_START = time.time()
                first_infer_time = WorkflowTimePoints.CHAT_FIRST_TEXT_START - WorkflowTimePoints.CHAT_START
                WorkflowTimePoints.CHAT_START = WorkflowTimePoints.CHAT_FIRST_TEXT_START
                log_text = f"chat_executor: seq_idx {num_setence}, infer_time {first_infer_time:.3f}, text {remaining_text}"
                _workflow_log(log_text, verbose=True)
                file_logger.debug(log_text)
                if chat_tts_span is None:
                    chat_tts_span = _profile_start("chat_tts")
                tts_index = tts_sound(tts_agent, remaining_text, lang)
                speecher_start_event.set()
                if action_name is not None:
                    action_with_tts(ctx.robot, action_name, tts_agent, tts_index)
                last_chat_text += remaining_text
                num_setence += 1

        if False:
            go_to_status = await navi_tools.go_to_status()
            if go_to_status == NavigationStatus.PENDING or go_to_status == NavigationStatus.SUCCEEDED:
                if "自我介绍" in text or "你好" in text or "您好" in text:
                    time.sleep(0.6)
                    await _do_arm_async_timed(ctx.robot, "face_wave")

        #out_text = run_response.content
        chat_queue.put(last_chat_text, "机器人")
        out_text = ""
        #print(f"OutText: {out_text}")

        #tts_wait(tts_agent)
        while True:
            time.sleep(0.5)
            if speecher_stop_event.is_set():
                _workflow_log("收到停止或打断命令，准备退出聊天", verbose=True)
                tts_stop(tts_agent)
                break
            if navi_tools is not None:
                if not await is_navigating(navi_tools):
                    _workflow_log("导航达到，停止等待语音", verbose=True)
                    break
            if tts_get_wav_count(tts_agent) == 0:
                _workflow_log("WAV播完，退出聊天", verbose=True)
                break
        if chat_tts_span is not None:
            _profile_end(chat_tts_span, sentence_count=num_setence)
        listener_stop_event.set()
        speecher_start_event.set()
        #audio_input_execute(stt_agent, "stop")
        audio_input_execute(stt_agent, "stop_async")
        speecher_stop_thread.join()

        return interrupt_text_holder["text"]

    class ChatSessionInfo:
        sess_idx: int = CHAT_SESSION_ID

    async def chat_loop_execute(text, navi_tools=None):
        max_chat_steps = workflow_configs["max_chat_steps"]
        for i in range(max_chat_steps):
            if text is None:
                if navi_tools is None:
                    text = audio_input_execute_timeout(stt_agent, timeout=60)
                else:
                    text = await audio_input_execute_timeout_navi(stt_agent, 60, navi_tools)
            if text == "<REC_TIMEOUT>" or text == "<NAVI_REACH>" or text == "<REC_DUPLICATE>":
                break
            if "停止聊天" in text:
                break
            #if i > 0:
            #    think_type = identify_think_type(text)
            #    tts_fast(tts_agent, think_type)
            interrupt_text = await chat_execute(text, ChatSessionInfo.sess_idx, navi_tools)
            if set_pending_user_text(interrupt_text):
                break
            text = None
        out_text = "Chat loop finish"
        #ChatSessionInfo.sess_idx += 1
        return out_text

    async def chat_executor(step_input):
        WorkflowTimePoints.PLAN_END = time.time()
        plan_time = WorkflowTimePoints.PLAN_END - WorkflowTimePoints.PLAN_START
        _workflow_log(f"chat_executor: plan_time: {plan_time:.3f}", verbose=True)
        original_task = step_input.message or ''
        previous_step = step_input.get_last_step_content()
        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"original_task: {original_task}", verbose=True)
        _workflow_log(f"previous_step: {previous_step}", verbose=True)
        _workflow_log(f"previous_steps: {previous_steps}", verbose=True)

        #text = previous_step.split("=")[2][1:-1]
        #text = previous_step.subtask_description
        text_lst = previous_steps.split("===")
        assert text_lst[1].replace(" ", "") == "audio_input_step"
        text = text_lst[2].replace("\n", "")
        _workflow_log(f"chat_input_text: {text}", verbose=True)
        #text = str(previous_step)
        #text = text.split("=")[2][1:-1]
        #text = str(original_task)
        #text = ""
        #print("text:", text)

        #out_text = await chat_execute(text)
        out_text = await chat_loop_execute(text)

        return StepOutput(content=f"{out_text}")

    async def vln_execute(ctx):
        tts_sound(tts_agent, f"{before_text}下面我将展示我的动态导航功能", "zh")
        while True:
            tts_sound(tts_agent, f"{before_text}请告诉我你想让我找什么？", "zh")
            audio_input_text = audio_input_execute_timeout(stt_agent, 300)
            task = audio_input_text
            _workflow_log(f"task: {task}", verbose=True)

            run_response = ctoe_translate_agent.run(task)
            out_text = run_response.content
            _workflow_log(f"out_text: {out_text}", verbose=True)

            task = out_text
            _workflow_log(f"task: {task}", verbose=True)
            await ctx.robot.vln(task)

    def load_mock_view_image():
        image_path = os.getenv(
            "RABBITBOT_MOCK_IMAGE",
            str(Path(__file__).resolve().parents[2] / "tests" / "tasks" / "resources" / "frig.jpg"),
        )
        image = cv2.imread(image_path)
        if image is not None:
            print(f"使用 mock 视觉图片: {image_path}")
            return image

        print(f"mock 视觉图片不存在或无法读取: {image_path}，使用内置测试图")
        image = np.full((720, 1280, 3), 245, dtype=np.uint8)
        cv2.rectangle(image, (120, 180), (520, 520), (80, 160, 240), -1)
        cv2.rectangle(image, (700, 220), (1080, 500), (80, 190, 120), -1)
        cv2.putText(image, "orange display board", (150, 560), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 30), 2)
        cv2.putText(image, "green robot area", (720, 540), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 30), 2)
        return image

    async def view_execute(ctx, task):
        _workflow_log(f"view task: {task}", verbose=True)
        view_mode = os.getenv("RABBITBOT_VIEW_MODE", "mock").strip().lower()
        if view_mode == "robot":
            out_text = await ctx.robot.view(task)
        else:
            image = load_mock_view_image()
            prompt = dedent(f"""\
                你是机二机器人的视觉问答模块。请根据图片内容回答用户问题。
                用户问题：{task}

                要求：
                - 用中文回答。
                - 回答要简短、自然，适合机器人直接说出来。
                - 如果图片中看不清或无法确定，请明确说明。
            """)
            messages, extra_body = general_vlm_openai.prepare_message_for_vllm([image], prompt)
            out_text = general_vlm_openai.get_chat_response(messages, extra_body)
        _workflow_log(f"view out_text: {out_text}", verbose=True)
        chat_queue.put(out_text, "机器人")
        tts_sound(tts_agent, f"{before_text}{out_text}", "zh")
        return out_text

    async def move_execute(ctx):
        tts_sound(tts_agent, f"{before_text}下面我将展示我的转向能力", "zh")
        while True:
            tts_sound(tts_agent, f"{before_text}请按回车键向左转", "zh")
            input("请按回车键继续")
            out_text = await ctx.robot.move(2)
            tts_sound(tts_agent, f"{before_text}请按回车键向右转", "zh")
            input("请按回车键继续")
            out_text = await ctx.robot.move(3)

    async def sound_execute(ctx):
        tts_sound(tts_agent, f"下面我将展示我的语音说话功能，我会重复你说的话", "zh")
        while True:
            audio_input_text = audio_input_execute_timeout(stt_agent, 300)
            tts_sound(tts_agent, f"{audio_input_text}", "zh")

    async def vln_executor(step_input):
        await vln_execute(ctx)
        response = 'VLN completed.'
        yield StepOutput(
            content=response,
        )

    async def view_executor(step_input):
        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"view previous_steps: {previous_steps}", verbose=True)
        text_lst = previous_steps.split("===")
        assert text_lst[1].replace(" ", "") == "audio_input_step"
        task = text_lst[2].replace("\n", "")
        await view_execute(ctx, task)
        response = 'VLM completed.'
        return StepOutput(
            content=response,
        )

    async def move_executor(step_input):
        await move_execute(ctx)
        response = 'Move completed.'
        yield StepOutput(
            content=response,
        )

    async def sound_executor(step_input):
        await sound_execute(ctx)
        response = 'Sound completed.'
        yield StepOutput(
            content=response,
        )

    async def unknown_executor(step_input):
        #tts_fast(tts_agent, "sorry")
        arm_lst = ["否定拒绝", "双手平摊开掌心向上"]
        n = len(arm_lst)
        rand_n = random.randint(0, n-1)
        await _do_arm_async_timed(ctx.robot, arm_lst[rand_n])
        tts_fast(tts_agent, "unknown")
        out_text = "<WORKFLOW_UNKOWN>"
        return StepOutput(content=f"{out_text}")

    navigation_routines = {
        'slam_vln': dedent("""\
            1. call go_to with the (x, y) of the target entity
            2. call dynamic_navigation to get close and face the target entity"""),
        'vln': dedent("""\
            1. call dynamic_navigation to complete the task"""),
    }
    navigation_agents: dict[str, Agent] = {}
    for routine, instruction in navigation_routines.items():
        navigation_agents[routine] = Agent(
            name='Navigation Agent ({})'.format(routine),
            role='Navigator',
            instructions=dedent("""\
                You are a navigation agent of a embodied robot.
                Given a task, you must use the navigation tool to complete.
                Routine:
                """ + instruction),
            tools=[navi_tools],
            model=model,
            show_tool_calls=True,
        )

    def _normalize_nav_text(text):
        return guide_normalize_nav_text(text)

    def _has_any(text, keywords):
        return guide_has_any(text, keywords)

    def is_chat_info_request(text):
        return guide_is_chat_info_request(text)

    def has_navigation_action(text):
        return guide_has_navigation_action(text)

    def is_visual_request(text):
        return guide_is_visual_request(text)

    def is_direct_navigation_request(text):
        return guide_is_direct_navigation_request(text)

    def is_next_board_request(text):
        return guide_is_next_board_request(text)

    def classify_task_by_rule(text):
        return guide_classify_task_by_rule(text)

    def resolve_navigation_entity_by_fuzzy(text, entity_lst):
        return guide_resolve_navigation_entity_by_fuzzy(text, entity_lst)

    async def navi_execute(
        subtask_description,
        skip_confirm=False,
    ):
        nodes = await ctx.memory.query(query=subtask_description, group_name="展点", limit=5)
        _workflow_log(f"nodes: {nodes}", verbose=True)
        #import pdb; pdb.set_trace()
        entities = [
            _prefer_json_entity_location({
                'name': node.name,
                'summary': node.summary,
                'location': node.attributes.get('location', ''),
                'description': node.attributes.get('description', ''),
            })
            for node in nodes
        ]

        rerank_prompt = dedent("""\
            Task: "{task_description}"
            Entities: {entities}""").format(
            task_description=subtask_description,
            entities=entities,
        )
        _workflow_log(f"rerank_prompt: {rerank_prompt}", verbose=True)
        # response_iterator = await entity_reranker_agent.arun(
        #     rerank_prompt, stream=True, stream_intermediate_steps=True,
        # )
        # async for event in response_iterator:
        #     yield event

        # response = entity_reranker_agent.run_response
        # entity_name = response.content.strip()
        entity_name = nodes[0].name
        _workflow_log(f"entity_name: {entity_name}", verbose=True)
        entity = next(
            (e for e in entities if e['name'] == entity_name), None
        )
        if entity:
            entity = {
                'name': entity['name'],
                'summary': entity['summary'],
                'location': entity['location'],
                'description': entity['description']
            }
            navigation_prompt = dedent("""\
                Task: "{task_description}"
                Target: {entity}""").format(
                task_description=subtask_description,
                entity=entity,
            )
            #import pdb; pdb.set_trace()
            console = ctx.console
            # Get the live display instance from the console
            #live = console._live

            # Stop the live display temporarily so we can ask for user confirmation
            #live.stop()  # type: ignore

            # Ask for confirmation only when the user's navigation intent is ambiguous.
            if skip_confirm:
                print(f"用户已明确要求前往，跳过导航确认: {entity['name']}")
                tts_sound(tts_agent, f"好的，我们现在去{entity['name']}", "zh")
                tts_wait(tts_agent)
                message = "y"
            else:
                #tts_sound(tts_agent, f"{before_text}你是否想去往{entity['name']}", "zh")
                #tts_sound(tts_agent, f"{before_text}要不要我带你去{entity['name']}看看吧", "zh")
                guide_go_to_text = build_guide_go_to_text(entity['name'])
                tts_sound(tts_agent, guide_go_to_text, "zh")
                tts_wait(tts_agent)
                #message = (
                #    Prompt.ask("Do you want to go to the {}?".format(entity['name']), choices=["y", "n"], default="y")
                #    .strip()
                #    .lower()
                #)
                #live.start()
                message = audio_input_yes_or_no_ignore_echo(stt_agent, guide_go_to_text, entity['name'])
                #message = input("请输入 y/n 来开启或取消导航：")
                while message != "y" and message != "n":
                    #tts_sound(tts_agent, f"{before_text}抱歉，我不理解你的回答。你是否想去往{entity['name']}", "zh")
                    tts_fast(tts_agent, "sorry")
                    tts_sound(tts_agent, guide_go_to_text, "zh")
                    tts_wait(tts_agent)
                    message = audio_input_yes_or_no_ignore_echo(stt_agent, guide_go_to_text, entity['name'])

            #import pdb; pdb.set_trace()
            # If the user does not want to continue, raise a StopExecution exception
            if message != "y":
                #live.stop()
                # Ask for confirmation
                #message = (
                #    Prompt.ask("I cannot find the target in my memory. Do you want to go to the target by dynamic navigation?", choices=["y", "n"], default="y")
                #    .strip()
                #    .lower()
                #)
                chat_queue.put("不用了。", "用户")
                tts_fast(tts_agent, "cancel")
                #tts_sound(tts_agent, f"{before_text}那需要我动态寻找{entity['name']}吗", "zh")
                #message = audio_input_yes_or_no(stt_agent)
                message = "n"
                while message != "y" and message != "n":
                    tts_sound(tts_agent, f"{before_text}抱歉，我不理解你的回答。我不知道{entity['name']}在哪里，需要我动态寻找吗", "zh")
                    message = audio_input_yes_or_no(stt_agent)
                if message == "y":
                    navigation_prompt = subtask_description
                    #response = await navigation_tools.dynamic_navigation(navigation_prompt)
                    response = 'Dynamic navigation completed.'
                    tts_sound(tts_agent, f"{before_text}动态寻找已完成", "zh")
                    #live.start()
                else:
                    response = "Unable to reach the place the user wants to go!"
            else:
                entity_name = entity['name']
                set_current_entity_name(entity_name)
                #tts_sound(tts_agent, f"{before_text}好的，我即将前往{entity_name}", "zh")
                #tts_sound(tts_agent, f"{before_text}我已经知道了{entity_name}在哪里了，下面我带你去", "zh")
                #tts_sound(tts_agent, f"{before_text}好的，下面我带你去{entity_name}", "zh")
                tts_fast(tts_agent, "naviguide")
                _workflow_log(f"entity location: {entity['location']}", verbose=True)
                location_points = _extract_location_points(entity)
                if not location_points:
                    print(f"展点缺少可用导航点位: {entity}")
                    return "Unable to reach the place the user wants to go!"
                x, y, ox, oy, oz, ow = location_points[0]
                enable_navi = os.getenv("RABBITBOT_ENABLE_NAVI", "1").strip().lower() not in {"0", "false", "no", "off"}
                _workflow_log(f"workflow enable_navi: {enable_navi}", verbose=True)
                if enable_navi:
                    if _wait_manual_navigation_success(entity_name):
                        navi_status = NavigationStatus.SUCCEEDED
                    else:
                        # v1
                        #response = await navigation_tools.go_to(x, y, yaw)
                        # v2
                        navi_query = NavigationQuery()
                        await navi_tools.go_to_async(
                            x, y, ox, oy, oz, ow, navi_query,
                            waypoints=location_points if len(location_points) > 1 else None,
                        )
                        # v3
                        #await navigation_tools.go_to(x, y, ox, oy, oz, ow)

                        #navi_status = navi_query.get_status()
                        enable_chat = False
                        while await is_navigating(navi_tools):
                            if enable_chat:
                                #tts_sound(tts_agent, f"{before_text}现在你可以和我聊天哟", "zh")
                                tts_fast(tts_agent, "navichat")
                                #audio_input_text = audio_input_execute(stt_agent, "speech_to_text_async", timeout=30)
                                audio_input_text = await audio_input_execute_timeout_navi(stt_agent, 30, navi_tools)
                                if audio_input_text != "<REC_TIMEOUT>" and audio_input_text != "<NAVI_REACH>":
                                    #tts_sound(tts_agent, f"{before_text}我听到了，让我想一想", "zh")
                                    think_type = identify_think_type(audio_input_text)
                                    tts_fast(tts_agent, think_type)
                                    #await chat_execute(audio_input_text)
                                    await chat_loop_execute(audio_input_text, navi_tools)
                            #navi_status = navi_query.get_status()

                        navi_status = await navi_tools.go_to_status()
                else:
                    #time.sleep(10.0)
                    navi_status = NavigationStatus.SUCCEEDED
                if navi_status == NavigationStatus.SUCCEEDED and "礼品" not in entity['name']:
                    enable_intro_description = True
                    if enable_intro_description:
                        #tts_sound(tts_agent, f"{before_text}我已经到达了，一会再聊", "zh")
                        #tts_sound(tts_agent, f"{before_text}下面我为你介绍{entity_name}", "zh")
                        time.sleep(0.1)
                        #tts_index = tts_sound(tts_agent, f"{before_text}请往这边看", "zh")
                        time.sleep(0.5)
                        #tts_sound(tts_agent, f"{before_text}{entity['description']}", "zh")
                        #action_with_tts(ctx.robot, "右手摆动（先内向后向外）", tts_agent, tts_index)
                        #text = f"{before_text}{entity['description']}"
                        text = f"{entity['description']}"
                        interrupt_text = tts_long_text_with_stt_stop(tts_agent, text, stt_agent, ctx.robot, before_text)
                        if set_pending_user_text(interrupt_text):
                            response = f"Interrupted by user: {interrupt_text}"
                            return response
                        #time.sleep(4.0)
                        #await ctx.robot.do_arm_async("右手摆动（先内向后向外）")

                        #tts_sound(tts_agent, f"{before_text}我介绍完了", "zh")

                    #target_group_name = "教育场景"
                    target_group_name = "人形机器人科研场景"
                    enable_game_execute = True
                    if target_group_name in entity['name'] and enable_game_execute:
                        location_name = target_group_name
                        entity_lst = await ctx.memory.get_group_names(location_name)
                        summary_lst= await ctx.memory.get_group_summary(location_name)
                        #recommand_entity_lst = random.sample(entity_lst, 3)
                        recommand_entity_lst = random.sample(entity_lst, 2)
                        entity_prompt = build_stt_prompt_by_list(recommand_entity_lst)
                        #tts_sound(tts_agent, f"{before_text}除了我刚才的介绍，这里还有{entity_prompt}等具体板块，需要我为再做详细的介绍吗？", "zh")
                        #message = audio_input_yes_or_no(stt_agent)
                        message = "y"
                        while message != "y" and message != "n":
                            #tts_sound(tts_agent, f"{before_text}抱歉，我不理解你的回答。你是否想去往{entity['name']}", "zh")
                            tts_fast(tts_agent, "sorry")
                            tts_sound(tts_agent, f"{before_text}还需要我为您详细介绍这个地方吗？", "zh")
                            message = audio_input_yes_or_no(stt_agent)
                        if message == "y":
                            #tts_sound(tts_agent, f"{before_text}下面我和你玩个小游戏", "zh")
                            await game_execute(ctx, target_group_name)
                            await thank_chat_execute(ctx)
                            input("请按回车键带用户去礼品处")
                            tts_sound(tts_agent, f"{before_text}好啊，没问题，跟我来", "zh")

                    #tts_sound(tts_agent, f"{before_text}我可以带你继续参观，你有想去的地方吗？或者和我聊天也可以。", "zh")
                    #tts_sound(tts_agent, f"{before_text}我们继续吧", "zh")

                    response = 'Navigation to ({}, {}) successful.'.format(x, y)
                    await navi_tools.reset_go_to_status()
                elif navi_status == NavigationStatus.SUCCEEDED and "礼品" in entity['name']:
                    tts_sound(tts_agent, f"{before_text}我马上到达了，一会再聊", "zh")
                    #await grab_execute(ctx)
                    response = 'Navigation to ({}, {}) successful.'.format(x, y)
                    await navi_tools.reset_go_to_status()
                else:
                    tts_sound(tts_agent, f"{before_text}很抱歉，我无法到达目的地", "zh")
                    response = 'Navigation to ({}, {}) failed.'.format(x, y)
            _workflow_log(f"response: {response}", verbose=True)
        else:
            console = ctx.console
            # Get the live display instance from the console
            #live = console._live

            # Stop the live display temporarily so we can ask for user confirmation
            #live.stop()  # type: ignore

            # Ask for confirmation
            #message = (
            #    Prompt.ask("Do you want to go to the target by dynamic navigation?", choices=["y", "n"], default="y")
            #    .strip()
            #    .lower()
            #)
            #live.start()
            #tts_sound(tts_agent, f"{before_text}你需要我去动态寻找吗", "zh")
            #message = audio_input_yes_or_no(stt_agent)
            message = "n"
            while message != "y" and message != "n":
                tts_sound(tts_agent, f"{before_text}抱歉，我不理解你的回答。你需要我去动态寻找吗", "zh")
                message = audio_input_yes_or_no(stt_agent)

            # If the user does not want to continue, raise a StopExecution exception
            if message != "y":
                response = "Unable to reach the place the user wants to go!"
            else:
                navigation_prompt = task.subtask_description
                #response = await navigation_tools.dynamic_navigation(navigation_prompt)
                response = 'Dynamic navigation completed.'
                tts_sound(tts_agent, f"{before_text}动态寻找已完成", "zh")
        return response

    async def navi_executor(
        step_input: StepInput,
    ) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        #task: DelegationTaskModel = step_input.previous_step_content
        WorkflowTimePoints.PLAN_END = time.time()
        plan_time = WorkflowTimePoints.PLAN_END - WorkflowTimePoints.PLAN_START
        _workflow_log(f"chat_executor: plan_time: {plan_time:.3f}", verbose=True)

        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"previous_steps: {previous_steps}", verbose=True)
        text_lst = previous_steps.split("===")
        assert text_lst[1].replace(" ", "") == "audio_input_step"
        text = text_lst[2].replace("\n", "")
        #subtask_description = task.subtask_description
        subtask_description = text

        response = await navi_execute(subtask_description)

        yield StepOutput(
            content=response,
        )

    async def navi_check_execute(input_text):
        WorkflowTimePoints.PLAN_END = time.time()
        plan_time = WorkflowTimePoints.PLAN_END - WorkflowTimePoints.PLAN_START
        _workflow_log(f"chat_executor: plan_time: {plan_time:.3f}", verbose=True)

        global last_chat_text
        _workflow_log(f"last_chat_text: {last_chat_text}", verbose=True)
        #print("input_text:", "机器人："  + last_chat_text + "用户："  + input_text)
        #input_text_with_chat = "机器人："  + last_chat_text + "用户："  + input_text
        history_text = chat_queue.build_history(max_count=4)
        input_text_with_chat = history_text
        _workflow_log(f"input_text_with_chat: {input_text_with_chat}", verbose=True)
        navi_check_span = _profile_start("navi_check")
        run_response = navi_check_agent.run(input_text_with_chat, session_id=str(NAVI_CHECK_SESSION_ID))
        _profile_end(navi_check_span)
        out_text = run_response.content
        _workflow_log(f"out_text: {out_text}", verbose=True)
        out_text = out_text.split("\n")[0]
        WorkflowTimePoints.NAVI_CHECK_END = time.time()
        navi_check_time = WorkflowTimePoints.NAVI_CHECK_END - WorkflowTimePoints.NAVI_CHECK_START
        _workflow_log(f"navi_check_execute: navi_check_time: {navi_check_time:.3f}", verbose=True)

        num_entity = 1
        recommand_entity_lst = random.sample(ctx.entity_lst, num_entity)

        if out_text[0] == "A":
            try:
                if len(out_text) > 1:
                    out_text = out_text[1:]
                    if out_text[0].isdigit():
                        entity_idx = int(out_text)
                        # 添加边界检查
                        if entity_idx < len(ctx.entity_lst):
                            out_text = ctx.entity_lst[entity_idx]
                            # 注意：不在这里放入队列，navi_execute 会处理确认询问
                        else:
                            out_text = f"{before_text}抱歉，我不太清楚你想去的地方，我们这里有 {recommand_entity_lst} 等板块可以参观"
                else:
                    out_text = f"{before_text}抱歉，我不太清楚你想去的地方，我们这里有 {recommand_entity_lst} 等板块可以参观"
            except (ValueError, IndexError) as exc:
                out_text = f"{before_text}抱歉，我不太清楚你想去的地方，我们这里有 {recommand_entity_lst} 等板块可以参观"
        elif out_text[0].isdigit():
            entity_idx = int(out_text)
            if entity_idx < len(ctx.entity_lst):
                out_text = ctx.entity_lst[entity_idx]
            else:
                out_text = f"{before_text}抱歉，我不太清楚你想去的地方，我们这里有 {recommand_entity_lst} 等板块可以参观"
        elif out_text[0] == "B":
            out_text = f"{before_text}抱歉，我不太清楚你想去的地方，我们这里有 {recommand_entity_lst} 等板块可以参观"
            chat_queue.put(out_text, "机器人")
        elif out_text[0] == "D":
            out_text = f"{before_text}请告诉我你想去什么地方？这里有 {recommand_entity_lst} 等板块可以参观"
            chat_queue.put(out_text, "机器人")
        elif out_text[0] == "C":
            n = len(ctx.entity_lst)
            rand_n = random.randint(0, n-1)
            out_text = ctx.entity_lst[rand_n]
            # 注意：不在这里放入队列，navi_execute 会处理确认询问
        _workflow_log(f"out_text: {out_text}", verbose=True)

        if is_next_board_request(input_text):
            next_entity_name = get_next_entity_name()
            if next_entity_name is not None:
                _workflow_log(f"next board request resolved to: {next_entity_name}", verbose=True)
                out_text = next_entity_name
                response = await navi_execute(out_text, skip_confirm=True)
                return response
            out_text = f"{before_text}已经是最后一个板块了"
            tts_sound(tts_agent, f"{out_text}", "zh")
            return out_text

        fuzzy_entity = None
        fuzzy_score = 0.0
        if out_text not in ctx.entity_lst and is_direct_navigation_request(input_text):
            fuzzy_entity, fuzzy_score = resolve_navigation_entity_by_fuzzy(input_text, ctx.entity_lst)
            if fuzzy_entity is not None:
                _workflow_log(f"导航目标模糊匹配: input={input_text}, entity={fuzzy_entity}, score={fuzzy_score:.3f}", verbose=True)
                out_text = fuzzy_entity

        if out_text in ctx.entity_lst:
            response = await navi_execute(out_text, skip_confirm=is_direct_navigation_request(input_text))
        else:
            if is_direct_navigation_request(input_text):
                out_text = f"{before_text}抱歉，我没听清你想去哪里，可以再说一遍吗？"
            tts_sound(tts_agent, f"{out_text}", "zh")
            response = out_text

        return response

    async def navi_check_executor(step_input):
        WorkflowTimePoints.NAVI_CHECK_START = time.time()
        previous_steps = step_input.get_all_previous_content()
        _workflow_log(f"previous_steps: {previous_steps}", verbose=True)
        text_lst = previous_steps.split("===")
        assert text_lst[1].replace(" ", "") == "audio_input_step"
        text = text_lst[2].replace("\n", "")

        #think_type = identify_think_type(text)
        #tts_fast(tts_agent, think_type)
        out_text = await navi_check_execute(text)

        return StepOutput(content=f"{out_text}")

    async def game_execute(ctx: Any, location_name: str, entity_name = None):
        # TODO: Navigate to the game location
        entity_lst = await ctx.memory.get_group_names(location_name)
        summary_lst= await ctx.memory.get_group_summary(location_name)
        entity_prompt = build_stt_prompt_by_list(entity_lst)

        # TODO: while循环等待用户提问
        tts_index = -1
        while True:
            # TODO: 语音等待用户提问
            #tts_sound(tts_agent, f"{before_text}请告诉我你想要找什么", "zh")
            if tts_index >= 0:
                wait_with_tts(tts_agent, tts_index)
            if entity_name is None:
                tts_fast(tts_agent, "introguide")
                tts_sound(tts_agent, f"{before_text}您还需要我介绍什么吗？", "zh")
                audio_input_text = audio_input_execute_timeout(stt_agent, 30, entity_prompt)
            else:
                audio_input_text = entity_name
            print(audio_input_text)
            if audio_input_text == "<REC_TIMEOUT>":
                continue
            flag = yes_or_no_quick_match(audio_input_text)
            if flag == "n":
                break
            # TODO: 如果用户结束游戏，则退出循环
            if "结束" in audio_input_text or "没有" in audio_input_text:
                break
            audio_input_text = audio_input_text.replace("原", "圆")
            print(audio_input_text)

            # 异步调用语音：例如：“我听到了，让我来找一找”、“我听到了，让我来想一想”
            answer_templates = [
                f"{before_text}好嘞，我听到了，让我来介绍一下",
                f"{before_text}好呀，请往这里看，我来给你讲讲",
                f"{before_text}明白了，我来给你介绍这个",
                f"{before_text}没问题，我来详细介绍一下",
                f"{before_text}明白，我来给你讲解一下这个"
            ]
            answer_template = np.random.choice(answer_templates)
            tts_sound(tts_agent, f"{answer_template}", "zh")

            # 添加查询检查
            search_response = search_check_agent.run(audio_input_text)

            search_response_text = search_response.content
            print(f"Agent判断的名称为：{search_response_text}")

            # 根据用户提问调用detect_tool.detect_location，并返回结果
            # audio_input_text = ctx.vlm_openai.prepare_correction_text_message_for_vllm(audio_input_text)
            # 异步执行memory查询
            memory_query_task = asyncio.create_task(ctx.memory.query(query=search_response_text, group_name=location_name, limit=1))
            # 在do_finger之前同步等待memory查询结果
            nodes = await memory_query_task
            memory_node = nodes[0]
            if memory_node.name == '异常结点':
                tts_index = tts_sound(tts_agent, f"{before_text}抱歉，我无法找到你想要找的物品", "zh")
                continue

            #{round(location[0], 1)}, {round(location[1], 1)}, {round(location[2], 1)}
            #tts_index = tts_sound(tts_agent, f"{before_text}太好了，我找到了！下面我给你介绍{memory_node.name}", "zh")
            description = memory_node.attributes.get('description', '')
            #tts_sound(tts_agent, f"找到了哦，我指给你看，{description}", "zh")
            interrupt_text = tts_long_text_with_stt_stop(tts_agent, description, stt_agent, ctx.robot, before_text)
            if set_pending_user_text(interrupt_text):
                return
            #tts_index = tts_sound(tts_agent, f"{before_text}我介绍完了", "zh")

            summary = memory_node.summary
            print("summary", summary)
            location = detect_tools.detect_location({'task': summary})
            # 判断是否没有识别到或者识别到多个物品
            if location[0] == 0 or location[1] == 0 or location[2] == 0:
                tts_index = tts_sound(tts_agent, f"{before_text}抱歉，我无法找到你想要找的物品", "zh")
                continue
            elif location[0] == -1 or location[1] == -1 or location[2] == -1:
                tts_index = tts_sound(tts_agent, f"{before_text}抱歉，我找到了多个相似物品，可以再描述一下吗", "zh")
                continue
            # TODO: 根据location[0], location[1], location[2]，调用ctx.robot.do_finger
            ctx.robot.do_finger(location[0], location[1], location[2])
            do_finger_check = False
            if do_finger_check:
                time.sleep(0.5)
                finger_status = await ctx.robot.do_finger_status_async()
                print(f"finger_status: {finger_status}")
                while finger_status == -1:
                    time.sleep(0.5)
                    finger_status = await ctx.robot.do_finger_status_async()
                    print(f"finger_status: {finger_status}")
                if finger_status == 1:
                    tts_index = tts_sound(tts_agent, f"{before_text}太好了，逆解成功了！", "zh")
                elif finger_status == 0:
                    tts_index = tts_sound(tts_agent, f"{before_text}糟糕，逆解失败了。", "zh")

            if entity_name is not None:
                break

            #input("请按回车键描述衣服")
            #time.sleep(1)
            #tts_index = tts_sound(tts_agent, f"{before_text}您穿的是青色衣服，显得很有活力！", "zh")

            #message = input("请按 y/n 开启或退出下一轮识别：")
            message = "y"
            if message == "y":
                break

    async def game_executor(step_input: StepInput) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        await game_execute(ctx, "人形机器人科研场景")
        response = 'Game completed.'
        yield StepOutput(
            content=response,
        )

    navigation_check_step = Step(
        name='navigation_check_step',
        description='Check navigation goal.',
        executor=navi_check_executor,
    )

    navigation_check_step = Step(
        name='navigation_check_step',
        description='Check navigation goal.',
        executor=navi_check_executor,
    )

    async def grab_execute(ctx: Any, yaw=0, pitch=25):
        while True:
            # tts_fast(tts_agent, "introguide")
            #tts_sound(tts_agent, f"{before_text}下面我来展示抓篮子功能，我准备好了！请按回车键继续", "zh")
            #audio_input_text = audio_input_execute_timeout(stt_agent, 120)
            await ctx.robot.do_head_async(yaw=0, pitch=0)
            audio_input_text = input("按回车键继续")
            print(audio_input_text)
            if audio_input_text == "<REC_TIMEOUT>":
                return
            flag = yes_or_no_quick_match(audio_input_text)
            if flag == "n":
                return
            if "结束" in audio_input_text or "没有" in audio_input_text:
                break
            # tts_sound(tts_agent, f"{before_text}有的，请您挑选", "zh")
            await ctx.robot.do_head_async(yaw=0, pitch=25)
            # time.sleep(5)
            await asyncio.sleep(2)
            locations = detect_tools.detect_key_point_pixel({'task': ''})
            #tts_sound(tts_agent, f"{before_text}找到了，让我把他拿起来", "zh")

            await ctx.robot.do_grab_async(locations[0], locations[1], locations[2])
            # Wait and monitor location changes for 5 seconds
            start_time = time.time()
            old_location = locations
            threshold = 0.2  # Distance threshold for location change detection

            catch_status = await ctx.robot.do_grab_status_async()
            while time.time() - start_time < 30 and catch_status != 1:
                await asyncio.sleep(1)

                new_location = detect_tools.detect_key_point_pixel({'task': ''})
                print(time.time(), new_location[1], old_location[1])
                # Calculate distance between old and new locations
                distance = abs(new_location[1] - old_location[1])
                print(f"distance: {distance}, threshold: {threshold}, new_location: {new_location}, old_location: {old_location}")
                if distance > threshold and new_location[2] - old_location[2] < 0.2 and new_location[0] - old_location[0] > -0.2:
                    print(f"Location changed significantly (distance: {distance}), re-grabbing...")
                    #tts_sound(tts_agent, f"{before_text}唉,有人在捣乱，让我重新定位并抓取一下", "zh")
                    tts_sound(tts_agent, f"{before_text}唉，有人在捣乱！", "zh")
                    # TODO: 发送停止指令
                    await ctx.robot.do_grab_cancel_async()
                    await asyncio.sleep(4)

                    new_location = detect_tools.detect_key_point_pixel({'task': ''})
                    await ctx.robot.do_grab_async(new_location[0], new_location[1], new_location[2])
                    old_location = new_location
                    await asyncio.sleep(4)
                    break
                catch_status = await ctx.robot.do_grab_status_async()
            # tts_sound(tts_agent, f"{before_text}我要开抓", "zh")
            tts_sound(tts_agent, f"{before_text}这是给您的小礼物 ，欢迎您再次来智元参观", "zh")
            await asyncio.sleep(1)
            await ctx.robot.do_head_async(yaw=0, pitch=0)
            await asyncio.sleep(1)
            await ctx.robot.do_head_async(yaw=30, pitch=0)
            await asyncio.sleep(3)
            await ctx.robot.do_head_async(yaw=0, pitch=0)
            input("请按回车键开启下一轮抓取测试")

    async def grab_executor(step_input: StepInput) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        await grab_execute(ctx)
        response = 'Grab completed.'
        yield StepOutput(
            content=response,
        )

    grab_step = Step(
        name='grab_step',
        description='Grab the object.',
        executor=grab_executor,
    )

    async def handshake_execute(ctx: Any, yaw=0, pitch=25):
        while True:
            # tts_fast(tts_agent, "introguide")
            tts_sound(tts_agent, f"{before_text}下面我来展示握手功能，我准备好了！我等你的命令", "zh")
            audio_input_text = audio_input_execute_timeout(stt_agent, 120)
            print(audio_input_text)
            if audio_input_text == "<REC_TIMEOUT>":
                return
            flag = yes_or_no_quick_match(audio_input_text)
            if flag == "n":
                return
            if "结束" in audio_input_text or "没有" in audio_input_text:
                break
            tts_sound(tts_agent, f"{before_text}好的", "zh")
            # await ctx.robot.do_head_async(yaw=yaw, pitch=pitch)
            # time.sleep(5)
            locations = detect_tools.detect_hand_location()
            #tts_sound(tts_agent, f"{before_text}找到了，让我把他拿起来", "zh")

            if locations[0] == 0 or locations[1] == 0 or locations[2] == 0:
                tts_index = tts_sound(tts_agent, f"{before_text}抱歉，我找不到你的手呢", "zh")
                continue

            await ctx.robot.do_handshake_async(locations[0], locations[1], locations[2] + 0.1)
            input("请按回车键开启下一轮握手测试")

    async def handshake_execute_v2(ctx: Any, yaw=0, pitch=25):
        # await ctx.robot.do_head_async(yaw=yaw, pitch=pitch)
        # time.sleep(5)
        locations = detect_tools.detect_hand_location()
        #tts_sound(tts_agent, f"{before_text}找到了，让我把他拿起来", "zh")

        if locations[0] == 0 or locations[1] == 0 or locations[2] == 0:
            tts_index = tts_sound(tts_agent, f"{before_text}抱歉，我找不到你的手呢", "zh")
        else:
            await ctx.robot.do_handshake_async(locations[0], locations[1], locations[2] + 0.1)

    async def handshake_executor(step_input: StepInput) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        await handshake_execute(ctx)
        response = 'Handshake completed.'
        yield StepOutput(
            content=response,
        )

    handshake_step = Step(
        name='handshake_step',
        description='Handshake with man.',
        executor=handshake_executor,
    )

    navigation_step = Step(
        name='navigation_step',
        description='Use static or dynamic navigation to complete the task.',
        executor=navi_executor,
    )

    game_step = Step(
        name='game_step',
        description='Play a game with the user.',
        executor=game_executor,
    )

    chat_step = Step(
        name='chat_step',
        description='Chat with the user.',
        executor=chat_executor,
    )

    vln_step = Step(
        name='vln_step',
        description='Navigation with VLN.',
        executor=vln_executor,
    )

    view_step = Step(
        name='view_step',
        description='View.',
        executor=view_executor,
    )

    move_step = Step(
        name='move_step',
        description='Move.',
        executor=move_executor,
    )

    sound_step = Step(
        name='sound_step',
        description='Sound.',
        executor=sound_executor,
    )

    unknown_step = Step(
        name='unknown_step',
        description='Unkown what to do.',
        executor=unknown_executor,
    )

    async def thank_chat_execute(ctx):
        input("请按回车键夸奖用户")
        await _do_arm_async_timed(ctx.robot, "比耶")
        tts_sound(tts_agent, f"{before_text}感谢你的夸奖！很高兴能为你导览。", "zh")
        tts_sound(tts_agent, f"{before_text}您今天的青色衣服也太帅了！", "zh")

    async def thank_chat_executor(step_input: StepInput) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        await thank_chat_execute(ctx)
        response = 'Chat completed.'
        yield StepOutput(
            content=response,
        )

    thank_chat_step = Step(
        name='thank_chat_step',
        description='Chat with the user.',
        executor=thank_chat_executor,
    )

    def simple_delegate_task(step_input: StepInput) -> List[Step]:
        task: SimpleDelegationTaskModel = step_input.previous_step_content

        if task.t == 'N':
            #return [navigation_step]
            return [navigation_check_step]
        # elif task.t == 'vision':
        #     return [vision_step]
        elif task.t == 'C':
            return [chat_step]
        elif task.t == 'V':
            return [view_step]
        elif task.t == 'G':
            return [game_step]
        elif task.t == 'O':
            return [unknown_step]

    def delegate_task(step_input: StepInput) -> List[Step]:
        task: DelegationTaskModel = step_input.previous_step_content

        if task.agent_name == 'navigation':
            return [navigation_step]
        # elif task.agent_name == 'vision':
        #     return [vision_step]
        elif task.agent_name == 'chat':
            return [chat_step]
        elif task.agent_name == 'game':
            return [game_step]

    router_step = Router(
        name='task_router',
        selector=simple_delegate_task,
        choices=[navigation_step, chat_step, view_step, game_step],
        description="Delegate the task to the appropriate agent based on the task description.",
    )

    async def task_completion_check(
        step_input: StepInput,
    ) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
        completion_span = _profile_start("completion_check")
        original_task = step_input.message or ''
        previous_steps = step_input.get_all_previous_content()

        if guide_start_by_voice_enabled() and not guide_started():
            result = StepOutput(content=CompletionCheckModel(task_completed=False))
            _profile_end(completion_span, skipped=True, reason="pre_guide_qa")
            return result
        if getattr(ctx, "post_docx_chat_mode", False):
            result = StepOutput(content=CompletionCheckModel(task_completed=False))
            _profile_end(completion_span, skipped=True)
            return result
        if SCRIPTED_TOUR_RETURN_TO_START in previous_steps:
            result = StepOutput(content=CompletionCheckModel(task_completed=True))
            _profile_summary_print(reason="return_to_start_requested")
            _profile_end(completion_span, skipped=True, task_completed=True, reason="return_to_start_requested")
            return result
        if SCRIPTED_TOUR_FINISHED in previous_steps:
            result = StepOutput(content=CompletionCheckModel(task_completed=True))
            _profile_summary_print(reason="docx_finished_loop_breaker")
            _profile_end(completion_span, skipped=True, task_completed=True)
            return result
        if SCRIPTED_TOUR_STEP_DONE in previous_steps:
            result = StepOutput(content=CompletionCheckModel(task_completed=False))
            _profile_end(completion_span, skipped=True)
            return result

        prompt = dedent("""\
            Task: "{task_description}"
            Previous Steps: {previous_steps}""").format(
            task_description=original_task,
            previous_steps=previous_steps,
        )

        result = await task_completion_check_agent.arun(
            prompt, stream=True, stream_intermediate_steps=True,
        )
        _profile_end(completion_span)
        return result

    def loop_breaker(outputs: List[StepOutput]) -> bool:
        if not outputs:
            return False

        for output in outputs:
            if isinstance(output.content, CompletionCheckModel):
                if output.content.task_completed:
                    _profile_summary_print(reason="loop_breaker_completed")
                    return True

        return False

    return Workflow(
        name='RabbitBot Main Workflow',
        description='Workflow for general tasks',
        steps=[
            Loop(
                name='Task Loop',
                steps=[
                    #vln_step,
                    #game_step,
                    #grab_step,
                    #view_step,
                    #handshake_step,
                    #move_step,
                    #sound_step,
                    #thank_chat_step,
                    audio_input_step,
                    #plan_step,
                    #router_step,
                    plan_step_v2,
                    task_completion_check,
                ],
                max_iterations=100,
                end_condition=loop_breaker,
            )
        ],
    )

    # - action: If the prompt mentions "action", to perform an action such as wavehands, greet, ask a question, etc.
    # If the task is to perform an action such as wavehands, greet, ask a question, etc, you should output "action".
    # action_chooser_agent = Agent(
    #     name='Action Chooser Agent',
    #     role='Action chooser',
    #     instructions=dedent("""\
    #         You are an action chooser agent.
    #         Given the action task, you must choose whether to use action such as wavehands, greet to complete the task."""),
    #     response_model=ActionModel,
    #     model=model,
    # )

    # async def action_executor(
    #     step_input: StepInput,
    # ) -> AsyncIterator[Union[WorkflowRunResponseEvent, StepOutput]]:
    #     task: DelegationTaskModel = step_input.previous_step_content
    #     await action_chooser_agent.arun(task.subtask_description)
    #     response = action_chooser_agent.run_response
    #     choice: ActionModel = action_chooser_agent.run_response.content
    #     print(choice.choice)
    #     if choice.choice == 'wavehands':
    #         pass
    #         return StepOutput(
    #             content=choice.choice,
    #             response=response,
    #         )
    #     elif choice.choice == 'greet':
    #         pass
    #         return StepOutput(
    #             content=choice.choice,
    #             response=response,
    #         )

    # action_step = Step(
    #     name='action_step',
    #     description='Use action executor to complete the task.',
    #     executor=action_executor,
    # )

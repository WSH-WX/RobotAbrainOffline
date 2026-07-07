"""机械臂动作与灵巧手手势编排（收手时序、并发/前后置释放）。从 workflow.py 拆出，行为不变。"""

import os
import time
import asyncio
import threading
import subprocess
from .workflow_config import _env_float
from .workflow_profiling import _workflow_action_log, _profile_start, _profile_end


ARM_ACTIONS_NEED_RELEASE_BEFORE_SPEECH = {"shake_hand", "face_wave", "high_wave", "hug"}
ARM_ACTIONS_NEED_RELEASE_AFTER_SPEECH = {"right_hand_up", "hands_up"}
ARM_RELEASE_ACTION = "release"
ARM_BEFORE_RELEASE_DELAYS = {
    "shake_hand": 0.0,
}
ARM_BEFORE_RELEASE_DELAY_ENV = {
    "shake_hand": "RABBITBOT_HANDSHAKE_BEFORE_RELEASE_DELAY",
}
HAND_GESTURE_COMMANDS = {}
def _get_hand_gesture_command(action_name):
    if not action_name:
        return ""
    env_name = f"RABBITBOT_HAND_GESTURE_{action_name.upper()}".replace("-", "_")
    command = os.getenv(env_name, HAND_GESTURE_COMMANDS.get(action_name, ""))
    return command.strip()
def _publish_hand_gesture_for_arm_action(action_name):
    command = _get_hand_gesture_command(action_name)
    if not command:
        _workflow_action_log("hand_gesture_skip", action_name, reason="未配置灵巧手动作")
        return

    topic = os.getenv("RABBITBOT_HAND_GESTURE_TOPIC", "/gesture_cmd")
    timeout = _env_float("RABBITBOT_HAND_GESTURE_PUB_TIMEOUT", 3.0)
    message = f"{{data: '{command}'}}"
    start_time = time.perf_counter()
    _workflow_action_log("hand_gesture_publish_start", action_name, topic=topic, data=command, timeout=timeout)
    try:
        subprocess.run(
            ["ros2", "topic", "pub", "--once", topic, "std_msgs/msg/String", message],
            check=True,
            timeout=timeout,
        )
        elapsed_seconds = time.perf_counter() - start_time
        _workflow_action_log("hand_gesture_publish_done", action_name, topic=topic, data=command, elapsed=f"{elapsed_seconds:.3f}s")
        print(f"已发布灵巧手动作: topic={topic}, data={command}")
    except FileNotFoundError as exc:
        elapsed_seconds = time.perf_counter() - start_time
        _workflow_action_log("hand_gesture_publish_error", action_name, topic=topic, data=command, elapsed=f"{elapsed_seconds:.3f}s", error=exc)
        print("发布灵巧手动作失败: 未找到 ros2 命令")
    except subprocess.TimeoutExpired:
        elapsed_seconds = time.perf_counter() - start_time
        _workflow_action_log("hand_gesture_publish_timeout", action_name, topic=topic, data=command, elapsed=f"{elapsed_seconds:.3f}s", timeout=timeout)
        print(f"发布灵巧手动作超时: topic={topic}, data={command}, timeout={timeout}")
    except subprocess.CalledProcessError as exc:
        elapsed_seconds = time.perf_counter() - start_time
        _workflow_action_log("hand_gesture_publish_error", action_name, topic=topic, data=command, elapsed=f"{elapsed_seconds:.3f}s", returncode=exc.returncode)
        print(f"发布灵巧手动作失败: topic={topic}, data={command}, returncode={exc.returncode}")
def _format_arm_action_success(result):
    if isinstance(result, dict):
        return result.get("success", "未知")
    if result is None:
        return "无返回"
    return "未知"
def _log_arm_action_latency(action_name, elapsed_seconds, result=None, error=None, call_type="async"):
    if error is not None:
        _workflow_action_log(
            "workflow_do_arm_result",
            action_name,
            success="异常",
            elapsed=f"{elapsed_seconds:.3f}s",
            mode=call_type,
            error=error,
        )
        print(
            f"手臂动作body回执耗时: action={action_name}, success=异常, "
            f"elapsed={elapsed_seconds:.3f}s, mode={call_type}, error={error}"
        )
        return
    success = _format_arm_action_success(result)
    _workflow_action_log(
        "workflow_do_arm_result",
        action_name,
        success=success,
        elapsed=f"{elapsed_seconds:.3f}s",
        mode=call_type,
    )
    print(
        f"手臂动作body回执耗时: action={action_name}, success={success}, "
        f"elapsed={elapsed_seconds:.3f}s, mode={call_type}"
    )
async def _do_arm_async_timed(robot, action_name):
    start_time = time.perf_counter()
    span_token = _profile_start("arm_action", action=action_name, mode="async")
    _workflow_action_log("workflow_do_arm_async_start", action_name)
    try:
        result = await robot.do_arm_async(action_name)
    except Exception as exc:
        elapsed_seconds = time.perf_counter() - start_time
        _log_arm_action_latency(action_name, elapsed_seconds, error=exc, call_type="async")
        _profile_end(span_token, action=action_name, mode="async", success=False, error=exc)
        raise
    elapsed_seconds = time.perf_counter() - start_time
    success = _format_arm_action_success(result)
    _log_arm_action_latency(action_name, elapsed_seconds, result=result, call_type="async")
    _profile_end(span_token, action=action_name, mode="async", success=success)
    return result
async def _send_release_arm(robot):
    span_token = _profile_start("release_arm", action=ARM_RELEASE_ACTION)
    _workflow_action_log("workflow_release_start", ARM_RELEASE_ACTION)
    release_result = await _do_arm_async_timed(robot, ARM_RELEASE_ACTION)
    if isinstance(release_result, dict) and not release_result.get("success", True):
        print(f"收回动作回执失败: action={ARM_RELEASE_ACTION}, result={release_result}")
    release_wait_seconds = _env_float("RABBITBOT_ARM_RELEASE_WAIT_SECONDS", 0.2)
    if release_wait_seconds > 0:
        _workflow_action_log("workflow_release_wait_start", ARM_RELEASE_ACTION, wait=f"{release_wait_seconds:.3f}s")
        await asyncio.sleep(release_wait_seconds)
        _workflow_action_log("workflow_release_wait_done", ARM_RELEASE_ACTION, wait=f"{release_wait_seconds:.3f}s")
    success = _format_arm_action_success(release_result)
    _profile_end(span_token, action=ARM_RELEASE_ACTION, success=success)
def _send_release_arm_sync(robot):
    span_token = _profile_start("release_arm", action=ARM_RELEASE_ACTION, mode="thread")
    _workflow_action_log("workflow_release_thread_start", ARM_RELEASE_ACTION)
    try:
        release_result = _do_arm_sync(robot, ARM_RELEASE_ACTION)
    except Exception as exc:
        _workflow_action_log("workflow_release_thread_error", ARM_RELEASE_ACTION, error=exc)
        _profile_end(span_token, action=ARM_RELEASE_ACTION, mode="thread", success=False, error=exc)
        return
    if isinstance(release_result, dict) and not release_result.get("success", True):
        print(f"收回动作回执失败: action={ARM_RELEASE_ACTION}, result={release_result}")
    release_wait_seconds = _env_float("RABBITBOT_ARM_RELEASE_WAIT_SECONDS", 0.2)
    if release_wait_seconds > 0:
        _workflow_action_log("workflow_release_thread_wait_start", ARM_RELEASE_ACTION, wait=f"{release_wait_seconds:.3f}s")
        time.sleep(release_wait_seconds)
        _workflow_action_log("workflow_release_thread_wait_done", ARM_RELEASE_ACTION, wait=f"{release_wait_seconds:.3f}s")
    success = _format_arm_action_success(release_result)
    _profile_end(span_token, action=ARM_RELEASE_ACTION, mode="thread", success=success)
async def _do_arm_before_speech(robot, action_name):
    _workflow_action_log("workflow_arm_before_speech_start", action_name)
    _publish_hand_gesture_for_arm_action(action_name)
    action_result = await _do_arm_async_timed(robot, action_name)
    if isinstance(action_result, dict) and not action_result.get("success", True):
        print(f"动作回执失败: action={action_name}, result={action_result}")
    if action_name not in ARM_ACTIONS_NEED_RELEASE_BEFORE_SPEECH:
        return

    default_before_release_delay = ARM_BEFORE_RELEASE_DELAYS.get(
        action_name,
        _env_float("RABBITBOT_ARM_BEFORE_RELEASE_DELAY", 0.0),
    )
    before_release_delay = _env_float(
        ARM_BEFORE_RELEASE_DELAY_ENV.get(action_name, "RABBITBOT_ARM_BEFORE_RELEASE_DELAY"),
        default_before_release_delay,
    )
    if before_release_delay > 0:
        _workflow_action_log("workflow_before_release_wait_start", action_name, wait=f"{before_release_delay:.3f}s")
        await asyncio.sleep(before_release_delay)
        _workflow_action_log("workflow_before_release_wait_done", action_name, wait=f"{before_release_delay:.3f}s")
    await _send_release_arm(robot)
def _do_arm_sync(robot, action_name):
    do_arm = getattr(robot, "do_arm", None)
    if callable(do_arm):
        start_time = time.perf_counter()
        span_token = _profile_start("arm_action", action=action_name, mode="sync")
        _workflow_action_log("workflow_do_arm_sync_start", action_name)
        try:
            result = do_arm(action_name)
        except Exception as exc:
            elapsed_seconds = time.perf_counter() - start_time
            _log_arm_action_latency(action_name, elapsed_seconds, error=exc, call_type="sync")
            _profile_end(span_token, action=action_name, mode="sync", success=False, error=exc)
            raise
        elapsed_seconds = time.perf_counter() - start_time
        success = _format_arm_action_success(result)
        _log_arm_action_latency(action_name, elapsed_seconds, result=result, call_type="sync")
        _profile_end(span_token, action=action_name, mode="sync", success=success)
        return result
    raise RuntimeError("robot 不支持同步 do_arm 调用")
async def _do_arm_during_speech(robot, action_name, speech_func, wait_action_before_return=True):
    action_thread = None
    action_result = None
    action_error = None

    def run_action():
        nonlocal action_result, action_error
        try:
            _workflow_action_log("workflow_concurrent_action_thread_start", action_name)
            _publish_hand_gesture_for_arm_action(action_name)
            action_result = _do_arm_sync(robot, action_name)
            _workflow_action_log("workflow_concurrent_action_thread_done", action_name)
        except Exception as exc:
            action_error = exc

    async def finish_action_after_speech():
        _workflow_action_log("workflow_concurrent_action_join_start", action_name)
        await asyncio.to_thread(action_thread.join)
        _workflow_action_log("workflow_concurrent_action_join_done", action_name)
        if action_error is not None:
            print(f"动作执行异常: action={action_name}, error={action_error}")
        else:
            if isinstance(action_result, dict) and not action_result.get("success", True):
                print(f"动作回执失败: action={action_name}, result={action_result}")

        await _release_arm_after_concurrent_speech(robot, action_name)

    def finish_action_after_speech_in_thread():
        _workflow_action_log("workflow_concurrent_action_join_thread_start", action_name)
        action_thread.join()
        _workflow_action_log("workflow_concurrent_action_join_thread_done", action_name)
        if action_error is not None:
            print(f"动作执行异常: action={action_name}, error={action_error}")
        else:
            if isinstance(action_result, dict) and not action_result.get("success", True):
                print(f"动作回执失败: action={action_name}, result={action_result}")

        if action_name not in ARM_ACTIONS_NEED_RELEASE_BEFORE_SPEECH | ARM_ACTIONS_NEED_RELEASE_AFTER_SPEECH:
            return
        release_delay = _env_float("RABBITBOT_ARM_CONCURRENT_RELEASE_DELAY", 0.0)
        if release_delay > 0:
            _workflow_action_log("workflow_concurrent_release_thread_wait_start", action_name, wait=f"{release_delay:.3f}s")
            time.sleep(release_delay)
            _workflow_action_log("workflow_concurrent_release_thread_wait_done", action_name, wait=f"{release_delay:.3f}s")
        _send_release_arm_sync(robot)

    if action_name:
        _workflow_action_log("workflow_concurrent_action_thread_create", action_name)
        action_thread = threading.Thread(target=run_action, daemon=True)
        action_thread.start()

    _workflow_action_log("workflow_concurrent_speech_start", action_name)
    speech_result = speech_func()
    _workflow_action_log("workflow_concurrent_speech_done", action_name)

    if action_thread is None:
        return speech_result

    if wait_action_before_return:
        await finish_action_after_speech()
    else:
        _workflow_action_log("workflow_concurrent_action_join_thread_create", action_name)
        threading.Thread(target=finish_action_after_speech_in_thread, daemon=True).start()
    return speech_result
async def _release_arm_after_concurrent_speech(robot, action_name):
    if action_name not in ARM_ACTIONS_NEED_RELEASE_BEFORE_SPEECH | ARM_ACTIONS_NEED_RELEASE_AFTER_SPEECH:
        return
    release_delay = _env_float("RABBITBOT_ARM_CONCURRENT_RELEASE_DELAY", 0.0)
    if release_delay > 0:
        _workflow_action_log("workflow_concurrent_release_wait_start", action_name, wait=f"{release_delay:.3f}s")
        await asyncio.sleep(release_delay)
        _workflow_action_log("workflow_concurrent_release_wait_done", action_name, wait=f"{release_delay:.3f}s")
    await _send_release_arm(robot)
async def _release_arm_after_speech(robot, action_name):
    if action_name not in ARM_ACTIONS_NEED_RELEASE_AFTER_SPEECH:
        return
    after_speech_delay = _env_float("RABBITBOT_ARM_AFTER_SPEECH_RELEASE_DELAY", 0.0)
    if after_speech_delay > 0:
        _workflow_action_log("workflow_after_speech_release_wait_start", action_name, wait=f"{after_speech_delay:.3f}s")
        await asyncio.sleep(after_speech_delay)
        _workflow_action_log("workflow_after_speech_release_wait_done", action_name, wait=f"{after_speech_delay:.3f}s")
    await _send_release_arm(robot)

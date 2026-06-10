#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


DEFAULT_URL = "http://127.0.0.1:28185/v1"
DEFAULT_TEXT = "哈喽，大家好，我是亿景小牛，欢迎来参观我们的动作捕捉房"
DEFAULT_TIMEOUT = 1.0
DEFAULT_ACTION_PAYLOAD = "19"
DEFAULT_END_ACTION_PAYLOAD = "0"
DEFAULT_GOAL_POSE_MSG = (
    "{data: '{\"x\":3.3358,\"y\":1.8962,\"z\":-0.0988,"
    "\"ox\":0.0156,\"oy\":0.0668,\"oz\":0.2212,\"ow\":0.9728,\"mode\":1}'}"
)
DEFAULT_GOAL_DELAY_SEC = 1.0


def publish_goal_pose() -> int:
    cmd = [
        "ros2",
        "topic",
        "pub",
        "--once",
        "/go_goal_pose",
        "std_msgs/msg/String",
        DEFAULT_GOAL_POSE_MSG,
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        print("ros2 command not found", file=sys.stderr)
        return 1

    if result.returncode != 0:
        print("Failed to publish /go_goal_pose", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    print("Published /go_goal_pose")
    return 0


def publish_action_cmd(action_payload: str) -> int:
    cmd = [
        "ros2",
        "topic",
        "pub",
        "--once",
        "/g1_arm/action_cmd",
        "std_msgs/msg/String",
        f"{{data: '{action_payload}'}}",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        print("ros2 command not found", file=sys.stderr)
        return 1

    if result.returncode != 0:
        print("Failed to publish /g1_arm/action_cmd", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    print(f"Published /g1_arm/action_cmd: {action_payload}")
    return 0


def send_text(url: str, text: str, timeout: float) -> int:
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"status: {resp.status}")
            if body:
                print(body)
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error: {exc.code}", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"URL error: {exc}", file=sys.stderr)
    except TimeoutError:
        print("Timeout error", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send text payload to local service."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Target URL")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Text to send")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--action",
        default=DEFAULT_ACTION_PAYLOAD,
        help="Action payload for /g1_arm/action_cmd before sending text",
    )
    parser.add_argument(
        "--end-action",
        default=DEFAULT_END_ACTION_PAYLOAD,
        help="Action payload for /g1_arm/action_cmd after sending text",
    )
    args = parser.parse_args()

    goal_rc = publish_goal_pose()
    if goal_rc != 0:
        return goal_rc
    time.sleep(DEFAULT_GOAL_DELAY_SEC)

    pub_rc = publish_action_cmd(args.action)
    if pub_rc != 0:
        return pub_rc

    text_rc = 1
    try:
        text_rc = send_text(args.url, args.text, args.timeout)
    finally:
        end_rc = publish_action_cmd(args.end_action)

    if text_rc != 0:
        return text_rc
    return end_rc


if __name__ == "__main__":
    raise SystemExit(main())

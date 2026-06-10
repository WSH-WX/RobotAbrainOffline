#!/usr/bin/env python3
"""
G1 Arm Action 命令发布脚本（ROS2）

接收话题
- Topic: /g1_arm/action_cmd
- Type : std_msgs/msg/String
- Content(JSON string):
    {"cmd":"execute","id":27}
    {"cmd":"execute","name":"clap"}
    {"cmd":"stop_custom"}
    {"cmd":"list"}

用法:
    python3 send_arm_action_cmd.py id <action_id>
    python3 send_arm_action_cmd.py name <action_name>
    python3 send_arm_action_cmd.py stop
    python3 send_arm_action_cmd.py list
    python3 send_arm_action_cmd.py names

示例:
    python3 send_arm_action_cmd.py id 27
    python3 send_arm_action_cmd.py name clap
    python3 send_arm_action_cmd.py stop
"""

import json
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


TOPIC = "/g1_arm/action_cmd"

# 与 goGoalNavigation_ros2.cpp 中 name->id 映射一致
ACTION_NAME_TO_ID = {
    "release arm": 99,
    "release": 99,
    "two-hand kiss": 11,
    "left kiss": 12,
    "right kiss": 12,
    "hands up": 15,
    "clap": 17,
    "high five": 18,
    "hug": 19,
    "heart": 20,
    "right heart": 21,
    "reject": 22,
    "right hand up": 23,
    "x-ray": 24,
    "face wave": 25,
    "high wave": 26,
    "shake hand": 27,
}


class ArmActionPublisher(Node):
    def __init__(self):
        super().__init__("arm_action_cmd_publisher")
        self.pub = self.create_publisher(String, TOPIC, 10)

    def publish_json(self, payload: dict):
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.pub.publish(msg)
        self.get_logger().info(f"[ARM CMD Published] topic={TOPIC} payload={msg.data}")
        rclpy.spin_once(self, timeout_sec=0.1)


def print_interface_spec():
    print("=== G1 Arm Action 接口说明（给上层交互）===")
    print(f"Topic: {TOPIC}")
    print("Type : std_msgs/msg/String")
    print("Content(JSON string):")
    print("  1) 按ID执行:   {\"cmd\":\"execute\",\"id\":27}")
    print("  2) 按name执行: {\"cmd\":\"execute\",\"name\":\"clap\"}")
    print("  3) 停止/释放:  {\"cmd\":\"stop_custom\"}  (当前实现映射为 release arm/id=99)")
    print("  4) 列表查询:   {\"cmd\":\"list\"}")
    print()
    print("支持的 name 列表:")
    for n, i in ACTION_NAME_TO_ID.items():
        print(f"  - {n:14s} -> {i}")


def print_usage():
    print("Usage:")
    print("  python3 send_arm_action_cmd.py id <action_id>")
    print("  python3 send_arm_action_cmd.py name <action_name>")
    print("  python3 send_arm_action_cmd.py stop")
    print("  python3 send_arm_action_cmd.py list")
    print("  python3 send_arm_action_cmd.py names")
    print()
    print("Examples:")
    print("  python3 send_arm_action_cmd.py id 27")
    print("  python3 send_arm_action_cmd.py name clap")
    print("  python3 send_arm_action_cmd.py name 'high five'")
    print("  python3 send_arm_action_cmd.py stop")


def main():
    if len(sys.argv) < 2:
        print_interface_spec()
        print()
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "names":
        print_interface_spec()
        sys.exit(0)

    payload = None

    if cmd == "id":
        if len(sys.argv) < 3:
            print("Error: missing action_id")
            print_usage()
            sys.exit(1)
        try:
            action_id = int(sys.argv[2])
        except ValueError:
            print("Error: action_id must be integer")
            sys.exit(1)
        payload = {"cmd": "execute", "id": action_id}

    elif cmd == "name":
        if len(sys.argv) < 3:
            print("Error: missing action_name")
            print_usage()
            sys.exit(1)
        action_name = " ".join(sys.argv[2:]).strip()
        payload = {"cmd": "execute", "name": action_name}

    elif cmd == "stop":
        payload = {"cmd": "stop_custom"}

    elif cmd == "list":
        payload = {"cmd": "list"}

    else:
        print(f"Error: unknown command '{cmd}'")
        print_usage()
        sys.exit(1)

    rclpy.init()
    node = ArmActionPublisher()
    try:
        node.publish_json(payload)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

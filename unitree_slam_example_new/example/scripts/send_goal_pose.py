#!/usr/bin/env python3
"""
目标位姿发布脚本
用于向 G1-Edu 导航节点发送目标位置

使用方法:
    python3 send_goal_pose.py x y z [ox oy oz ow] [mode]
    
示例:
    python3 send_goal_pose.py 1.0 2.0 0.0
    python3 send_goal_pose.py 1.0 2.0 0.0 0.0 0.0 0.0 1.0
    python3 send_goal_pose.py 1.0 2.0 0.0 0.0 0.0 0.0 1.0 1
    python3 scripts/send_goal_pose.py 3.3358  1.8962  -0.0988  0.0156  0.0668  0.2212  0.9728 对应/home/unitree/test1.pcd地图
"""

import sys
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class GoalPosePublisher(Node):
    def __init__(self):
        super().__init__('goal_pose_publisher')
        self.publisher = self.create_publisher(String, '/go_goal_pose', 10)
    
    def publish_goal(self, x, y, z, ox=0.0, oy=0.0, oz=0.0, ow=1.0, mode=1):
        """发布目标位姿"""
        goal_data = {
            "x": float(x),
            "y": float(y),
            "z": float(z),
            "ox": float(ox),
            "oy": float(oy),
            "oz": float(oz),
            "ow": float(ow),
            "mode": int(mode)
        }
        
        msg = String()
        msg.data = json.dumps(goal_data)
        
        self.publisher.publish(msg)
        self.get_logger().info(f'\033[32m[Goal Published]\033[0m {msg.data}')
        
        # 等待消息发送
        rclpy.spin_once(self, timeout_sec=0.1)


def print_usage():
    print("Usage: python3 send_goal_pose.py x y z [ox oy oz ow] [mode]")
    print()
    print("Arguments:")
    print("  x, y, z     : Target position (required)")
    print("  ox, oy, oz, ow : Target orientation quaternion (optional, default: 0,0,0,1)")
    print("  mode        : Navigation mode (optional, default: 1)")
    print()
    print("Examples:")
    print("  python3 send_goal_pose.py 1.0 2.0 0.0")
    print("  python3 send_goal_pose.py 1.0 2.0 0.0 0.0 0.0 0.707 0.707")
    print("  python3 send_goal_pose.py 1.0 2.0 0.0 0.0 0.0 0.0 1.0 1")


def main():
    # 解析参数
    if len(sys.argv) < 4:
        print_usage()
        sys.exit(1)
    
    try:
        x = float(sys.argv[1])
        y = float(sys.argv[2])
        z = float(sys.argv[3])
        
        # 四元数（可选）
        if len(sys.argv) >= 8:
            ox = float(sys.argv[4])
            oy = float(sys.argv[5])
            oz = float(sys.argv[6])
            ow = float(sys.argv[7])
        else:
            ox, oy, oz, ow = 0.0, 0.0, 0.0, 1.0
        
        # 模式（可选）
        if len(sys.argv) >= 9:
            mode = int(sys.argv[8])
        else:
            mode = 1
            
    except ValueError as e:
        print(f"Error: Invalid argument - {e}")
        print_usage()
        sys.exit(1)
    
    # 发布目标
    rclpy.init()
    node = GoalPosePublisher()
    
    try:
        node.publish_goal(x, y, z, ox, oy, oz, ow, mode)
    except Exception as e:
        node.get_logger().error(f'Failed to publish goal: {e}')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

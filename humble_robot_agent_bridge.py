#!/usr/bin/env python3
import ast
import asyncio
import json
import math
import os
import threading
import time
from enum import IntEnum

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import UInt8, String
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

from custom_action_interfaces.action import NaviArm, NaviWayPoint


class NavigationStatus(IntEnum):
    PENDING = 0
    ACTIVE = 1
    PREEMPTED = 2
    SUCCEEDED = 3
    ABORTED = 4


class RobotBridgeNode(Node):
    def __init__(self):
        super().__init__('humble_robot_agent_bridge')
        self.arm_client = ActionClient(self, NaviArm, 'navi_arm')
        self.waypoint_client = ActionClient(self, NaviWayPoint, 'navi_way_point')
        self.gesture_pub = self.create_publisher(String, '/gesture_cmd', 10)
        self.nav_status = NavigationStatus.PENDING
        self.nav_last_status = -1
        self.nav_next_status = -1
        self.nav_sub_status = ''
        self.nav_waypoints = []
        self.nav_waypoint_index = -1
        self.nav_waiting_for_arrival = False
        self.nav_final_arrived = False
        self.nav_arm_ready = False
        self.nav_forwarding = False
        self.nav_server_timeout = 5.0
        self.nav_goal_timeout = 15.0
        self.nav_lock = threading.Lock()
        self.pose_lock = threading.Lock()
        self.current_pose = None
        self.current_pose_received_at = None
        self.pose_invalid_logged = False
        self.create_subscription(UInt8, '/kuavo_navigation_state', self._nav_state_cb, 10)
        self.create_subscription(String, '/nav_status', self._nav_status_cb, 10)
        self.create_subscription(String, '/current_pose', self._current_pose_cb, 10)

    def _current_pose_cb(self, msg):
        try:
            payload = json.loads(msg.data)
            required = ('x', 'y', 'z', 'ox', 'oy', 'oz', 'ow')
            normalized = {key: float(payload[key]) for key in required}
            if not all(math.isfinite(value) for value in normalized.values()):
                raise ValueError('pose contains non-finite values')
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if not self.pose_invalid_logged:
                self.get_logger().warning(
                    f'Ignored invalid /current_pose message: error_type={type(exc).__name__} error={exc}'
                )
                self.pose_invalid_logged = True
            return
        first_pose = False
        with self.pose_lock:
            first_pose = self.current_pose is None
            self.current_pose = normalized
            self.current_pose_received_at = time.time()
            self.pose_invalid_logged = False
        if first_pose:
            self.get_logger().info(
                f'Current pose available through HTTP: x={normalized["x"]:.3f} y={normalized["y"]:.3f}'
            )

    def get_current_pose_payload(self):
        with self.pose_lock:
            pose = dict(self.current_pose) if self.current_pose is not None else None
            received_at = self.current_pose_received_at
        if pose is None or received_at is None:
            return {'localized': False, 'message': 'current pose has not been published'}
        age_seconds = max(0.0, time.time() - received_at)
        max_age_seconds = float(os.getenv('ROBOT_BRIDGE_POSE_MAX_AGE_SECONDS', '30'))
        if age_seconds > max_age_seconds:
            return {
                'localized': False,
                'message': f'current pose is stale ({age_seconds:.1f}s)',
                'age_seconds': round(age_seconds, 3),
            }
        pose.update({'localized': True, 'age_seconds': round(age_seconds, 3)})
        return pose

    def _nav_state_cb(self, msg):
        with self.nav_lock:
            self.nav_next_status = int(msg.data)
            if int(msg.data) == 1:
                self.nav_status = NavigationStatus.ACTIVE
            elif int(msg.data) == 2:
                if self.nav_status == NavigationStatus.ACTIVE:
                    self.nav_status = NavigationStatus.ACTIVE

    def _nav_status_cb(self, msg):
        status = (msg.data or '').strip()
        next_waypoint = None
        next_waypoint_index = -1
        server_timeout = 0.0
        goal_timeout = 0.0
        with self.nav_lock:
            self.nav_sub_status = status
            if status == 'arm_ready':
                self.nav_arm_ready = True
                if self.nav_final_arrived:
                    self.nav_status = NavigationStatus.SUCCEEDED
                else:
                    self.nav_status = NavigationStatus.ACTIVE
            elif status == 'mid_arrived':
                self.nav_waiting_for_arrival = False
                self.nav_status = NavigationStatus.ACTIVE
                if (
                    not self.nav_forwarding
                    and self.nav_waypoint_index + 1 < len(self.nav_waypoints)
                ):
                    next_waypoint_index = self.nav_waypoint_index + 1
                    next_waypoint = self.nav_waypoints[next_waypoint_index]
                    server_timeout = self.nav_server_timeout
                    goal_timeout = self.nav_goal_timeout
                    self.nav_waypoint_index = next_waypoint_index
                    self.nav_forwarding = True
                elif self.nav_waypoint_index + 1 >= len(self.nav_waypoints):
                    self.nav_final_arrived = True
                    if self.nav_arm_ready:
                        self.nav_status = NavigationStatus.SUCCEEDED
            elif status == 'arrived':
                self.nav_waiting_for_arrival = False
                self.nav_final_arrived = True
                if self.nav_arm_ready:
                    self.nav_status = NavigationStatus.SUCCEEDED
                else:
                    self.nav_status = NavigationStatus.ACTIVE
            elif status == 'preempted':
                self.nav_waiting_for_arrival = False
                self.nav_status = NavigationStatus.PREEMPTED
            elif status == 'navigating':
                self.nav_status = NavigationStatus.ACTIVE
        if next_waypoint is not None:
            threading.Thread(
                target=self._forward_next_waypoint,
                args=(next_waypoint_index, next_waypoint, server_timeout, goal_timeout),
                daemon=True,
            ).start()

    def reset_nav_status(self):
        with self.nav_lock:
            self.nav_status = NavigationStatus.PENDING
            self.nav_last_status = -1
            self.nav_next_status = -1
            self.nav_sub_status = ''
            self.nav_waypoints = []
            self.nav_waypoint_index = -1
            self.nav_waiting_for_arrival = False
            self.nav_final_arrived = False
            self.nav_arm_ready = False
            self.nav_forwarding = False

    def start_waypoint_sequence(self, waypoints, server_timeout: float, result_timeout: float):
        with self.nav_lock:
            self.nav_status = NavigationStatus.PENDING
            self.nav_last_status = -1
            self.nav_next_status = -1
            self.nav_sub_status = ''
            self.nav_waypoints = list(waypoints)
            self.nav_waypoint_index = 0
            self.nav_waiting_for_arrival = False
            self.nav_final_arrived = False
            self.nav_arm_ready = False
            self.nav_forwarding = False
            self.nav_server_timeout = float(server_timeout)
            self.nav_goal_timeout = float(result_timeout)
        return self.send_waypoint_goal(waypoints[0], server_timeout, result_timeout)

    def get_nav_status_payload(self):
        with self.nav_lock:
            return {
                'status': str(int(self.nav_status)),
                'last_status': self.nav_last_status,
                'next_status': self.nav_next_status,
                'sub': self.nav_sub_status,
            }

    def send_arm_goal(self, action_name: str, server_timeout: float, result_timeout: float):
        bridge_start = time.perf_counter()
        self.get_logger().info(f'HTTP /do_arm_async task={action_name}')
        if not self.arm_client.wait_for_server(timeout_sec=server_timeout):
            total_ms = (time.perf_counter() - bridge_start) * 1000.0
            self.get_logger().warning(
                f'Bridge timing [/do_arm_async]: server_unavailable total={total_ms:.2f} ms task={action_name}'
            )
            return {'success': False, 'message': 'navi_arm action server not available'}
        goal_msg = NaviArm.Goal()
        goal_msg.action_name = str(action_name)
        send_goal_start = time.perf_counter()
        send_future = self.arm_client.send_goal_async(goal_msg)
        if not wait_future(send_future, result_timeout):
            total_ms = (time.perf_counter() - bridge_start) * 1000.0
            self.get_logger().warning(
                f'Bridge timing [/do_arm_async]: goal_response_timeout total={total_ms:.2f} ms task={action_name}'
            )
            return {'success': False, 'message': 'goal response timeout'}
        goal_response_ms = (time.perf_counter() - send_goal_start) * 1000.0
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            total_ms = (time.perf_counter() - bridge_start) * 1000.0
            self.get_logger().warning(
                f'Bridge timing [/do_arm_async]: goal_rejected total={total_ms:.2f} ms response={goal_response_ms:.2f} ms task={action_name}'
            )
            return {'success': False, 'message': 'goal rejected'}
        result_wait_start = time.perf_counter()
        result_future = goal_handle.get_result_async()
        if not wait_future(result_future, result_timeout):
            total_ms = (time.perf_counter() - bridge_start) * 1000.0
            wait_result_ms = (time.perf_counter() - result_wait_start) * 1000.0
            self.get_logger().warning(
                f'Bridge timing [/do_arm_async]: result_timeout total={total_ms:.2f} ms goal_response={goal_response_ms:.2f} ms wait_result={wait_result_ms:.2f} ms task={action_name}'
            )
            return {'success': False, 'message': 'result timeout'}
        wait_result_ms = (time.perf_counter() - result_wait_start) * 1000.0
        total_ms = (time.perf_counter() - bridge_start) * 1000.0
        result = result_future.result().result
        self.get_logger().info(
            f'Bridge timing [/do_arm_async]: total={total_ms:.2f} ms goal_response={goal_response_ms:.2f} ms wait_result={wait_result_ms:.2f} ms task={action_name}'
        )
        return {
            'success': bool(getattr(result, 'success', True)),
            'message': str(getattr(result, 'message', '')),
        }

    def publish_gesture_command(self, command: str):
        bridge_start = time.perf_counter()
        command = str(command or '').strip()
        if not command:
            return {'success': False, 'message': 'empty gesture command'}
        msg = String()
        msg.data = command
        self.gesture_pub.publish(msg)
        publish_ms = (time.perf_counter() - bridge_start) * 1000.0
        self.get_logger().info(f'HTTP /gesture_cmd command={command}')
        self.get_logger().info(
            f'Bridge timing [/gesture_cmd]: publish={publish_ms:.2f} ms topic=/gesture_cmd data={command}'
        )
        return {'success': True, 'message': 'gesture command published', 'topic': '/gesture_cmd', 'data': command}

    def send_waypoint_goal(self, waypoint, server_timeout: float, result_timeout: float):
        x, y, ox, oy, oz, ow = waypoint
        self.get_logger().info(
            f'HTTP /go_to_async waypoint x={x:.4f} y={y:.4f} ox={ox:.4f} oy={oy:.4f} oz={oz:.4f} ow={ow:.4f}'
        )
        if not self.waypoint_client.wait_for_server(timeout_sec=server_timeout):
            with self.nav_lock:
                self.nav_status = NavigationStatus.ABORTED
            return {'success': False, 'message': 'navi_way_point action server not available'}
        goal_msg = NaviWayPoint.Goal()
        goal_msg.position_x = float(x)
        goal_msg.position_y = float(y)
        goal_msg.position_z = 0.0
        goal_msg.orientation_x = float(ox)
        goal_msg.orientation_y = float(oy)
        goal_msg.orientation_z = float(oz)
        goal_msg.orientation_w = float(ow)
        with self.nav_lock:
            self.nav_status = NavigationStatus.ACTIVE
            self.nav_last_status = self.nav_next_status
            self.nav_sub_status = ''
        send_future = self.waypoint_client.send_goal_async(goal_msg)
        if not wait_future(send_future, result_timeout):
            with self.nav_lock:
                self.nav_status = NavigationStatus.ABORTED
            return {'success': False, 'message': 'waypoint goal response timeout'}
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            with self.nav_lock:
                self.nav_status = NavigationStatus.ABORTED
            return {'success': False, 'message': 'waypoint goal rejected'}
        with self.nav_lock:
            self.nav_waiting_for_arrival = True
        return {'success': True, 'message': 'waypoint goal sent'}

    def _forward_next_waypoint(self, waypoint_index: int, waypoint, server_timeout: float, result_timeout: float):
        self.get_logger().info(
            f'Forward next waypoint {waypoint_index + 1}/{len(self.nav_waypoints)} after mid_arrived'
        )
        result = self.send_waypoint_goal(waypoint, server_timeout, result_timeout)
        with self.nav_lock:
            self.nav_forwarding = False
            if not result.get('success'):
                self.nav_status = NavigationStatus.ABORTED
                self.nav_sub_status = f"forward_failed:{result.get('message', '')}"


def wait_future(future, timeout_sec):
    start = time.time()
    while rclpy.ok() and not future.done():
        if timeout_sec is not None and time.time() - start > timeout_sec:
            return False
        time.sleep(0.02)
    return future.done()


def normalize_waypoints(task: str):
    point = ast.literal_eval(task)
    if isinstance(point, dict):
        point = (point.get('x'), point.get('y'), point.get('ox'), point.get('oy'), point.get('oz'), point.get('ow'))
    if isinstance(point, (list, tuple)) and len(point) >= 6 and not isinstance(point[0], (list, tuple, dict)):
        point = [point]
    if not isinstance(point, (list, tuple)):
        raise ValueError('task must be a waypoint tuple/list or list of waypoints')
    waypoints = []
    for item in point:
        if isinstance(item, dict):
            values = (item.get('x'), item.get('y'), item.get('ox'), item.get('oy'), item.get('oz'), item.get('ow'))
        else:
            values = item[:6]
        waypoints.append(tuple(float(v) for v in values))
    if not waypoints:
        raise ValueError('no valid waypoint')
    return waypoints


rclpy.init()
node = RobotBridgeNode()
executor = MultiThreadedExecutor()
executor.add_node(node)
threading.Thread(target=executor.spin, daemon=True).start()

app = FastAPI()


@app.get('/health')
def health():
    return {'ok': True, 'service': 'humble_robot_agent_bridge'}


@app.get('/current_pose')
def current_pose():
    return node.get_current_pose_payload()


@app.post('/do_arm_async')
async def do_arm_async(task: str = Form(...)):
    result = await asyncio.to_thread(
        node.send_arm_goal,
        task,
        float(os.getenv('ROBOT_BRIDGE_ARM_SERVER_TIMEOUT', '5')),
        float(os.getenv('ROBOT_BRIDGE_ARM_RESULT_TIMEOUT', '90')),
    )
    return JSONResponse(content=result, status_code=200 if result.get('success') else 503)


@app.post('/gesture_cmd')
async def gesture_cmd(task: str = Form(...)):
    result = node.publish_gesture_command(task)
    return JSONResponse(content=result, status_code=200 if result.get('success') else 400)


@app.post('/do_gesture_async')
async def do_gesture_async(task: str = Form(...)):
    result = node.publish_gesture_command(task)
    return JSONResponse(content=result, status_code=200 if result.get('success') else 400)


@app.post('/do_hand_async')
async def do_hand_async(task: str = Form(...)):
    result = node.publish_gesture_command(task)
    return JSONResponse(content=result, status_code=200 if result.get('success') else 400)


@app.post('/go_to_async')
async def go_to_async(task: str = Form(...)):
    server_timeout = float(os.getenv('ROBOT_BRIDGE_NAV_SERVER_TIMEOUT', '5'))
    goal_timeout = float(os.getenv('ROBOT_BRIDGE_NAV_GOAL_TIMEOUT', '15'))
    try:
        waypoints = normalize_waypoints(task)
    except Exception as exc:
        node.reset_nav_status()
        with node.nav_lock:
            node.nav_status = NavigationStatus.ABORTED
        return JSONResponse(content={'success': False, 'message': str(exc)}, status_code=400)
    result = await asyncio.to_thread(
        node.start_waypoint_sequence,
        waypoints,
        server_timeout,
        goal_timeout,
    )
    return JSONResponse(content=result, status_code=200 if result.get('success') else 503)


@app.post('/go_to_status')
async def go_to_status(task: str = Form('')):
    return JSONResponse(content=node.get_nav_status_payload())


@app.post('/reset_go_to_status')
async def reset_go_to_status(task: str = Form('')):
    node.reset_nav_status()
    return JSONResponse(content=node.get_nav_status_payload())

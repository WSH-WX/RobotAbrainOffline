# 搜索目标 + 前往目标 + 移动跟随 项目计划（在线建图导航）
## 1. 范围与约束
- 模式：纯在线边建图边导航
- 平台：NVIDIA Jetson Orin 64G
- 目标：类别搜索 -> 实例锁定 -> 持续跟随
- 优先级：低速稳定（0.3~0.6 m/s）
## 2. 方案对比与推荐
### 方案1：单体大状态机
- 优点：联调快
- 缺点：耦合高、后期难维护
### 方案2：分层架构（推荐）
- 感知 / 目标管理 / 导航控制 / FSM 解耦
- 优点：可维护、可替换、易调参
- 缺点：前期接口设计更严格
### 方案3：Nav2核心 + 语义插件
- 优点：工程化强
- 缺点：学习与集成成本更高
**推荐：方案2。**
---
## 3. 总体架构
- 感知层：`detector_node` + `tracker_node` + `depth_fusion_node`
- 地图定位层：SLAM + local/global costmap
- 目标管理层：搜索、锁定、重识别、丢失恢复
- 导航控制层：Nav2桥接 + 连续重规划
- 行为层：FSM（`IDLE -> SEARCH -> APPROACH -> FOLLOW -> LOST_RECOVERY -> ARRIVED`）
---
## 4. ROS2 接口规范
### 4.1 TF
- `map`, `odom`, `base_link`, `camera_link/camera_optical_frame`, `lidar_link`
- 关系：`map->odom`, `odom->base_link`, `base_link->camera_link`, `base_link->lidar_link`
### 4.2 Topics（核心）
- `/perception/detections`：检测输出（10~15Hz）
- `/perception/tracks`：跟踪输出（10~15Hz）
- `/perception/targets_3d`：3D目标（10Hz）
- `/mission/target_state`：目标状态（5Hz）
- `/mission/current_target`：当前目标（5Hz）
- `/mission/nav_goal`：导航目标（事件触发/2~3Hz）
- `/nav/status`：导航状态（5Hz）
- `/safety/stop`：安全停（实时）
### 4.3 节点职责（摘要）
- `detector_node`：YOLO TensorRT检测
- `tracker_node`：实例ID跟踪
- `depth_fusion_node`：bbox+深度融合成3D点
- `target_manager_node`：类别搜索、实例锁定、重捕逻辑
- `search_planner_node`：前沿探索与观察点生成
- `nav_bridge_node`：任务目标到Nav2动作桥接
- `behavior_fsm_node`：状态机切换
- `safety_node`：紧急停障与安全限速
---
## 5. 时延与频率预算（低速稳定）
- 检测/跟踪：10~15Hz
- 3D融合：10Hz
- 目标管理/FSM：5Hz
- 跟随重规划：2~3Hz
- 控制：20~30Hz
- 端到端时延（图像->目标更新）：< 250ms
---
## 6. WBS（周计划 + 人天）
> 估算：1算法 + 1系统工程师并行
### M0（第1周，10~12人天）
- 传感器驱动/同步、TF标定、推理环境、监控、冒烟测试
### M1（第2~3周，18~22人天）
- 静态目标搜索+到达（检测、融合、目标管理v1、Nav2桥接、FSM v1）
### M2（第4周，10~14人天）
- 实例锁定与抗误检（跟踪器、锁定逻辑、重识别窗口）
### M3（第5~6周，16~20人天）
- 移动目标持续跟随（运动估计、连续重规划、跟随控制、丢失恢复、FSM v2）
### M4（第7周，10~13人天）
- 安全策略、故障降级、看门狗、长稳测试
### M5（第8周，6~8人天）
- 验收脚本、参数模板、手册与回归测试
总量：**70~89人天**，双人并行约**8~10周**。
---
## 7. 验收标准
- M1：10次任务搜索+到达成功率 ≥ 80%，到达误差 ≤ 1.0m
- M2：多同类目标锁定准确率 ≥ 85%
- M3：低速跟随3分钟不中断（短遮挡可恢复）
- M4：连续运行1小时无致命故障
---
## 8. 自定义消息定义（.msg）草案
### `TrackedObject.msg`
```text
std_msgs/Header header
int32 track_id
int32 class_id
string class_name
float32 score
float32 cx
float32 cy
float32 w
float32 h
int32 age
int32 lost_count
```
### `TrackedObjectArray.msg`
```text
std_msgs/Header header
TrackedObject[] objects
```
### `Target3D.msg`
```text
std_msgs/Header header
int32 track_id
int32 class_id
string class_name
float32 score
geometry_msgs/Point p_cam
geometry_msgs/Point p_base
geometry_msgs/Point p_map
float32 distance
float32 vx
float32 vy
float32 vz
bool valid_depth
```
### `Target3DArray.msg`
```text
std_msgs/Header header
Target3D[] targets
```
### `TargetState.msg`
```text
std_msgs/Header header
uint8 mode
uint8 state
string target_class
int32 lock_track_id
geometry_msgs/PoseStamped target_pose_map
float32 confidence
float32 distance
int32 lost_frames
uint8 MODE_CLASS=0
uint8 MODE_INSTANCE=1
uint8 STATE_IDLE=0
uint8 STATE_SEARCHING=1
uint8 STATE_LOCKED=2
uint8 STATE_APPROACHING=3
uint8 STATE_FOLLOWING=4
uint8 STATE_LOST=5
uint8 STATE_ARRIVED=6
uint8 STATE_SAFE_STOP=7
```
### `NavStatus.msg`
```text
std_msgs/Header header
uint8 status
string text
geometry_msgs/PoseStamped current_pose
geometry_msgs/PoseStamped active_goal
float32 remaining_distance
float32 eta_sec
bool replanning
uint8 NAV_IDLE=0
uint8 NAV_RUNNING=1
uint8 NAV_SUCCEEDED=2
uint8 NAV_FAILED=3
uint8 NAV_CANCELED=4
```
### `PerceptionHealth.msg`（可选）
```text
std_msgs/Header header
float32 detector_fps
float32 tracker_fps
float32 fusion_fps
float32 pipeline_latency_ms
float32 gpu_usage
float32 gpu_temp_c
bool degraded_mode
string note
```
---
## 9. 服务定义（.srv）草案
### `SetTargetClass.srv`
```text
string class_name
---
bool ok
string message
```
### `LockTargetId.srv`
```text
int32 track_id
---
bool ok
string message
```
### `CancelTarget.srv`
```text
---
bool ok
string message
```
---
## 10. 风险与对策
- 误检追错：多帧确认 + 类别白名单 + 实例锁定
- 深度跳变：ROI中位数 + 离群剔除 + 时间滤波
- 遮挡丢失：最后可见点重访 + 扇形扫描 + 前沿重搜索
- GPU波动：限帧/降分辨率/退化模式
- 地图漂移：回环优化 + 局部短期跟随优先
---
## 11. 实施目录建议
- `perception_pkg/`
- `target_manager_pkg/`
- `nav_bridge_pkg/`
- `behavior_fsm_pkg/`
- `safety_pkg/`
- `bringup_pkg/`
launch建议：
- `bringup_sensors.launch.py`
- `bringup_perception.launch.py`
- `bringup_nav_slam.launch.py`
- `bringup_mission.launch.py`
- `bringup_all.launch.py`

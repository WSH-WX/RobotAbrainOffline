Global 2D Navigation (G1)
==========================

This folder contains Python and C++ versions, split into two programs:

1) Grid map builder
   - Python: build_grid_map.py
   - C++:    build_grid_map.cpp (binary: build_grid_map_cpp)

2) 2D planner
   - Python: plan_nav_2d.py
   - C++:    plan_nav_2d.cpp (binary: plan_nav_2d_cpp)

3) Dynamic replanning planner
   - Python: plan_nav_dynamic_replan.py
   - C++:    plan_nav_dynamic_replan.cpp (binary: plan_nav_dynamic_replan_cpp)
   - Event-triggered global replanning when new obstacles block path

Core constraints supported:
- obstacle avoidance
- straight-line segments
- each segment length <= max segment (default 10m)
- waypoint count reduced as much as possible


Python version
--------------
Dependencies:
  pip install numpy open3d pillow

A. Build occupancy map:
python3 build_grid_map.py \
  --input /mnt/disk1/unitree_slam_example/global_maps/global_map_20260330_155423.pcd \
  --output /mnt/disk1/unitree_slam_example/global_nav/map_data.npz \
  --resolution 0.10 \
  --z-min -0.20 \
  --z-max 1.50 \
  --inflation-radius 0.45

B. Plan sparse path:
python3 plan_nav_2d.py \
  --map /mnt/disk1/unitree_slam_example/global_nav/map_data.npz \
  --start 0.0 0.0 \
  --goal 8.0 5.0 \
  --goal-yaw 0.0 \
  --max-segment 10.0 \
  --output /mnt/disk1/unitree_slam_example/global_nav/path_waypoints.json

C. Dynamic event-triggered replanning:
python3 plan_nav_dynamic_replan.py \
  --map /mnt/disk1/unitree_slam_example/global_nav/map_data.npz \
  --start 0.0 0.0 \
  --goal 8.0 5.0 \
  --goal-yaw 0.0 \
  --max-segment 10.0 \
  --obstacles-json /mnt/disk1/unitree_slam_example/global_nav/dyn_obstacles_demo.json \
  --dyn-margin 0.10 \
  --cooldown 1.0 \
  --confirm-frames 3 \
  --output /mnt/disk1/unitree_slam_example/global_nav/path_dynamic_replan.json

Example dynamic obstacle file:
{
  "frames": [
    {"t": 0.0, "obstacles": []},
    {"t": 0.5, "obstacles": [{"x": 1.2, "y": 0.5, "r": 0.4}]},
    {"t": 1.0, "obstacles": [{"x": 1.3, "y": 0.6, "r": 0.4}]}
  ]
}


C++ version
-----------
Dependencies (Ubuntu):
  sudo apt install -y build-essential cmake libpcl-dev

Build:
cd /mnt/disk1/unitree_slam_example/global_nav
mkdir -p build && cd build
cmake ..
make -j

A. Build occupancy map text file:
./build_grid_map_cpp \
  --input /mnt/disk1/unitree_slam_example/global_maps/global_map_20260330_155423.pcd \
  --output /mnt/disk1/unitree_slam_example/global_nav/map_data_cpp.txt \
  --resolution 0.10 \
  --z-min -0.20 \
  --z-max 1.50 \
  --inflation-radius 0.45

B. Plan sparse path:
./plan_nav_2d_cpp \
  --map /mnt/disk1/unitree_slam_example/global_nav/map_data_cpp.txt \
  --start 0.0 0.0 \
  --goal 8.0 5.0 \
  --goal-yaw 0.0 \
  --max-segment 10.0 \
  --output /mnt/disk1/unitree_slam_example/global_nav/path_waypoints_cpp.json

C. Dynamic event-triggered replanning:
./plan_nav_dynamic_replan_cpp \
  --map /mnt/disk1/unitree_slam_example/global_nav/map_data_cpp.txt \
  --start 13.41417 -5.59831 \
  --goal -5.18583 4.00169 \
  --goal-yaw 0.0 \
  --max-segment 10.0 \
  --obstacles-json /mnt/disk1/unitree_slam_example/global_nav/dyn_obstacles_demo.json \
  --dyn-margin 0.10 \
  --cooldown 1.0 \
  --confirm-frames 3 \
  --output /mnt/disk1/unitree_slam_example/global_nav/path_dynamic_replan_cpp.json


Output files
------------
Python:
- map_data.npz
- map_data.png (optional debug image)
- path_waypoints.json

C++:
- map_data_cpp.txt (custom occupancy text format)
- path_waypoints_cpp.json
- path_dynamic_replan_cpp.json

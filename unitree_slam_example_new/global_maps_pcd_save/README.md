# global_maps_pcd_save

Use Unitree SLAM document method 1 (C++ code) to save the global map as a PCD file.

The program calls the `slam_operate` service API `1802` with this request body:

```json
{"data":{"address":"/path/to/map.pcd"}}
```

## Build

```bash
cd /mnt/ssd/navgation/projects/unitree_slam_example_new/global_maps_pcd_save
cmake -S . -B build
cmake --build build -j2
```

## Run

Run this after mapping has collected enough data and you are ready to end/save mapping.
Replace `eth0` with the network interface connected to the robot.

```bash
./build/global_maps_pcd_save eth0
```

Default output path:

```text
/mnt/ssd/navgation/projects/unitree_slam_example_new/global_maps_pcd_save/maps/global_map.pcd
```

Custom output path:

```bash
./build/global_maps_pcd_save eth0 /mnt/ssd/navgation/projects/unitree_slam_example_new/global_maps_pcd_save/maps/my_map.pcd
```

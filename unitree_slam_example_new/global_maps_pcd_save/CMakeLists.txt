cmake_minimum_required(VERSION 3.16)
project(global_maps_pcd_save)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(unitree_sdk2 REQUIRED)

add_executable(global_maps_pcd_save src/global_maps_pcd_save.cpp)
target_link_libraries(global_maps_pcd_save unitree_sdk2)

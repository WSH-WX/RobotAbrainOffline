cmake_minimum_required(VERSION 3.10)
project(global_nav_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PCL REQUIRED COMPONENTS io)

add_executable(build_grid_map_cpp build_grid_map.cpp)
target_link_libraries(build_grid_map_cpp PRIVATE ${PCL_LIBRARIES})
target_include_directories(build_grid_map_cpp PRIVATE ${PCL_INCLUDE_DIRS})
target_compile_definitions(build_grid_map_cpp PRIVATE ${PCL_DEFINITIONS})

add_executable(plan_nav_2d_cpp plan_nav_2d.cpp)
add_executable(plan_nav_dynamic_replan_cpp plan_nav_dynamic_replan.cpp)

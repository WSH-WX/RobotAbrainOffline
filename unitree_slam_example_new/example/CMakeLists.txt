project(slam_example)
cmake_minimum_required(VERSION 3.16)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(/usr/local/include include)

find_package(unitree_sdk2 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(custom_action_interfaces REQUIRED)

add_executable(keyDemo src/keyDemo.cpp)
target_link_libraries(keyDemo unitree_sdk2)

add_executable(goGoalNavigation src/goGoalNavigation_ros2.cpp)
target_include_directories(goGoalNavigation PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    goGoalNavigation
    unitree_sdk2
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(goGoalNavigation custom_action_interfaces geometry_msgs)

add_executable(goGoalNavigation66 src/goGoalNavigation_ros2_66.cpp)
target_include_directories(goGoalNavigation66 PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    goGoalNavigation66
    unitree_sdk2
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(goGoalNavigation66 custom_action_interfaces geometry_msgs)

add_executable(gestureTopicBridge src/gesture_topic_bridge.cpp)
target_include_directories(gestureTopicBridge PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    gestureTopicBridge
    unitree_sdk2
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(gestureTopicBridge custom_action_interfaces)

add_executable(integratedLauncher src/integrated_launcher.cpp)

add_library(g1_actions STATIC
    src/actions/g1_actions.cpp
)
target_include_directories(g1_actions PUBLIC include)

add_executable(g1Arm7DIYActionExample src/g1_arm7__diy_action_example.cpp)
target_include_directories(g1Arm7DIYActionExample PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    g1Arm7DIYActionExample
    unitree_sdk2
    g1_actions
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(g1Arm7DIYActionExample custom_action_interfaces)

add_executable(g1ArmOfficialActionServer src/g1_arm_official_action_server.cpp)
target_include_directories(g1ArmOfficialActionServer PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    g1ArmOfficialActionServer
    unitree_sdk2
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(g1ArmOfficialActionServer custom_action_interfaces)

# goGoalNavigation launches this sibling executable at runtime.
add_dependencies(goGoalNavigation g1Arm7DIYActionExample)

add_executable(goGoalNavigationRos2Mock src/goGoalNavigation_ros2_mock.cpp)
target_include_directories(goGoalNavigationRos2Mock PRIVATE ${std_msgs_INCLUDE_DIRS})
target_link_libraries(
    goGoalNavigationRos2Mock
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action
    ${std_msgs_LIBRARIES}
)
ament_target_dependencies(goGoalNavigationRos2Mock custom_action_interfaces geometry_msgs)

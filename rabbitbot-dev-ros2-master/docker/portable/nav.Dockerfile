FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive \
    RABBITBOT_PORTABLE_PROJECT_ROOT=/workspace/projects/rabbitbot-dev-ros2-master

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-colcon-common-extensions \
    ros-humble-rclpy \
    ros-humble-rclcpp \
    ros-humble-rclcpp-action \
    ros-humble-std-msgs \
    ros-humble-geometry-msgs \
    ros-humble-rosidl-default-generators \
    ros-humble-ament-cmake \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir fastapi 'uvicorn[standard]'

WORKDIR /workspace/projects
COPY humble_robot_agent_bridge.py /workspace/projects/humble_robot_agent_bridge.py
COPY custom_action_ws/src /workspace/projects/custom_action_ws/src
COPY unitree_sdk2 /workspace/projects/unitree_sdk2
COPY unitree_slam_example_new/example /workspace/projects/unitree_slam_example_new/example
COPY rabbitbot-dev-ros2-master/docker/portable/nav_entrypoint.sh /usr/local/bin/rabbitbot-portable-nav-entrypoint

# 清理宿主历史构建产物，避免旧 CMakeCache 污染容器内重新配置。
RUN rm -rf /workspace/projects/unitree_slam_example_new/example/build \
    /workspace/projects/unitree_slam_example_new/example/run_logs

RUN bash -lc 'source /opt/ros/humble/setup.bash && cd /workspace/projects/custom_action_ws && colcon build --merge-install --base-paths src'
RUN cmake -S /workspace/projects/unitree_sdk2 -B /workspace/projects/unitree_sdk2/build -DBUILD_EXAMPLES=OFF \
    && cmake --build /workspace/projects/unitree_sdk2/build -j"$(nproc)" \
    && cmake --install /workspace/projects/unitree_sdk2/build --prefix /opt/unitree_sdk2
RUN bash -lc 'source /opt/ros/humble/setup.bash && source /workspace/projects/custom_action_ws/install/setup.bash && cmake -S /workspace/projects/unitree_slam_example_new/example -B /workspace/projects/unitree_slam_example_new/example/build -DCMAKE_PREFIX_PATH="/opt/unitree_sdk2;/workspace/projects/custom_action_ws/install:${CMAKE_PREFIX_PATH}" && cmake --build /workspace/projects/unitree_slam_example_new/example/build -j"$(nproc)"'

RUN chmod +x /usr/local/bin/rabbitbot-portable-nav-entrypoint

CMD ["/usr/local/bin/rabbitbot-portable-nav-entrypoint"]

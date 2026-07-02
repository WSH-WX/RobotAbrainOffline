# RabbitBot portable 自包含 core 镜像。
#
# 设计说明：
#   1. 本机现存的四个上游镜像（navid-rabbitbot:stt-tts-audio-ct2cuda-20260511、
#      rabbitbot-vllm:20260511、foxy-ros-cam-orb-ubuntu20:rabbitbot-20260511）已不在本机，
#      只剩 neo4j:5.26-community；因此无法在本机完成“完全从零、不 FROM unified-runtime”的 core。
#   2. rabbitbot-unified-runtime:20260518 本身就是这四个上游镜像的合并产物，已包含
#      Neo4j、Java、ROS Foxy、Python 3.8、STT/TTS、VLM venv 等全部运行时。
#   3. 因此本 Dockerfile 以 unified-runtime 为基础镜像，并把宿主 gitignore 的重型运行依赖
#      （py38/py310 虚拟环境、vln、pyorbbecsdk-v2-py310、unitree_sdk2）以及项目源码烤进镜像固定路径，
#      使全新 Orin 运行期不再需要任何宿主依赖目录，只靠 GitHub 源码 + 本镜像即可冷启动。
#
# 构建上下文要求：
#   必须使用 build_or_pull_images.sh 生成的专用暂存上下文，该上下文不受顶层 .dockerignore
#   对 py38/py310/vln/pyorbbecsdk 的排除影响，从而能把这些目录真正烤进镜像。

ARG CORE_BASE_IMAGE=rabbitbot-unified-runtime:20260518
FROM ${CORE_BASE_IMAGE}

LABEL org.opencontainers.image.title="RabbitBot Portable Core (self-contained)"
LABEL org.opencontainers.image.description="自包含 portable core：在 unified runtime 基础上烤入 py38/py310/vln/pyorbbecsdk/unitree_sdk2 与项目源码，运行期不再依赖宿主目录"
LABEL org.opencontainers.image.version="20260611"

ENV RABBITBOT_DIR=/workspace/projects/rabbitbot-dev-ros2-master \
    RABBITBOT_MODELS_DIR=/models \
    RABBITBOT_PORTABLE_SELF_CONTAINED=1

# 把项目源码与重型运行依赖烤入镜像固定路径。
# 这些路径同时是运行期 named volume 的 seed 来源：portable 模式下宿主源码 bind mount 会遮蔽
# 这些子目录，届时由从镜像 seed 的 named volume 把 py38/py310/vln/pyorbbecsdk 重新顶上来。
COPY rabbitbot-dev-ros2-master /workspace/projects/rabbitbot-dev-ros2-master
COPY vln /workspace/projects/vln
COPY pyorbbecsdk-v2-py310 /workspace/projects/pyorbbecsdk-v2-py310
COPY unitree_sdk2 /workspace/projects/unitree_sdk2
COPY humble_robot_agent_bridge.py /workspace/projects/humble_robot_agent_bridge.py

# 从烤入的源码安装统一容器入口与冒烟脚本到 /usr/local/bin，保证镜像自身可独立冒烟。
RUN cp /workspace/projects/rabbitbot-dev-ros2-master/scripts_1/unified_runtime/start_unified_container.sh /usr/local/bin/rabbitbot-start-unified \
    && cp /workspace/projects/rabbitbot-dev-ros2-master/scripts_1/unified_runtime/smoke_check.sh /usr/local/bin/rabbitbot-unified-smoke-check \
    && chmod +x /usr/local/bin/rabbitbot-start-unified /usr/local/bin/rabbitbot-unified-smoke-check \
    && mkdir -p /workspace/projects/models /workspace/projects/rabbitbot-dev-ros2-master/logs/unified_runtime

CMD ["/usr/local/bin/rabbitbot-start-unified"]

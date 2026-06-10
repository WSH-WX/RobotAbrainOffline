#!/usr/bin/env bash
# 检查 air_robot_gt_projects 自主运行项目的关键文件、环境、路径和语法。

set -euo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PROJECTS_DIR="${AIR_ROOT}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
    log_ok "存在：$1"
}

log_info "检查目录结构"
require_path "${REPO_DIR}"
require_path "${PROJECTS_DIR}/models"
require_path "${PROJECTS_DIR}/custom_action_ws/install/setup.bash"
require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation66"
require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/g1ArmOfficialActionServer"
require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation"
require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/gestureTopicBridge"
require_path "${PROJECTS_DIR}/unitree_sdk2/build/bin/g1_loco_client"
require_path "${PROJECTS_DIR}/dfx_inspire_service/build/inspire_g1"
require_path "${PROJECTS_DIR}/unitree_sdk2"
require_path "${PROJECTS_DIR}/vln/ros2_ws/install/setup.bash"
require_path "${PROJECTS_DIR}/pyorbbecsdk-v2-py310/install/lib"
require_path "${PROJECTS_DIR}/humble_robot_agent_bridge.py"
require_path "${REPO_DIR}/py38/bin/python"
require_path "${REPO_DIR}/py310/bin/python"
require_path "/opt/ros/humble/setup.bash"

log_info "检查 Docker 镜像"
if docker image inspect rabbitbot-unified-runtime:20260518 >/dev/null 2>&1; then
    log_ok "Docker 镜像存在：rabbitbot-unified-runtime:20260518"
else
    log_error "Docker 镜像不存在：rabbitbot-unified-runtime:20260518"
    exit 1
fi

log_info "检查脚本语法"
scripts=(
    "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
    "${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"
    "${REPO_DIR}/scripts_1/stop_unified_workflow.sh"
    "${REPO_DIR}/scripts_1/build_unified_runtime_image.sh"
    "${REPO_DIR}/scripts/build_unitree_g1_tts_bridge.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/one_click_start.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/start_robot_stack_host.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/setup_inspire_sudo_nopasswd.sh"
)
for script in "${scripts[@]}"; do
    bash -n "$script"
    log_ok "bash -n 通过：$script"
done

log_info "检查 Python 编译"
cd "${REPO_DIR}"
python3 -m py_compile \
    rabbitbot/control_console/app.py \
    rabbitbot/control_console/config.py \
    rabbitbot/control_console/commands.py \
    rabbitbot/agno_agents/workflow.py \
    rabbitbot/provider.py \
    rabbitbot/audio/unitree_g1_tts.py \
    robot_app.py memory_app.py tts_app.py
log_ok "Python 编译通过"

log_info "检查 sudoers 模板"
visudo -cf "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers"
log_ok "sudoers 模板语法通过"

log_info "检查 air ROS 工作区解析"
custom_lib="$(
    bash -lc "set +u; source /opt/ros/humble/setup.bash; export COLCON_CURRENT_PREFIX='${PROJECTS_DIR}/custom_action_ws/install'; source '${PROJECTS_DIR}/custom_action_ws/install/setup.bash'; set -u; ldd '${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation66' | awk '/libcustom_action_interfaces__rosidl_typesupport_cpp.so/ {print \$3; exit}'"
)"
case "$custom_lib" in
    "${PROJECTS_DIR}/custom_action_ws/install"/*)
        log_ok "custom_action_interfaces 动态库解析到 air 目录：$custom_lib"
        ;;
    *)
        log_error "custom_action_interfaces 动态库未解析到 air 目录：${custom_lib:-未找到}"
        exit 1
        ;;
esac

log_info "检查旧路径硬编码"
if grep -RIn "/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master" \
    "${REPO_DIR}/rabbitbot" "${REPO_DIR}/scripts" "${REPO_DIR}/scripts_1" "${REPO_DIR}/deploy" \
    --exclude-dir=__pycache__ --exclude='*.pyc'; then
    log_error "仍存在旧项目根硬编码，请先处理。"
    exit 1
fi
if grep -RIn "/mnt/ssd/navgation/projects/" \
    "${PROJECTS_DIR}/unitree_slam_example_new/example"/*.sh \
    --exclude='*.bak' --exclude='*.bak_*' | grep -v "/mnt/ssd/navgation/projects/air_robot_gt_projects"; then
    log_error "unitree_slam 示例运行脚本仍存在旧 projects 路径硬编码，请先处理。"
    exit 1
fi
log_ok "未发现运行脚本旧项目根硬编码"

log_ok "air_robot_gt_projects 自检完成"

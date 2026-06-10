#!/usr/bin/env bash
# 检查 air_robot_gt_projects 自主运行项目的关键文件、环境和语法。

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
for script in     "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"     "${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"     "${REPO_DIR}/scripts_1/stop_unified_workflow.sh"     "${REPO_DIR}/scripts_1/build_unified_runtime_image.sh"     "${REPO_DIR}/scripts/build_unitree_g1_tts_bridge.sh"     "${PROJECTS_DIR}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"; do
    bash -n "$script"
    log_ok "bash -n 通过：$script"
done

log_info "检查 Python 编译"
cd "${REPO_DIR}"
python3 -m py_compile     rabbitbot/control_console/app.py     rabbitbot/control_console/config.py     rabbitbot/control_console/commands.py     rabbitbot/agno_agents/workflow.py     rabbitbot/provider.py     rabbitbot/audio/unitree_g1_tts.py     robot_app.py memory_app.py tts_app.py
log_ok "Python 编译通过"

log_info "检查 sudoers 模板"
visudo -cf "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers"
log_ok "sudoers 模板语法通过"

log_info "检查旧路径硬编码"
if grep -RIn "/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master"     "${REPO_DIR}/rabbitbot" "${REPO_DIR}/scripts" "${REPO_DIR}/scripts_1" "${REPO_DIR}/deploy"     --exclude-dir=__pycache__ --exclude='*.pyc'; then
    log_error "仍存在旧项目根硬编码，请先处理。"
    exit 1
fi
log_ok "未发现旧项目根硬编码"

log_ok "air_robot_gt_projects 自检完成"

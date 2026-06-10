#!/usr/bin/env bash
# 安装 air_robot_gt_projects 的 systemd 服务和控制台 sudoers 授权。
# 本脚本不会启动导航主程序，也不会启用开机自启。

set -euo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
RESTART_CONTROL_CONSOLE="${RESTART_CONTROL_CONSOLE:-1}"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
}

require_path "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
require_path "${REPO_DIR}/deploy/rabbitbot-control-console.service"
require_path "${REPO_DIR}/scripts_1/systemd/rabbitbot-loop.service"
require_path "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers"
require_path "${AIR_ROOT}/models"
require_path "${AIR_ROOT}/custom_action_ws/install/setup.bash"
require_path "${AIR_ROOT}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"

if ! docker image inspect rabbitbot-unified-runtime:20260518 >/dev/null 2>&1; then
    log_error "Docker 镜像不存在：rabbitbot-unified-runtime:20260518"
    exit 1
fi

visudo -cf "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers"

log_info "停止旧的 rabbitbot-loop.service（如正在运行）"
"${SUDO[@]}" systemctl stop rabbitbot-loop.service 2>/dev/null || true

log_info "安装 systemd unit"
"${SUDO[@]}" install -m 0644 "${REPO_DIR}/scripts_1/systemd/rabbitbot-loop.service" /etc/systemd/system/rabbitbot-loop.service
"${SUDO[@]}" install -m 0644 "${REPO_DIR}/deploy/rabbitbot-control-console.service" /etc/systemd/system/rabbitbot-control-console.service

log_info "安装控制台 sudoers 授权"
"${SUDO[@]}" install -m 0440 "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers" /etc/sudoers.d/rabbitbot-control-console
"${SUDO[@]}" visudo -cf /etc/sudoers.d/rabbitbot-control-console

log_info "刷新 systemd 并保持服务非开机自启"
"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl disable rabbitbot-loop.service rabbitbot-control-console.service >/dev/null 2>&1 || true

if [ "${RESTART_CONTROL_CONSOLE}" = "1" ]; then
    log_info "重启控制台服务，使其加载 air 项目路径"
    "${SUDO[@]}" systemctl restart rabbitbot-control-console.service
else
    log_info "RESTART_CONTROL_CONSOLE=${RESTART_CONTROL_CONSOLE}，不重启控制台服务"
fi

log_ok "安装完成。导航主程序未启动，开机自启未启用。"
systemctl is-enabled rabbitbot-loop.service rabbitbot-control-console.service 2>/dev/null || true
systemctl is-active rabbitbot-loop.service rabbitbot-control-console.service 2>/dev/null || true

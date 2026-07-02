#!/usr/bin/env bash
# 安装 air_robot_gt_projects 的 systemd 服务和控制台 sudoers 授权。
# 本脚本不会启动导航主程序，也不会启用开机自启；portable / legacy 两条路径共用相同服务名，具体由 runtime/portable.env 控制。

set -euo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
RESTART_CONTROL_CONSOLE="${RESTART_CONTROL_CONSOLE:-1}"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
SERVICE_USER="${RABBITBOT_SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${RABBITBOT_SERVICE_GROUP:-$(id -gn "${SERVICE_USER}")}"
GENERATED_DIR=""

if [ "$(id -u)" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
}

require_path "${REPO_DIR}/scripts_1/start_loop_entry.sh"
require_path "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
require_path "${REPO_DIR}/scripts_1/start_nav_bridge_portable.sh"
require_path "${REPO_DIR}/scripts_1/start_control_console.sh"
require_path "${AIR_ROOT}/deploy/bootstrap_host.sh"
# systemd 通过 EnvironmentFile 加载本机 portable.env；该文件不进入 Git，必须先由 bootstrap 生成。
if [ ! -f "${PORTABLE_ENV_FILE}" ]; then
    log_error "缺少本机运行配置：${PORTABLE_ENV_FILE}。该文件不随仓库迁移，请先执行 deploy/bootstrap_host.sh 在本机生成后再安装 systemd 服务。"
    exit 1
fi

runtime_mode="$(sed -n 's/^RABBITBOT_RUNTIME_MODE=//p' "${PORTABLE_ENV_FILE}" | tail -n 1)"
log_info "准备安装 systemd 服务：runtime_mode=${runtime_mode:-未设置}, user=${SERVICE_USER}, group=${SERVICE_GROUP}, repo=${REPO_DIR}"
if [ "${runtime_mode:-}" = "portable" ]; then
    log_info "当前将通过 runtime/portable.env 让 rabbitbot-loop.service 使用 portable 入口。"
else
    require_path "${AIR_ROOT}/models"
    require_path "${AIR_ROOT}/custom_action_ws/install/setup.bash"
    require_path "${AIR_ROOT}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"
fi


generate_install_templates() {
    GENERATED_DIR="$(mktemp -d)"
    trap 'if [ -n "${GENERATED_DIR}" ]; then rm -rf "${GENERATED_DIR}"; fi' EXIT

    log_info "生成本机 systemd / sudoers 模板：dir=${GENERATED_DIR}, user=${SERVICE_USER}, group=${SERVICE_GROUP}"
    cat >"${GENERATED_DIR}/rabbitbot-loop.service" <<UNIT
[Unit]
Description=RabbitBot Loop 导航桥接与导览 workflow 待命循环
Documentation=file:${AIR_ROOT}/HANDOFF_REPORT.md
After=docker.service network-online.target
Wants=docker.service network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/scripts_1/start_loop_entry.sh
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30
SyslogIdentifier=rabbitbot-loop
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${REPO_DIR}/runtime/rabbitbot-loop.env
EnvironmentFile=-${REPO_DIR}/runtime/portable.env

[Install]
WantedBy=multi-user.target
UNIT

    cat >"${GENERATED_DIR}/rabbitbot-control-console.service" <<UNIT
[Unit]
Description=RabbitBot LAN Control Console
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${REPO_DIR}
Environment=RABBITBOT_CONSOLE_HOST=0.0.0.0
Environment=RABBITBOT_CONSOLE_PORT=8080
Environment=RABBITBOT_PROJECT_ROOT=${REPO_DIR}
EnvironmentFile=-${REPO_DIR}/runtime/portable.env
ExecStart=/bin/bash ${REPO_DIR}/scripts_1/start_control_console.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

    cat >"${GENERATED_DIR}/rabbitbot-control-console.sudoers" <<SUDOERS
# 允许局域网控制台只管理 RabbitBot 主循环服务。
${SERVICE_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl start rabbitbot-loop.service, /usr/bin/systemctl restart rabbitbot-loop.service, /usr/bin/systemctl stop rabbitbot-loop.service
SUDOERS

    visudo -cf "${GENERATED_DIR}/rabbitbot-control-console.sudoers"
    log_ok "本机 sudoers 模板语法通过：${GENERATED_DIR}/rabbitbot-control-console.sudoers"
}

generate_install_templates

log_info "停止旧的 rabbitbot-loop.service（如正在运行）"
"${SUDO[@]}" systemctl stop rabbitbot-loop.service 2>/dev/null || true

log_info "安装 systemd unit"
"${SUDO[@]}" install -m 0644 "${GENERATED_DIR}/rabbitbot-loop.service" /etc/systemd/system/rabbitbot-loop.service
"${SUDO[@]}" install -m 0644 "${GENERATED_DIR}/rabbitbot-control-console.service" /etc/systemd/system/rabbitbot-control-console.service

log_info "安装控制台 sudoers 授权"
"${SUDO[@]}" install -m 0440 "${GENERATED_DIR}/rabbitbot-control-console.sudoers" /etc/sudoers.d/rabbitbot-control-console
"${SUDO[@]}" visudo -cf /etc/sudoers.d/rabbitbot-control-console

log_info "刷新 systemd 并保持服务非开机自启"
"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl disable rabbitbot-loop.service rabbitbot-control-console.service >/dev/null 2>&1 || true

if [ "${RESTART_CONTROL_CONSOLE}" = "1" ]; then
    log_info "重启控制台服务，使其加载最新 portable / legacy 配置"
    "${SUDO[@]}" systemctl restart rabbitbot-control-console.service
else
    log_info "RESTART_CONTROL_CONSOLE=${RESTART_CONTROL_CONSOLE}，不重启控制台服务"
fi

log_ok "安装完成。导航主程序未启动，开机自启未启用。"
systemctl is-enabled rabbitbot-loop.service rabbitbot-control-console.service 2>/dev/null || true
systemctl is-active rabbitbot-loop.service rabbitbot-control-console.service 2>/dev/null || true

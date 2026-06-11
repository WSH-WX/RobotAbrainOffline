#!/usr/bin/env bash
set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
fi

DDS_INTERFACE="${RABBITBOT_DDS_INTERFACE:-${1:-eno1}}"
DDS_HOST_CIDR="${RABBITBOT_DDS_HOST_CIDR:-${2:-192.168.123.222/24}}"
CONNECTION_NAME="${RABBITBOT_DDS_CONNECTION_NAME:-rabbitbot-dds-${DDS_INTERFACE}}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if ! command -v nmcli >/dev/null 2>&1; then
    log_error "当前主机未找到 nmcli，无法写入持久网卡配置。"
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi
if ! ip link show dev "${DDS_INTERFACE}" >/dev/null 2>&1; then
    log_error "指定网卡不存在：${DDS_INTERFACE}"
    exit 1
fi

log_info "开始配置机器人 DDS 网卡：interface=${DDS_INTERFACE}, cidr=${DDS_HOST_CIDR}, connection=${CONNECTION_NAME}"
if nmcli -g NAME connection show | grep -Fxq "${CONNECTION_NAME}"; then
    log_info "复用已有 NetworkManager 连接：${CONNECTION_NAME}"
else
    "${SUDO[@]}" nmcli connection add type ethernet ifname "${DDS_INTERFACE}" con-name "${CONNECTION_NAME}" autoconnect yes >/dev/null
    log_info "已创建新的 NetworkManager 连接：${CONNECTION_NAME}"
fi

"${SUDO[@]}" nmcli connection modify "${CONNECTION_NAME}" ipv4.method manual ipv4.addresses "${DDS_HOST_CIDR}" ipv6.method ignore connection.autoconnect yes >/dev/null
"${SUDO[@]}" nmcli connection up "${CONNECTION_NAME}" >/dev/null
log_ok "机器人 DDS 网卡配置完成：interface=${DDS_INTERFACE}, cidr=${DDS_HOST_CIDR}"

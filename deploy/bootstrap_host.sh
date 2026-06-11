#!/usr/bin/env bash
set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
CONTROL_CONSOLE_VENV="${REPO_DIR}/runtime/control_console_venv"
MODELS_CACHE_DIR_DEFAULT="${AIR_ROOT}/models"
DDS_INTERFACE_DEFAULT="${RABBITBOT_DDS_INTERFACE:-eno1}"
DDS_HOST_CIDR_DEFAULT="${RABBITBOT_DDS_HOST_CIDR:-192.168.123.222/24}"
NAV_MAP_PATH_DEFAULT="${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}"
APPLY_ROBOT_NETWORK="${APPLY_ROBOT_NETWORK:-0}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log_error "缺少必要命令：$1"
        exit 1
    fi
    log_ok "已找到命令：$1"
}

upsert_env() {
    local key="$1"
    local value="$2"
    local file="$3"
    python3 - "$key" "$value" "$file" <<'PY'
import pathlib
import re
import sys
key, value, path = sys.argv[1:4]
file_path = pathlib.Path(path)
text = file_path.read_text(encoding='utf-8') if file_path.exists() else ''
pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
line = f"{key}={value}\n"
if pattern.search(text):
    text = pattern.sub(line.rstrip('\n'), text)
    if not text.endswith('\n'):
        text += '\n'
else:
    if text and not text.endswith('\n'):
        text += '\n'
    text += line
file_path.write_text(text, encoding='utf-8')
PY
}

log_info "开始初始化 portable 宿主环境：air_root=${AIR_ROOT}"
require_command git
require_command docker
require_command python3
if ! docker compose version >/dev/null 2>&1; then
    log_error "当前 docker 不支持 compose 子命令，请先安装 Docker Compose 插件。"
    exit 1
fi
log_ok "docker compose 可用"

mkdir -p "${REPO_DIR}/runtime" "${AIR_ROOT}/unitree_slam_example_new/example/run_logs" "${REPO_DIR}/logs/nav_workflow_control"
upsert_env "RABBITBOT_DDS_INTERFACE" "${DDS_INTERFACE_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_DDS_HOST_CIDR" "${DDS_HOST_CIDR_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_NAV_MAP_PATH" "${NAV_MAP_PATH_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_MODELS_CACHE_DIR" "${RABBITBOT_MODELS_CACHE_DIR:-${MODELS_CACHE_DIR_DEFAULT}}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_PORTABLE_COMPOSE_FILE" "${REPO_DIR}/docker/portable/compose.yaml" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_RUNTIME_MODE" "portable" "${PORTABLE_ENV_FILE}"

log_info "准备轻量控制台虚拟环境：venv=${CONTROL_CONSOLE_VENV}"
python3 -m venv "${CONTROL_CONSOLE_VENV}"
"${CONTROL_CONSOLE_VENV}/bin/pip" install --upgrade pip >/dev/null
"${CONTROL_CONSOLE_VENV}/bin/pip" install -r "${AIR_ROOT}/deploy/portable_host_requirements.txt" >/dev/null
log_ok "控制台轻量虚拟环境已就绪"

if [ "${APPLY_ROBOT_NETWORK}" = "1" ]; then
    log_info "根据 portable env 配置机器人 DDS 网卡"
    "${AIR_ROOT}/deploy/setup_robot_network.sh"
else
    log_warn "未自动配置机器人 DDS 网卡；如需写入持久网络配置，请设置 APPLY_ROBOT_NETWORK=1 后重新执行。"
fi

log_ok "portable 宿主初始化完成：env=${PORTABLE_ENV_FILE}, venv=${CONTROL_CONSOLE_VENV}"

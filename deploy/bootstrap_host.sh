#!/usr/bin/env bash
set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
PORTABLE_ENV_EXAMPLE_FILE="${PORTABLE_ENV_FILE}.example"
CONTROL_CONSOLE_VENV="${REPO_DIR}/runtime/control_console_venv"
MODELS_CACHE_DIR_DEFAULT="${AIR_ROOT}/models"
DDS_INTERFACE_DEFAULT="${RABBITBOT_DDS_INTERFACE:-eno1}"
DDS_HOST_CIDR_DEFAULT="${RABBITBOT_DDS_HOST_CIDR:-192.168.123.222/24}"
NAV_MAP_PATH_DEFAULT="${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}"
APPLY_ROBOT_NETWORK="${APPLY_ROBOT_NETWORK:-0}"
# INSTALL_HOST_PACKAGES=1 时，允许本脚本通过 sudo apt-get 自动安装缺失的宿主依赖（当前仅 venv 能力）。
INSTALL_HOST_PACKAGES="${INSTALL_HOST_PACKAGES:-0}"

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

venv_probe() {
    # 功能性探测：实际创建一个临时 venv。仅检查 venv 模块存在不可靠——
    # Ubuntu 缺 python3-venv 时 venv 模块仍在，但 ensurepip 缺失导致创建失败。
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    if python3 -m venv "${tmp_dir}/venv_probe" >/dev/null 2>&1; then
        rm -rf "${tmp_dir}"
        return 0
    fi
    rm -rf "${tmp_dir}"
    return 1
}

ensure_python_venv_capability() {
    local python_version python_minor venv_packages
    python_version="$(python3 -V 2>&1)"
    python_minor="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    venv_packages="python3-venv python${python_minor}-venv"

    if venv_probe; then
        log_ok "python3 -m venv 可用：${python_version}"
        return 0
    fi

    if [ "${INSTALL_HOST_PACKAGES}" != "1" ]; then
        log_error "python3 -m venv 不可用：python=${python_version}，自动安装未启用（INSTALL_HOST_PACKAGES=${INSTALL_HOST_PACKAGES}）。"
        log_error "下一步：手动执行 sudo apt-get update && sudo apt-get install -y ${venv_packages}；或运行 INSTALL_HOST_PACKAGES=1 bash deploy/bootstrap_host.sh 自动安装。"
        exit 1
    fi

    local sudo_cmd=()
    if [ "$(id -u)" -ne 0 ]; then
        sudo_cmd=(sudo)
    fi
    log_warn "python3 -m venv 不可用，按 INSTALL_HOST_PACKAGES=1 尝试自动安装：python=${python_version}, packages=${venv_packages}"
    if ! "${sudo_cmd[@]}" apt-get update; then
        log_error "自动安装失败：apt-get update 失败（sudo=${sudo_cmd[*]:-无}）。请检查 apt 源与网络后重试，或手动安装 ${venv_packages}。"
        exit 1
    fi
    # python3-venv 为元包；同时装版本化包，避免个别系统元包未指向当前默认 Python。
    if ! "${sudo_cmd[@]}" apt-get install -y python3-venv "python${python_minor}-venv"; then
        log_error "自动安装失败：apt-get install -y ${venv_packages} 失败。请手动安装后重试。"
        exit 1
    fi
    if ! venv_probe; then
        log_error "已安装 ${venv_packages}，但 python3 -m venv 仍不可用：python=${python_version}。请检查 Python 安装是否完整（ensurepip 是否存在）。"
        exit 1
    fi
    log_ok "venv 依赖已自动安装并验证可用：packages=${venv_packages}"
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
ensure_python_venv_capability

mkdir -p "${REPO_DIR}/runtime" "${AIR_ROOT}/unitree_slam_example_new/example/run_logs" "${REPO_DIR}/logs/nav_workflow_control"

# 本机 portable.env 不进入 Git：不存在时先从随仓库迁移的模板复制生成，再增量写入本机配置。
if [ ! -f "${PORTABLE_ENV_FILE}" ]; then
    if [ -f "${PORTABLE_ENV_EXAMPLE_FILE}" ]; then
        cp "${PORTABLE_ENV_EXAMPLE_FILE}" "${PORTABLE_ENV_FILE}"
        log_info "未发现本机 portable.env，已从模板生成：${PORTABLE_ENV_EXAMPLE_FILE} -> ${PORTABLE_ENV_FILE}"
    else
        log_warn "模板 ${PORTABLE_ENV_EXAMPLE_FILE} 不存在（仓库可能不完整），将仅以增量写入方式生成最小 portable.env：${PORTABLE_ENV_FILE}"
    fi
else
    log_info "本机 portable.env 已存在，保留现有内容并增量更新本机配置：${PORTABLE_ENV_FILE}"
fi

upsert_env "RABBITBOT_DDS_INTERFACE" "${DDS_INTERFACE_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_DDS_HOST_CIDR" "${DDS_HOST_CIDR_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_NAV_MAP_PATH" "${NAV_MAP_PATH_DEFAULT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_PROJECTS_DIR" "${AIR_ROOT}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_MODELS_CACHE_DIR" "${RABBITBOT_MODELS_CACHE_DIR:-${MODELS_CACHE_DIR_DEFAULT}}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_PORTABLE_COMPOSE_FILE" "${REPO_DIR}/docker/portable/compose.yaml" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_RUNTIME_MODE" "portable" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_ENABLE_VLM" "${RABBITBOT_ENABLE_VLM:-1}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_ENABLE_EMBEDDING" "${RABBITBOT_ENABLE_EMBEDDING:-1}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_ENABLE_STT" "${RABBITBOT_ENABLE_STT:-1}" "${PORTABLE_ENV_FILE}"
upsert_env "RABBITBOT_AUTO_DOWNLOAD_MODELS" "${RABBITBOT_AUTO_DOWNLOAD_MODELS:-1}" "${PORTABLE_ENV_FILE}"
# portable 端口拓扑：28180 归属 nav bridge，core 不启动 robot_app.py。
upsert_env "RABBITBOT_UNIFIED_START_ROBOT_AGENT" "${RABBITBOT_UNIFIED_START_ROBOT_AGENT:-0}" "${PORTABLE_ENV_FILE}"

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

#!/usr/bin/env bash
set -Eeuo pipefail

DDS_INTERFACE="${1:-${RABBITBOT_DDS_INTERFACE:-eno1}}"
NAV_MAP_PATH="${2:-${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
AIR_ROOT="$(cd "${PROJECT_DIR}/.." && pwd)"
PORTABLE_ENV_FILE="${RABBITBOT_PORTABLE_ENV_FILE:-${PROJECT_DIR}/runtime/portable.env}"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
fi

COMPOSE_FILE="${RABBITBOT_PORTABLE_COMPOSE_FILE:-${PROJECT_DIR}/docker/portable/compose.yaml}"
COMPOSE_PROJECT="${RABBITBOT_PORTABLE_COMPOSE_PROJECT:-rabbitbot-portable}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"

log_info() { echo "[INFO] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if ! command -v docker >/dev/null 2>&1; then
    log_error "未找到 docker，无法启动 portable nav 服务"
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    log_error "当前 docker 不支持 compose 子命令，无法启动 portable nav 服务"
    exit 1
fi
if [ ! -f "${COMPOSE_FILE}" ]; then
    log_error "portable compose 文件不存在：${COMPOSE_FILE}"
    exit 1
fi

export RABBITBOT_AIR_ROOT="${AIR_ROOT}"
export RABBITBOT_PROJECT_ROOT="${PROJECT_DIR}"
export RABBITBOT_DDS_INTERFACE="${DDS_INTERFACE}"
export RABBITBOT_NAV_MAP_PATH="${NAV_MAP_PATH}"
export RABBITBOT_PORTABLE_NAV_IMAGE="${NAV_IMAGE}"

log_info "以前台方式启动 portable nav：project=${COMPOSE_PROJECT}, compose=${COMPOSE_FILE}, image=${NAV_IMAGE}, interface=${DDS_INTERFACE}, map=${NAV_MAP_PATH}"
exec docker compose -f "${COMPOSE_FILE}" --project-name "${COMPOSE_PROJECT}" up --force-recreate --remove-orphans rabbitbot-nav

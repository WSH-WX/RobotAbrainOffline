#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORTABLE_ENV_FILE="${RABBITBOT_PORTABLE_ENV_FILE:-${PROJECT_DIR}/runtime/portable.env}"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
fi

RUNTIME_MODE="${RABBITBOT_RUNTIME_MODE:-legacy}"
if [ "${RUNTIME_MODE}" = "portable" ]; then
    export RABBITBOT_NAV_RUNTIME="${RABBITBOT_NAV_RUNTIME:-compose}"
    export NAV_INTERFACE="${NAV_INTERFACE:-${RABBITBOT_DDS_INTERFACE:-eno1}}"
    export NAV_PCD_PATH="${NAV_PCD_PATH:-${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}}"
    export IMAGE_NAME="${IMAGE_NAME:-${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}}"
    export CONTAINER_NAME="${CONTAINER_NAME:-${RABBITBOT_PORTABLE_CORE_CONTAINER_NAME:-rabbitbot-unified-runtime}}"
    export RABBITBOT_UNIFIED_START_VLM="${RABBITBOT_UNIFIED_START_VLM:-${RABBITBOT_ENABLE_VLM:-0}}"
    export RABBITBOT_UNIFIED_START_STT="${RABBITBOT_UNIFIED_START_STT:-${RABBITBOT_ENABLE_STT:-0}}"
    export NAV_BRIDGE_SCRIPT="${NAV_BRIDGE_SCRIPT:-${PROJECT_DIR}/scripts_1/start_nav_bridge_portable.sh}"
    echo "[INFO] 使用 portable 模式启动主循环：image=${IMAGE_NAME}, nav_script=${NAV_BRIDGE_SCRIPT}, interface=${NAV_INTERFACE}, map=${NAV_PCD_PATH}"
else
    echo "[INFO] 使用 legacy 模式启动主循环"
fi

exec "${PROJECT_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"

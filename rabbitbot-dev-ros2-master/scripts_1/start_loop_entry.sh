#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORTABLE_ENV_FILE="${RABBITBOT_PORTABLE_ENV_FILE:-${PROJECT_DIR}/runtime/portable.env}"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
elif [ -f "${PORTABLE_ENV_FILE}.example" ]; then
    # 本机 portable.env 不进入 Git；不存在时回退读取随仓库迁移的模板，保证只读校验类场景可用。
    echo "[WARN] 未找到本机配置 ${PORTABLE_ENV_FILE}，回退读取模板 ${PORTABLE_ENV_FILE}.example；正式部署请先执行 deploy/bootstrap_host.sh 生成本机 portable.env。"
    set -a
    source "${PORTABLE_ENV_FILE}.example"
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
    # portable 端口拓扑：core 不启动 robot_app.py；28180 由 nav bridge 提供（主循环先启动 nav bridge，再复用/启动 core，最后预启动 workflow）。
    export RABBITBOT_UNIFIED_START_ROBOT_AGENT="${RABBITBOT_UNIFIED_START_ROBOT_AGENT:-0}"
    export RABBITBOT_ROBOT_AGENT_URL="${RABBITBOT_ROBOT_AGENT_URL:-http://127.0.0.1:28180}"
    export NAV_BRIDGE_SCRIPT="${NAV_BRIDGE_SCRIPT:-${PROJECT_DIR}/scripts_1/start_nav_bridge_portable.sh}"
    echo "[INFO] 使用 portable 模式启动主循环：image=${IMAGE_NAME}, nav_script=${NAV_BRIDGE_SCRIPT}, interface=${NAV_INTERFACE}, map=${NAV_PCD_PATH}, core_robot_agent=${RABBITBOT_UNIFIED_START_ROBOT_AGENT}"
else
    echo "[INFO] 使用 legacy 模式启动主循环"
fi

exec "${PROJECT_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"

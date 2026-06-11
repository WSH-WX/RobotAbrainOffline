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

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }

# 镜像来源：默认 local，表示镜像来自本机构建或离线导入；此时只校验本地镜像存在，不访问远端仓库。
# 构建机若要现场构建可显式传入 MODE=build；全新 Orin 默认走 check。
log_info "开始启动 portable 基础服务：image_source=${RABBITBOT_IMAGE_SOURCE:-local}, core=${RABBITBOT_PORTABLE_CORE_IMAGE:-未设置}"
"${AIR_ROOT}/deploy/build_or_pull_images.sh"
(
    cd "${REPO_DIR}"
    RABBITBOT_RUNTIME_MODE=portable \
    RABBITBOT_PORTABLE_INJECT_DEPS="${RABBITBOT_PORTABLE_INJECT_DEPS:-1}" \
    IMAGE_NAME="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}" \
    CONTAINER_NAME="${RABBITBOT_PORTABLE_CORE_CONTAINER_NAME:-rabbitbot-unified-runtime}" \
    RUN_WORKFLOW_AFTER_START=0 \
    RABBITBOT_WORKFLOW_NON_INTEGRATION=0 \
    RABBITBOT_WORKFLOW_VERBOSE=0 \
    RABBITBOT_UNIFIED_START_VLM="${RABBITBOT_ENABLE_VLM:-0}" \
    RABBITBOT_UNIFIED_START_STT="${RABBITBOT_ENABLE_STT:-0}" \
    bash scripts_1/start_unified_integration_workflow.sh
)
log_ok "portable core 基础服务已完成启动检查；如需待命循环，请启动 rabbitbot-loop.service 或执行 scripts_1/start_loop_entry.sh"

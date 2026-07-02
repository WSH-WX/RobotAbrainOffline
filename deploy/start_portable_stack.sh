#!/usr/bin/env bash
set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"

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

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

ensure_models() {
    local targets=("$@")
    if [ "${#targets[@]}" -eq 0 ]; then
        log_warn "未传入模型键，跳过模型检查"
        return 0
    fi
    local models_dir="${RABBITBOT_MODELS_CACHE_DIR:-${AIR_ROOT}/models}"
    local start_ts elapsed
    mkdir -p "${models_dir}"
    start_ts="$(date +%s)"
    log_info "开始检查/下载 portable 基础服务模型：targets=${targets[*]}, models_dir=${models_dir}"
    RABBITBOT_MODELS_CACHE_DIR="${models_dir}" "${AIR_ROOT}/deploy/ensure_models.sh" "${targets[@]}"
    elapsed=$(( $(date +%s) - start_ts ))
    log_ok "portable 基础服务模型检查完成：targets=${#targets[@]}, elapsed=${elapsed}s"
}

# 镜像来源：默认 local，表示镜像来自本机构建或离线导入；此时只校验本地镜像存在，不访问远端仓库。
# 构建机若要现场构建可显式传入 MODE=build；全新 Orin 默认走 check。
log_info "开始启动 portable 基础服务：base_runtime=${RABBITBOT_BASE_RUNTIME:-unified}, image_source=${RABBITBOT_IMAGE_SOURCE:-local}, core=${RABBITBOT_PORTABLE_CORE_IMAGE:-未设置}"
"${AIR_ROOT}/deploy/build_or_pull_images.sh"
if [ "${RABBITBOT_BASE_RUNTIME:-unified}" = "compose" ]; then
    # 解耦栈：用 docker compose 拉起 neo4j + 四个 rabbitbot 基础容器（与 loop 的 ensure_decoupled_services 保持一致）。
    # 不含 rabbitbot-navbridge：28180 由 nav bridge 按 nav 先行的顺序在 start_loop_entry.sh 中启动。
    # neo4j 官方镜像需已 import(离线) 或可自动 pull(联网)；缺失时 compose 会给出明确报错。
    COMPOSE_FILE="${RABBITBOT_DECOUPLED_COMPOSE_FILE:-${REPO_DIR}/docker/portable/docker-compose.decoupled.yaml}"
    if [ ! -f "${COMPOSE_FILE}" ]; then
        echo "[ERROR] 缺少解耦 compose 文件：${COMPOSE_FILE}" >&2
        exit 1
    fi
    ensure_models qwen_vlm qwen_embedding sensevoice
    log_info "解耦栈启动基础服务（compose）：file=${COMPOSE_FILE}"
    ( cd "$(dirname "${COMPOSE_FILE}")" && docker compose -f "${COMPOSE_FILE}" up -d neo4j rabbitbot-vlm rabbitbot-audio rabbitbot-memory rabbitbot-workflow )
    log_ok "解耦栈基础服务已拉起（neo4j/vlm/audio/memory/workflow，不含 28180 nav bridge）；如需待命循环与 nav bridge，请启动 rabbitbot-loop.service 或执行 scripts_1/start_loop_entry.sh"
else
    (
        cd "${REPO_DIR}"
        RABBITBOT_RUNTIME_MODE=portable \
        RABBITBOT_PORTABLE_INJECT_DEPS="${RABBITBOT_PORTABLE_INJECT_DEPS:-1}" \
        IMAGE_NAME="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}" \
        CONTAINER_NAME="${RABBITBOT_PORTABLE_CORE_CONTAINER_NAME:-rabbitbot-unified-runtime}" \
        RUN_WORKFLOW_AFTER_START=0 \
        RABBITBOT_WORKFLOW_NON_INTEGRATION=0 \
        RABBITBOT_WORKFLOW_VERBOSE=0 \
        RABBITBOT_UNIFIED_START_VLM="${RABBITBOT_ENABLE_VLM:-1}" \
        RABBITBOT_UNIFIED_START_EMBEDDING="${RABBITBOT_ENABLE_EMBEDDING:-1}" \
        RABBITBOT_UNIFIED_START_STT="${RABBITBOT_ENABLE_STT:-1}" \
        RABBITBOT_UNIFIED_START_ROBOT_AGENT="${RABBITBOT_UNIFIED_START_ROBOT_AGENT:-0}" \
        bash scripts_1/start_unified_integration_workflow.sh
    )
    # portable 端口拓扑：unified 单容器只负责 core 基础服务（7687/28182/28185），不要求 28180 就绪；
    # 28180 由 nav bridge 提供，统一在 start_loop_entry.sh（nav 先行）中启动。
    log_ok "portable core 基础服务已完成启动检查（不含 28180）；如需待命循环与 nav bridge，请启动 rabbitbot-loop.service 或执行 scripts_1/start_loop_entry.sh"
fi

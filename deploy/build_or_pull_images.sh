#!/usr/bin/env bash
# 准备 portable core / nav 镜像。
#
# MODE 取值：
#   build  在构建机上构建 core/nav 镜像（core 使用专用暂存上下文，烤入 py38/py310/vln/pyorbbecsdk）。
#   check  只校验本地已存在 core/nav 镜像，用于全新 Orin（不构建、不拉取）。
#   none   跳过镜像准备，由启动脚本自行校验。
#   pull   仅尝试从镜像仓库拉取 core/nav。
#   both   先尝试拉取，失败再构建（兼容旧行为）。
#
# 当 runtime/portable.env 中 RABBITBOT_IMAGE_SOURCE=local 且未显式传入 MODE 时，默认进入 check 模式，
# 表示镜像来自本机构建或离线导入，不尝试访问远端仓库。

set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
fi

IMAGE_SOURCE="${RABBITBOT_IMAGE_SOURCE:-local}"
if [ -n "${MODE:-}" ]; then
    MODE="${MODE}"
elif [ "${IMAGE_SOURCE}" = "local" ]; then
    MODE="check"
else
    MODE="both"
fi

CORE_IMAGE="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"
CORE_BASE_IMAGE="${RABBITBOT_PORTABLE_CORE_BASE_IMAGE:-rabbitbot-unified-runtime:20260518}"
BUILD_CORE="${RABBITBOT_PORTABLE_BUILD_CORE:-1}"
BUILD_NAV="${RABBITBOT_PORTABLE_BUILD_NAV:-1}"
CORE_DOCKERFILE="${REPO_DIR}/docker/portable/core.Dockerfile"
NAV_DOCKERFILE="${REPO_DIR}/docker/portable/nav.Dockerfile"
CORE_BUILD_CTX="${AIR_ROOT}/.portable_core_ctx"

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

image_id() {
    docker image inspect "$1" --format '{{.Id}}' 2>/dev/null || true
}

pull_image_if_needed() {
    local image="$1"
    local label="$2"
    if docker image inspect "${image}" >/dev/null 2>&1; then
        log_ok "镜像已存在，跳过拉取：label=${label}, image=${image}"
        return 0
    fi
    log_info "尝试拉取镜像：label=${label}, image=${image}"
    docker pull "${image}"
    log_ok "镜像拉取完成：label=${label}, image=${image}"
}

check_image_present() {
    local image="$1"
    local label="$2"
    if docker image inspect "${image}" >/dev/null 2>&1; then
        log_ok "本地镜像存在：label=${label}, image=${image}, id=$(image_id "${image}")"
        return 0
    fi
    log_error "本地缺少 portable 镜像：label=${label}, image=${image}。请先在构建机执行 MODE=build 构建，或用 deploy/import_portable_images.sh 导入离线镜像。"
    return 1
}

prepare_core_build_context() {
    log_info "准备 core 专用构建上下文（绕过顶层 .dockerignore 对 py38/py310/vln/pyorbbecsdk 的排除）：ctx=${CORE_BUILD_CTX}"
    rm -rf "${CORE_BUILD_CTX}"
    mkdir -p "${CORE_BUILD_CTX}"
    require_path "${REPO_DIR}"
    require_path "${AIR_ROOT}/vln"
    require_path "${AIR_ROOT}/pyorbbecsdk-v2-py310"
    require_path "${AIR_ROOT}/humble_robot_agent_bridge.py"
    require_path "${REPO_DIR}/py38"
    require_path "${REPO_DIR}/py310"
    if ! command -v rsync >/dev/null 2>&1; then
        log_error "缺少 rsync，无法准备 core 构建上下文。请先安装 rsync。"
        exit 1
    fi
    # 使用 rsync 拷贝并排除缓存/日志/控制台 venv：
    # 这些文件可能由容器以 root 创建，硬链接会因 protected_hardlinks 失败，且本就不需要进入镜像。
    rsync -a \
        --exclude='__pycache__/' \
        --exclude='*.py[cod]' \
        --exclude='logs/' \
        --exclude='runtime/control_console_venv/' \
        --exclude='.portable_core_ctx/' \
        "${REPO_DIR}/" "${CORE_BUILD_CTX}/rabbitbot-dev-ros2-master/"
    rsync -a --exclude='__pycache__/' --exclude='*.py[cod]' "${AIR_ROOT}/vln/" "${CORE_BUILD_CTX}/vln/"
    rsync -a --exclude='__pycache__/' --exclude='*.py[cod]' "${AIR_ROOT}/pyorbbecsdk-v2-py310/" "${CORE_BUILD_CTX}/pyorbbecsdk-v2-py310/"
    cp -f "${AIR_ROOT}/humble_robot_agent_bridge.py" "${CORE_BUILD_CTX}/humble_robot_agent_bridge.py"
    cp -f "${CORE_DOCKERFILE}" "${CORE_BUILD_CTX}/core.Dockerfile"
    # core 上下文的 dockerignore：保留 py38/py310/vln/pyorbbecsdk，仅剔除日志、缓存和构建产物。
    cat >"${CORE_BUILD_CTX}/.dockerignore" <<'IGN'
**/__pycache__/
**/*.py[cod]
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/*.tmp
**/*.bak
**/*.bak_*
.DS_Store
rabbitbot-dev-ros2-master/logs/
rabbitbot-dev-ros2-master/runtime/control_console_venv/
rabbitbot-dev-ros2-master/__pycache__/
IGN
    log_ok "core 构建上下文准备完成：ctx=${CORE_BUILD_CTX}"
}

cleanup_core_build_context() {
    if [ -d "${CORE_BUILD_CTX}" ]; then
        rm -rf "${CORE_BUILD_CTX}"
        log_info "已清理 core 构建上下文：${CORE_BUILD_CTX}"
    fi
}

build_core_image() {
    if [ "${BUILD_CORE}" != "1" ]; then
        log_warn "已配置跳过 portable core 本地构建：BUILD_CORE=${BUILD_CORE}"
        return 0
    fi
    if ! docker image inspect "${CORE_BASE_IMAGE}" >/dev/null 2>&1; then
        log_error "缺少 portable core 基础镜像：${CORE_BASE_IMAGE}。该镜像是 unified runtime 合并产物，本机无法从零重建；请先恢复该基础镜像，或改用可导入的 portable core 成品镜像。"
        exit 1
    fi
    local start_ts="${SECONDS}"
    log_info "开始构建自包含 portable core 镜像：image=${CORE_IMAGE}, base=${CORE_BASE_IMAGE}"
    prepare_core_build_context
    trap cleanup_core_build_context RETURN
    docker build \
        -f "${CORE_BUILD_CTX}/core.Dockerfile" \
        --build-arg CORE_BASE_IMAGE="${CORE_BASE_IMAGE}" \
        -t "${CORE_IMAGE}" \
        "${CORE_BUILD_CTX}"
    cleanup_core_build_context
    trap - RETURN
    log_ok "portable core 镜像构建完成：image=${CORE_IMAGE}, id=$(image_id "${CORE_IMAGE}"), elapsed=$((SECONDS - start_ts))s"
}

build_nav_image() {
    if [ "${BUILD_NAV}" != "1" ]; then
        log_warn "已配置跳过 portable nav 本地构建：BUILD_NAV=${BUILD_NAV}"
        return 0
    fi
    require_path "${AIR_ROOT}/unitree_sdk2"
    require_path "${AIR_ROOT}/custom_action_ws/src/custom_action_interfaces"
    require_path "${AIR_ROOT}/unitree_slam_example_new/example"
    local start_ts="${SECONDS}"
    log_info "开始构建自包含 portable nav 镜像：image=${NAV_IMAGE}"
    docker build -f "${NAV_DOCKERFILE}" -t "${NAV_IMAGE}" "${AIR_ROOT}"
    log_ok "portable nav 镜像构建完成：image=${NAV_IMAGE}, id=$(image_id "${NAV_IMAGE}"), elapsed=$((SECONDS - start_ts))s"
}

log_info "开始准备 portable 镜像：mode=${MODE}, image_source=${IMAGE_SOURCE}, core=${CORE_IMAGE}, nav=${NAV_IMAGE}"
case "${MODE}" in
    none)
        log_warn "MODE=none，跳过镜像准备；由启动脚本自行校验本地镜像存在性。"
        ;;
    check)
        rc=0
        check_image_present "${CORE_IMAGE}" "portable_core" || rc=1
        check_image_present "${NAV_IMAGE}" "portable_nav" || rc=1
        if [ "${rc}" -ne 0 ]; then
            log_error "portable 镜像校验未通过：本机缺少必要镜像，无法继续冷启动。"
            exit 1
        fi
        log_ok "portable 镜像校验通过：core/nav 本地均存在"
        ;;
    pull)
        pull_image_if_needed "${CORE_IMAGE}" "portable_core"
        pull_image_if_needed "${NAV_IMAGE}" "portable_nav"
        ;;
    build)
        build_core_image
        build_nav_image
        ;;
    both)
        pull_image_if_needed "${CORE_IMAGE}" "portable_core" || build_core_image
        if ! docker image inspect "${NAV_IMAGE}" >/dev/null 2>&1; then
            build_nav_image
        else
            log_ok "portable nav 镜像已存在，跳过构建：${NAV_IMAGE}"
        fi
        ;;
    *)
        log_error "不支持的 MODE：${MODE}，仅支持 build/check/none/pull/both"
        exit 1
        ;;
esac

log_ok "portable 镜像准备完成：mode=${MODE}"

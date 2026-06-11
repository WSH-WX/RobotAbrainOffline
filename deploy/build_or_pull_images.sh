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

MODE="${MODE:-both}"
CORE_IMAGE="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"
CORE_BASE_IMAGE="${RABBITBOT_PORTABLE_CORE_BASE_IMAGE:-rabbitbot-unified-runtime:20260518}"
BUILD_CORE="${RABBITBOT_PORTABLE_BUILD_CORE:-0}"
BUILD_NAV="${RABBITBOT_PORTABLE_BUILD_NAV:-1}"

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

build_core_image() {
    if [ "${BUILD_CORE}" != "1" ]; then
        log_warn "已配置跳过 portable core 本地构建：BUILD_CORE=${BUILD_CORE}"
        return 0
    fi
    if ! docker image inspect "${CORE_BASE_IMAGE}" >/dev/null 2>&1; then
        log_error "缺少 portable core 基础镜像：${CORE_BASE_IMAGE}。请先拉取/恢复该镜像，或改用可拉取的 portable core 成品镜像。"
        exit 1
    fi
    log_info "开始构建 portable core 镜像：image=${CORE_IMAGE}, base=${CORE_BASE_IMAGE}"
    docker build -f "${REPO_DIR}/docker/portable/core.Dockerfile" --build-arg CORE_BASE_IMAGE="${CORE_BASE_IMAGE}" -t "${CORE_IMAGE}" "${AIR_ROOT}"
    log_ok "portable core 镜像构建完成：${CORE_IMAGE}"
}

build_nav_image() {
    if [ "${BUILD_NAV}" != "1" ]; then
        log_warn "已配置跳过 portable nav 本地构建：BUILD_NAV=${BUILD_NAV}"
        return 0
    fi
    require_path "${AIR_ROOT}/unitree_sdk2"
    require_path "${AIR_ROOT}/custom_action_ws/src/custom_action_interfaces"
    require_path "${AIR_ROOT}/unitree_slam_example_new/example"
    log_info "开始构建 portable nav 镜像：image=${NAV_IMAGE}"
    docker build -f "${REPO_DIR}/docker/portable/nav.Dockerfile" -t "${NAV_IMAGE}" "${AIR_ROOT}"
    log_ok "portable nav 镜像构建完成：${NAV_IMAGE}"
}

log_info "开始准备 portable 镜像：mode=${MODE}, core=${CORE_IMAGE}, nav=${NAV_IMAGE}"
case "${MODE}" in
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
        log_error "不支持的 MODE：${MODE}，仅支持 pull/build/both"
        exit 1
        ;;
 esac

log_ok "portable 镜像准备完成"

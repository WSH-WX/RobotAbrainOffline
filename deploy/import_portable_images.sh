#!/usr/bin/env bash
# 在全新 Orin 上导入 portable core / nav 离线镜像。
#
# 行为：
#   1. 校验 <IMAGE_DIR>/images.sha256 中记录的 tar 校验值。
#   2. 通过 docker load 导入镜像。
#   3. 确认导入后的 tag 与 runtime/portable.env 中的 core/nav 镜像 tag 一致。
#
# 用法：
#   IMAGE_DIR=/path/to/portable-images bash deploy/import_portable_images.sh

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

IMAGE_DIR="${IMAGE_DIR:-${AIR_ROOT}/outputs/portable-images}"
CORE_IMAGE="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if ! command -v docker >/dev/null 2>&1; then
    log_error "未找到 docker，无法导入镜像。"
    exit 1
fi
if [ ! -d "${IMAGE_DIR}" ]; then
    log_error "镜像目录不存在：${IMAGE_DIR}"
    exit 1
fi
if [ ! -f "${IMAGE_DIR}/images.sha256" ]; then
    log_error "缺少校验文件：${IMAGE_DIR}/images.sha256"
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    SHA_CMD=(sha256sum -c)
elif command -v shasum >/dev/null 2>&1; then
    SHA_CMD=(shasum -a 256 -c)
else
    log_error "未找到 sha256sum / shasum，无法校验镜像。"
    exit 1
fi

cd "${IMAGE_DIR}"
log_info "开始校验离线镜像 tar 的 sha256：dir=${IMAGE_DIR}"
if ! "${SHA_CMD[@]}" images.sha256; then
    log_error "镜像 sha256 校验失败，拒绝导入。请确认离线镜像 tar 完整、未被损坏。"
    exit 1
fi
log_ok "镜像 sha256 校验通过"

load_one() {
    local tar_name="$1"
    local expected_tag="$2"
    local label="$3"
    if [ ! -f "${tar_name}" ]; then
        log_error "缺少镜像 tar：${IMAGE_DIR}/${tar_name}"
        exit 1
    fi
    local start_ts="${SECONDS}"
    log_info "开始导入镜像：label=${label}, tar=${tar_name}, expected_tag=${expected_tag}"
    docker load -i "${tar_name}"
    if ! docker image inspect "${expected_tag}" >/dev/null 2>&1; then
        log_error "导入后未发现预期 tag：${expected_tag}。请确认离线镜像与 runtime/portable.env 的 tag 配置一致。"
        exit 1
    fi
    log_ok "镜像导入完成：label=${label}, tag=${expected_tag}, id=$(docker image inspect "${expected_tag}" --format '{{.Id}}'), elapsed=$((SECONDS - start_ts))s"
}

load_one "rabbitbot-core-portable.tar" "${CORE_IMAGE}" "portable_core"
load_one "rabbitbot-nav-portable.tar" "${NAV_IMAGE}" "portable_nav"

log_ok "portable 镜像离线导入完成：core=${CORE_IMAGE}, nav=${NAV_IMAGE}"

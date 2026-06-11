#!/usr/bin/env bash
# 把 portable core / nav 镜像导出为离线 tar，用于“暂不发布镜像仓库”阶段的交付。
#
# 输出：
#   <OUTPUT_DIR>/rabbitbot-core-portable.tar
#   <OUTPUT_DIR>/rabbitbot-nav-portable.tar
#   <OUTPUT_DIR>/images.sha256
#   <OUTPUT_DIR>/images.lock.json
#
# 用法：
#   bash deploy/export_portable_images.sh
#   OUTPUT_DIR=/path/to/out bash deploy/export_portable_images.sh

set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    source "${PORTABLE_ENV_FILE}"
    set +a
fi

OUTPUT_DIR="${OUTPUT_DIR:-${AIR_ROOT}/outputs/portable-images}"
CORE_IMAGE="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"
CORE_TAR="rabbitbot-core-portable.tar"
NAV_TAR="rabbitbot-nav-portable.tar"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if ! command -v docker >/dev/null 2>&1; then
    log_error "未找到 docker，无法导出镜像。"
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    SHA_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    SHA_CMD=(shasum -a 256)
else
    log_error "未找到 sha256sum / shasum，无法计算镜像校验值。"
    exit 1
fi

image_id() { docker image inspect "$1" --format '{{.Id}}' 2>/dev/null || true; }

require_image() {
    if ! docker image inspect "$1" >/dev/null 2>&1; then
        log_error "待导出镜像不存在：$1。请先执行 MODE=build bash deploy/build_or_pull_images.sh。"
        exit 1
    fi
}

require_image "${CORE_IMAGE}"
require_image "${NAV_IMAGE}"

mkdir -p "${OUTPUT_DIR}"
cd "${OUTPUT_DIR}"

export_one() {
    local image="$1"
    local tar_name="$2"
    local label="$3"
    local start_ts="${SECONDS}"
    log_info "开始导出镜像：label=${label}, image=${image}, id=$(image_id "${image}"), tar=${OUTPUT_DIR}/${tar_name}"
    docker save "${image}" -o "${tar_name}"
    local bytes
    bytes="$(stat -c '%s' "${tar_name}" 2>/dev/null || stat -f '%z' "${tar_name}")"
    log_ok "镜像导出完成：label=${label}, tar=${tar_name}, bytes=${bytes}, elapsed=$((SECONDS - start_ts))s"
}

export_one "${CORE_IMAGE}" "${CORE_TAR}" "portable_core"
export_one "${NAV_IMAGE}" "${NAV_TAR}" "portable_nav"

log_info "计算镜像 sha256 校验值"
"${SHA_CMD[@]}" "${CORE_TAR}" "${NAV_TAR}" >images.sha256
log_ok "已写入 images.sha256"

core_sha="$(awk -v f="${CORE_TAR}" '$2==f || $2=="*"f {print $1}' images.sha256 | head -1)"
nav_sha="$(awk -v f="${NAV_TAR}" '$2==f || $2=="*"f {print $1}' images.sha256 | head -1)"

python3 - "${CORE_IMAGE}" "$(image_id "${CORE_IMAGE}")" "${CORE_TAR}" "${core_sha}" \
            "${NAV_IMAGE}" "$(image_id "${NAV_IMAGE}")" "${NAV_TAR}" "${nav_sha}" <<'PY' >images.lock.json
import json, os, sys
(core_image, core_id, core_tar, core_sha,
 nav_image, nav_id, nav_tar, nav_sha) = sys.argv[1:9]
def size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return None
data = {
    "schema_version": 1,
    "delivery": "offline_docker_save_load",
    "images": {
        "portable_core": {"tag": core_image, "image_id": core_id, "tar": core_tar,
                           "sha256": core_sha, "bytes": size(core_tar)},
        "portable_nav": {"tag": nav_image, "image_id": nav_id, "tar": nav_tar,
                         "sha256": nav_sha, "bytes": size(nav_tar)},
    },
}
print(json.dumps(data, ensure_ascii=False, indent=2))
PY

log_ok "已写入 images.lock.json"
log_ok "portable 镜像离线导出完成：dir=${OUTPUT_DIR}"
log_info "交付清单："
log_info "  core: tag=${CORE_IMAGE}, id=$(image_id "${CORE_IMAGE}"), tar=${OUTPUT_DIR}/${CORE_TAR}, sha256=${core_sha}"
log_info "  nav : tag=${NAV_IMAGE}, id=$(image_id "${NAV_IMAGE}"), tar=${OUTPUT_DIR}/${NAV_TAR}, sha256=${nav_sha}"

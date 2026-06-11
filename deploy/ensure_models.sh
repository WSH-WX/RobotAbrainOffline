#!/usr/bin/env bash
set -Eeuo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
MANIFEST_FILE="${AIR_ROOT}/third_party/manifest.lock"

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

DOWNLOAD_IMAGE="${RABBITBOT_MODEL_DOWNLOAD_IMAGE:-python:3.11-slim}"
HF_TOKEN="${HF_TOKEN:-}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if ! command -v docker >/dev/null 2>&1; then
    log_error "未找到 docker，无法在轻量下载容器中获取模型。"
    exit 1
fi
if [ ! -f "${MANIFEST_FILE}" ]; then
    log_error "模型依赖清单不存在：${MANIFEST_FILE}"
    exit 1
fi

resolve_targets() {
    python3 - "${MANIFEST_FILE}" "$@" <<'PY'
import json
import os
import sys
manifest_path = sys.argv[1]
manual = sys.argv[2:]
with open(manifest_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
models = data.get('models', {})
targets = []
if manual:
    for key in manual:
        if key not in models:
            raise SystemExit(f"未知模型键：{key}")
        targets.append(key)
else:
    enable_vlm = os.environ.get('RABBITBOT_ENABLE_VLM', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    enable_stt = os.environ.get('RABBITBOT_ENABLE_STT', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    if enable_vlm:
        targets.extend(['qwen_vlm', 'qwen_embedding'])
    if enable_stt:
        targets.append('sensevoice')
for key in targets:
    model = models[key]
    print(f"{key}\t{model['hf_repo']}\t{model['target_dir']}")
PY
}

download_model() {
    local key="$1"
    local repo="$2"
    local relative_target="$3"
    local target_dir="${AIR_ROOT}/${relative_target}"

    if [ -d "${target_dir}" ] && [ "$(find "${target_dir}" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')" != "0" ]; then
        log_ok "模型已存在，跳过下载：key=${key}, path=${target_dir}"
        return 0
    fi

    mkdir -p "${target_dir}"
    log_info "开始下载模型：key=${key}, repo=${repo}, target=${target_dir}, downloader=${DOWNLOAD_IMAGE}"
    docker run --rm \
        -e HF_TOKEN="${HF_TOKEN}" \
        -v "${target_dir}:/models/${key}" \
        "${DOWNLOAD_IMAGE}" \
        bash -lc "pip install --quiet huggingface_hub && if [ -n \"\${HF_TOKEN}\" ]; then huggingface-cli login --token \"\${HF_TOKEN}\" --add-to-git-credential >/dev/null; fi && huggingface-cli download '${repo}' --local-dir /models/${key} --local-dir-use-symlinks False"
    log_ok "模型下载完成：key=${key}, path=${target_dir}"
}

mapfile -t targets < <(resolve_targets "$@")
if [ "${#targets[@]}" -eq 0 ]; then
    log_warn "当前未启用任何按需模型，跳过下载。若要强制下载，请传入模型键名，例如：bash deploy/ensure_models.sh qwen_vlm qwen_embedding"
    exit 0
fi

for item in "${targets[@]}"; do
    key="${item%%$'\t'*}"
    rest="${item#*$'\t'}"
    repo="${rest%%$'\t'*}"
    target="${rest#*$'\t'}"
    download_model "${key}" "${repo}" "${target}"
done

log_ok "按需模型检查完成：count=${#targets[@]}"

#!/usr/bin/env bash
# 启动夸父机器人统一容器联调 workflow。
#
# 运行模型：
#   1. 统一容器只作为基础服务底座，容器内入口固定 AUTO_START_WORKFLOW=0。
#   2. 本脚本等待 Neo4j、TTS、Memory Agent、Robot Agent 就绪；VLM/Embedding/STT 默认跳过。
#   3. workflow 通过 docker exec 在当前终端前台启动，联调/非联调模式由本次执行传入。
#
# 常用环境变量：
#   START_AFTER_CREATE=0            只创建容器，不启动服务和 workflow
#   RUN_WORKFLOW_AFTER_START=0      只启动基础服务，不启动 workflow
#   RECREATE_CONTAINER=1            强制删除并重建统一容器
#   RABBITBOT_WORKFLOW_VERBOSE=1    显示 workflow 详细日志
#   RABBITBOT_UNIFIED_ATTACH_STDIN=1 将终端输入传给 workflow
#   RABBITBOT_UNIFIED_START_VLM=1 显式启动 VLM
#   RABBITBOT_UNIFIED_START_EMBEDDING=1 显式启动 Embedding
#   RABBITBOT_UNIFIED_START_STT=1 显式启动 STT（默认不启动，当前 workflow 不再需要）
#
# workflow 运行环境变量速查：
# - RABBITBOT_STRICT_DOCX_SCRIPT：是否启用严格 DOCX 剧本模式，默认启用。
# - RABBITBOT_SCRIPTED_TOUR：是否启用脚本化导览推进，默认启用。
# - RABBITBOT_WORKFLOW_NON_INTEGRATION：是否使用非联调手动确认导航模式。
# - RABBITBOT_WORKFLOW_VERBOSE：是否打印调试级 workflow 过程日志。
# - RABBITBOT_WORKFLOW_PROFILE：是否写入 workflow profile JSONL，默认启用。
# - RABBITBOT_WORKFLOW_PROFILE_LOG：显式指定 workflow profile JSONL 路径。
# - RABBITBOT_LOG_DIR：未指定 profile 路径时的日志目录。
# - RABBITBOT_WORKFLOW_SUMMARY：是否在退出时打印 workflow 耗时汇总，默认启用。
# - RABBITBOT_TTS_STRICT_FAILURE：TTS 请求失败时是否按致命错误终止 workflow，默认 0，即记录错误并继续导览。
# - RABBITBOT_DIALOGUE_INDEX：选择 conf/dialogue_<序号>.json，未设置时默认 0。
# - RABBITBOT_DOCX_GUIDE_DIALOGUE_INDEX：旧版台词序号变量，仅在 RABBITBOT_DIALOGUE_INDEX 未设置时兜底。
# - RABBITBOT_DOCX_GUIDE_DIALOGUE_FILE：直接指定台词 JSON 文件完整路径，优先级高于序号。
# - RABBITBOT_COFFEE_DELIVERY_COMMAND：覆盖“呼叫咖啡车”的后台命令。
# - RABBITBOT_COFFEE_DELIVERY_COMMAND_TIMEOUT：呼叫咖啡车后台命令等待超时时间，单位秒。
# - RABBITBOT_OPENING_MODE：控制开场流程，full 为完整开场，skip/0/false/off 为跳过。
# - RABBITBOT_ENABLE_NAVI：是否真实执行导航，设为 0/false/no/off 时跳过导航。
# - RABBITBOT_HAND_GESTURE_<ACTION>：为指定手臂动作配置灵巧手 ROS 字符串命令。
# - RABBITBOT_HAND_GESTURE_TOPIC：灵巧手命令发布 topic，默认 /gesture_cmd。
# - RABBITBOT_HAND_GESTURE_PUB_TIMEOUT：灵巧手命令发布超时，单位秒。
# - RABBITBOT_HANDSHAKE_BEFORE_RELEASE_DELAY：握手动作收手前等待时间，单位秒。
# - RABBITBOT_ARM_BEFORE_RELEASE_DELAY：其它前置动作收手前默认等待时间，单位秒。
# - RABBITBOT_ARM_AFTER_SPEECH_RELEASE_DELAY：台词后收手动作的等待时间，单位秒。
# - RABBITBOT_ARM_CONCURRENT_RELEASE_DELAY：动作与台词并发时收手前等待时间，单位秒。
# - RABBITBOT_ARM_RELEASE_WAIT_SECONDS：发送 release 后额外等待时间，单位秒。
# - RABBITBOT_VIEW_MODE：视觉问答来源，robot 使用机器人视觉，其它值使用 mock。
# - RABBITBOT_MOCK_IMAGE：mock 视觉问答使用的本地图片路径。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RABBITBOT_REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_PROJECT_ROOT="$(cd "${RABBITBOT_REPO_DIR}/.." && pwd)"

# 加载 portable 运行模式配置（若存在），以便在 portable 模式下注入自包含镜像的重型依赖卷。
# 关键开关保留调用方优先级：显式传入 RABBITBOT_RUNTIME_MODE=legacy / RABBITBOT_UNIFIED_START_ROBOT_AGENT=1
# 时不被 env 文件覆盖，便于现场临时回退 legacy 行为。
_CALLER_RUNTIME_MODE="${RABBITBOT_RUNTIME_MODE:-}"
_CALLER_START_ROBOT_AGENT="${RABBITBOT_UNIFIED_START_ROBOT_AGENT:-}"
PORTABLE_ENV_FILE="${RABBITBOT_PORTABLE_ENV_FILE:-${RABBITBOT_REPO_DIR}/runtime/portable.env}"
if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    source "${PORTABLE_ENV_FILE}"
    set +a
fi
if [ -n "${_CALLER_RUNTIME_MODE}" ]; then
    RABBITBOT_RUNTIME_MODE="${_CALLER_RUNTIME_MODE}"
fi

IMAGE_NAME="${IMAGE_NAME:-rabbitbot-unified-runtime:20260518}"
CONTAINER_NAME="${CONTAINER_NAME:-rabbitbot-unified-runtime}"
PROJECT_ROOT="${PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
CONTAINER_PROJECT_ROOT="${CONTAINER_PROJECT_ROOT:-/workspace/projects}"
MODELS_DIR="${MODELS_DIR:-${PROJECT_ROOT}/models}"
CONTAINER_RABBITBOT_DIR="${CONTAINER_RABBITBOT_DIR:-${CONTAINER_PROJECT_ROOT}/rabbitbot-dev-ros2-master}"
CONTAINER_LOG_DIR="${CONTAINER_LOG_DIR:-${CONTAINER_RABBITBOT_DIR}/logs/unified_runtime}"
RECREATE_CONTAINER="${RECREATE_CONTAINER:-0}"
RECREATE_INCOMPATIBLE_CONTAINER="${RECREATE_INCOMPATIBLE_CONTAINER:-1}"
START_AFTER_CREATE="${START_AFTER_CREATE:-1}"
RUN_WORKFLOW_AFTER_START="${RUN_WORKFLOW_AFTER_START:-${AUTO_START_WORKFLOW:-1}}"
RABBITBOT_UNIFIED_ATTACH_STDIN="${RABBITBOT_UNIFIED_ATTACH_STDIN:-0}"
RABBITBOT_WORKFLOW_NON_INTEGRATION="${RABBITBOT_WORKFLOW_NON_INTEGRATION:-0}"
RABBITBOT_WORKFLOW_VERBOSE="${RABBITBOT_WORKFLOW_VERBOSE:-0}"
RABBITBOT_TTS_STRICT_FAILURE="${RABBITBOT_TTS_STRICT_FAILURE:-0}"
STOP_EXISTING_WORKFLOW="${STOP_EXISTING_WORKFLOW:-1}"
WAIT_DEFAULT_SECONDS="${WAIT_DEFAULT_SECONDS:-420}"
WAIT_VLM_SECONDS="${WAIT_VLM_SECONDS:-600}"
RABBITBOT_UNIFIED_START_VLM="${RABBITBOT_UNIFIED_START_VLM:-0}"
RABBITBOT_UNIFIED_START_EMBEDDING="${RABBITBOT_UNIFIED_START_EMBEDDING:-0}"
RABBITBOT_UNIFIED_START_STT="${RABBITBOT_UNIFIED_START_STT:-0}"
RABBITBOT_TTS_BACKEND="${RABBITBOT_TTS_BACKEND:-unitree}"
RABBITBOT_UNITREE_TTS_INTERFACE="${RABBITBOT_UNITREE_TTS_INTERFACE:-eno1}"
RABBITBOT_UNITREE_TTS_VOLUME="${RABBITBOT_UNITREE_TTS_VOLUME:-100}"
RABBITBOT_UNITREE_TTS_SPEAKER_ID="${RABBITBOT_UNITREE_TTS_SPEAKER_ID:-0}"
RABBITBOT_UNITREE_TTS_TIMEOUT="${RABBITBOT_UNITREE_TTS_TIMEOUT:-10}"

# portable 自包含运行模式：
#   当 RABBITBOT_RUNTIME_MODE=portable 且 RABBITBOT_PORTABLE_INJECT_DEPS!=0 时，
#   为 4 个宿主 gitignore 的重型依赖目录注入 named volume；这些卷在首次使用时会从自包含 core
#   镜像 seed 出 py38/py310/vln/pyorbbecsdk，从而即使宿主源码目录缺这些子目录也能正常运行。
#   宿主源码目录仍 bind mount 到 /workspace/projects 以提供 GitHub 源码、conf 与日志可见性。
RABBITBOT_RUNTIME_MODE="${RABBITBOT_RUNTIME_MODE:-legacy}"
RABBITBOT_PORTABLE_INJECT_DEPS="${RABBITBOT_PORTABLE_INJECT_DEPS:-1}"

# 28180 端口拓扑：
#   legacy 默认 core 内启动 robot_app.py（监听 28180）。
#   portable 默认 core 不启动 Robot Agent，28180 归属 nav bridge 的 humble_robot_agent_bridge；
#   workflow 通过 RABBITBOT_ROBOT_AGENT_URL（默认 http://127.0.0.1:28180）访问 nav bridge。
if [ "${RABBITBOT_RUNTIME_MODE}" = "portable" ]; then
    RABBITBOT_UNIFIED_START_ROBOT_AGENT="${RABBITBOT_UNIFIED_START_ROBOT_AGENT:-0}"
else
    # legacy 模式：portable.env 中的该键不生效；仅调用方显式传入时才覆盖，否则按 legacy 默认 1。
    if [ -n "${_CALLER_START_ROBOT_AGENT}" ]; then
        RABBITBOT_UNIFIED_START_ROBOT_AGENT="${_CALLER_START_ROBOT_AGENT}"
    else
        RABBITBOT_UNIFIED_START_ROBOT_AGENT=1
    fi
fi
RABBITBOT_ROBOT_AGENT_URL="${RABBITBOT_ROBOT_AGENT_URL:-http://127.0.0.1:28180}"

log_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1" >&2
}

log_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

require_dir() {
    if [ ! -d "$1" ]; then
        log_error "目录不存在：$1"
        exit 1
    fi
}

container_exists() {
    docker ps -a --format '{{.Names}}' | grep -qx "$1"
}

container_running() {
    docker ps --format '{{.Names}}' | grep -qx "$1"
}

container_env_value() {
    local container="$1"
    local key="$2"
    docker inspect "${container}" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | sed -n "s/^${key}=//p" \
        | tail -n 1
}

container_mount_source() {
    local container="$1"
    local destination="$2"
    docker inspect "${container}" --format '{{range .Mounts}}{{printf "%s\t%s\n" .Destination .Source}}{{end}}' 2>/dev/null \
        | awk -F '	' -v dest="${destination}" '$1 == dest {print $2; exit}'
}

port_open() {
    local port="$1"
    timeout 2 bash -lc "</dev/tcp/127.0.0.1/${port}" >/dev/null 2>&1
}

http_ok() {
    local url="$1"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${url}" 2>/dev/null || true)
    [ "${code}" = "200" ]
}

json_model_ok() {
    curl -s --max-time 5 "$1" 2>/dev/null | grep -q '"data"'
}

wait_until() {
    local name="$1"
    local seconds="$2"
    shift 2
    local count=0
    echo -n "等待 ${name} 就绪"
    until "$@"; do
        sleep 2
        count=$((count + 2))
        echo -n "."
        if [ "${count}" -ge "${seconds}" ]; then
            echo ""
            log_error "${name} 启动超时 (${seconds} 秒)"
            return 1
        fi
    done
    echo ""
    log_success "${name} 已就绪"
}

wait_for_base_services() {
    log_info "等待统一容器基础服务就绪：${CONTAINER_NAME}"
    wait_until "Neo4j Bolt (7687)" "${WAIT_DEFAULT_SECONDS}" port_open 7687
    if [ "${RABBITBOT_UNIFIED_START_VLM}" = "1" ]; then
        wait_until "VLM 服务 (8000)" "${WAIT_VLM_SECONDS}" json_model_ok http://127.0.0.1:8000/v1/models
    else
        log_info "RABBITBOT_UNIFIED_START_VLM=0，跳过等待 VLM 服务 (8000)"
    fi
    if [ "${RABBITBOT_UNIFIED_START_EMBEDDING}" = "1" ]; then
        wait_until "Embedding 服务 (8005)" "${WAIT_DEFAULT_SECONDS}" json_model_ok http://127.0.0.1:8005/v1/models
    else
        log_info "RABBITBOT_UNIFIED_START_EMBEDDING=0，跳过等待 Embedding 服务 (8005)"
    fi
    wait_until "TTS 服务 (28185)" "${WAIT_DEFAULT_SECONDS}" http_ok http://127.0.0.1:28185/docs
    if [ "${RABBITBOT_UNIFIED_START_STT}" = "1" ]; then
        wait_until "STT 服务 (28184)" "${WAIT_DEFAULT_SECONDS}" http_ok http://127.0.0.1:28184/docs
    else
        log_info "RABBITBOT_UNIFIED_START_STT=0，跳过等待 STT 服务 (28184)"
    fi
    wait_until "Memory Agent 服务 (28182)" "${WAIT_DEFAULT_SECONDS}" http_ok http://127.0.0.1:28182/docs
    if [ "${RABBITBOT_UNIFIED_START_ROBOT_AGENT}" = "1" ]; then
        wait_until "Robot Agent 服务 (28180)" "${WAIT_DEFAULT_SECONDS}" port_open 28180
    else
        log_info "RABBITBOT_UNIFIED_START_ROBOT_AGENT=0，跳过等待 core 内部 Robot Agent (28180)；portable 模式下 28180 由 nav bridge 提供，可达性在 workflow 启动前检查"
    fi
}

check_external_robot_agent_reachable() {
    # core 不托管 Robot Agent 时，在 workflow 启动前确认外部 28180 可达。
    if [ "${RABBITBOT_UNIFIED_START_ROBOT_AGENT}" = "1" ]; then
        return 0
    fi
    local host_port host port
    host_port="$(printf '%s' "${RABBITBOT_ROBOT_AGENT_URL}" | sed -E 's#^[a-zA-Z]+://##; s#/.*$##')"
    host="${host_port%%:*}"
    port="${host_port##*:}"
    if [ -z "${port}" ] || [ "${port}" = "${host}" ]; then
        port=80
    fi
    if timeout 3 bash -lc "</dev/tcp/${host}/${port}" >/dev/null 2>&1; then
        log_success "外部 Robot Agent 可达：${RABBITBOT_ROBOT_AGENT_URL}"
        return 0
    fi
    log_error "外部 Robot Agent 不可达：${RABBITBOT_ROBOT_AGENT_URL}。portable 模式下 28180 应由 nav bridge 提供；请先通过 start_loop_entry.sh（nav 先行）启动，或单独运行 scripts_1/start_nav_bridge_portable.sh。"
    return 1
}

ensure_compatible_container() {
    if ! container_exists "${CONTAINER_NAME}"; then
        return 0
    fi

    if [ "${RECREATE_CONTAINER}" = "1" ]; then
        log_warn "删除已有统一容器：${CONTAINER_NAME}"
        docker rm -f "${CONTAINER_NAME}" >/dev/null
        return 0
    fi

    local container_auto_start
    container_auto_start="$(container_env_value "${CONTAINER_NAME}" AUTO_START_WORKFLOW || true)"
    local container_start_vlm
    container_start_vlm="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNIFIED_START_VLM || true)"
    local container_start_embedding
    container_start_embedding="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNIFIED_START_EMBEDDING || true)"
    local container_start_stt
    container_start_stt="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNIFIED_START_STT || true)"
    local container_start_robot_agent
    container_start_robot_agent="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNIFIED_START_ROBOT_AGENT || true)"
    local container_tts_backend
    container_tts_backend="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_TTS_BACKEND || true)"
    local container_unitree_interface
    container_unitree_interface="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNITREE_TTS_INTERFACE || true)"
    local container_unitree_volume
    container_unitree_volume="$(container_env_value "${CONTAINER_NAME}" RABBITBOT_UNITREE_TTS_VOLUME || true)"
    local container_image
    container_image="$(docker inspect "${CONTAINER_NAME}" --format '{{.Config.Image}}' 2>/dev/null || true)"
    local container_project_mount
    container_project_mount="$(container_mount_source "${CONTAINER_NAME}" "${CONTAINER_PROJECT_ROOT}" || true)"
    local container_models_mount
    container_models_mount="$(container_mount_source "${CONTAINER_NAME}" "/models" || true)"
    local expected_project_mount
    expected_project_mount="$(cd "${PROJECT_ROOT}" && pwd)"
    local expected_models_mount
    expected_models_mount="$(cd "${MODELS_DIR}" && pwd)"
    local incompatible_reason=""
    if [ -n "${container_image}" ] && [ "${container_image}" != "${IMAGE_NAME}" ]; then
        incompatible_reason="镜像变化：container=${container_image}, expected=${IMAGE_NAME}（如刚导入新的 portable core 镜像，会据此重建容器以生效）"
    elif [ "${container_project_mount}" != "${expected_project_mount}" ]; then
        incompatible_reason="项目挂载路径变化：container=${container_project_mount:-未设置}, expected=${expected_project_mount}"
    elif [ "${container_models_mount}" != "${expected_models_mount}" ]; then
        incompatible_reason="模型挂载路径变化：container=${container_models_mount:-未设置}, expected=${expected_models_mount}"
    elif [ "${container_auto_start}" != "0" ]; then
        incompatible_reason="旧的自启动 workflow 模式"
    elif [ "${container_start_vlm:-未设置}" != "${RABBITBOT_UNIFIED_START_VLM}" ]; then
        incompatible_reason="VLM 启动配置变化：container=${container_start_vlm:-未设置}, expected=${RABBITBOT_UNIFIED_START_VLM}"
    elif [ "${container_start_embedding:-未设置}" != "${RABBITBOT_UNIFIED_START_EMBEDDING}" ]; then
        incompatible_reason="Embedding 启动配置变化：container=${container_start_embedding:-未设置}, expected=${RABBITBOT_UNIFIED_START_EMBEDDING}"
    elif [ "${container_start_stt:-未设置}" != "${RABBITBOT_UNIFIED_START_STT}" ]; then
        incompatible_reason="STT 启动配置变化：container=${container_start_stt:-未设置}, expected=${RABBITBOT_UNIFIED_START_STT}"
    elif [ "${container_start_robot_agent:-1}" != "${RABBITBOT_UNIFIED_START_ROBOT_AGENT}" ]; then
        # 旧容器未设置该变量时视为 1（legacy 行为），避免 legacy 模式误判重建；portable 期望 0 时会触发重建。
        incompatible_reason="Robot Agent 启动配置变化：container=${container_start_robot_agent:-未设置(按1)}, expected=${RABBITBOT_UNIFIED_START_ROBOT_AGENT}"
    elif [ "${container_tts_backend:-local}" != "${RABBITBOT_TTS_BACKEND}" ]; then
        incompatible_reason="TTS 后端配置变化：container=${container_tts_backend:-local}, expected=${RABBITBOT_TTS_BACKEND}"
    elif [ "${RABBITBOT_TTS_BACKEND}" = "unitree" ] && [ "${container_unitree_interface:-eno1}" != "${RABBITBOT_UNITREE_TTS_INTERFACE}" ]; then
        incompatible_reason="Unitree TTS 网卡配置变化：container=${container_unitree_interface:-eno1}, expected=${RABBITBOT_UNITREE_TTS_INTERFACE}"
    elif [ "${RABBITBOT_TTS_BACKEND}" = "unitree" ] && [ "${container_unitree_volume:-85}" != "${RABBITBOT_UNITREE_TTS_VOLUME}" ]; then
        incompatible_reason="Unitree TTS 音量配置变化：container=${container_unitree_volume:-85}, expected=${RABBITBOT_UNITREE_TTS_VOLUME}"
    fi

    if [ -n "${incompatible_reason}" ]; then
        if [ "${RECREATE_INCOMPATIBLE_CONTAINER}" = "1" ]; then
            log_warn "已有统一容器配置不匹配，将重建：${CONTAINER_NAME}，原因：${incompatible_reason}"
            docker rm -f "${CONTAINER_NAME}" >/dev/null
        else
            log_error "已有统一容器配置不匹配：${incompatible_reason}"
            log_error "请设置 RECREATE_CONTAINER=1 或 RECREATE_INCOMPATIBLE_CONTAINER=1 后重试。"
            exit 1
        fi
    fi
}

portable_dep_enabled() {
    [ "${RABBITBOT_RUNTIME_MODE}" = "portable" ] && [ "${RABBITBOT_PORTABLE_INJECT_DEPS}" != "0" ]
}

# 4 个宿主 gitignore 的重型依赖目录；portable 模式下用从 core 镜像 seed 的 named volume 顶替。
PORTABLE_DEP_NAMES=(py38 py310 vln pyorbbecsdk-v2-py310)

portable_dep_volume() {
    case "$1" in
        py38) echo "rabbitbot_portable_py38" ;;
        py310) echo "rabbitbot_portable_py310" ;;
        vln) echo "rabbitbot_portable_vln" ;;
        pyorbbecsdk-v2-py310) echo "rabbitbot_portable_pyorbbecsdk" ;;
    esac
}

portable_dep_dest() {
    case "$1" in
        py38) echo "${CONTAINER_RABBITBOT_DIR}/py38" ;;
        py310) echo "${CONTAINER_RABBITBOT_DIR}/py310" ;;
        vln) echo "${CONTAINER_PROJECT_ROOT}/vln" ;;
        pyorbbecsdk-v2-py310) echo "${CONTAINER_PROJECT_ROOT}/pyorbbecsdk-v2-py310" ;;
    esac
}

reset_portable_dep_volumes() {
    # 新建容器前重置依赖卷，确保从当前 core 镜像重新 seed，避免旧镜像版本残留。
    local name vol
    for name in "${PORTABLE_DEP_NAMES[@]}"; do
        vol="$(portable_dep_volume "${name}")"
        if docker volume inspect "${vol}" >/dev/null 2>&1; then
            docker volume rm "${vol}" >/dev/null 2>&1 || log_warn "依赖卷删除失败（可能正被占用），将复用现有卷：${vol}"
        fi
        docker volume create "${vol}" >/dev/null
    done
    log_info "已重置 portable 重型依赖卷，将在容器创建时从 core 镜像重新 seed：count=${#PORTABLE_DEP_NAMES[@]}"
}

create_container_if_needed() {
    if container_exists "${CONTAINER_NAME}"; then
        log_info "复用已有统一容器：${CONTAINER_NAME}"
        return 0
    fi

    docker volume create rabbitbot_unified_neo4j_data >/dev/null
    docker volume create rabbitbot_unified_neo4j_logs >/dev/null

    audio_args=()
    if [ -e /dev/snd ]; then
        audio_args+=(
            -v /dev/snd:/dev/snd
            --device-cgroup-rule 'c 116:* rwm'
        )
    fi

    dep_args=()
    if portable_dep_enabled; then
        reset_portable_dep_volumes
        local dep_name
        for dep_name in "${PORTABLE_DEP_NAMES[@]}"; do
            dep_args+=( -v "$(portable_dep_volume "${dep_name}"):$(portable_dep_dest "${dep_name}")" )
        done
        log_info "portable 模式：注入 ${#PORTABLE_DEP_NAMES[@]} 个重型依赖卷（py38/py310/vln/pyorbbecsdk），运行期不再要求宿主提供这些目录"
    fi

    log_info "创建统一容器基础服务底座：${CONTAINER_NAME}"
    log_info "TTS 默认后端：${RABBITBOT_TTS_BACKEND}，Unitree 网卡：${RABBITBOT_UNITREE_TTS_INTERFACE}，音量：${RABBITBOT_UNITREE_TTS_VOLUME}"
    docker create \
        --name "${CONTAINER_NAME}" \
        --network host \
        --ipc host \
        --runtime nvidia \
        "${audio_args[@]}" \
        "${dep_args[@]}" \
        -e RABBITBOT_DIR="${CONTAINER_RABBITBOT_DIR}" \
        -e RABBITBOT_LOG_DIR="${CONTAINER_LOG_DIR}" \
        -e RABBITBOT_TTS_ALLOW_BUILTIN="${RABBITBOT_TTS_ALLOW_BUILTIN:-0}" \
        -e RABBITBOT_UNIFIED_TTS_DEVICE="${RABBITBOT_UNIFIED_TTS_DEVICE:-cuda}" \
        -e RABBITBOT_UNIFIED_TTS_FAST_SOUND_PRELOAD="${RABBITBOT_UNIFIED_TTS_FAST_SOUND_PRELOAD:-0}" \
        -e RABBITBOT_UNIFIED_TTS_STARTUP_SPEECH="${RABBITBOT_UNIFIED_TTS_STARTUP_SPEECH:-0}" \
        -e RABBITBOT_TTS_BACKEND="${RABBITBOT_TTS_BACKEND}" \
        -e RABBITBOT_UNITREE_TTS_INTERFACE="${RABBITBOT_UNITREE_TTS_INTERFACE}" \
        -e RABBITBOT_UNITREE_TTS_VOLUME="${RABBITBOT_UNITREE_TTS_VOLUME}" \
        -e RABBITBOT_UNITREE_TTS_SPEAKER_ID="${RABBITBOT_UNITREE_TTS_SPEAKER_ID}" \
        -e RABBITBOT_UNITREE_TTS_TIMEOUT="${RABBITBOT_UNITREE_TTS_TIMEOUT}" \
        -e RABBITBOT_WORKFLOW_VERBOSE="${RABBITBOT_WORKFLOW_VERBOSE}" \
        -e RABBITBOT_TTS_STRICT_FAILURE="${RABBITBOT_TTS_STRICT_FAILURE}" \
        -e RABBITBOT_UNIFIED_START_VLM="${RABBITBOT_UNIFIED_START_VLM}" \
        -e RABBITBOT_UNIFIED_START_EMBEDDING="${RABBITBOT_UNIFIED_START_EMBEDDING}" \
        -e RABBITBOT_UNIFIED_START_STT="${RABBITBOT_UNIFIED_START_STT}" \
        -e RABBITBOT_UNIFIED_START_ROBOT_AGENT="${RABBITBOT_UNIFIED_START_ROBOT_AGENT}" \
        -e RABBITBOT_ROBOT_AGENT_URL="${RABBITBOT_ROBOT_AGENT_URL}" \
        -e AUTO_START_WORKFLOW=0 \
        -e WAIT_DEFAULT_SECONDS="${WAIT_DEFAULT_SECONDS}" \
        -e WAIT_VLM_SECONDS="${WAIT_VLM_SECONDS}" \
        -v "${PROJECT_ROOT}:${CONTAINER_PROJECT_ROOT}" \
        -v "${MODELS_DIR}:/models" \
        -v rabbitbot_unified_neo4j_data:/var/lib/neo4j/data \
        -v rabbitbot_unified_neo4j_logs:/var/lib/neo4j/logs \
        "${IMAGE_NAME}" \
        bash "${CONTAINER_RABBITBOT_DIR}/scripts_1/unified_runtime/start_unified_container.sh" >/dev/null

    log_info "统一容器创建完成：${CONTAINER_NAME}"
}

start_container_if_needed() {
    if container_running "${CONTAINER_NAME}"; then
        log_info "统一容器基础服务底座已运行：${CONTAINER_NAME}"
    else
        log_info "后台启动统一容器基础服务底座：${CONTAINER_NAME}"
        docker start "${CONTAINER_NAME}" >/dev/null
    fi
}

stop_existing_workflow_if_needed() {
    if [ "${STOP_EXISTING_WORKFLOW}" != "1" ]; then
        return 0
    fi
    log_info "清理容器内已有 workflow 进程，避免重复启动"
    docker exec "${CONTAINER_NAME}" bash -lc '
pkill -f "[e]xamples/run_kuavo_agno.py" 2>/dev/null || true
pkill -f "[s]cripts/start_kuavo_agno_workflow.bash" 2>/dev/null || true
' >/dev/null 2>&1 || true
}

run_workflow_foreground() {
    local mode_label="联调"
    if [ "${RABBITBOT_WORKFLOW_NON_INTEGRATION}" = "1" ]; then
        mode_label="非联调"
    fi

    docker_exec_args=()
    if [ "${RABBITBOT_UNIFIED_ATTACH_STDIN}" = "1" ]; then
        docker_exec_args+=(-i)
    fi
    if [ -t 1 ]; then
        docker_exec_args+=(-t)
    fi

    log_info "前台启动统一容器 ${mode_label} workflow：${CONTAINER_NAME}"
    log_info "后续输出会直接显示在当前终端；日志同步写入容器 ${CONTAINER_LOG_DIR}/rabbitbot_workflow_latest.log"

    exec docker exec "${docker_exec_args[@]}" \
        -e RABBITBOT_WORKFLOW_NON_INTEGRATION="${RABBITBOT_WORKFLOW_NON_INTEGRATION}" \
        -e RABBITBOT_WORKFLOW_VERBOSE="${RABBITBOT_WORKFLOW_VERBOSE}" \
        -e RABBITBOT_TTS_STRICT_FAILURE="${RABBITBOT_TTS_STRICT_FAILURE}" \
        -e RABBITBOT_DIR="${CONTAINER_RABBITBOT_DIR}" \
        -e RABBITBOT_LOG_DIR="${CONTAINER_LOG_DIR}" \
        -e PYTHONUNBUFFERED=1 \
        "${CONTAINER_NAME}" bash -lc '
set -euo pipefail
cd "${RABBITBOT_DIR}"
log_dir="${RABBITBOT_LOG_DIR:-${RABBITBOT_DIR}/logs/unified_runtime}"
mkdir -p "${log_dir}"
log_path="${log_dir}/rabbitbot_workflow_$(date +%Y%m%d_%H%M%S).log"
ln -sf "${log_path}" "${log_dir}/rabbitbot_workflow_latest.log"
echo "Workflow容器日志: ${log_path}"
PYTHONUNBUFFERED=1 bash scripts/start_kuavo_agno_workflow.bash 2>&1 | tee -a "${log_path}"
'
}

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    log_error "镜像不存在：${IMAGE_NAME}，请先运行 scripts_1/build_unified_runtime_image.sh"
    exit 1
fi

require_dir "${PROJECT_ROOT}"
require_dir "${MODELS_DIR}"

ensure_compatible_container
create_container_if_needed

if [ "${START_AFTER_CREATE}" != "1" ]; then
    log_info "START_AFTER_CREATE=${START_AFTER_CREATE}，仅完成容器创建/复用，不启动基础服务和 workflow"
    exit 0
fi

start_container_if_needed
wait_for_base_services

if [ "${RUN_WORKFLOW_AFTER_START}" != "1" ]; then
    log_info "RUN_WORKFLOW_AFTER_START=${RUN_WORKFLOW_AFTER_START}，仅保持基础服务运行，不启动 workflow"
    exit 0
fi

if ! check_external_robot_agent_reachable; then
    exit 1
fi
stop_existing_workflow_if_needed
run_workflow_foreground

#!/usr/bin/env bash
# 检查 air_robot_gt_projects 在 legacy / portable 两条路径下的关键文件、环境、路径和语法。
#
# PORTABLE_CHECK_MODE：
#   builder    构建机模式（默认）：要求宿主存在 unitree_sdk2 / vln / pyorbbecsdk / py38 / py310 /
#              custom_action_ws/install / 导航构建产物 / dfx 等外部构建源；用于生成 portable 镜像前的自检。
#   clean_orin 全新 Orin 模式：不要求上述宿主外部目录与 legacy Python 虚拟环境存在；改为要求 GitHub 源码、
#              已导入的 portable core/nav 镜像、portable env、compose、宿主初始化结果和地图路径配置存在。

set -euo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PROJECTS_DIR="${AIR_ROOT}"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
MANIFEST_FILE="${AIR_ROOT}/third_party/manifest.lock"
DOCKERIGNORE_FILE="${AIR_ROOT}/.dockerignore"

PORTABLE_CHECK_MODE="${PORTABLE_CHECK_MODE:-builder}"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    source "${PORTABLE_ENV_FILE}"
    set +a
elif [ -f "${PORTABLE_ENV_FILE}.example" ]; then
    # 本机 portable.env 不进入 Git；不存在时回退读取随仓库迁移的模板，保证只读校验类场景可用。
    echo "[WARN] 未找到本机配置 ${PORTABLE_ENV_FILE}，回退读取模板 ${PORTABLE_ENV_FILE}.example；正式部署请先执行 deploy/bootstrap_host.sh 生成本机 portable.env。"
    set -a
    # shellcheck disable=SC1090
    source "${PORTABLE_ENV_FILE}.example"
    set +a
fi

# grep 类静态检查使用实际生效的 env 文件：优先本机 portable.env，否则用随仓库迁移的模板。
if [ -f "${PORTABLE_ENV_FILE}" ]; then
    PORTABLE_ENV_EFFECTIVE_FILE="${PORTABLE_ENV_FILE}"
else
    PORTABLE_ENV_EFFECTIVE_FILE="${PORTABLE_ENV_FILE}.example"
fi

CORE_IMAGE="${RABBITBOT_PORTABLE_CORE_IMAGE:-ghcr.io/aaronai/rabbitbot-core-portable:20260611}"
NAV_IMAGE="${RABBITBOT_PORTABLE_NAV_IMAGE:-ghcr.io/aaronai/rabbitbot-nav-portable:20260611}"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

case "${PORTABLE_CHECK_MODE}" in
    builder|clean_orin) ;;
    *)
        log_error "不支持的 PORTABLE_CHECK_MODE：${PORTABLE_CHECK_MODE}，仅支持 builder / clean_orin"
        exit 1
        ;;
esac
log_info "portable 自检模式：PORTABLE_CHECK_MODE=${PORTABLE_CHECK_MODE}"

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
    log_ok "存在：$1"
}

info_optional_absent() {
    # clean_orin 模式下，外部构建目录“不存在”是预期的，记录为信息而非错误。
    if [ -e "$1" ]; then
        log_ok "存在（clean_orin 下非必需）：$1"
    else
        log_info "外部构建目录不存在，clean_orin 模式下符合预期：$1"
    fi
}

check_manifest() {
    python3 - "${MANIFEST_FILE}" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
required_dependencies = {
    'unitree_sdk2',
    'dfx_inspire_service',
    'pyorbbecsdk-v2-py310',
    'vln',
    'custom_action_ws_install',
    'legacy_python_envs',
}
required_images = {'portable_core', 'portable_nav', 'legacy_unified_core_base'}
required_models = {'qwen_vlm', 'qwen_embedding', 'sensevoice'}
missing = []
missing.extend(sorted(required_dependencies - set(data.get('dependencies', {}))))
missing.extend(sorted(required_images - set(data.get('images', {}))))
missing.extend(sorted(required_models - set(data.get('models', {}))))
if missing:
    raise SystemExit('manifest_missing=' + ','.join(missing))
# portable 阶段不应再保留未解决的阻塞项。
if data.get('blockers'):
    raise SystemExit('manifest_unresolved_blockers=' + ','.join(b.get('id', '?') for b in data['blockers']))
print('manifest-ok')
PY
}

check_portable_env_keys() {
    local required_keys=(
        RABBITBOT_RUNTIME_MODE
        RABBITBOT_NAV_RUNTIME
        RABBITBOT_PORTABLE_CORE_IMAGE
        RABBITBOT_PORTABLE_NAV_IMAGE
        RABBITBOT_IMAGE_SOURCE
        RABBITBOT_DDS_INTERFACE
        RABBITBOT_DDS_HOST_CIDR
        RABBITBOT_NAV_MAP_PATH
        RABBITBOT_ENABLE_VLM
        RABBITBOT_ENABLE_EMBEDDING
        RABBITBOT_ENABLE_STT
        RABBITBOT_AUTO_DOWNLOAD_MODELS
        RABBITBOT_UNIFIED_START_ROBOT_AGENT
    )
    for key in "${required_keys[@]}"; do
        if ! grep -Eq "^${key}=" "${PORTABLE_ENV_EFFECTIVE_FILE}"; then
            log_error "portable env 缺少必填键：${key}"
            exit 1
        fi
    done
    log_ok "portable env 关键键存在：count=${#required_keys[@]}"
    # portable 端口拓扑约定：core 不启动 robot_app.py，28180 归属 nav bridge。
    if ! grep -Eq '^RABBITBOT_UNIFIED_START_ROBOT_AGENT=0$' "${PORTABLE_ENV_EFFECTIVE_FILE}"; then
        log_error "portable env 必须设置 RABBITBOT_UNIFIED_START_ROBOT_AGENT=0：portable 模式下 28180 由 nav bridge 提供，core 不应启动 Robot Agent。"
        exit 1
    fi
    log_ok "portable env 端口拓扑配置正确：RABBITBOT_UNIFIED_START_ROBOT_AGENT=0"
}

check_core_skips_internal_28180() {
    # 静态检查：core 启动链路必须支持在 portable 模式下跳过内部 Robot Agent 与 28180 等待。
    local integration_script="${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"
    local container_script="${REPO_DIR}/scripts_1/unified_runtime/start_unified_container.sh"
    if ! grep -q 'RABBITBOT_UNIFIED_START_ROBOT_AGENT' "${integration_script}"; then
        log_error "core 启动脚本缺少 Robot Agent 开关支持：${integration_script}"
        exit 1
    fi
    if ! grep -q 'RABBITBOT_UNIFIED_START_ROBOT_AGENT' "${container_script}"; then
        log_error "统一容器入口缺少 Robot Agent 开关支持：${container_script}"
        exit 1
    fi
    log_ok "core 启动链路支持 portable 模式跳过内部 Robot Agent (28180)"
}

check_portable_unitree_tts_policy() {
    # Unitree 本体 TTS 服务运行在 core 容器内，core 镜像和运行期依赖卷必须提供 unitree_sdk2。
    local integration_script="${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"
    local core_dockerfile="${REPO_DIR}/docker/portable/core.Dockerfile"
    local image_script="${PROJECTS_DIR}/deploy/build_or_pull_images.sh"
    if ! grep -q 'COPY unitree_sdk2 /workspace/projects/unitree_sdk2' "${core_dockerfile}"; then
        log_error "portable core 镜像未烤入 unitree_sdk2，Unitree TTS 会在全新 Orin 上构建失败：${core_dockerfile}"
        exit 1
    fi
    if ! grep -q 'unitree_sdk2) echo "rabbitbot_portable_unitree_sdk2"' "${integration_script}"; then
        log_error "portable core 运行期未注入 unitree_sdk2 依赖卷，宿主 GitHub 源码会遮蔽镜像内依赖：${integration_script}"
        exit 1
    fi
    if ! grep -q 'require_path "${AIR_ROOT}/unitree_sdk2"' "${image_script}"; then
        log_error "portable core 构建上下文未要求 unitree_sdk2，可能构建出缺 TTS 依赖的镜像：${image_script}"
        exit 1
    fi
    log_ok "portable core Unitree TTS 依赖策略正确：unitree_sdk2 已纳入 core 镜像与运行期依赖卷"
}

check_portable_models_policy() {
    # portable 冷启动默认启用 VLM/Embedding/STT；启动对应服务前必须自动检查/下载模型。
    local integration_script="${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"
    local loop_script="${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
    local ensure_script="${PROJECTS_DIR}/deploy/ensure_models.sh"
    local decoupled_compose="${REPO_DIR}/docker/portable/docker-compose.decoupled.yaml"
    if ! grep -q 'prepare_models_dir' "${integration_script}"; then
        log_error "core 启动脚本缺少按需模型目录策略：${integration_script}"
        exit 1
    fi
    if ! grep -q 'ensure_enabled_models' "${integration_script}"; then
        log_error "core 启动脚本缺少启用服务前模型自动检查/下载：${integration_script}"
        exit 1
    fi
    if ! grep -q 'ensure_enabled_models' "${loop_script}"; then
        log_error "loop 解耦启动链路缺少模型自动检查/下载：${loop_script}"
        exit 1
    fi
    if ! grep -q 'model_ready' "${ensure_script}"; then
        log_error "模型下载脚本缺少关键文件完整性检查：${ensure_script}"
        exit 1
    fi
    if ! grep -q 'RABBITBOT_ENABLE_EMBEDDING' "${ensure_script}"; then
        log_error "模型下载脚本缺少 Embedding 显式开关支持：${ensure_script}"
        exit 1
    fi
    if ! grep -q 'RABBITBOT_MODELS_CACHE_DIR' "${decoupled_compose}"; then
        log_error "解耦 compose 未使用 RABBITBOT_MODELS_CACHE_DIR 挂载模型目录：${decoupled_compose}"
        exit 1
    fi
    log_ok "portable 模型策略正确：启用服务前会自动检查/下载 VLM/Embedding/STT 模型"
}

check_python_venv_capability() {
    # 功能性探测 python3 -m venv：缺 python3-venv 时 venv 模块仍在，但 ensurepip 缺失导致创建失败。
    # 判定：venv 可用 → 通过；不可用但存在 apt-get（可经 INSTALL_HOST_PACKAGES=1 自动安装）→ 可解释告警放行；
    #       两者皆无 → 错误。
    local tmp_dir python_minor
    tmp_dir="$(mktemp -d)"
    if python3 -m venv "${tmp_dir}/venv_probe" >/dev/null 2>&1; then
        rm -rf "${tmp_dir}"
        log_ok "python3 -m venv 可用：$(python3 -V 2>&1)"
        return 0
    fi
    rm -rf "${tmp_dir}"
    python_minor="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if command -v apt-get >/dev/null 2>&1; then
        log_warn "python3 -m venv 当前不可用，但本机存在 apt-get，可自动补齐：执行 INSTALL_HOST_PACKAGES=1 bash deploy/bootstrap_host.sh，或手动 sudo apt-get install -y python3-venv python${python_minor}-venv。"
        return 0
    fi
    log_error "python3 -m venv 不可用且未找到 apt-get，bootstrap_host.sh 将无法创建控制台虚拟环境。请先为系统补齐 Python venv 能力（python3-venv / ensurepip）。"
    exit 1
}

check_port_topology_runtime() {
    # 运行期端口拓扑检查（仅当相关容器在运行时执行）：
    #   core 运行中：容器内不应有 robot_app.py 占用 28180。
    #   nav 运行中：28180 应处于监听状态（由 humble_robot_agent_bridge 提供）。
    local core_container="${RABBITBOT_PORTABLE_CORE_CONTAINER_NAME:-rabbitbot-unified-runtime}"
    if ! command -v docker >/dev/null 2>&1; then
        log_info "未找到 docker，跳过运行期端口拓扑检查。"
        return 0
    fi
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${core_container}"; then
        if docker exec "${core_container}" bash -lc 'pgrep -f "[u]vicorn robot_app:app" >/dev/null' >/dev/null 2>&1; then
            log_error "运行期端口拓扑异常：统一容器 ${core_container} 内仍在运行 robot_app.py（28180）。portable 模式下应由 nav bridge 提供 28180，请重建统一容器。"
            exit 1
        fi
        log_ok "运行期端口拓扑：core 容器未占用 28180（未运行 robot_app.py）"
    else
        log_info "core 容器未运行，跳过 core 侧端口拓扑检查。"
    fi
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -Eq 'rabbitbot-nav'; then
        if timeout 2 bash -lc '</dev/tcp/127.0.0.1/28180' >/dev/null 2>&1; then
            log_ok "运行期端口拓扑：nav 容器运行中且 28180 在监听（humble_robot_agent_bridge）"
        else
            log_warn "nav 容器运行中但 28180 未监听；bridge 可能仍在启动或已异常，请查看 nav 容器日志。"
        fi
    else
        log_info "nav 容器未运行，跳过 nav 侧端口拓扑检查。"
    fi
}

check_dockerignore_rules() {
    local required_entries=(
        '.git'
        'models/'
        'rabbitbot-dev-ros2-master/py38/'
        'rabbitbot-dev-ros2-master/py310/'
        'custom_action_ws/build/'
        'custom_action_ws/install/'
        'unitree_slam_example_new/example/build/'
        'unitree_slam_example_new/example/run_logs/'
    )
    local missing=()
    local entry
    for entry in "${required_entries[@]}"; do
        if ! grep -Fqx "${entry}" "${DOCKERIGNORE_FILE}"; then
            missing+=("${entry}")
        fi
    done
    if [ "${#missing[@]}" -ne 0 ]; then
        log_error ".dockerignore 缺少关键规则：${missing[*]}"
        exit 1
    fi
    log_ok ".dockerignore 关键规则存在：count=${#required_entries[@]}"
}

check_no_naked_runtime_hardcode() {
    local files=(
        "${REPO_DIR}/scripts/start_kuavo_agno_workflow.bash"
        "${REPO_DIR}/scripts/start_robot_app.bash"
        "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
        "${REPO_DIR}/scripts_1/start_control_console.sh"
        "${PROJECTS_DIR}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"
    )
    local patterns=(
        'export ROS_MASTER_URI=http://192\.168\.26\.1:11311'
        'export ROS_IP=192\.168\.26\.13'
        'NAV_INTERFACE="\$\{NAV_INTERFACE:-eno1\}"'
        'NETWORK_INTERFACE="\$\{1:-eno1\}"'
    )
    local matched=0
    local file pattern
    for file in "${files[@]}"; do
        [ -f "${file}" ] || continue
        for pattern in "${patterns[@]}"; do
            if grep -Eq "${pattern}" "${file}"; then
                log_error "检测到未环境变量化的运行时硬编码：file=${file}, pattern=${pattern}"
                matched=1
            fi
        done
    done
    if [ "${matched}" -ne 0 ]; then
        exit 1
    fi
    log_ok "关键运行脚本未发现未环境变量化的固定 IP / 网卡硬编码"
}

# ---------------------------------------------------------------------------
# 1. 共享检查：目录结构、清单、env、dockerignore、portable docker 文件、部署脚本
# ---------------------------------------------------------------------------
log_info "检查共享目录结构与文件"
require_path "${REPO_DIR}"
require_path "${PROJECTS_DIR}/humble_robot_agent_bridge.py"
require_path "${PROJECTS_DIR}/custom_action_ws/src/custom_action_interfaces"
require_path "${MANIFEST_FILE}"
# 本机 portable.env 不进入 Git；共享检查只要求可迁移模板存在，实际 env 是否就绪由各模式自行提示。
require_path "${PORTABLE_ENV_FILE}.example"
require_path "${DOCKERIGNORE_FILE}"
require_path "${REPO_DIR}/docker/portable/compose.yaml"
require_path "${REPO_DIR}/docker/portable/docker-compose.decoupled.yaml"
require_path "${REPO_DIR}/docker/portable/core.Dockerfile"
require_path "${REPO_DIR}/docker/portable/nav.Dockerfile"
require_path "${REPO_DIR}/docker/portable/nav_entrypoint.sh"
require_path "${REPO_DIR}/scripts_1/start_loop_entry.sh"
require_path "${REPO_DIR}/scripts_1/start_nav_bridge_portable.sh"
require_path "${PROJECTS_DIR}/deploy/bootstrap_host.sh"
require_path "${PROJECTS_DIR}/deploy/ensure_models.sh"
require_path "${PROJECTS_DIR}/deploy/build_or_pull_images.sh"
require_path "${PROJECTS_DIR}/deploy/start_portable_stack.sh"
require_path "${PROJECTS_DIR}/deploy/setup_robot_network.sh"
require_path "${PROJECTS_DIR}/deploy/export_portable_images.sh"
require_path "${PROJECTS_DIR}/deploy/import_portable_images.sh"

log_info "检查依赖清单"
manifest_result="$(check_manifest)"
log_ok "依赖清单检查通过：${manifest_result}"
check_portable_env_keys
check_dockerignore_rules
check_core_skips_internal_28180
check_portable_models_policy
check_portable_unitree_tts_policy
check_port_topology_runtime

log_info "检查脚本语法"
scripts=(
    "${REPO_DIR}/scripts_1/start_nav_bridge_workflow_loop.sh"
    "${REPO_DIR}/scripts_1/start_unified_integration_workflow.sh"
    "${REPO_DIR}/scripts_1/stop_unified_workflow.sh"
    "${REPO_DIR}/scripts_1/build_unified_runtime_image.sh"
    "${REPO_DIR}/scripts_1/start_nav_bridge_portable.sh"
    "${REPO_DIR}/scripts_1/start_loop_entry.sh"
    "${REPO_DIR}/scripts_1/start_control_console.sh"
    "${REPO_DIR}/scripts/build_unitree_g1_tts_bridge.sh"
    "${PROJECTS_DIR}/deploy/bootstrap_host.sh"
    "${PROJECTS_DIR}/deploy/setup_robot_network.sh"
    "${PROJECTS_DIR}/deploy/ensure_models.sh"
    "${PROJECTS_DIR}/deploy/build_or_pull_images.sh"
    "${PROJECTS_DIR}/deploy/start_portable_stack.sh"
    "${PROJECTS_DIR}/deploy/export_portable_images.sh"
    "${PROJECTS_DIR}/deploy/import_portable_images.sh"
)
for script in "${scripts[@]}"; do
    bash -n "$script"
    log_ok "bash -n 通过：$script"
done

log_info "检查 Python 编译"
cd "${REPO_DIR}"
python3 -m py_compile \
    rabbitbot/control_console/app.py \
    rabbitbot/control_console/config.py \
    rabbitbot/control_console/commands.py \
    rabbitbot/control_console/status.py \
    rabbitbot/agno_agents/workflow.py \
    rabbitbot/provider.py \
    rabbitbot/audio/unitree_g1_tts.py \
    robot_app.py memory_app.py tts_app.py
log_ok "Python 编译通过"

log_info "检查控制台状态解析运行时回归"
PYTHONPATH="${REPO_DIR}" python3 - <<'PY'
from rabbitbot.control_console.status import parse_latest_pose_from_lines

pose = parse_latest_pose_from_lines([], source_label="portable 自检空导航日志")
if pose.available:
    raise SystemExit("empty_nav_log_unexpected_pose")
print(f"pose_available={pose.available}, localized={pose.localized}, message={pose.message}")
PY
log_ok "控制台状态解析运行时回归通过"

log_info "检查动态 sudoers 模板"
sudoers_tmp="$(mktemp)"
trap 'rm -f "${sudoers_tmp}"' EXIT
cat >"${sudoers_tmp}" <<SUDOERS
# 允许局域网控制台只管理 RabbitBot 主循环服务。
$(id -un) ALL=(root) NOPASSWD: /usr/bin/systemctl start rabbitbot-loop.service, /usr/bin/systemctl restart rabbitbot-loop.service, /usr/bin/systemctl stop rabbitbot-loop.service
SUDOERS
visudo -cf "${sudoers_tmp}"
log_ok "动态 sudoers 模板语法通过：user=$(id -un)"

log_info "检查 portable 运行时关键配置（共享）"
check_no_naked_runtime_hardcode
if ! grep -Eq '^RABBITBOT_RUNTIME_MODE=portable$' "${PORTABLE_ENV_EFFECTIVE_FILE}"; then
    log_warn "portable env 当前未默认启用 portable 模式；若准备在新 Orin 冷启动，请先执行 bootstrap_host.sh 或手动确认 runtime/portable.env。"
else
    log_ok "portable env 默认模式为 portable"
fi

log_info "检查旧路径硬编码（共享）"
if grep -RIn "/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master" \
    "${REPO_DIR}/rabbitbot" "${REPO_DIR}/scripts" "${REPO_DIR}/scripts_1" "${REPO_DIR}/deploy" \
    --exclude-dir=__pycache__ --exclude='*.pyc'; then
    log_error "仍存在旧项目根硬编码，请先处理。"
    exit 1
fi
log_ok "未发现核心源码旧项目根硬编码"

# ---------------------------------------------------------------------------
# 2. 构建机模式专属检查：要求外部构建源存在
# ---------------------------------------------------------------------------
run_builder_checks() {
    log_info "构建机模式：检查外部构建源是否存在"
    if [ -d "${PROJECTS_DIR}/models" ]; then
        log_ok "模型目录已存在：${PROJECTS_DIR}/models"
    else
        log_info "模型目录尚不存在，将由 deploy/ensure_models.sh 在启用模型服务前自动创建并下载：${PROJECTS_DIR}/models"
    fi
    require_path "${PROJECTS_DIR}/custom_action_ws/install/setup.bash"
    require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation66"
    require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/g1ArmOfficialActionServer"
    require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation"
    require_path "${PROJECTS_DIR}/unitree_slam_example_new/example/build/gestureTopicBridge"
    require_path "${PROJECTS_DIR}/unitree_sdk2/build/bin/g1_loco_client"
    require_path "${PROJECTS_DIR}/dfx_inspire_service/build/inspire_g1"
    require_path "${PROJECTS_DIR}/unitree_sdk2"
    require_path "${PROJECTS_DIR}/vln/ros2_ws/install/setup.bash"
    require_path "${PROJECTS_DIR}/pyorbbecsdk-v2-py310/install/lib"
    require_path "${REPO_DIR}/py38/bin/python"
    require_path "${REPO_DIR}/py310/bin/python"
    require_path "/opt/ros/humble/setup.bash"

    log_info "构建机模式：检查 portable core 基础镜像"
    if docker image inspect "${RABBITBOT_PORTABLE_CORE_BASE_IMAGE:-rabbitbot-unified-runtime:20260518}" >/dev/null 2>&1; then
        log_ok "portable core 基础镜像存在：${RABBITBOT_PORTABLE_CORE_BASE_IMAGE:-rabbitbot-unified-runtime:20260518}"
    else
        log_error "构建机缺少 portable core 基础镜像：${RABBITBOT_PORTABLE_CORE_BASE_IMAGE:-rabbitbot-unified-runtime:20260518}，无法构建自包含 core 镜像。"
        exit 1
    fi

    log_info "构建机模式：检查 example 运行脚本语法"
    local example_scripts=(
        "${PROJECTS_DIR}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"
        "${PROJECTS_DIR}/unitree_slam_example_new/example/one_click_start.sh"
        "${PROJECTS_DIR}/unitree_slam_example_new/example/start_robot_stack_host.sh"
        "${PROJECTS_DIR}/unitree_slam_example_new/example/setup_inspire_sudo_nopasswd.sh"
    )
    local s
    for s in "${example_scripts[@]}"; do
        bash -n "${s}"
        log_ok "bash -n 通过：${s}"
    done

    log_info "构建机模式：检查 air ROS 工作区动态库解析"
    local custom_lib
    custom_lib="$({
        bash -lc "set +u; source /opt/ros/humble/setup.bash; export COLCON_CURRENT_PREFIX='${PROJECTS_DIR}/custom_action_ws/install'; source '${PROJECTS_DIR}/custom_action_ws/install/setup.bash'; set -u; ldd '${PROJECTS_DIR}/unitree_slam_example_new/example/build/goGoalNavigation66' | awk '/libcustom_action_interfaces__rosidl_typesupport_cpp.so/ {print \$3; exit}'"
    })"
    case "$custom_lib" in
        "${PROJECTS_DIR}/custom_action_ws/install"/*)
            log_ok "custom_action_interfaces 动态库解析到 air 目录：$custom_lib"
            ;;
        *)
            log_error "custom_action_interfaces 动态库未解析到 air 目录：${custom_lib:-未找到}"
            exit 1
            ;;
    esac

    log_info "构建机模式：检查 example 运行脚本旧 projects 路径硬编码"
    if grep -RIn "/mnt/ssd/navgation/projects/" \
        "${PROJECTS_DIR}/unitree_slam_example_new/example"/*.sh \
        --exclude='*.bak' --exclude='*.bak_*' | grep -v "/mnt/ssd/navgation/projects/air_robot_gt_projects"; then
        log_error "unitree_slam 示例运行脚本仍存在旧 projects 路径硬编码，请先处理。"
        exit 1
    fi
    log_ok "未发现 example 运行脚本旧项目根硬编码"
}

# ---------------------------------------------------------------------------
# 3. 全新 Orin 模式专属检查：外部目录可缺失，转而要求镜像/初始化结果
# ---------------------------------------------------------------------------
run_clean_orin_checks() {
    if [ ! -f "${PORTABLE_ENV_FILE}" ]; then
        log_warn "本机 ${PORTABLE_ENV_FILE} 尚未生成，本次按模板 portable.env.example 做只读默认校验；正式部署前请先执行 deploy/bootstrap_host.sh。"
    fi
    log_info "全新 Orin 模式：确认外部构建目录缺失时仍可通过（这些目录已固化进 portable 镜像）"
    info_optional_absent "${REPO_DIR}/py38"
    info_optional_absent "${REPO_DIR}/py310"
    info_optional_absent "${PROJECTS_DIR}/vln"
    info_optional_absent "${PROJECTS_DIR}/pyorbbecsdk-v2-py310"
    info_optional_absent "${PROJECTS_DIR}/unitree_sdk2"
    info_optional_absent "${PROJECTS_DIR}/custom_action_ws/install"
    info_optional_absent "${PROJECTS_DIR}/dfx_inspire_service"

    log_info "全新 Orin 模式：校验已导入的 portable 镜像"
    if ! command -v docker >/dev/null 2>&1; then
        log_error "全新 Orin 缺少 docker，无法校验 portable 镜像。"
        exit 1
    fi
    local img label rc=0
    for pair in "${CORE_IMAGE}|portable_core" "${NAV_IMAGE}|portable_nav"; do
        img="${pair%%|*}"
        label="${pair##*|}"
        if docker image inspect "${img}" >/dev/null 2>&1; then
            log_ok "portable 镜像已存在：label=${label}, image=${img}"
        else
            log_error "全新 Orin 缺少 portable 镜像：label=${label}, image=${img}。请先用 deploy/import_portable_images.sh 导入离线镜像。"
            rc=1
        fi
    done
    if [ "${rc}" -ne 0 ]; then
        exit 1
    fi

    log_info "全新 Orin 模式：校验宿主 venv 能力（bootstrap_host.sh 的前置条件）"
    check_python_venv_capability

    log_info "全新 Orin 模式：校验宿主初始化结果与地图路径配置"
    if [ -x "${REPO_DIR}/runtime/control_console_venv/bin/python" ]; then
        log_ok "控制台轻量虚拟环境已就绪：${REPO_DIR}/runtime/control_console_venv"
    else
        log_warn "未发现控制台轻量虚拟环境：${REPO_DIR}/runtime/control_console_venv；请先执行 deploy/bootstrap_host.sh。"
    fi

    local map_path="${RABBITBOT_NAV_MAP_PATH:-}"
    if [ -z "${map_path}" ]; then
        log_error "未配置导航地图路径，请在 runtime/portable.env 设置 RABBITBOT_NAV_MAP_PATH。"
        exit 1
    fi
    if [ -e "${map_path}" ]; then
        log_ok "导航地图文件存在：RABBITBOT_NAV_MAP_PATH=${map_path}"
    else
        log_warn "导航地图在 Orin 本地不可见：RABBITBOT_NAV_MAP_PATH=${map_path}；地图不随仓库迁移。若机器人侧已有该地图且可定位，这是可接受状态；迁移验收仍需确认机器人侧路径存在，或更新 runtime/portable.env 的 RABBITBOT_NAV_MAP_PATH。"
    fi
    log_ok "全新 Orin 模式专属检查完成"
}

if [ "${PORTABLE_CHECK_MODE}" = "builder" ]; then
    run_builder_checks
else
    run_clean_orin_checks
fi

log_ok "air_robot_gt_projects 自检完成：PORTABLE_CHECK_MODE=${PORTABLE_CHECK_MODE}"

#!/usr/bin/env bash
# 检查 air_robot_gt_projects 在 legacy / portable 两条路径下的关键文件、环境、路径和语法。

set -euo pipefail

AIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${AIR_ROOT}/rabbitbot-dev-ros2-master"
PROJECTS_DIR="${AIR_ROOT}"
PORTABLE_ENV_FILE="${REPO_DIR}/runtime/portable.env"
MANIFEST_FILE="${AIR_ROOT}/third_party/manifest.lock"
DOCKERIGNORE_FILE="${AIR_ROOT}/.dockerignore"

log_info() { echo "[INFO] $1"; }
log_ok() { echo "[OK] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
    log_ok "存在：$1"
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
print('manifest-ok')
PY
}

check_portable_env_keys() {
    local required_keys=(
        RABBITBOT_RUNTIME_MODE
        RABBITBOT_NAV_RUNTIME
        RABBITBOT_PORTABLE_CORE_IMAGE
        RABBITBOT_PORTABLE_NAV_IMAGE
        RABBITBOT_DDS_INTERFACE
        RABBITBOT_DDS_HOST_CIDR
        RABBITBOT_NAV_MAP_PATH
        RABBITBOT_ENABLE_VLM
        RABBITBOT_ENABLE_STT
    )
    for key in "${required_keys[@]}"; do
        if ! grep -Eq "^${key}=" "${PORTABLE_ENV_FILE}"; then
            log_error "portable env 缺少必填键：${key}"
            exit 1
        fi
    done
    log_ok "portable env 关键键存在：count=${#required_keys[@]}"
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
        'export ROS_MASTER_URI=http://192\\.168\\.26\\.1:11311'
        'export ROS_IP=192\\.168\\.26\\.13'
        'NAV_INTERFACE="\\$\\{NAV_INTERFACE:-eno1\\}"'
        'NETWORK_INTERFACE="\\$\\{1:-eno1\\}"'
    )
    local matched=0
    for file in "${files[@]}"; do
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

log_info "检查目录结构"
require_path "${REPO_DIR}"
require_path "${PROJECTS_DIR}/models"
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
require_path "${PROJECTS_DIR}/humble_robot_agent_bridge.py"
require_path "${REPO_DIR}/py38/bin/python"
require_path "${REPO_DIR}/py310/bin/python"
require_path "/opt/ros/humble/setup.bash"
require_path "${MANIFEST_FILE}"
require_path "${PORTABLE_ENV_FILE}"
require_path "${DOCKERIGNORE_FILE}"
require_path "${REPO_DIR}/docker/portable/compose.yaml"
require_path "${REPO_DIR}/docker/portable/core.Dockerfile"
require_path "${REPO_DIR}/docker/portable/nav.Dockerfile"
require_path "${REPO_DIR}/scripts_1/start_loop_entry.sh"
require_path "${REPO_DIR}/scripts_1/start_nav_bridge_portable.sh"
require_path "${PROJECTS_DIR}/deploy/bootstrap_host.sh"
require_path "${PROJECTS_DIR}/deploy/ensure_models.sh"
require_path "${PROJECTS_DIR}/deploy/build_or_pull_images.sh"
require_path "${PROJECTS_DIR}/deploy/start_portable_stack.sh"
require_path "${PROJECTS_DIR}/deploy/setup_robot_network.sh"

log_info "检查 Docker 镜像"
if docker image inspect rabbitbot-unified-runtime:20260518 >/dev/null 2>&1; then
    log_ok "legacy unified 基础镜像存在：rabbitbot-unified-runtime:20260518"
else
    log_warn "当前宿主缺少 legacy unified 基础镜像：rabbitbot-unified-runtime:20260518；若后续只走可拉取的 portable core 成品镜像，可忽略本告警。"
fi

log_info "检查依赖清单"
manifest_result="$(check_manifest)"
log_ok "依赖清单检查通过：${manifest_result}"
check_portable_env_keys
check_dockerignore_rules

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
    "${PROJECTS_DIR}/unitree_slam_example_new/example/start_nav_arm_bridge.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/one_click_start.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/start_robot_stack_host.sh"
    "${PROJECTS_DIR}/unitree_slam_example_new/example/setup_inspire_sudo_nopasswd.sh"
    "${PROJECTS_DIR}/deploy/bootstrap_host.sh"
    "${PROJECTS_DIR}/deploy/setup_robot_network.sh"
    "${PROJECTS_DIR}/deploy/ensure_models.sh"
    "${PROJECTS_DIR}/deploy/build_or_pull_images.sh"
    "${PROJECTS_DIR}/deploy/start_portable_stack.sh"
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

log_info "检查 sudoers 模板"
visudo -cf "${REPO_DIR}/scripts_1/systemd/rabbitbot-control-console.sudoers"
log_ok "sudoers 模板语法通过"

log_info "检查 air ROS 工作区解析"
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

log_info "检查旧路径硬编码"
if grep -RIn "/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master" \
    "${REPO_DIR}/rabbitbot" "${REPO_DIR}/scripts" "${REPO_DIR}/scripts_1" "${REPO_DIR}/deploy" \
    --exclude-dir=__pycache__ --exclude='*.pyc'; then
    log_error "仍存在旧项目根硬编码，请先处理。"
    exit 1
fi
if grep -RIn "/mnt/ssd/navgation/projects/" \
    "${PROJECTS_DIR}/unitree_slam_example_new/example"/*.sh \
    --exclude='*.bak' --exclude='*.bak_*' | grep -v "/mnt/ssd/navgation/projects/air_robot_gt_projects"; then
    log_error "unitree_slam 示例运行脚本仍存在旧 projects 路径硬编码，请先处理。"
    exit 1
fi
log_ok "未发现运行脚本旧项目根硬编码"

log_info "检查 portable 运行时关键配置"
check_no_naked_runtime_hardcode
if ! grep -Eq '^RABBITBOT_RUNTIME_MODE=portable$' "${PORTABLE_ENV_FILE}"; then
    log_warn "portable env 当前未默认启用 portable 模式；若准备在新 Orin 冷启动，请先执行 bootstrap_host.sh 或手动确认 runtime/portable.env。"
else
    log_ok "portable env 默认模式为 portable"
fi

log_ok "air_robot_gt_projects 自检完成"

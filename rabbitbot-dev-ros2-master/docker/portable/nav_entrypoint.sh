#!/usr/bin/env bash
set -Eeuo pipefail

DDS_INTERFACE="${RABBITBOT_DDS_INTERFACE:-eno1}"
NAV_MAP_PATH="${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}"
WORKSPACE_ROOT="/workspace/projects"
NAV_ROOT="${WORKSPACE_ROOT}/unitree_slam_example_new/example"
WS_SETUP="${WORKSPACE_ROOT}/custom_action_ws/install/setup.bash"
ROS_SETUP="/opt/ros/humble/setup.bash"
RUN_DIR="${NAV_ROOT}/run_logs/nav_portable_$(date +%Y%m%d_%H%M%S)"
LATEST_LINK="${NAV_ROOT}/run_logs/latest_portable"

log_info() { echo "[INFO] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

require_path() {
    if [ ! -e "$1" ]; then
        log_error "缺少必要路径：$1"
        exit 1
    fi
}

start_bg() {
    local name="$1"
    local cmd="$2"
    local log_file="${RUN_DIR}/${name}.log"
    local pid_file="${RUN_DIR}/${name}.pid"
    nohup bash -lc "$cmd" >"${log_file}" 2>&1 &
    local pid=$!
    echo "${pid}" >"${pid_file}"
    log_info "后台节点已启动：name=${name}, pid=${pid}, log=${log_file}"
}

cleanup() {
    log_info "portable nav 容器收到退出信号，开始停止后台节点"
    if compgen -G "${RUN_DIR}/*.pid" >/dev/null; then
        xargs -r kill < <(cat "${RUN_DIR}"/*.pid) 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

require_path "${ROS_SETUP}"
require_path "${WS_SETUP}"
require_path "${NAV_ROOT}/build/goGoalNavigation66"
require_path "${NAV_ROOT}/build/g1ArmOfficialActionServer"
require_path "${WORKSPACE_ROOT}/humble_robot_agent_bridge.py"

mkdir -p "${RUN_DIR}"
ln -sfnT "${RUN_DIR}" "${LATEST_LINK}"

if [ ! -e "${NAV_MAP_PATH}" ]; then
    log_warn "地图路径当前在容器内不可见，仍继续启动：path=${NAV_MAP_PATH}"
fi

COMMON_ENV="set +u; source '${ROS_SETUP}'; export COLCON_CURRENT_PREFIX='${WORKSPACE_ROOT}/custom_action_ws/install'; source '${WS_SETUP}'; set -u"
CMD_NAV="${COMMON_ENV}; cd '${NAV_ROOT}' && ./build/goGoalNavigation66 '${DDS_INTERFACE}' '${NAV_MAP_PATH}'"
CMD_ARM="${COMMON_ENV}; cd '${NAV_ROOT}' && ./build/g1ArmOfficialActionServer '${DDS_INTERFACE}'"

log_info "portable nav 容器启动：interface=${DDS_INTERFACE}, map=${NAV_MAP_PATH}, run_dir=${RUN_DIR}"
start_bg "01_goGoalNavigation66" "${CMD_NAV}"
sleep 2
start_bg "02_g1ArmOfficialActionServer" "${CMD_ARM}"
sleep 2
# 把后台节点日志透传到容器 stdout：宿主 loop 健康检查读取的是 compose 输出日志，
# 必须能在其中看到 DDS/网卡/进程异常（如 eno1 不可用、DdsException）与 [Ready]/[Pose] 状态行。
tail -n +1 -F "${RUN_DIR}/01_goGoalNavigation66.log" "${RUN_DIR}/02_g1ArmOfficialActionServer.log" 2>/dev/null &
log_info "前台启动 28180 bridge，日志：${RUN_DIR}/03_humble_robot_agent_bridge.log"
set +u
source "${ROS_SETUP}"
export COLCON_CURRENT_PREFIX="${WORKSPACE_ROOT}/custom_action_ws/install"
source "${WS_SETUP}"
set -u
cd "${WORKSPACE_ROOT}"
python3 -m uvicorn humble_robot_agent_bridge:app --host 0.0.0.0 --port 28180 --log-level info 2>&1 | tee "${RUN_DIR}/03_humble_robot_agent_bridge.log"

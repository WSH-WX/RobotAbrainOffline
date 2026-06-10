#!/usr/bin/env bash
set -euo pipefail

NETWORK_INTERFACE="${1:-eno1}"
PCD_PATH="${2:-/home/unitree/test.pcd}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECTS_DIR="${RABBITBOT_PROJECTS_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
EXAMPLE_DIR="${NAV_EXAMPLE_DIR:-${SCRIPT_DIR}}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
WS_SETUP="${WS_SETUP:-${PROJECTS_DIR}/custom_action_ws/install/setup.bash}"
BRIDGE_APP="humble_robot_agent_bridge:app"
RUN_DIR="$EXAMPLE_DIR/run_logs/nav_arm_bridge_$(date +%Y%m%d_%H%M%S)"
LATEST_LINK="$EXAMPLE_DIR/run_logs/latest_nav_arm_bridge"

require_path() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
}

start_bg() {
  local name="$1"
  local cmd="$2"
  local log_file="$RUN_DIR/${name}.log"
  local pid_file="$RUN_DIR/${name}.pid"

  nohup bash -lc "$cmd" >"$log_file" 2>&1 &
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "[$name] pid=$pid log=$log_file"
}

start_log_tail() {
  local name="$1"
  local log_file="$2"
  local pid_file="$RUN_DIR/${name}.pid"

  tail -n +1 -F "$log_file" &
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "[$name] pid=$pid following $log_file"
}

cleanup_on_exit() {
  echo
  echo "Stopping background nodes started by this script..."
  if compgen -G "$RUN_DIR/*.pid" >/dev/null; then
    xargs -r kill < <(cat "$RUN_DIR"/*.pid) 2>/dev/null || true
  fi
}

require_path "$ROS_SETUP"
require_path "$WS_SETUP"
require_path "$EXAMPLE_DIR/build/goGoalNavigation66"
require_path "$EXAMPLE_DIR/build/g1ArmOfficialActionServer"
require_path "$PROJECTS_DIR/humble_robot_agent_bridge.py"

mkdir -p "$RUN_DIR"
ln -sfnT "$RUN_DIR" "$LATEST_LINK"

if [[ ! -e "$PCD_PATH" ]]; then
  echo "Warning: PCD path is not visible from this shell: $PCD_PATH" >&2
  echo "The navigation node will still be started with this path." >&2
fi

if ss -ltnp | grep -q ':28180'; then
  echo "Port 28180 is already occupied:" >&2
  ss -ltnp | grep ':28180' >&2 || true
  echo "Stop the process above first, then rerun this script." >&2
  exit 1
fi

COMMON_ENV="set +u; source '$ROS_SETUP'; source '$WS_SETUP'; set -u"
CMD_NAV="$COMMON_ENV; cd '$EXAMPLE_DIR' && ./build/goGoalNavigation66 '$NETWORK_INTERFACE' '$PCD_PATH'"
CMD_ARM="$COMMON_ENV; cd '$EXAMPLE_DIR' && ./build/g1ArmOfficialActionServer '$NETWORK_INTERFACE'"
CMD_BRIDGE="$COMMON_ENV; cd '$PROJECTS_DIR' && python3 -m uvicorn $BRIDGE_APP --host 0.0.0.0 --port 28180 --log-level info"

trap cleanup_on_exit INT TERM

echo "Starting navigation, arm action server, and Humble 28180 bridge"
echo "  interface : $NETWORK_INTERFACE"
echo "  pcd       : $PCD_PATH"
echo "  logs      : $RUN_DIR"
echo "  ros setup : $ROS_SETUP"
echo "  ws setup  : $WS_SETUP"
echo

# 1. 启动导航节点
start_bg "01_goGoalNavigation66" "$CMD_NAV"
start_log_tail "01_goGoalNavigation66_tail" "$RUN_DIR/01_goGoalNavigation66.log"
sleep 2

# 2. 启动手臂节点
start_bg "02_g1ArmOfficialActionServer" "$CMD_ARM"
sleep 2

# 3. 启动宿主机 Humble 28180 bridge，保持前台运行，方便高层脚本检测端口已占用。
echo "[03_humble_robot_agent_bridge] running in foreground"
echo "  log=$RUN_DIR/03_humble_robot_agent_bridge.log"
echo "  Press Ctrl+C to stop bridge and background nodes started by this script."
echo
cd "$PROJECTS_DIR"
set +u
source "$ROS_SETUP"
source "$WS_SETUP"
set -u
python3 -m uvicorn "$BRIDGE_APP" --host 0.0.0.0 --port 28180 --log-level info 2>&1 | tee "$RUN_DIR/03_humble_robot_agent_bridge.log"

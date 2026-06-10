#!/usr/bin/env bash
set -eo pipefail

NETWORK_INTERFACE="${1:-eno1}"
PCD_PATH="${2:-/home/unitree/test3.pcd}"
NAV_SPEED="${3:-0.6}"
SUDO_PASSWORD="${SUDO_PASSWORD:-111111}"

ROS_SETUP="/opt/ros/humble/setup.bash"
WS_SETUP="/mnt/ssd/navgation/projects/custom_action_ws/install/setup.bash"
PROJECTS_DIR="/mnt/ssd/navgation/projects"
EXAMPLE_DIR="$PROJECTS_DIR/unitree_slam_example_new/example"
LOCO_DIR="$PROJECTS_DIR/unitree_sdk2/build/bin"
INSPIRE_DIR="$PROJECTS_DIR/dfx_inspire_service/build"
BRIDGE_APP="humble_robot_agent_bridge:app"
RUN_DIR="$EXAMPLE_DIR/run_logs/$(date +%Y%m%d_%H%M%S)"
LATEST_LINK="$EXAMPLE_DIR/run_logs/latest"

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
  echo "$pid" > "$pid_file"
  echo "[$name] pid=$pid log=$log_file"
}

stop_known_conflicts() {
  pkill -f "uvicorn $BRIDGE_APP --host 0.0.0.0 --port 28180" 2>/dev/null || true
  pkill -f "uvicorn robot_app:app.*--port 28180" 2>/dev/null || true
  pkill -f "[g]oGoalNavigation" 2>/dev/null || true
  pkill -f "[g]estureTopicBridge" 2>/dev/null || true
  printf '%s\n' "$SUDO_PASSWORD" | sudo -S pkill -f "[i]nspire_g1" 2>/dev/null || true
  sleep 1
}

check_bridge_port_free() {
  if ss -ltnp | grep -q ':28180'; then
    echo "Port 28180 is still occupied:" >&2
    ss -ltnp | grep ':28180' >&2 || true
    echo "Stop the process above first, then rerun this script." >&2
    exit 1
  fi
}

require_path "$ROS_SETUP"
require_path "$WS_SETUP"
require_path "$LOCO_DIR/g1_loco_client"
require_path "$EXAMPLE_DIR/build/goGoalNavigation"
require_path "$PROJECTS_DIR/humble_robot_agent_bridge.py"
require_path "$INSPIRE_DIR/inspire_g1"
require_path "$EXAMPLE_DIR/build/gestureTopicBridge"

update_latest_link() {
  if [[ -L "$LATEST_LINK" || ! -e "$LATEST_LINK" ]]; then
    ln -sfnT "$RUN_DIR" "$LATEST_LINK"
    return
  fi

  if [[ -d "$LATEST_LINK" ]]; then
    local backup_path="${LATEST_LINK}.bak_$(date +%Y%m%d_%H%M%S)"
    mv "$LATEST_LINK" "$backup_path"
    echo "Existing run_logs/latest directory moved to: $backup_path"
    ln -sfnT "$RUN_DIR" "$LATEST_LINK"
    return
  fi

  echo "Cannot update $LATEST_LINK because it is not a symlink or directory." >&2
  exit 1
}

mkdir -p "$RUN_DIR"
update_latest_link

if [[ ! -e "$PCD_PATH" ]]; then
  echo "Note: PCD path is not visible from this shell: $PCD_PATH"
  echo "Passing it to goGoalNavigation anyway; the SLAM service may resolve it on its own side."
fi

stop_known_conflicts
check_bridge_port_free

COMMON_ENV="source '$ROS_SETUP' && source '$WS_SETUP'"
CMD_LOCO="cd '$LOCO_DIR' && ./g1_loco_client --network_interface='$NETWORK_INTERFACE' --set_fsm_id=801 --disable_service=vui_service"
CMD_NAV="$COMMON_ENV && cd '$EXAMPLE_DIR' && ./build/goGoalNavigation '$NETWORK_INTERFACE' '$PCD_PATH' --nav_speed='$NAV_SPEED'"
CMD_BRIDGE="$COMMON_ENV && cd '$PROJECTS_DIR' && python3 -m uvicorn $BRIDGE_APP --host 0.0.0.0 --port 28180 --log-level info"
CMD_INSPIRE="cd '$INSPIRE_DIR' && printf '%s\n' '$SUDO_PASSWORD' | sudo -S ./inspire_g1"
CMD_GESTURE="$COMMON_ENV && cd '$EXAMPLE_DIR' && ./build/gestureTopicBridge '$NETWORK_INTERFACE'"

echo "Starting robot stack"
echo "  interface : $NETWORK_INTERFACE"
echo "  pcd       : $PCD_PATH"
echo "  nav_speed : $NAV_SPEED"
echo "  logs      : $RUN_DIR"
echo

# 1. Disable service and switch to walk/run locomotion mode.
start_bg "01_loco_mode" "$CMD_LOCO"
sleep 2

# 2. Start navigation action server. This also manages arm action process after arrival.
start_bg "02_goGoalNavigation" "$CMD_NAV"
sleep 2

# 3. Start host Humble bridge on 28180 before the high-level Docker robot_app can occupy it.
start_bg "03_humble_robot_agent_bridge" "$CMD_BRIDGE"
sleep 2

# 4. Start Inspire hand low-level controller with sudo password supplied from SUDO_PASSWORD.
start_bg "04_inspire_g1" "$CMD_INSPIRE"
sleep 2

# 5. Start gesture topic bridge for high-level hand commands.
start_bg "05_gestureTopicBridge" "$CMD_GESTURE"
sleep 1

echo
echo "Startup commands issued. Process snapshot:"
ps -eo pid,etime,pcpu,pmem,args | grep -E 'g1_loco_client|goGoalNavigation|humble_robot_agent_bridge|inspire_g1|gestureTopicBridge' | grep -v grep || true

echo
echo "Bridge port check:"
ss -ltnp | grep ':28180' || true

echo
echo "Useful commands:"
echo "  tail -f $RUN_DIR/*.log"
echo "  tail -f $LATEST_LINK/*.log"
echo "  xargs -r kill < <(cat $RUN_DIR/*.pid)"
echo "  pkill -f 'g1_loco_client|goGoalNavigation|humble_robot_agent_bridge|inspire_g1|gestureTopicBridge'"

echo
echo "Printing goGoalNavigation log in this terminal:"
echo "  log: $RUN_DIR/02_goGoalNavigation.log"
echo "  Ctrl+C stops log following only; background processes keep running."
touch "$RUN_DIR/02_goGoalNavigation.log"
tail -n 120 -F "$RUN_DIR/02_goGoalNavigation.log"

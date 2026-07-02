#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORTABLE_ENV_FILE="${RABBITBOT_PORTABLE_ENV_FILE:-${PROJECT_DIR}/runtime/portable.env}"
CONTROL_CONSOLE_VENV="${PROJECT_DIR}/runtime/control_console_venv"

if [ -f "${PORTABLE_ENV_FILE}" ]; then
  set -a
  source "${PORTABLE_ENV_FILE}"
  set +a
elif [ -f "${PORTABLE_ENV_FILE}.example" ]; then
  # 本机 portable.env 不进入 Git；不存在时回退读取随仓库迁移的模板。
  echo "[WARN] 未找到本机配置 ${PORTABLE_ENV_FILE}，回退读取模板 ${PORTABLE_ENV_FILE}.example；正式部署请先执行 deploy/bootstrap_host.sh 生成本机 portable.env。"
  set -a
  source "${PORTABLE_ENV_FILE}.example"
  set +a
fi

export RABBITBOT_PROJECT_ROOT="${RABBITBOT_PROJECT_ROOT:-${PROJECT_DIR}}"
export RABBITBOT_CONSOLE_HOST="${RABBITBOT_CONSOLE_HOST:-0.0.0.0}"
export RABBITBOT_CONSOLE_PORT="${RABBITBOT_CONSOLE_PORT:-8080}"
export NAV_PCD_PATH="${NAV_PCD_PATH:-${RABBITBOT_NAV_MAP_PATH:-/home/unitree/test9.pcd}}"

if [ -x "${CONTROL_CONSOLE_VENV}/bin/python" ]; then
  PYTHON_BIN="${CONTROL_CONSOLE_VENV}/bin/python"
  echo "[INFO] 使用控制台轻量虚拟环境：${PYTHON_BIN}"
else
  PYTHON_BIN="python3"
  echo "[INFO] 未发现控制台轻量虚拟环境，回退到系统 Python：${PYTHON_BIN}"
fi

cd "${PROJECT_DIR}"
exec "${PYTHON_BIN}" -m rabbitbot.control_console

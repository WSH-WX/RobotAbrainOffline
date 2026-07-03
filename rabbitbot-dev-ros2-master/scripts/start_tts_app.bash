#!/usr/bin/env bash

export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

export HF_ENDPOINT=https://hf-mirror.com

#export HTTP_PROXY=http://127.0.0.1:7897
#export HTTPS_PROXY=http://127.0.0.1:7897

#export TTS_CLOUD="http://10.10.30.22:28187"

source /opt/venv/bin/activate

RABBITBOT_TTS_AUDIO_BACKEND="${RABBITBOT_TTS_AUDIO_BACKEND:-alsa}"
RABBITBOT_ENABLE_PULSE_AUDIO="${RABBITBOT_ENABLE_PULSE_AUDIO:-0}"
PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/1000/pulse/native}"
printf '[%s] TTS启动检查: 音频兼容层配置：tts_audio_backend=%s, pulse_enabled=%s, pulse_server=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${RABBITBOT_TTS_AUDIO_BACKEND}" "${RABBITBOT_ENABLE_PULSE_AUDIO}" "${PULSE_SERVER}"

RABBITBOT_TTS_BACKEND="${RABBITBOT_TTS_BACKEND:-auto}"
RABBITBOT_UNITREE_TTS_INTERFACE="${RABBITBOT_UNITREE_TTS_INTERFACE:-eno1}"
RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER="${RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER:-1}"
RABBITBOT_UNITREE_TTS_REQUIRE_IPV4="${RABBITBOT_UNITREE_TTS_REQUIRE_IPV4:-1}"
RABBITBOT_UNITREE_TTS_AUTO_PROBE="${RABBITBOT_UNITREE_TTS_AUTO_PROBE:-1}"
RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT="${RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT:-3}"
RABBITBOT_UNITREE_TTS_BINARY="${RABBITBOT_UNITREE_TTS_BINARY:-build/unitree_g1_tts_bridge}"
RABBITBOT_UNITREE_TTS_BUILD_SCRIPT="${RABBITBOT_UNITREE_TTS_BUILD_SCRIPT:-scripts/build_unitree_g1_tts_bridge.sh}"

tts_start_log() {
    printf '[%s] TTS启动检查: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

env_enabled() {
    case "${1:-}" in
        1|true|TRUE|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

unitree_ipv4_address() {
    python - "${RABBITBOT_UNITREE_TTS_INTERFACE}" <<'PY'
import fcntl
import socket
import struct
import sys

iface = sys.argv[1].encode("utf-8")[:15]
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    packed = fcntl.ioctl(sock.fileno(), 0x8915, struct.pack("256s", iface))
except OSError:
    sys.exit(2)
print(socket.inet_ntoa(packed[20:24]))
PY
}

unitree_interface_healthcheck() {
    iface="${RABBITBOT_UNITREE_TTS_INTERFACE}"
    sys_iface="/sys/class/net/${iface}"
    if [ ! -e "${sys_iface}" ] && ! grep -q "^ *${iface}:" /proc/net/dev 2>/dev/null; then
        tts_start_log "Unitree接口检查失败：interface=${iface}, reason=接口不存在"
        return 1
    fi

    operstate="unknown"
    if [ -r "${sys_iface}/operstate" ]; then
        operstate="$(cat "${sys_iface}/operstate" 2>/dev/null || echo unknown)"
    fi
    carrier="unknown"
    if [ -r "${sys_iface}/carrier" ]; then
        carrier="$(cat "${sys_iface}/carrier" 2>/dev/null || echo unknown)"
    fi
    tts_start_log "Unitree接口状态：interface=${iface}, operstate=${operstate}, carrier=${carrier}"

    if env_enabled "${RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER}"; then
        if [ "${carrier}" = "0" ] || [ "${operstate}" = "down" ]; then
            tts_start_log "Unitree链路检查失败：interface=${iface}, operstate=${operstate}, carrier=${carrier}, reason=无物理载波或接口未 UP"
            return 1
        fi
        if [ "${carrier}" = "unknown" ] && [ "${operstate}" != "up" ]; then
            tts_start_log "Unitree链路检查失败：interface=${iface}, operstate=${operstate}, carrier=${carrier}, reason=无法确认链路可用"
            return 1
        fi
    fi

    ipv4="$(unitree_ipv4_address 2>/dev/null || true)"
    if [ -n "${ipv4}" ]; then
        tts_start_log "Unitree IPv4检查通过：interface=${iface}, ipv4=${ipv4}"
    elif env_enabled "${RABBITBOT_UNITREE_TTS_REQUIRE_IPV4}"; then
        tts_start_log "Unitree IPv4检查失败：interface=${iface}, reason=未读取到 IPv4 地址"
        return 1
    else
        tts_start_log "Unitree IPv4检查跳过：interface=${iface}, reason=未读取到 IPv4 地址但未强制要求"
    fi
    return 0
}

ensure_unitree_probe_binary() {
    if [ -x "${RABBITBOT_UNITREE_TTS_BINARY}" ]; then
        tts_start_log "Unitree桥接程序可用：binary=${RABBITBOT_UNITREE_TTS_BINARY}"
        return 0
    fi
    if [ ! -f "${RABBITBOT_UNITREE_TTS_BUILD_SCRIPT}" ]; then
        tts_start_log "Unitree桥接程序检查失败：binary=${RABBITBOT_UNITREE_TTS_BINARY}, build_script=${RABBITBOT_UNITREE_TTS_BUILD_SCRIPT}, reason=构建脚本不存在"
        return 1
    fi

    build_log="/tmp/rabbitbot_unitree_tts_probe_build.log"
    tts_start_log "Unitree桥接程序缺失，开始构建：binary=${RABBITBOT_UNITREE_TTS_BINARY}, build_script=${RABBITBOT_UNITREE_TTS_BUILD_SCRIPT}"
    if bash "${RABBITBOT_UNITREE_TTS_BUILD_SCRIPT}" >"${build_log}" 2>&1; then
        tts_start_log "Unitree桥接程序构建完成：binary=${RABBITBOT_UNITREE_TTS_BINARY}"
        return 0
    fi
    build_rc=$?
    tts_start_log "Unitree桥接程序构建失败：returncode=${build_rc}, log=${build_log}, tail=$(tail -20 "${build_log}" 2>/dev/null | tr '\n' ';')"
    return 1
}

unitree_audio_probe() {
    if ! env_enabled "${RABBITBOT_UNITREE_TTS_AUTO_PROBE}"; then
        tts_start_log "Unitree音频服务探测跳过：reason=RABBITBOT_UNITREE_TTS_AUTO_PROBE=${RABBITBOT_UNITREE_TTS_AUTO_PROBE}"
        return 0
    fi
    if ! ensure_unitree_probe_binary; then
        return 1
    fi

    probe_stdout="/tmp/rabbitbot_unitree_tts_probe.stdout"
    probe_stderr="/tmp/rabbitbot_unitree_tts_probe.stderr"
    timeout_seconds="$(python - "${RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT}" <<'PY'
import math
import sys
try:
    value = float(sys.argv[1])
except (TypeError, ValueError):
    value = 3.0
print(max(1, int(math.ceil(value + 2.0))))
PY
)"
    tts_start_log "Unitree音频服务探测开始：interface=${RABBITBOT_UNITREE_TTS_INTERFACE}, probe=get_volume, timeout=${RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT}s"
    if command -v timeout >/dev/null 2>&1; then
        timeout "${timeout_seconds}s" "${RABBITBOT_UNITREE_TTS_BINARY}" \
            --network "${RABBITBOT_UNITREE_TTS_INTERFACE}" \
            --timeout "${RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT}" \
            --probe get_volume >"${probe_stdout}" 2>"${probe_stderr}"
        probe_rc=$?
    else
        "${RABBITBOT_UNITREE_TTS_BINARY}" \
            --network "${RABBITBOT_UNITREE_TTS_INTERFACE}" \
            --timeout "${RABBITBOT_UNITREE_TTS_PROBE_TIMEOUT}" \
            --probe get_volume >"${probe_stdout}" 2>"${probe_stderr}"
        probe_rc=$?
    fi

    probe_out="$(tail -20 "${probe_stdout}" 2>/dev/null | tr '\n' ';')"
    probe_err="$(tail -20 "${probe_stderr}" 2>/dev/null | tr '\n' ';')"
    if [ "${probe_rc}" -eq 0 ]; then
        tts_start_log "Unitree音频服务探测通过：returncode=0, stdout=${probe_out}, stderr=${probe_err}"
        return 0
    fi
    tts_start_log "Unitree音频服务探测失败：returncode=${probe_rc}, stdout=${probe_out}, stderr=${probe_err}"
    return 1
}

if [ "${RABBITBOT_TTS_BACKEND}" = "auto" ]; then
    tts_start_log "TTS后端自动选择开始：interface=${RABBITBOT_UNITREE_TTS_INTERFACE}, require_carrier=${RABBITBOT_UNITREE_TTS_REQUIRE_CARRIER}, require_ipv4=${RABBITBOT_UNITREE_TTS_REQUIRE_IPV4}, auto_probe=${RABBITBOT_UNITREE_TTS_AUTO_PROBE}"
    if unitree_interface_healthcheck && unitree_audio_probe; then
        tts_start_log "TTS后端自动选择完成：effective=unitree, reason=Unitree接口、链路、IPv4与音频服务探测通过"
        RABBITBOT_TTS_BACKEND="unitree"
    else
        tts_start_log "TTS后端自动选择完成：effective=local, reason=Unitree健康检查失败，回退本地外接输出设备"
        RABBITBOT_TTS_BACKEND="local"
        export TTS_DEVICE_NAME="${TTS_DEVICE_NAME:-BT67}"
    fi
    export RABBITBOT_TTS_BACKEND
fi

case "${RABBITBOT_TTS_BACKEND}" in
    unitree|g1|robot)
        unitree_volume_desc="${RABBITBOT_UNITREE_TTS_VOLUME:-设备当前音量}"
        echo "使用 Unitree G1 本体 TTS 后端，跳过 Orin 本地输出声卡扫描。音量=${unitree_volume_desc}"
        export OUTPUT_DEVICE_INDEX=""
        ;;
    *)
        # TTS_DEVICE_NAME 只在明确指定时作为最高优先级；默认自动选择稳定出现的外接声卡。
        # 设备探测统一收敛到 rabbitbot.audio.device_probe，便于后续接入 Pulse/蓝牙后端。
        DEVICE_NAME="${TTS_DEVICE_NAME:-}"
        TTS_DEVICE_WAIT_SECONDS="${TTS_DEVICE_WAIT_SECONDS:-20}"
        TTS_DEVICE_STABLE_COUNT="${TTS_DEVICE_STABLE_COUNT:-3}"
        RABBITBOT_TTS_ALLOW_BUILTIN="${RABBITBOT_TTS_ALLOW_BUILTIN:-1}"

        if [ "${RABBITBOT_TTS_AUDIO_BACKEND}" = "pulse_future" ]; then
            echo "PulseAudio TTS 后端仍是预留架构，本轮不直接播放；将继续按 ALSA 路径选择设备。"
            export RABBITBOT_TTS_AUDIO_BACKEND="alsa"
        fi

        if [ -d /dev/snd ]; then
            DEVICE_INFO=$(python -m rabbitbot.audio.device_probe tts 2>/tmp/rabbitbot_tts_device_probe.err)
            DEVICE_SCAN_STATUS=$?
            DEVICE_INDEX=$(echo "$DEVICE_INFO" | cut -d'|' -f1)
            DEVICE_FOUND_NAME=$(echo "$DEVICE_INFO" | cut -d'|' -f2)
            DEVICE_SELECT_REASON=$(echo "$DEVICE_INFO" | cut -d'|' -f3)
        else
            DEVICE_SCAN_STATUS=2
            DEVICE_INDEX=""
            echo "未检测到 /dev/snd，无法启动 TTS 输出"
        fi

        if [ "${DEVICE_SCAN_STATUS}" -eq 0 ] && [ -n "$DEVICE_INDEX" ]; then
            export OUTPUT_DEVICE_INDEX=$DEVICE_INDEX
            echo "使用输出音频设备 ${DEVICE_FOUND_NAME}，index=${OUTPUT_DEVICE_INDEX}，reason=${DEVICE_SELECT_REASON}"
        else
            echo "未找到稳定可用的输出音频设备，拒绝启动 TTS。"
            echo "当前已默认允许内置声卡回退；如需强制外接声卡，请设置 RABBITBOT_TTS_ALLOW_BUILTIN=0。"
            echo "音频设备探测日志: /tmp/rabbitbot_tts_device_probe.err"
            exit 1
        fi
        ;;
esac

uvicorn tts_app:app --host 0.0.0.0 --port 28185 --log-level debug --workers 1
#python tts_app.py

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)

BUILTIN_AUDIO_KEYWORDS = (
    "orin", "jetson", "tegra", "nvidia", "hda", "hdmi", "ape", "admaif", "tegrasnd",
)
HDA_KEYWORDS = ("nvidia jetson agx orin hda", " hda", "hdmi")
MICROPHONE_KEYWORDS = ("mic", "microphone", "dji", "wireless", "rx")
OUTPUT_CLASS_KEYWORDS = ("bt67", "speaker", "monitor", "output")
IMMEDIATE_RETURN_REASONS = {"unitree_backend", "pulse_backend_reserved_not_enabled", "stt_only_supports_alsa_currently"}


@dataclass(frozen=True)
class AudioDevice:
    kind: str
    direction: str
    name: str
    index: str | None = None
    channels: int | None = None
    available: bool = True
    connected: bool | None = None
    reason: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeviceSelection:
    kind: str
    direction: str
    available: bool
    device_name: str = ""
    device_index: str = ""
    reason: str = ""
    candidate_count: int = 0
    pulse_candidate_count: int = 0
    bluetooth_candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_builtin_audio(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in BUILTIN_AUDIO_KEYWORDS)


def _is_orin_hda_audio(name: str) -> bool:
    lowered = f" {name.lower()}"
    return any(keyword in lowered for keyword in HDA_KEYWORDS)


def sounddevice_devices() -> list[dict[str, Any]]:
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - 依赖现场环境
        logger.warning("sounddevice 不可用，无法枚举 ALSA/PortAudio 设备：type=%s, error=%s", type(exc).__name__, exc)
        return []
    devices = []
    for index, device in enumerate(sd.query_devices()):
        item = dict(device)
        item["index"] = index
        devices.append(item)
    return devices


def alsa_candidates(devices: Iterable[dict[str, Any]], direction: str) -> list[AudioDevice]:
    channel_key = "max_output_channels" if direction == "playback" else "max_input_channels"
    output: list[AudioDevice] = []
    for fallback_index, device in enumerate(devices):
        channels = int(device.get(channel_key, 0) or 0)
        if channels <= 0:
            continue
        index = str(device.get("index", fallback_index))
        name = str(device.get("name", ""))
        output.append(AudioDevice(kind="alsa", direction=direction, name=name, index=index, channels=channels, available=True))
    return output


def parse_pactl_short(output: str, direction: str) -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    for line in (output or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        state = parts[4] if len(parts) > 4 else "unknown"
        devices.append(
            AudioDevice(
                kind="pulse",
                direction=direction,
                name=parts[1],
                index=parts[0],
                available=True,
                connected=state.upper() != "SUSPENDED",
                reason=f"pulse_state:{state}",
            )
        )
    return devices


def _run_command(args: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(args, check=False, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("音频设备探测命令执行失败：cmd=%s, type=%s, error=%s", args[:3], type(exc).__name__, exc)
        return ""
    if result.returncode != 0:
        logger.debug("音频设备探测命令返回非零：cmd=%s, returncode=%s", args[:3], result.returncode)
        return ""
    return result.stdout


def pulse_candidates() -> list[AudioDevice]:
    sinks = parse_pactl_short(_run_command(["pactl", "list", "short", "sinks"]), "playback")
    sources = parse_pactl_short(_run_command(["pactl", "list", "short", "sources"]), "capture")
    return sinks + sources


def parse_bluetoothctl_devices(output: str) -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    for line in (output or "").splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        devices.append(
            AudioDevice(
                kind="bluetooth",
                direction="unknown",
                name=parts[2],
                index=parts[1],
                available=True,
                connected=None,
                reason="bluetooth_device",
            )
        )
    return devices


def bluetooth_candidates() -> list[AudioDevice]:
    return parse_bluetoothctl_devices(_run_command(["bluetoothctl", "devices"], timeout=2.0))


def select_tts_device(
    devices: Iterable[dict[str, Any]],
    preferred_name: str = "",
    allow_builtin: bool = True,
    audio_backend: str = "alsa",
    pulse_count: int = 0,
    bluetooth_count: int = 0,
) -> DeviceSelection:
    backend = (audio_backend or "alsa").strip().lower()
    if backend == "unitree":
        return DeviceSelection(kind="unitree", direction="playback", available=True, reason="unitree_backend")
    if backend == "pulse_future":
        return DeviceSelection(
            kind="pulse",
            direction="playback",
            available=False,
            reason="pulse_backend_reserved_not_enabled",
            pulse_candidate_count=pulse_count,
            bluetooth_candidate_count=bluetooth_count,
        )

    candidates = alsa_candidates(devices, "playback")
    preferred = preferred_name.strip().lower()
    preferred_matches = [item for item in candidates if preferred and preferred in item.name.lower() and (allow_builtin or not _is_builtin_audio(item.name))]
    non_hda_external = [item for item in candidates if not _is_builtin_audio(item.name) and not _is_orin_hda_audio(item.name)]
    builtin_fallback = [item for item in candidates if allow_builtin and _is_builtin_audio(item.name)]
    if preferred_matches:
        selected = preferred_matches[0]
        reason = "preferred_name"
    elif non_hda_external:
        selected = non_hda_external[0]
        reason = "non_hda_external"
    elif builtin_fallback:
        selected = builtin_fallback[0]
        reason = "builtin_fallback"
    else:
        return DeviceSelection(
            kind="alsa",
            direction="playback",
            available=False,
            reason="no_alsa_playback_device",
            candidate_count=len(candidates),
            pulse_candidate_count=pulse_count,
            bluetooth_candidate_count=bluetooth_count,
        )
    return DeviceSelection(
        kind="alsa",
        direction="playback",
        available=True,
        device_name=selected.name,
        device_index=selected.index or "",
        reason=reason,
        candidate_count=len(candidates),
        pulse_candidate_count=pulse_count,
        bluetooth_candidate_count=bluetooth_count,
    )


def select_stt_device(
    devices: Iterable[dict[str, Any]],
    preferred_name: str = "",
    audio_backend: str = "alsa",
    pulse_count: int = 0,
    bluetooth_count: int = 0,
) -> DeviceSelection:
    backend = (audio_backend or "alsa").strip().lower()
    if backend != "alsa":
        return DeviceSelection(
            kind=backend,
            direction="capture",
            available=False,
            reason="stt_only_supports_alsa_currently",
            pulse_candidate_count=pulse_count,
            bluetooth_candidate_count=bluetooth_count,
        )
    candidates = alsa_candidates(devices, "capture")
    preferred = preferred_name.strip().lower()
    preferred_matches = [item for item in candidates if preferred and preferred in item.name.lower()]
    mic_external = [item for item in candidates if not _is_builtin_audio(item.name) and any(keyword in item.name.lower() for keyword in MICROPHONE_KEYWORDS)]
    external = [item for item in candidates if not _is_builtin_audio(item.name) and not any(keyword in item.name.lower() for keyword in OUTPUT_CLASS_KEYWORDS)]
    builtin = [item for item in candidates if _is_builtin_audio(item.name)]
    if preferred_matches:
        selected = preferred_matches[0]
        reason = "preferred_name"
    elif mic_external:
        selected = mic_external[0]
        reason = "external_microphone"
    elif external:
        selected = external[0]
        reason = "external_input"
    elif builtin:
        selected = builtin[0]
        reason = "builtin_fallback"
    else:
        return DeviceSelection(
            kind="alsa",
            direction="capture",
            available=False,
            reason="no_alsa_capture_device",
            candidate_count=len(candidates),
            pulse_candidate_count=pulse_count,
            bluetooth_candidate_count=bluetooth_count,
        )
    return DeviceSelection(
        kind="alsa",
        direction="capture",
        available=True,
        device_name=selected.name,
        device_index=selected.index or "",
        reason=reason,
        candidate_count=len(candidates),
        pulse_candidate_count=pulse_count,
        bluetooth_candidate_count=bluetooth_count,
    )


def build_report(devices: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    sound_devices = list(devices) if devices is not None else sounddevice_devices()
    pulse = pulse_candidates()
    bluetooth = bluetooth_candidates()
    return {
        "alsa_playback": [item.to_dict() for item in alsa_candidates(sound_devices, "playback")],
        "alsa_capture": [item.to_dict() for item in alsa_candidates(sound_devices, "capture")],
        "pulse": [item.to_dict() for item in pulse],
        "bluetooth": [item.to_dict() for item in bluetooth],
    }


def _emit_candidates(selection: DeviceSelection, report: dict[str, Any]) -> None:
    logger.info(
        "音频设备探测摘要：target=%s, kind=%s, available=%s, selected=%s, index=%s, reason=%s, alsa_candidates=%s, pulse_candidates=%s, bluetooth_candidates=%s",
        selection.direction,
        selection.kind,
        selection.available,
        selection.device_name or "未选择",
        selection.device_index or "无",
        selection.reason,
        selection.candidate_count,
        selection.pulse_candidate_count,
        selection.bluetooth_candidate_count,
    )
    for group in ("alsa_playback", "alsa_capture", "pulse", "bluetooth"):
        for item in report.get(group, []):
            logger.debug(
                "音频设备候选：group=%s, kind=%s, direction=%s, index=%s, name=%s, channels=%s, available=%s, connected=%s, reason=%s",
                group,
                item.get("kind"),
                item.get("direction"),
                item.get("index"),
                item.get("name"),
                item.get("channels"),
                item.get("available"),
                item.get("connected"),
                item.get("reason"),
            )


def _should_wait_for_external(selection: DeviceSelection, wait_builtin_until_deadline: bool) -> bool:
    return (
        wait_builtin_until_deadline
        and selection.available
        and selection.kind == "alsa"
        and selection.reason == "builtin_fallback"
    )


def wait_for_selection(
    target: str,
    preferred_name: str,
    audio_backend: str,
    wait_seconds: float,
    stable_count: int,
    allow_builtin: bool = True,
    wait_builtin_until_deadline: bool = True,
) -> DeviceSelection:
    deadline = time.monotonic() + max(0.0, wait_seconds)
    stable_target = max(1, stable_count)
    last_key: tuple[str, str] | None = None
    stable_seen = 0
    last_selection = DeviceSelection(kind="alsa", direction="playback" if target == "tts" else "capture", available=False, reason="not_scanned")

    while True:
        devices = sounddevice_devices()
        report = build_report(devices)
        pulse_count = len(report["pulse"])
        bluetooth_count = len(report["bluetooth"])
        if target == "tts":
            selection = select_tts_device(
                devices,
                preferred_name=preferred_name,
                allow_builtin=allow_builtin,
                audio_backend=audio_backend,
                pulse_count=pulse_count,
                bluetooth_count=bluetooth_count,
            )
        else:
            selection = select_stt_device(
                devices,
                preferred_name=preferred_name,
                audio_backend=audio_backend,
                pulse_count=pulse_count,
                bluetooth_count=bluetooth_count,
            )
        last_selection = selection
        _emit_candidates(selection, report)

        if selection.reason in IMMEDIATE_RETURN_REASONS:
            return selection

        deadline_reached = time.monotonic() >= deadline
        if _should_wait_for_external(selection, wait_builtin_until_deadline) and not deadline_reached:
            logger.info(
                "仅发现内置音频设备，继续等待外接设备：target=%s, selected=%s, index=%s, deadline_seconds=%.1f",
                target,
                selection.device_name,
                selection.device_index,
                max(0.0, deadline - time.monotonic()),
            )
            stable_seen = 0
            last_key = None
        elif selection.available:
            key = (selection.device_index, selection.device_name)
            stable_seen = stable_seen + 1 if key == last_key else 1
            last_key = key
            logger.info(
                "音频设备稳定检测：target=%s, index=%s, name=%s, stable=%s/%s, reason=%s",
                target,
                selection.device_index,
                selection.device_name,
                stable_seen,
                stable_target,
                selection.reason,
            )
            if stable_seen >= stable_target or deadline_reached:
                return selection
        else:
            stable_seen = 0
            last_key = None

        if deadline_reached:
            logger.warning(
                "音频设备等待超时，使用最后一次探测结果：target=%s, available=%s, selected=%s, index=%s, reason=%s",
                target,
                last_selection.available,
                last_selection.device_name or "未选择",
                last_selection.device_index or "无",
                last_selection.reason,
            )
            return last_selection
        time.sleep(1)


def wait_for_tts_selection(
    preferred_name: str,
    allow_builtin: bool,
    audio_backend: str,
    wait_seconds: float,
    stable_count: int,
) -> DeviceSelection:
    return wait_for_selection(
        target="tts",
        preferred_name=preferred_name,
        audio_backend=audio_backend,
        wait_seconds=wait_seconds,
        stable_count=stable_count,
        allow_builtin=allow_builtin,
        wait_builtin_until_deadline=allow_builtin,
    )


def wait_for_stt_selection(
    preferred_name: str,
    audio_backend: str,
    wait_seconds: float,
    stable_count: int,
) -> DeviceSelection:
    return wait_for_selection(
        target="stt",
        preferred_name=preferred_name,
        audio_backend=audio_backend,
        wait_seconds=wait_seconds,
        stable_count=stable_count,
        allow_builtin=True,
        wait_builtin_until_deadline=True,
    )


def configure_logging() -> None:
    logging.basicConfig(level=os.environ.get("RABBITBOT_AUDIO_PROBE_LOG_LEVEL", "INFO"), format="%(levelname)s:%(name)s:%(message)s")


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="RabbitBot 音频设备探测与选择")
    parser.add_argument("target", choices=("tts", "stt", "report"))
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    if args.target == "report":
        report = build_report()
        logger.info(
            "音频设备报告生成完成：alsa_playback=%s, alsa_capture=%s, pulse=%s, bluetooth=%s",
            len(report["alsa_playback"]),
            len(report["alsa_capture"]),
            len(report["pulse"]),
            len(report["bluetooth"]),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.target == "tts":
        selection = wait_for_tts_selection(
            preferred_name=os.environ.get("TTS_DEVICE_NAME", ""),
            allow_builtin=_bool_env(os.environ.get("RABBITBOT_TTS_ALLOW_BUILTIN"), True),
            audio_backend=os.environ.get("RABBITBOT_TTS_AUDIO_BACKEND", "alsa"),
            wait_seconds=float(os.environ.get("TTS_DEVICE_WAIT_SECONDS", "20")),
            stable_count=int(os.environ.get("TTS_DEVICE_STABLE_COUNT", "3")),
        )
    else:
        selection = wait_for_stt_selection(
            preferred_name=os.environ.get("STT_DEVICE_NAME", ""),
            audio_backend=os.environ.get("RABBITBOT_STT_AUDIO_BACKEND", "alsa"),
            wait_seconds=float(os.environ.get("STT_DEVICE_WAIT_SECONDS", "10")),
            stable_count=int(os.environ.get("STT_DEVICE_STABLE_COUNT", "2")),
        )

    if args.json:
        print(json.dumps(selection.to_dict(), ensure_ascii=False))
    else:
        print("|".join([selection.device_index, selection.device_name, selection.reason, selection.kind, "1" if selection.available else "0"]))
    return 0 if selection.available else 2


if __name__ == "__main__":
    raise SystemExit(main())

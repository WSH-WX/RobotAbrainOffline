import unittest
from unittest.mock import patch

from rabbitbot.audio import device_probe
from rabbitbot.audio.device_probe import (
    parse_bluetoothctl_devices,
    parse_pactl_short,
    select_stt_device,
    select_tts_device,
)


class DeviceProbeTest(unittest.TestCase):
    def test_tts_prefers_non_hda_external_output(self):
        devices = [
            {"index": 0, "name": "NVIDIA Jetson AGX Orin HDA", "max_output_channels": 2},
            {"index": 3, "name": "REDMI Speaker 2-4550: USB Audio (hw:3,0)", "max_output_channels": 2},
        ]

        selected = select_tts_device(devices, allow_builtin=True)

        self.assertTrue(selected.available)
        self.assertEqual(selected.kind, "alsa")
        self.assertEqual(selected.device_index, "3")
        self.assertEqual(selected.reason, "non_hda_external")

    def test_tts_builtin_fallback_can_be_disabled(self):
        devices = [{"index": 0, "name": "NVIDIA Jetson AGX Orin HDA", "max_output_channels": 2}]

        selected = select_tts_device(devices, allow_builtin=False)

        self.assertFalse(selected.available)
        self.assertEqual(selected.reason, "no_alsa_playback_device")

    def test_tts_pulse_future_is_reserved_not_selected(self):
        selected = select_tts_device([], audio_backend="pulse_future", pulse_count=1, bluetooth_count=1)

        self.assertFalse(selected.available)
        self.assertEqual(selected.kind, "pulse")
        self.assertEqual(selected.reason, "pulse_backend_reserved_not_enabled")
        self.assertEqual(selected.pulse_candidate_count, 1)

    def test_tts_waits_for_external_when_builtin_appears_first(self):
        builtin = [{"index": 0, "name": "NVIDIA Jetson AGX Orin HDA", "max_output_channels": 2}]
        external = builtin + [{"index": 3, "name": "REDMI Speaker 2-4550: USB Audio (hw:3,0)", "max_output_channels": 2}]

        with patch.object(device_probe, "sounddevice_devices", side_effect=[builtin, external]), \
             patch.object(device_probe, "pulse_candidates", return_value=[]), \
             patch.object(device_probe, "bluetooth_candidates", return_value=[]), \
             patch.object(device_probe.time, "sleep", return_value=None):
            selected = device_probe.wait_for_tts_selection("", True, "alsa", wait_seconds=5, stable_count=1)

        self.assertEqual(selected.device_index, "3")
        self.assertEqual(selected.reason, "non_hda_external")

    def test_stt_prefers_external_microphone(self):
        devices = [
            {"index": 2, "name": "NVIDIA Jetson AGX Orin APE", "max_input_channels": 16},
            {"index": 4, "name": "DJI MIC MINI: USB Audio (hw:1,0)", "max_input_channels": 2},
        ]

        selected = select_stt_device(devices)

        self.assertTrue(selected.available)
        self.assertEqual(selected.device_index, "4")
        self.assertEqual(selected.reason, "external_microphone")

    def test_stt_waits_for_external_when_builtin_appears_first(self):
        builtin = [{"index": 2, "name": "NVIDIA Jetson AGX Orin APE", "max_input_channels": 16}]
        external = builtin + [{"index": 4, "name": "DJI MIC MINI: USB Audio (hw:1,0)", "max_input_channels": 2}]

        with patch.object(device_probe, "sounddevice_devices", side_effect=[builtin, external]), \
             patch.object(device_probe, "pulse_candidates", return_value=[]), \
             patch.object(device_probe, "bluetooth_candidates", return_value=[]), \
             patch.object(device_probe.time, "sleep", return_value=None):
            selected = device_probe.wait_for_stt_selection("", "alsa", wait_seconds=5, stable_count=1)

        self.assertEqual(selected.device_index, "4")
        self.assertEqual(selected.reason, "external_microphone")

    def test_parse_pulse_and_bluetooth_candidates(self):
        pulse = parse_pactl_short("0\tbluez_sink.dev\tmodule-bluez5-device.c\ts16le 2ch 44100Hz\tSUSPENDED\n", "playback")
        bluetooth = parse_bluetoothctl_devices("Device 50:92:6A:86:78:D1 REDMI Speaker 2-4550\n")

        self.assertEqual(len(pulse), 1)
        self.assertEqual(pulse[0].kind, "pulse")
        self.assertFalse(pulse[0].connected)
        self.assertEqual(len(bluetooth), 1)
        self.assertEqual(bluetooth[0].kind, "bluetooth")


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import Mock, patch

from rabbitbot.audio.unitree_g1_tts import UnitreeG1TTS


class UnitreeG1TTSVolumeTest(unittest.TestCase):
    def _patched_env(self, volume_env=None):
        env = {
            "RABBITBOT_UNITREE_TTS_BINARY": "unitree_g1_tts_bridge",
            "RABBITBOT_UNITREE_TTS_AUTO_BUILD": "0",
        }
        if volume_env is not None:
            env["RABBITBOT_UNITREE_TTS_VOLUME"] = volume_env
        return patch.dict(os.environ, env, clear=True)

    def test_default_respects_device_volume(self):
        completed = Mock(returncode=0, stdout="ok", stderr="")
        with self._patched_env(), \
             patch.object(UnitreeG1TTS, "_ensure_binary", return_value=None), \
             patch.object(UnitreeG1TTS, "_subprocess_env", return_value={}), \
             patch("rabbitbot.audio.unitree_g1_tts.subprocess.run", return_value=completed) as run:
            engine = UnitreeG1TTS()
            engine.put_text("你好")

        command = run.call_args.args[0]
        self.assertNotIn("--volume", command)
        self.assertEqual(engine.volume, -1)

    def test_explicit_volume_still_passes_volume_argument(self):
        completed = Mock(returncode=0, stdout="ok", stderr="")
        with self._patched_env("55"), \
             patch.object(UnitreeG1TTS, "_ensure_binary", return_value=None), \
             patch.object(UnitreeG1TTS, "_subprocess_env", return_value={}), \
             patch("rabbitbot.audio.unitree_g1_tts.subprocess.run", return_value=completed) as run:
            engine = UnitreeG1TTS()
            engine.put_text("你好")

        command = run.call_args.args[0]
        self.assertIn("--volume", command)
        self.assertEqual(command[command.index("--volume") + 1], "55")


if __name__ == "__main__":
    unittest.main()

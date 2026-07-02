import os
import unittest
from unittest.mock import patch

from rabbitbot.runtime.config import env_float, env_url


class RuntimeConfigTest(unittest.TestCase):
    def test_env_url_uses_default_for_missing_value(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(env_url("SERVICE_URL", "http://default"), "http://default")

    def test_env_url_uses_default_for_blank_value(self):
        with patch.dict(os.environ, {"SERVICE_URL": "   "}, clear=True):
            self.assertEqual(env_url("SERVICE_URL", "http://default"), "http://default")

    def test_env_float_reads_valid_value(self):
        with patch.dict(os.environ, {"TIMEOUT": "2.5"}, clear=True):
            self.assertEqual(env_float("TIMEOUT", 10.0), 2.5)

    def test_env_float_falls_back_for_invalid_value(self):
        with patch.dict(os.environ, {"TIMEOUT": "bad"}, clear=True):
            self.assertEqual(env_float("TIMEOUT", 10.0), 10.0)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch

from requests.exceptions import Timeout

from rabbitbot.clients.audio import STTAgent, TTSAgent


class _Resp:
    def __init__(self, payload, status_code=200):
        self.text = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
        self.status_code = status_code


class AudioClientTest(unittest.TestCase):
    def test_tts_returns_out_text(self):
        with patch("rabbitbot.clients.audio.requests.post", return_value=_Resp({"out_text": "ok"})) as post:
            agent = TTSAgent("http://127.0.0.1:28185/v1")
            self.assertEqual(agent.run("hello"), "ok")
            self.assertEqual(post.call_args.kwargs["timeout"], 10.0)

    def test_stt_updates_utterance_id(self):
        with patch("rabbitbot.clients.audio.requests.post", return_value=_Resp({"out_text": "你好", "utterance_id": "42"})):
            agent = STTAgent("http://127.0.0.1:28184/v1")
            self.assertEqual(agent.run("start_async"), "你好")
            self.assertEqual(agent.last_utterance_id, 42)

    def test_timeout_returns_empty_text(self):
        with patch("rabbitbot.clients.audio.requests.post", side_effect=Timeout()):
            agent = TTSAgent("http://127.0.0.1:28185/v1")
            self.assertEqual(agent.run("hello"), "")

    def test_bad_json_returns_empty_text(self):
        with patch("rabbitbot.clients.audio.requests.post", return_value=_Resp("not-json")):
            agent = STTAgent("http://127.0.0.1:28184/v1")
            self.assertEqual(agent.run("start_async"), "")

    def test_http_error_returns_empty_text(self):
        with patch("rabbitbot.clients.audio.requests.post", return_value=_Resp({"error": "bad"}, status_code=500)):
            agent = TTSAgent("http://127.0.0.1:28185/v1")
            self.assertEqual(agent.run("hello"), "")


if __name__ == "__main__":
    unittest.main()

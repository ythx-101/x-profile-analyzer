"""离线单元测试（stdlib unittest）：不访问网络，不需要 Camofox / API Key。
运行：python3 -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import x_profile_analyzer as xpa  # noqa: E402

NO_AUTH_FILE = Path("/nonexistent/auth-profiles.json")  # 不读取真实 home 目录

# 人工构造的快照片段，仅用于测试（不是真实 Nitter 输出）
FAKE_SNAPSHOT = """
- link "@alice" [e1]:
  - /url: /alice
- link "2h" [e2]:
  - /url: /alice/status/111
- text: first tweet text
- text: 1 2 3
- link "@alice" [e3]:
  - /url: /alice
- link "Jan 19, 2025" [e4]:
  - /url: /alice/status/222
- text: older tweet text
- text: 4 5 6
"""


class FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ParseDateTests(unittest.TestCase):
    def test_relative(self):
        for s in ("2h", "3d"):
            dt = xpa._parse_tweet_date(s)
            self.assertIsInstance(dt, datetime)
            self.assertLessEqual(dt, datetime.now())

    def test_absolute(self):
        self.assertEqual(xpa._parse_tweet_date("Jan 19, 2025"), datetime(2025, 1, 19))
        dt = xpa._parse_tweet_date("Jan 19")
        self.assertEqual((dt.month, dt.day), (1, 19))
        self.assertLessEqual(dt, datetime.now())

    def test_invalid(self):
        self.assertIsNone(xpa._parse_tweet_date("not a date"))
        self.assertIsNone(xpa._parse_tweet_date(""))


class HeatmapTests(unittest.TestCase):
    def test_too_few(self):
        self.assertEqual(xpa._build_activity_heatmap([{"time": "2h"}] * 9), "")

    def test_enough(self):
        out = xpa._build_activity_heatmap([{"time": "Jan 19, 2025"}] * 10)
        for name in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            self.assertIn(name, out)


class ParsingTests(unittest.TestCase):
    def test_extract_cursor(self):
        snap = 'link "Load more" [e9]:\n  - /url: /alice?cursor=ABC123&x=1'
        self.assertEqual(xpa._extract_cursor(snap, "alice"), "ABC123")
        self.assertIsNone(xpa._extract_cursor("nothing", "alice"))

    def test_parse_tweets_year_boundary(self):
        tweets = xpa._parse_tweets(FAKE_SNAPSHOT, "alice", 10)
        self.assertEqual(len(tweets), 2)
        self.assertEqual(tweets[0]["text"], "first tweet text")
        self.assertEqual(tweets[1]["text"], "older tweet text")
        self.assertEqual(tweets[1]["time"], "Jan 19, 2025")


class AnalyzeTests(unittest.TestCase):
    user = {"username": "alice"}
    tweets = [{"text": "hi", "time": "2h", "replies": 0, "retweets": 0, "views": 0}]

    def test_minimax_request(self):
        resp = FakeResp({"content": [{"type": "text", "text": "REPORT"}]})
        with mock.patch("urllib.request.urlopen", return_value=resp) as m:
            out = xpa.analyze_profile_with_minimax(
                self.user, self.tweets, "k", api_url=xpa.MINIMAX_API_URL,
                model_name="MiniMax-M2.5", backend="minimax")
        self.assertEqual(out, "REPORT")
        req = m.call_args[0][0]
        self.assertEqual(req.full_url, xpa.MINIMAX_API_URL)
        self.assertEqual(json.loads(req.data)["model"], "MiniMax-M2.5")
        self.assertEqual(req.get_header("X-api-key"), "k")

    def test_openai_request(self):
        resp = FakeResp({"choices": [{"message": {"content": "OAI REPORT"}}]})
        url = "https://api.deepseek.com/v1/chat/completions"
        with mock.patch("urllib.request.urlopen", return_value=resp) as m:
            out = xpa.analyze_profile_with_minimax(
                self.user, self.tweets, "k", api_url=url,
                model_name="deepseek-chat", backend="openai")
        self.assertEqual(out, "OAI REPORT")
        req = m.call_args[0][0]
        self.assertTrue(req.full_url.endswith("/chat/completions"))
        self.assertEqual(req.get_header("Authorization"), "Bearer k")
        self.assertEqual(json.loads(req.data)["model"], "deepseek-chat")


class ConfigTests(unittest.TestCase):
    def _cfg(self, env):
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(xpa, "AUTH_PROFILES_PATH", NO_AUTH_FILE):
            return xpa.load_api_config()

    def test_minimax_priority(self):
        key, url, model, backend = self._cfg({"MINIMAX_API_KEY": "m", "OPENAI_API_KEY": "o"})
        self.assertEqual((key, url, model, backend),
                         ("m", xpa.MINIMAX_API_URL, "MiniMax-M2.5", "minimax"))

    def test_minimax_model_override(self):
        _, _, model, _ = self._cfg({"MINIMAX_API_KEY": "m", "MINIMAX_MODEL": "MiniMax-M1"})
        self.assertEqual(model, "MiniMax-M1")

    def test_openai_base_normalized(self):
        key, url, model, backend = self._cfg({
            "OPENAI_API_KEY": "o", "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
            "OPENAI_MODEL": "deepseek-chat"})
        self.assertEqual(url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual((model, backend), ("deepseek-chat", "openai"))

    def test_openai_full_endpoint_kept(self):
        _, url, _, _ = self._cfg({
            "OPENAI_API_KEY": "o",
            "OPENAI_BASE_URL": "https://x.example/v1/chat/completions"})
        self.assertEqual(url, "https://x.example/v1/chat/completions")

    def test_no_key(self):
        with self.assertRaises(RuntimeError):
            self._cfg({})


if __name__ == "__main__":
    unittest.main()

import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from wechat_memory.providers import analyze_deepseek, DEEPSEEK_ENDPOINT, NoRedirect


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"id": "1", "conversation": "test", "sender": "A", "timestamp": "2026-09-21T10:00:00+08:00",
                      "type": "text", "text": "你好", "media": ["C:/secret/photo.jpg"], "secret_metadata": "private"}]

    def invoke(self, **kwargs):
        return analyze_deepseek(self.rows, "test-only-key", consent=True, **kwargs)

    def test_opt_in_validation_before_network(self):
        with patch("wechat_memory.providers.build_opener") as opener:
            for consent in (False, None, "true", 1):
                with self.assertRaises(ValueError):
                    analyze_deepseek(self.rows, "test-only-key", consent=consent)
            for key in (None, "", "bad\nkey-value"):
                with self.assertRaises(ValueError):
                    analyze_deepseek(self.rows, key, consent=True)
            for mode in ("shell", [], None):
                with self.assertRaises(ValueError):
                    self.invoke(mode=mode)
            opener.assert_not_called()

    def test_fixed_endpoint_minimal_payload_and_no_tools(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": "摘要 [1]"}, "finish_reason": "stop"}]}).encode()
        with patch("wechat_memory.providers.build_opener") as builder:
            builder.return_value.open.return_value = response
            self.assertEqual(self.invoke(mode="communication"), "摘要 [1]")
            request = builder.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, DEEPSEEK_ENDPOINT)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-only-key")
            payload = json.loads(request.data)
            self.assertNotIn("secret", payload["messages"][1]["content"])
            self.assertNotIn("media", payload["messages"][1]["content"])
            self.assertNotIn("tools", payload)
            self.assertEqual(builder.call_args.args[0].proxies, {})
            self.assertIsInstance(builder.call_args.args[1], NoRedirect)

    def test_oversize_never_silently_truncated(self):
        self.rows[0]["text"] = "字" * 30001
        with patch("wechat_memory.providers.build_opener") as builder:
            with self.assertRaisesRegex(ValueError, "30000"):
                self.invoke()
            builder.assert_not_called()

    def test_errors_do_not_echo_secrets_and_never_retry(self):
        for error in (HTTPError(DEEPSEEK_ENDPOINT, 401, "test-only-key", {}, io.BytesIO(b"secret-body")),
                      URLError("test-only-key")):
            with patch("wechat_memory.providers.build_opener") as builder:
                builder.return_value.open.side_effect = error
                with self.assertRaises(ValueError) as caught:
                    self.invoke()
                self.assertNotIn("test-only-key", str(caught.exception))
                self.assertNotIn("secret-body", str(caught.exception))
                self.assertEqual(builder.return_value.open.call_count, 1)

    def test_incomplete_or_invalid_result_rejected(self):
        for raw in (b"not json", b"{}", json.dumps({"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}).encode()):
            with patch("wechat_memory.providers.build_opener") as builder:
                builder.return_value.open.return_value.__enter__.return_value.read.return_value = raw
                with self.assertRaises(ValueError):
                    self.invoke()

    def test_redirect_handler_refuses_redirect(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))

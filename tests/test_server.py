from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread
import unittest
from unittest.mock import patch

from wechat_memory.server import make_server


class LocalAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.worker = Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.messages = json.loads((Path(__file__).resolve().parents[1] / "examples/demo.json").read_text())["messages"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def request(self, path, data=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        supplied = {"Content-Type": "application/json", "X-Session-Token": self.server.token}
        supplied.update(headers or {})
        connection.request("GET" if data is None else "POST", path, None if data is None else json.dumps(data), supplied)
        response = connection.getresponse()
        status, body, response_headers = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return status, body, response_headers

    def test_assets_and_no_arbitrary_file_access(self):
        for route in ("/", "/app.js", "/style.css"):
            status, body, headers = self.request(route)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 100)
            self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn(b"__SESSION_TOKEN__", self.request("/")[1])
        self.assertEqual(self.request("/../pyproject.toml")[0], 404)

    def test_external_origin_host_and_missing_token_rejected(self):
        for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"}, {"X-Session-Token": ""}):
            self.assertEqual(self.request("/api/import", {"messages": self.messages}, headers)[0], 403)
        self.assertEqual(self.request("/", headers={"Host": "evil.example"})[0], 403)

    def test_import_and_exports(self):
        code, body, _ = self.request("/api/import", {"messages": self.messages})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["stats"]["message_count"], 3)
        for fmt, expected in (("markdown", "# 聊天记录"), ("json", '"messages"'), ("ics", "BEGIN:VCALENDAR")):
            code, body, _ = self.request("/api/export", {"messages": self.messages, "format": fmt})
            self.assertEqual(code, 200)
            self.assertIn(expected, json.loads(body)["content"])

    def test_invalid_input_and_body_limit(self):
        self.assertEqual(self.request("/api/import", {"messages": [{"id": "bad"}]})[0], 400)
        self.assertEqual(self.request("/api/import", [], {"Content-Length": "20971521"})[0], 413)
        self.assertEqual(self.request("/api/photos", {"folder": "relative"})[0], 400)

    def test_model_is_explicit_and_local(self):
        with patch("wechat_memory.server.analyze", return_value="summary") as model:
            self.request("/api/import", {"messages": self.messages})
            model.assert_not_called()
            code, body, _ = self.request("/api/analyze", {"messages": self.messages, "model": "local-model", "endpoint": "https://example.com"})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["content"], "summary")
            self.assertEqual(model.call_args.args[1], "local-model")
            self.assertEqual(model.call_args.kwargs, {})


if __name__ == "__main__":
    unittest.main()

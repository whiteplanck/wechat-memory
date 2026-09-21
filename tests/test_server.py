from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread
import unittest
import tempfile
from unittest.mock import patch

from wechat_memory.server import make_server


class LocalAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory()
        cls.server = make_server(0, cls.storage.name)
        cls.worker = Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.messages = json.loads((Path(__file__).resolve().parents[1] / "examples/demo.json").read_text(encoding="utf-8"))["messages"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.storage.cleanup()

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

    def test_import_persists_and_can_be_reopened(self):
        code, body, _ = self.request("/api/import", {"messages": self.messages, "label": "我的档案"})
        self.assertEqual(code, 200)
        archive = json.loads(body)["archive"]
        self.assertTrue(Path(archive["path"]).is_file())
        code, body, _ = self.request("/api/archive", {"id": archive["id"]})
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(body)["messages"]), 3)
        code, body, _ = self.request("/api/archives", {})
        self.assertEqual(code, 200)
        self.assertIn(archive["id"], [a["id"] for a in json.loads(body)["archives"]])
        self.assertEqual(self.request("/api/archive", {"id": "../../etc/passwd"})[0], 400)

    def test_demo_is_not_saved(self):
        with patch.object(self.server.store, "save") as save:
            code, body, _ = self.request("/api/import", {"messages": self.messages, "save": False})
            self.assertEqual(code, 200)
            self.assertNotIn("archive", json.loads(body))
            save.assert_not_called()

    def test_relationship_api_durable_and_explicit_cloud(self):
        rows=[{"id":"a","conversation":"pair","sender":"A","timestamp":"2026-01-01T10:00:00+08:00","text":"我喜欢你"},
              {"id":"b","conversation":"pair","sender":"B","timestamp":"2026-01-01T10:01:00+08:00","text":"我很开心"}]
        code,body,_=self.request('/api/relationship/build',{'messages':rows,'conversation':'pair'})
        self.assertEqual(code,200);report=json.loads(body)
        self.assertEqual(len(report['profiles']),2)
        self.assertEqual(self.request('/api/relationship/load',{'id':report['id']})[0],200)
        with patch('wechat_memory.server.analyze_deepseek',return_value='带证据的模拟结果') as mock:
            self.assertEqual(self.request('/api/relationship/analyze',{'id':report['id'],'provider':'deepseek','model':'test'})[0],400)
            mock.assert_not_called()
            code,body,_=self.request('/api/relationship/analyze',{'id':report['id'],'provider':'deepseek','model':'test','consent':True,'api_key':'test-key-not-real'})
            self.assertEqual(code,200)
            self.assertEqual(mock.call_args.args[-1],'relationship')
            self.assertNotIn(b'test-key-not-real',body)
            self.assertEqual(json.loads(body)['ai'],'带证据的模拟结果')

    def test_deepseek_consent_and_no_key_storage(self):
        data = {"messages": self.messages, "provider": "deepseek", "model": "deepseek-flash", "api_key": "test-only-key"}
        with patch("wechat_memory.providers.build_opener") as network:
            self.assertEqual(self.request("/api/analyze", data)[0], 400)
            network.assert_not_called()
        with patch("wechat_memory.server.analyze_deepseek", return_value="report") as provider, patch.object(self.server.store, "save") as save:
            code, body, _ = self.request("/api/analyze", {**data, "consent": True, "mode": "communication"})
            self.assertEqual(code, 200)
            self.assertNotIn(b"test-only-key", body)
            self.assertEqual(provider.call_args.kwargs, {"consent": True, "mode": "communication"})
            save.assert_not_called()
        self.assertEqual(self.request("/api/analyze", {**data, "provider": "unknown"})[0], 400)

    def test_saved_key_never_returned_and_still_requires_consent(self):
        with patch.object(self.server, "credentials") as credentials, patch("wechat_memory.server.analyze_deepseek", return_value="report") as model:
            credentials.status.return_value = {"saved": True, "supported": True}
            credentials.save.return_value = credentials.status.return_value
            credentials.delete.return_value = {"saved": False, "supported": True}
            credentials.load.return_value = "test-only-key"
            for route, data in (("status", {}), ("save", {"api_key": "test-only-key"}), ("delete", {})):
                code, body, _ = self.request("/api/credentials/" + route, data)
                self.assertEqual(code, 200)
                self.assertNotIn(b"test-only-key", body)
            data = {"messages": self.messages, "provider": "deepseek", "model": "deepseek-flash", "use_saved_key": True}
            self.assertEqual(self.request("/api/analyze", data)[0], 400)
            credentials.load.assert_not_called()
            self.assertEqual(self.request("/api/analyze", {**data, "consent": True})[0], 200)
            self.assertEqual(model.call_args.args[1], "test-only-key")
            self.assertEqual(self.request("/api/credentials/delete", {}, {"X-Session-Token": ""})[0], 403)

    def test_external_import_retains_original_and_exports_bundle(self):
        raw = {"contact_display": "参考格式", "messages": [{"local_id": 99, "sender": "me", "timestamp": 1726142400,
                "type": "text", "content": "你好", "extra_metadata": "原样保留"}]}
        code, body, _ = self.request("/api/import", {"raw": raw, "label": "外部记录"})
        self.assertEqual(code, 200)
        result = json.loads(body)
        archive = self.server.store.load(result["archive"]["id"])
        self.assertEqual(archive["original_import"], raw)
        code, body, _ = self.request("/api/bundle", {"id": archive["id"]})
        self.assertEqual(code, 200)
        self.assertTrue(Path(json.loads(body)["index"]).is_file())
        code, body, _ = self.request("/api/material", {"messages": result["messages"]})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["coverage"]["total_messages"], 1)


if __name__ == "__main__":
    unittest.main()

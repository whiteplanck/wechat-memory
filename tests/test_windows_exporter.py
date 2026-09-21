import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory.storage import ArchiveStore
from wechat_memory.windows_exporter import WindowsExporter, safe_session_id


class WindowsExporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ArchiveStore(Path(self.tmp.name) / "archives")
        self.exporter = WindowsExporter(self.store, Path(self.tmp.name) / "tools")
        self.platform = patch.object(self.exporter, "require_windows")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.command = patch.object(self.exporter, "command", return_value=["node.exe", "cli.cjs"])
        self.command.start()
        self.addCleanup(self.command.stop)

    def test_session_id_validation(self):
        for value in ("wxid_test", "12345@chatroom", "filehelper"):
            self.assertTrue(safe_session_id(value))
        for value in ("../escape", "C:\\secret", "--help", "x&whoami", None, ".."):
            self.assertFalse(safe_session_id(value))

    def test_session_list_excludes_summary_and_keys(self):
        result = {"success": True, "sessions": [{"username": "wxid_test", "displayName": "虚构联系人", "summary": "private text", "key": "secret"}]}
        with patch.object(self.exporter, "_run", return_value=json.dumps(result)) as run:
            rows = self.exporter.list_sessions("虚构")
        self.assertEqual(rows["sessions"], [{"id": "wxid_test", "name": "虚构联系人"}])
        self.assertIn("--json", run.call_args.args[0])

    def fixture_export(self, command, timeout):
        self.assertEqual(timeout, 600)
        self.assertIn("--non-interactive", command)
        self.assertEqual(command[command.index("--limit") + 1], "0")
        out = Path(command[command.index("--output") + 1]) / "wxid_test_messages.json"
        raw = {"schema": "weflow-message/v1", "messages": [
            {"localId": 1, "serverId": "101", "createTime": 1726142400, "localType": 1, "isSend": 1, "parsedContent": "测试消息"},
            {"localId": 1, "serverId": "102", "createTime": 1726142460, "localType": 1, "isSend": 0, "parsedContent": "第二分片同 localId"}],
            "coverage": {"requestedLimit": 0, "returned": 2, "mayHaveMore": False}}
        out.write_text(json.dumps(raw), encoding="utf-8")
        return json.dumps({"success": True, "path": str(out), "count": 2})

    def test_selected_session_is_exported_and_archived(self):
        self.exporter.sessions["wxid_test"] = {"id": "wxid_test", "name": "虚构联系人"}
        with patch.object(self.exporter, "_run", side_effect=self.fixture_export):
            result = self.exporter.export("wxid_test")
        self.assertEqual(result["count"], 2)
        self.assertTrue(Path(result["raw_path"]).exists())
        record = self.store.load(result["archive"]["id"])
        self.assertEqual(record["messages"][0]["id"], "server-101")
        self.assertEqual(record["original_import"]["coverage"]["returned"], 2)

    def test_export_requires_selected_session(self):
        with patch.object(self.exporter, "_run") as run:
            with self.assertRaises(ValueError):
                self.exporter.export("wxid_not_selected")
            run.assert_not_called()

    def test_invalid_output_path_rejected(self):
        self.exporter.sessions["wxid_test"] = {"name": "测试"}
        with patch.object(self.exporter, "_run", return_value=json.dumps({"success": True, "path": str(Path(self.tmp.name) / "outside.json")})):
            with self.assertRaisesRegex(ValueError, "输出文件不在"):
                self.exporter.export("wxid_test")
        self.assertEqual(self.store.list()["archives"], [])

    def test_count_mismatch_keeps_raw_but_does_not_archive(self):
        self.exporter.sessions["wxid_test"] = {"name": "测试"}
        def wrong_count(command, timeout):
            result = json.loads(self.fixture_export(command, timeout))
            return json.dumps({**result, "count": 9})
        with patch.object(self.exporter, "_run", side_effect=wrong_count):
            with self.assertRaisesRegex(ValueError, "覆盖范围校验失败"):
                self.exporter.export("wxid_test")
        self.assertEqual(len(list((self.store.directory / "raw").rglob("*.json"))), 1)
        self.assertEqual(self.store.list()["archives"], [])

    def test_raw_tool_errors_are_not_reflected(self):
        for result in ('secret-key=abcd', '{"success":false,"error":"secret-key=abcd"}'):
            with patch.object(self.exporter, "_run", return_value=result):
                with self.assertRaises(ValueError) as error:
                    self.exporter.invoke(["sessions", "--json"])
                self.assertNotIn("abcd", str(error.exception))

    def test_concurrent_tasks_rejected(self):
        self.exporter.lock.acquire()
        try:
            with self.assertRaisesRegex(ValueError, "已有提取任务"):
                self.exporter.list_sessions()
        finally:
            self.exporter.lock.release()

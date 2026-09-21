import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory.storage import ArchiveStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ArchiveStore(self.tmp.name)
        self.messages = json.loads((Path(__file__).resolve().parents[1] / "examples/demo.json").read_text())["messages"]

    def test_reload_after_restart_and_deduplication(self):
        saved = self.store.save(self.messages, "旅行")
        reopened = ArchiveStore(self.tmp.name)
        self.assertEqual(len(reopened.load(saved["id"])["messages"]), 3)
        again = reopened.save(self.messages, "重复导入")
        self.assertEqual(saved, again)
        self.assertEqual(len(reopened.list()["archives"]), 1)
        if os.name != "nt":
            self.assertEqual(Path(saved["path"]).stat().st_mode & 0o777, 0o600)

    def test_distinct_imports_preserve_older_archive(self):
        first = self.store.save(self.messages, "完整")
        second = self.store.save(self.messages[:1], "部分")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list()["archives"]), 2)

    def test_invalid_import_and_failed_write_leave_no_archive(self):
        with self.assertRaises(ValueError):
            self.store.save([{}], "错误")
        with patch("wechat_memory.storage.os.link", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save(self.messages, "失败")
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_corruption_reported_and_never_overwritten(self):
        saved = self.store.save(self.messages, "旅行")
        path = Path(saved["path"])
        path.write_text("broken", encoding="utf-8")
        self.assertEqual(len(self.store.list()["errors"]), 1)
        with self.assertRaises(ValueError):
            self.store.save(self.messages, "旅行")
        self.assertEqual(path.read_text(), "broken")

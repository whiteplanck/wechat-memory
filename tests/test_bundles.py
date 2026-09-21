import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory.bundles import create_bundle, analysis_material
from wechat_memory.storage import ArchiveStore


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.store = ArchiveStore(self.root / "archives")
        self.messages = [{"id": "1", "conversation": "旅行/<script>", "sender": "小林", "timestamp": "2026-09-19T09:00:00+08:00",
                          "text": "<script>alert(1)</script>", "type": "image", "media": ["a.jpg", "missing.jpg", "../outside.txt", "https://example.com/photo.jpg"]}]
        (self.media / "a.jpg").write_bytes(b"fictional-image")
        (self.root / "outside.txt").write_text("not an attachment")

    def test_portable_copy_manifest_and_offline_html(self):
        archive = self.store.save(self.messages, "旅行")
        result = create_bundle(self.store, archive["id"], str(self.media))
        self.assertEqual((result["copied"], result["skipped"]), (1, 3))
        bundle = Path(result["path"])
        rows = json.loads((bundle / "messages.json").read_text(encoding="utf-8"))["messages"]
        self.assertEqual((bundle / rows[0]["media"][0]).read_bytes(), b"fictional-image")
        html = next((bundle / "contacts").glob("*/chat.html")).read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertTrue((bundle / "analysis_prompt.txt").exists())
        self.assertTrue((bundle / "photos.ics").exists())
        self.assertEqual(len(self.store.load(archive["id"])["messages"][0]["media"]), 4)
        # Copied media survive removal of the source file.
        (self.media / "a.jpg").unlink()
        self.assertEqual((bundle / rows[0]["media"][0]).read_bytes(), b"fictional-image")

    def test_symlink_escape_is_not_copied(self):
        try:
            (self.media / "escape.txt").symlink_to(self.root / "outside.txt")
        except OSError:
            self.skipTest("当前系统未授予创建符号链接的权限")
        self.messages[0]["media"] = ["escape.txt"]
        archive = self.store.save(self.messages, "旅行")
        result = create_bundle(self.store, archive["id"], str(self.media))
        self.assertEqual(result["copied"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_text_only_backup_and_size_limit(self):
        archive = self.store.save(self.messages, "旅行")
        result = create_bundle(self.store, archive["id"])
        self.assertEqual(result["copied"], 0)
        with patch("wechat_memory.bundles.MAX_FILE", 1):
            result = create_bundle(self.store, archive["id"], str(self.media))
            self.assertEqual(result["copied"], 0)
            self.assertEqual(list((Path(result["path"]) / "attachments").iterdir()), [])

    def test_sampling_coverage_and_no_network(self):
        messages = [{**self.messages[0], "id": str(i), "text": "字" * 500} for i in range(120)]
        stats, coverage, prompt = analysis_material(messages)
        self.assertEqual(stats["message_count"], 120)
        self.assertEqual(coverage["sampled_messages"], 60)
        self.assertEqual(coverage["truncated_messages"], 60)
        self.assertIn('"id": "119"', prompt)

    def test_failure_leaves_no_published_partial_bundle(self):
        archive = self.store.save(self.messages, "旅行")
        with patch("wechat_memory.bundles.json_file", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                create_bundle(self.store, archive["id"])
        self.assertEqual(list((self.store.directory / "bundles").iterdir()), [])

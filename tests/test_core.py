import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory.core import normalize, tree, statistics, calendar, chat_photo_events
from wechat_memory.cli import main
from wechat_memory.photos import scan_photos
from wechat_memory.providers import analyze

DEMO = Path(__file__).resolve().parents[1] / "examples/demo.json"


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(DEMO.read_text(encoding="utf-8"))["messages"]
        self.messages = normalize(self.raw)

    def test_stats_tree(self):
        self.assertEqual(statistics(self.messages)["message_count"], 3)
        self.assertEqual(len(tree(self.messages)[self.raw[0]["conversation"]]), 2)

    def test_duplicate_and_naive_timestamps(self):
        with self.assertRaises(ValueError):
            normalize(self.raw + [self.raw[0]])
        self.raw[0]["timestamp"] = "2026-09-19T10:00:00"
        with self.assertRaises(ValueError):
            normalize(self.raw)

    def test_actual_instant_ordering(self):
        self.raw[0]["timestamp"] = "2026-09-19T11:00:00+08:00"
        self.raw[1]["timestamp"] = "2026-09-19T04:00:00+00:00"
        self.assertEqual(normalize(self.raw)[0]["id"], "demo-001")

    def test_calendar_date_escape_and_utf8_folding(self):
        events = chat_photo_events(self.messages)
        events[0]["title"] = "照片" * 80 + ",;\nEND:VEVENT"
        result = calendar(events)
        self.assertIn("DTSTART;VALUE=DATE:20260919", result)
        self.assertIn("DTEND;VALUE=DATE:20260920", result)
        self.assertEqual(result.split("\r\n").count("END:VEVENT"), 1)
        self.assertTrue(all(len(line.encode()) <= 75 for line in result.split("\r\n")))

    def test_cli_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "archive.json")
            self.assertEqual(main(["export", str(DEMO), "--format", "json", "--output", out]), 0)
            self.assertEqual(normalize(json.loads(Path(out).read_text(encoding="utf-8"))), self.messages)
            self.assertEqual(main(["export", str(DEMO), "--output", out]), 1)

    def test_remote_requires_consent(self):
        with self.assertRaises(ValueError):
            analyze(self.messages, "example", "https://example.com")

    def test_ai_request_with_mock(self):
        with patch("wechat_memory.providers.build_opener") as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"message":{"content":"test summary"}}'
            self.assertEqual(analyze(self.messages, "local-model"), "test summary")
            request = build.return_value.open.call_args.args[0]
            self.assertFalse(json.loads(request.data)["stream"])

    def test_photo_exif_and_missing_date(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("optional Pillow not installed")
        with tempfile.TemporaryDirectory() as tmp:
            image = Image.new("RGB", (10, 10))
            exif = Image.Exif()
            exif[36867] = "2026:09:19 10:30:00"
            image.save(Path(tmp) / "dated.jpg", exif=exif)
            image.save(Path(tmp) / "undated.jpg")
            events, skipped = scan_photos(tmp)
            self.assertEqual(events[0]["date"], "2026-09-19")
            self.assertEqual(len(skipped), 1)


if __name__ == "__main__":
    unittest.main()

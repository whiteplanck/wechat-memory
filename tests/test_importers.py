from datetime import datetime
import json
import unittest

from wechat_memory.importers import import_records, parse_time


class ImportTests(unittest.TestCase):
    def test_timestamp_units_and_explicit_timezone(self):
        for value in (1726142400, 1726142400000, "1726142400000000", "1726142400000000000"):
            stamp, assumed = parse_time(value)
            self.assertEqual(datetime.fromisoformat(stamp).timestamp(), 1726142400)
            self.assertFalse(assumed)
        self.assertEqual(parse_time("2026-09-19 09:00", "+08:00"), ("2026-09-19T09:00:00+08:00", True))
        self.assertEqual(parse_time("2026-09-19T09:00:00Z")[0], "2026-09-19T09:00:00+00:00")
        with self.assertRaises(ValueError):
            parse_time(True)

    def test_reference_project_messages_and_transcript(self):
        raw = {"contact_display": "小林", "messages": [{"local_id": 42, "sender": "me", "timestamp": 1726142400000,
                "type": "voice", "content": "[语音]", "transcript": "明天见", "emoji_ref": "kept-in-original"}]}
        result = import_records(raw)
        self.assertEqual(result["source"], "she-love-me")
        self.assertEqual(result["messages"][0]["sender"], "我")
        self.assertEqual(result["messages"][0]["type"], "audio")
        self.assertIn("明天见", result["messages"][0]["text"])

    def test_weflow_and_ciphertalk(self):
        raw = [{"localId": 1, "createTime": 1726142400, "localType": 3, "parsedContent": "照片", "isSend": 1,
                "media": {"localPath": "photos/a.jpg"}}]
        result = import_records(raw, contact="朋友")
        self.assertEqual(result["source"], "weflow-cli")
        self.assertEqual(result["messages"][0]["media"], ["photos/a.jpg"])
        self.assertEqual(result["messages"][0]["sender"], "我")
        raw = {"messages": [{"messageId": 7, "timestamp": "2026/09/19 09:00", "direction": "in", "content": "你好"}]}
        result = import_records(raw, contact="小林")
        self.assertEqual(result["messages"][0]["sender"], "小林")
        self.assertEqual(len(result["warnings"]), 1)

    def test_markdown_keeps_multiline_and_reports_preamble(self):
        text = "# 对话\n[2026-09-19 09:30] 小林: 第一行\n第二行\n[2026-09-19 09:31] 我：收到"
        result = import_records(text, contact="旅行")
        self.assertEqual(len(result["messages"]), 2)
        self.assertIn("第二行", result["messages"][0]["text"])
        self.assertEqual(len(result["warnings"]), 2)

    def test_invalid_message_never_silently_dropped(self):
        with self.assertRaises(ValueError):
            import_records({"contact_display": "朋友", "messages": [{"sender": "me", "content": "无时间"}]})

    def test_bom_json(self):
        result = import_records("\ufeff" + json.dumps({"messages": []}))
        self.assertEqual(result["messages"], [])

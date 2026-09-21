from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from wechat_memory.relationships import build_report, RelationshipStore, export_report, tags, percentile


def message(i, sender, time, text="你好", kind="text"):
    return {"id": str(i), "conversation": "双人", "sender": sender, "timestamp": time, "text": text, "type": kind}


class RelationshipTests(unittest.TestCase):
    def test_bursts_median_and_censoring(self):
        rows = [message(1,"A","2026-01-01T10:00:00+08:00"),message(2,"A","2026-01-01T10:01:00+08:00"),
                message(3,"B","2026-01-01T10:03:00+08:00"),message(4,"A","2026-01-01T10:07:00+08:00")]
        r=build_report(rows,"双人")
        a,b=r["profiles"]
        self.assertEqual(b["reply_seconds"]["median"],120)
        self.assertEqual(a["reply_seconds"]["median"],240)
        self.assertEqual(a["counts"]["turns"],2)
        self.assertIsNone(a["interaction_index"])
        self.assertIsNone(a["components"]["initiative"])
        self.assertEqual(percentile([10,20],.5),15)

    def test_quiet_hours_gap_and_timezone(self):
        rows=[message(1,"A","2026-01-01T22:59:00+08:00"),message(2,"B","2026-01-01T23:01:00+08:00"),message(3,"A","2026-01-02T10:00:00+08:00")]
        r=build_report(rows,"双人")
        self.assertIsNone(r["profiles"][1]["reply_seconds"]["median"])
        self.assertEqual(r["profiles"][1]["reply_seconds"]["raw_median"],120)
        self.assertEqual(r["profiles"][0]["counts"]["initiations"],1)
        self.assertEqual(build_report(rows,"双人",quiet=False)["profiles"][1]["reply_seconds"]["median"],120)
        self.assertNotEqual(r["id"],build_report(rows,"双人",utc_offset=0)["id"])

    def test_group_rejected_before_date_filter(self):
        rows=[message(1,"A","2026-01-01T10:00:00Z"),message(2,"B","2026-01-01T11:00:00Z"),message(3,"C","2026-02-01T10:00:00Z")]
        with self.assertRaises(ValueError):build_report(rows,"双人",end="2026-01-02")
        with self.assertRaises(ValueError):build_report(rows[:2],"双人",gap_hours=True)
        with self.assertRaises(ValueError):build_report(rows[:2],"双人",start="2026-02-02",end="2026-01-01")

    def test_index_reproducible_and_supported_samples(self):
        rows=[]
        for day in range(6):
            for i in range(12):
                time=datetime(2026,1,1,10,tzinfo=timezone.utc)+timedelta(days=day,minutes=i)
                rows.append(message(len(rows),"A" if i%2==0 else "B",time.isoformat()))
        r=build_report(rows,"双人")
        for p in r["profiles"]:
            self.assertIsNotNone(p["interaction_index"])
            c=p["components"]
            self.assertEqual(p["interaction_index"],round(c["continuation"]*.5+c["initiative"]*.3+c["sharing"]*.2,1))
        self.assertEqual(r["id"],build_report(list(reversed(rows)),"双人")["id"])

    def test_candidates_not_confirmed_and_negation(self):
        rows=[message(1,"A","2026-01-01T10:00:00Z","电影里他说我喜欢你，明年去蜜月"),message(2,"B","2026-01-01T10:01:00Z","不喜欢你")]
        r=build_report(rows,"双人")
        self.assertTrue(r["events"])
        self.assertTrue(all(e["status"]=="candidate" and not e["date"] for e in r["events"]))
        self.assertNotIn("warmth",tags(rows[1]))
        self.assertNotIn("warmth",tags(rows[0]))
        self.assertNotIn("BEGIN:VEVENT",export_report(r,"ics"))

    def test_durable_events_and_path_guard(self):
        r=build_report([message(1,"A","2026-01-01T10:00:00Z","我喜欢你"),message(2,"B","2026-01-01T10:01:00Z")],"双人")
        with tempfile.TemporaryDirectory() as d:
            store=RelationshipStore(Path(d));store.create(r)
            e={**r["events"][0],"date":"2025-12-31","status":"confirmed"}
            store.update_event(r["id"],e)
            self.assertEqual(store.create(r)["events"][0]["date"],"2025-12-31")
            self.assertIn("20251231",export_report(store.load(r["id"]),"ics"))
            with self.assertRaises(ValueError):store.load("../bad")
            with self.assertRaises(ValueError):store.update_event(r["id"],{**e,"date":""})
            self.assertEqual(len(store.list()),1)


if __name__=="__main__":unittest.main()

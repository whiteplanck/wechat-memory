"""Offline, auditable dyadic interaction metrics. Not a psychometric test."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import os
import re
import tempfile
import threading

from .core import normalize, calendar
from .storage import ArchiveStore

METHOD = "interaction-v1"
LABELS = {"warmth": "亲近表达", "support": "支持表达", "distress": "负面感受/宣泄",
          "positive": "积极感受", "sharing": "内容分享"}
WORDS = {
    "warmth": ("喜欢你", "爱你", "想你", "抱抱", "想见你"),
    "support": ("辛苦了", "我陪你", "我在呢", "我理解", "为你高兴", "恭喜", "别自责"),
    "distress": ("我难过", "我好累", "我很累", "我害怕", "我焦虑", "我委屈", "我很生气", "我不开心"),
    "positive": ("我很开心", "好开心", "太开心", "好幸福", "太高兴", "好消息"),
}
EVENTS = {"confession": ("表白", "我喜欢你", "我爱你", "做我女朋友", "做我男朋友"),
          "conflict": ("吵架", "别再联系", "你根本不", "冷战"),
          "repair": ("和好", "对不起", "原谅我"),
          "commitment": ("在一起了", "结婚", "订婚", "领证"),
          "honeymoon_trip": ("蜜月",), "breakup": ("分手", "分开吧")}
EVENT_LABELS = {"confession": "表白", "conflict": "争执", "repair": "道歉/修复", "commitment": "关系承诺",
                "honeymoon_trip": "蜜月旅行", "honeymoon_phase": "热恋阶段（手动记录）", "breakup": "分开", "other": "其他大事"}
SOURCES = [
    {"title": "Laurenceau et al., 1998 · 披露与感知回应", "url": "https://doi.org/10.1037/0022-3514.74.5.1238"},
    {"title": "Gable et al., 2004 · 分享积极事件与回应", "url": "https://doi.org/10.1037/0022-3514.87.2.228"},
    {"title": "Templeton et al., 2022 · 口语轮替速度（不可直接套用微信）", "url": "https://doi.org/10.1073/pnas.2116915119"},
]


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * fraction
    lo = int(pos)
    return round(ordered[lo] + (ordered[min(lo + 1, len(ordered) - 1)] - ordered[lo]) * (pos - lo), 1)


def rate(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def tags(message):
    text = message["text"]
    found = set()
    for kind, words in WORDS.items():
        # This small dictionary intentionally abstains on common negations/quotes.
        if any(re.search(r"(?<!不)(?<!没)(?<!别)" + re.escape(word), text) for word in words):
            if not any(x in text for x in ("他说", "她说", "电影", "歌词", "小说", "“", '"')):
                found.add(kind)
    if message["type"] in ("image", "video", "file") or re.search(r"https?://", text) or "分享给你" in text:
        found.add("sharing")
    return found


def _quiet_overlap(start, end, quiet):
    if not quiet:
        return False
    # Both timestamps are already in the same fixed analysis time zone.
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor <= end:
        if start < cursor + timedelta(hours=8) and end >= cursor:
            return True
        if start < cursor + timedelta(days=1) and end >= cursor + timedelta(hours=23):
            return True
        cursor += timedelta(days=1)
    return False


def build_report(raw, conversation, start="", end="", gap_hours=4, quiet=True, utc_offset=8):
    if type(gap_hours) not in (int, float) or gap_hours not in (1, 4, 8, 24):
        raise ValueError("会话间隔请选择 1、4、8 或 24 小时")
    if type(quiet) is not bool or type(utc_offset) is not int or not -12 <= utc_offset <= 14:
        raise ValueError("时间设置无效")
    for value in (start, end):
        if not isinstance(value, str) or (value and date.fromisoformat(value).isoformat() != value):
            raise ValueError("日期格式应为 YYYY-MM-DD")
    if start and end and start > end:
        raise ValueError("开始日期不能晚于结束日期")
    all_rows = normalize(raw)
    if not isinstance(conversation, str) or not conversation:
        raise ValueError("请选择一个一对一会话")
    all_rows = [m for m in all_rows if m["conversation"] == conversation]
    # Check before filtering; a group must never become an apparent dyad by date slicing.
    people = sorted({m["sender"] for m in all_rows})
    if len(people) != 2:
        raise ValueError("仅支持恰好两位发言者的会话；群聊或单方记录不能计算双向关系")
    zone = timezone(timedelta(hours=utc_offset))
    local = lambda m: datetime.fromisoformat(m["timestamp"]).astimezone(zone)
    rows = [m for m in all_rows if (not start or local(m).date().isoformat() >= start)
            and (not end or local(m).date().isoformat() <= end)]
    if not rows or len({m["sender"] for m in rows}) != 2:
        raise ValueError("此范围没有双方消息，请扩大日期范围")
    settings = {"conversation": conversation, "start": start, "end": end, "gap_hours": gap_hours,
                "quiet": quiet, "utc_offset": utc_offset}
    report_id = ArchiveStore.identity({"rows": rows, "settings": settings, "method": METHOD})
    gap = gap_hours * 3600
    counters = {p: Counter() for p in people}
    days = {p: set() for p in people}
    evidence = {p: defaultdict(list) for p in people}
    monthly = defaultdict(lambda: {p: Counter() for p in people})
    candidates, turns = [], []
    event_total = 0
    for i, m in enumerate(rows):
        p, moment = m["sender"], local(m)
        found = tags(m)
        c = counters[p]
        c["messages"] += 1
        c["characters"] += len(m["text"])
        days[p].add(moment.date().isoformat())
        month = monthly[moment.strftime("%Y-%m")][p]
        month["messages"] += 1
        for kind in found:
            c[kind] += 1
            month[kind] += 1
            if len(evidence[p][kind]) < 12:
                evidence[p][kind].append(m["id"])
        new_session = not turns or (moment - turns[-1]["end"]).total_seconds() >= gap
        if new_session and i:
            c["initiations"] += 1  # First observed message is left-censored, not an initiation.
        if new_session or turns[-1]["sender"] != p:
            turns.append({"sender": p, "start": moment, "end": moment, "ids": [m["id"]], "tags": set(found)})
        else:
            turns[-1]["end"] = moment
            turns[-1]["ids"].append(m["id"])
            turns[-1]["tags"].update(found)
        for kind, words in EVENTS.items():
            if any(word in m["text"] for word in words):
                event_total += 1
                if len(candidates) < 200:
                    candidates.append({"id": f"{kind}:{m['id']}", "kind": kind, "title": EVENT_LABELS[kind],
                        "mentioned_on": moment.date().isoformat(), "date": "", "end_date": "", "status": "candidate",
                        "note": "仅为关键词候选，可能是否定、转述、回忆或未来计划。请核对实际发生日期。",
                        "evidence_ids": [x["id"] for x in rows[max(0, i-1):i+2]]})
    delays = {p: [] for p in people}
    eligible_delays = {p: [] for p in people}
    reply_evidence = {p: [] for p in people}
    for i, turn in enumerate(turns):
        p = turn["sender"]
        counters[p]["turns"] += 1
        if i + 1 == len(turns):
            continue
        following = turns[i+1]
        target = next(x for x in people if x != p)
        seconds = (following["start"] - turn["end"]).total_seconds()
        responded = following["sender"] == target and seconds < gap
        horizon = following["start"] if responded else turn["end"] + timedelta(seconds=gap)
        if responded:
            delays[target].append(seconds)
        # No full observation window for an unanswered final opportunity: abstain.
        if horizon > local(rows[-1]) or _quiet_overlap(turn["end"], horizon, quiet):
            counters[target]["excluded_opportunities"] += 1
            continue
        counters[target]["opportunities"] += 1
        counters[target]["responses"] += int(responded)
        if responded:
            eligible_delays[target].append(seconds)
            if len(reply_evidence[target]) < 20:
                reply_evidence[target].append({"from_id": turn["ids"][-1], "to_id": following["ids"][0], "seconds": seconds})
            if "distress" in turn["tags"] or "positive" in turn["tags"]:
                counters[target]["disclosure_responses"] += 1
                counters[target]["support_after_disclosure"] += int("support" in following["tags"])
    profiles = []
    total_initiations = sum(c["initiations"] for c in counters.values())
    for p in people:
        c = counters[p]
        own_turns = [t for t in turns if t["sender"] == p]
        sharing_turns = sum("sharing" in t["tags"] for t in own_turns)
        components = {"continuation": rate(c["responses"], c["opportunities"]),
                      "initiative": rate(c["initiations"], total_initiations),
                      "sharing": rate(sharing_turns, c["turns"])}
        enough = c["messages"] >= 30 and len(days[p]) >= 3 and c["opportunities"] >= 5 and total_initiations >= 5
        score = round(sum(components[k] * w for k, w in (("continuation", .5), ("initiative", .3), ("sharing", .2))), 1) if enough else None
        profiles.append({"person": p, "toward": next(x for x in people if x != p), "counts": dict(c),
            "active_days": len(days[p]), "message_share": rate(c["messages"], len(rows)),
            "sharing_turns": sharing_turns, "components": components, "interaction_index": score,
            "index_status": "启发式互动投入，不是喜爱概率" if enough else "样本不足：需本人 ≥30 条、≥3 活跃日、≥5 回应机会及双方 ≥5 次发起",
            "reply_seconds": {"raw_n": len(delays[p]), "n": len(eligible_delays[p]),
                              "median": percentile(eligible_delays[p], .5), "q1": percentile(eligible_delays[p], .25),
                              "q3": percentile(eligible_delays[p], .75), "raw_median": percentile(delays[p], .5)},
            "evidence": dict(evidence[p]), "reply_evidence": reply_evidence[p]})
    return {"id": report_id, "method": METHOD, "created_at": datetime.now(timezone.utc).isoformat(),
            "settings": settings, "scope": {"messages": len(rows), "from": rows[0]["timestamp"], "to": rows[-1]["timestamp"],
                                           "source_hash": ArchiveStore.identity(rows)},
            "profiles": profiles, "monthly": [{"month": k, "people": v} for k, v in sorted(monthly.items())],
            "events": candidates, "candidate_count": event_total, "messages": rows, "ai": "", "sources": SOURCES,
            "limitations": ["无法从聊天确定真实爱意；指数不经过心理测量验证，不能作关系决策的唯一依据。",
                "会话间隔是产品设置；首条发起、末尾未完整观察的等待不计。回应是相邻轮替，不证明语义回复、已读或有空。",
                "回复时延仅统计会话内跨发送方轮替；默认排除 23:00–08:00，不扣除工作时间；跨会话延迟不计，可能低估实际等待。",
                "情感词与分享仅为线索，不读图片/语音；反讽、否定、转述与关系背景可能误判。宣泄不自动加分或扣分。",
                "总分 = 窗口内接续率×50% + 双方发起份额×30% + 本人分享轮次率×20%。权重为产品启发式，不来自论文。回复速度不计分。",
                "指标针对当前档案范围，缺失/删除记录、线下互动和双方表达习惯会造成偏差；不推断人格类型或心理疾病。"]}


class RelationshipStore:
    def __init__(self, directory):
        self.directory = directory / "relationships"
        self.lock = threading.RLock()

    def path(self, report_id):
        if not isinstance(report_id, str) or not re.fullmatch(r"[a-f0-9]{64}", report_id):
            raise ValueError("无效的关系报告编号")
        return self.directory / (report_id + ".json")

    def load(self, report_id):
        return json.loads(self.path(report_id).read_text(encoding="utf-8"))

    def save(self, report):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".relationship-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path(report["id"]))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return report

    def create(self, report):
        with self.lock:
            if self.path(report["id"]).exists():
                return self.load(report["id"])  # Never discard manual confirmations/AI on regeneration.
            return self.save(report)

    def list(self):
        result = []
        for path in self.directory.glob("*.json"):
            try:
                r = self.load(path.stem)
                result.append({"id": r["id"], "conversation": r["settings"]["conversation"], "created_at": r["created_at"], "scope": r["scope"]})
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return sorted(result, key=lambda r: r["created_at"], reverse=True)

    def update_event(self, report_id, event):
        with self.lock:
            report = self.load(report_id)
            if not isinstance(event, dict):
                raise ValueError("事件必须是对象")
            kind, state = event.get("kind"), event.get("status")
            if kind not in EVENT_LABELS or state not in ("confirmed", "dismissed", "candidate"):
                raise ValueError("事件类型或状态无效")
            for field in ("title", "note", "date", "end_date"):
                if not isinstance(event.get(field, ""), str) or len(event.get(field, "")) > (2000 if field == "note" else 200):
                    raise ValueError("事件字段格式无效或过长")
            actual, ending = event.get("date", ""), event.get("end_date", "")
            for day in (actual, ending):
                if day and date.fromisoformat(day).isoformat() != day:
                    raise ValueError("日期无效")
            if state == "confirmed" and (not actual or not event.get("title", "").strip()):
                raise ValueError("确认事件需要标题和实际日期")
            if ending and (not actual or ending < actual):
                raise ValueError("结束日期不能早于开始日期")
            old = next((x for x in report["events"] if x["id"] == event.get("id")), None)
            if not old:
                if event.get("id"):
                    raise ValueError("事件不存在")
                import uuid
                old = {"id": "manual:" + uuid.uuid4().hex, "evidence_ids": [], "mentioned_on": ""}
                report["events"].append(old)
            old.update({k: event.get(k, "") for k in ("kind", "status", "title", "note", "date", "end_date")})
            return self.save(report)

    def save_ai(self, report_id, content):
        with self.lock:
            report = self.load(report_id)
            report["ai"] = content
            report["ai_created_at"] = datetime.now(timezone.utc).isoformat()
            return self.save(report)


def export_report(report, fmt):
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    if fmt == "ics":
        events = []
        for e in report["events"]:
            if e["status"] == "confirmed":
                events.append({"date": e["date"], "title": e["title"], "description": e["note"] +
                    ("\n阶段结束：" + e["end_date"] if e.get("end_date") else "")})
        return calendar(events)
    if fmt != "markdown":
        raise ValueError("不支持的报告格式")
    lines = ["# 情感与关系报告", "", "```json", json.dumps({k: v for k, v in report.items() if k not in ("messages", "ai")}, ensure_ascii=False, indent=2), "```", "", "## AI 解读（未自动验证）", ""]
    lines.extend("> " + line for line in report["ai"].splitlines())
    lines.extend(["", "## 可回查原文", ""])
    for m in report["messages"]:
        lines.extend("> " + line for line in f"[{m['id']}] {m['timestamp']} {m['sender']}\n{m['text']}".splitlines())
        lines.append("")
    return "\n".join(lines)

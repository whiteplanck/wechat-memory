"""Pure archive operations. No network or implicit filesystem writes."""

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json


def normalize(raw):
    if isinstance(raw, dict):
        raw = raw.get("messages")
    if not isinstance(raw, list):
        raise ValueError("输入必须是消息数组或包含 messages 数组的对象")
    messages, ids = [], set()
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"第 {i + 1} 条消息不是对象")
        message = {}
        for key in ("id", "conversation", "sender", "timestamp", "text"):
            value = row.get(key)
            if not isinstance(value, str) or (key != "text" and not value.strip()):
                raise ValueError(f"第 {i + 1} 条消息缺少有效字段 {key}")
            message[key] = value
        stamp = datetime.fromisoformat(message["timestamp"])
        if stamp.tzinfo is None:
            raise ValueError("timestamp 必须包含时区，例如 +08:00")
        message["timestamp"] = stamp.isoformat()
        identity = (message["conversation"], message["id"])
        if identity in ids:
            raise ValueError(f"重复消息 ID：{identity}")
        ids.add(identity)
        message["type"] = row.get("type", "text")
        if message["type"] not in ("text", "image", "audio", "video", "file", "other"):
            raise ValueError("不支持的消息 type")
        media = row.get("media", [])
        if not isinstance(media, list) or not all(isinstance(p, str) for p in media):
            raise ValueError("media 必须是路径字符串数组")
        message["media"] = media
        messages.append(message)
    return sorted(messages, key=lambda m: datetime.fromisoformat(m["timestamp"]))


def tree(messages):
    result = {}
    for m in messages:
        day = m["timestamp"][:10]
        result.setdefault(m["conversation"], {}).setdefault(day, []).append(m["id"])
    return result


def statistics(messages):
    return {
        "message_count": len(messages),
        "conversations": dict(Counter(m["conversation"] for m in messages)),
        "senders": dict(Counter(m["sender"] for m in messages)),
        "types": dict(Counter(m["type"] for m in messages)),
        "days": dict(Counter(m["timestamp"][:10] for m in messages)),
    }


def markdown(messages):
    parts = ["# 聊天记录\n"]
    # Indented code blocks preserve untrusted chat text without active HTML/links.
    for m in messages:
        content = f'{m["timestamp"]} | {m["conversation"]} | {m["sender"]}\n{m["text"]}'
        if m["media"]:
            content += "\n附件：" + ", ".join(m["media"])
        parts.append("\n".join("    " + line for line in content.splitlines()) + "\n")
    return "\n".join(parts)


def ics_escape(value):
    return value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold(line):
    chunks, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            chunks.append(current)
            current = " "
        current += char
    return "\r\n".join(chunks + [current])


def calendar(events):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//wechat-memory//Photo Calendar//ZH", "CALSCALE:GREGORIAN"]
    for event in events:
        day = datetime.strptime(event["date"], "%Y-%m-%d").date()
        uid = hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        lines.extend([
            "BEGIN:VEVENT", f"UID:{uid}@wechat-memory", "DTSTAMP:19700101T000000Z",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + ics_escape(event["title"]), "DESCRIPTION:" + ics_escape(event["description"]), "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def chat_photo_events(messages):
    return [
        {"date": m["timestamp"][:10], "title": f'{m["conversation"]} · {m["sender"]}的照片',
         "description": f'日期依据：消息发送时间\n消息 ID：{m["id"]}\n{m["text"]}\n' + "\n".join(m["media"])}
        for m in messages if m["type"] == "image"
    ]

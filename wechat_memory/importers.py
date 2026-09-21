"""Explicit adapters for exported records; never access the WeChat process."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .core import normalize

FORMATS = {"auto", "standard", "she-love-me", "weflow-cli", "ciphertalk", "markdown"}


def parse_time(value, offset="+08:00"):
    if not re.fullmatch(r"[+-](?:0\d|1[0-4]):[0-5]\d", offset):
        raise ValueError("时区必须是 +08:00 这样的 UTC 偏移")
    minutes = (int(offset[1:3]) * 60 + int(offset[4:])) * (-1 if offset[0] == "-" else 1)
    zone = timezone(timedelta(minutes=minutes))
    if isinstance(value, bool) or value is None:
        raise ValueError("缺少有效时间戳")
    text = str(value).strip()
    assumed = False
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            seconds = Decimal(text)
            while seconds >= 100_000_000_000:
                seconds /= 1000
            stamp = datetime.fromtimestamp(float(seconds), timezone.utc).astimezone(zone)
        except (InvalidOperation, OverflowError, OSError) as exc:
            raise ValueError("时间戳超出范围") from exc
    else:
        stamp = datetime.fromisoformat(text.replace("/", "-"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=zone)
            assumed = True
    if not 2000 <= stamp.year <= 2100:
        raise ValueError("外部记录时间需在 2000 至 2100 年之间")
    return stamp.isoformat(), assumed


def first(row, keys, default=None):
    return next((row[key] for key in keys if row.get(key) is not None), default)


def import_records(raw, fmt="auto", contact="", offset="+08:00"):
    if fmt not in FORMATS:
        raise ValueError("不支持的导入格式")
    if not isinstance(contact, str):
        raise ValueError("会话名必须是字符串")
    warnings = []
    if isinstance(raw, str) and fmt in {"auto", "markdown"}:
        if fmt == "auto":
            try:
                raw = json.loads(raw.lstrip("\ufeff"))
            except json.JSONDecodeError:
                fmt = "markdown"
        if fmt == "markdown":
            rows = []
            pattern = re.compile(r"^\s*(?:[-*]\s+)?\[(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)\]\s+([^:：]+)[:：]\s?(.*)$")
            preamble = 0
            for line in raw.lstrip("\ufeff").splitlines():
                match = pattern.match(line)
                if match:
                    stamp, sender, text = match.groups()
                    rows.append({"timestamp": stamp, "sender": sender.strip(), "content": text, "type": "text"})
                elif rows:
                    rows[-1]["content"] += "\n" + line
                elif line.strip():
                    preamble += 1
            if not rows:
                raise ValueError("未识别到消息。支持格式：[2026-09-19 09:30] 小林: 消息内容")
            if preamble:
                warnings.append(f"消息之前的 {preamble} 行说明保存在原始导入内容中，未计为消息")
            raw = {"messages": rows}
    if isinstance(raw, str):
        raw = json.loads(raw.lstrip("\ufeff"))
    metadata = raw if isinstance(raw, dict) else {}
    rows = metadata.get("messages") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("需要消息数组或包含 messages 数组的对象")
    if fmt == "auto":
        head = rows[0] if rows else {}
        if not rows or all(key in head for key in ("id", "conversation", "text")):
            fmt = "standard"
        elif "contact_display" in metadata or "local_id" in head:
            fmt = "she-love-me"
        elif "parsedContent" in head or "senderUsername" in head:
            fmt = "weflow-cli"
        elif any(key in head for key in ("direction", "createTime", "messageId")):
            fmt = "ciphertalk"
        else:
            raise ValueError("未识别到格式，请选择数据来源；支持标准 JSON、she-love-me、weflow-cli、CipherTalk 和时间戳 Markdown")
    if fmt == "standard":
        return {"messages": normalize(rows), "source": fmt, "warnings": warnings}
    conversation = contact.strip() or str(metadata.get("contact_display") or metadata.get("contact_username") or "导入会话")
    converted, assumed_count, unknown_count, media_warnings = [], 0, 0, 0
    type_map = {"1": "text", "3": "image", "34": "audio", "43": "video", "voice": "audio", "语音": "audio", "图片": "image", "文本": "text", "视频": "video", "文件": "file"}
    for index, row in enumerate(rows, 1):
        try:
            stamp, assumed = parse_time(first(row, ("timestamp", "createTime", "create_time", "time")), offset)
            assumed_count += int(assumed)
            kind = str(first(row, ("localType", "type", "kind"), "text")).lower()
            kind = type_map.get(kind, kind)
            if kind not in {"text", "image", "audio", "video", "file", "other"}:
                kind = "other"
            sender = first(row, ("senderUsername", "sender", "senderName"))
            if not sender:
                direction = row.get("direction")
                sent = row.get("isSend")
                if direction == "out" or sent in (1, "1", True):
                    sender = "我"
                elif direction == "in" or sent in (0, "0", False):
                    sender = conversation
                else:
                    sender = "未知发送者"
                    unknown_count += 1
            sender = {"me": "我", "them": conversation}.get(str(sender), str(sender))
            text = first(row, ("parsedContent", "content", "text", "rawContent"), "")
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            media = row.get("media", [])
            transcript = first(row, ("transcript", "voiceTranscript", "voice_transcript"))
            if isinstance(media, dict):
                transcript = transcript or media.get("transcript")
                path = first(media, ("path", "localPath", "filePath"))
                media = [path] if isinstance(path, str) else []
                if not media:
                    media_warnings += 1
            elif isinstance(media, str):
                media = [media]
            if transcript:
                text += "\n[语音转写] " + str(transcript)
            identity = first(row, ("id", "local_id", "localId", "messageId"))
            if fmt == "weflow-cli" and row.get("serverId") not in (None, "", 0, "0"):
                identity = "server-" + str(row["serverId"])
            if identity is None:
                identity = "import-" + hashlib.sha256(json.dumps([row, index], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
            converted.append({"id": str(identity), "conversation": str(row.get("conversation") or conversation),
                              "sender": sender, "timestamp": stamp, "text": text, "type": kind, "media": media})
        except (ValueError, TypeError) as exc:
            raise ValueError(f"第 {index} 条消息转换失败：{exc}。未保存任何记录。") from exc
    if assumed_count:
        warnings.append(f"{assumed_count} 条消息未标注时区，按 {offset} 解释")
    if unknown_count:
        warnings.append(f"{unknown_count} 条消息缺少发送者，保留为未知发送者")
    if media_warnings:
        warnings.append(f"{media_warnings} 条媒体元数据没有本地路径；原始内容保留，尚不能复制附件")
    return {"messages": normalize(converted), "source": fmt, "warnings": warnings}

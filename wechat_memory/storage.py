"""Durable, immutable JSON archives outside the source repository."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .core import normalize

DEFAULT_DATA_DIR = Path.home() / "Documents" / "WeChatMemory"


class ArchiveStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or DEFAULT_DATA_DIR).expanduser().resolve()

    def load(self, archive_id):
        if not isinstance(archive_id, str) or not re.fullmatch(r"[0-9a-f]{64}", archive_id):
            raise ValueError("无效的档案编号")
        path = self.directory / f"{archive_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("id") != archive_id:
            raise ValueError("档案格式损坏")
        messages = normalize(record.get("messages"))
        if self.identity(messages) != archive_id:
            raise ValueError("档案内容校验失败；原文件已保留，请检查备份")
        if not isinstance(record.get("label"), str) or not isinstance(record.get("created_at"), str):
            raise ValueError("档案元数据损坏")
        return {**record, "messages": messages, "path": str(path)}

    @staticmethod
    def identity(messages):
        payload = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def summary(record):
        return {key: record[key] for key in ("id", "label", "created_at", "path")} | {"count": len(record["messages"])}

    def save(self, messages, label):
        messages = normalize(messages)
        if not isinstance(label, str) or not label.strip():
            label = "聊天档案"
        archive_id = self.identity(messages)
        target = self.directory / f"{archive_id}.json"
        if target.exists():
            return self.summary(self.load(archive_id))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {"version": 1, "id": archive_id, "label": label[:200],
                  "created_at": datetime.now(timezone.utc).isoformat(), "messages": messages}
        fd, temporary = tempfile.mkstemp(prefix=".saving-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(record, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            try:
                # Publish a complete file atomically without replacing any archive.
                os.link(temporary, target)
            except FileExistsError:
                pass  # Another import of the same content completed first.
        finally:
            Path(temporary).unlink(missing_ok=True)
        return self.summary(self.load(archive_id))

    def list(self):
        archives, errors = [], []
        for path in self.directory.glob("*.json"):
            try:
                archives.append(self.summary(self.load(path.stem)))
            except (ValueError, OSError, TypeError, KeyError) as exc:
                errors.append({"file": path.name, "error": str(exc)})
        archives.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
        return {"archives": archives, "directory": str(self.directory), "errors": errors}

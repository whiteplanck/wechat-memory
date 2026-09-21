"""Versioned, local annotations and opt-in offline voice transcription."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import wave

class MemoryStore:
    def __init__(self, archives):
        self.archives = archives
        self.directory = archives.directory / "annotations"
        self.lock = threading.RLock()
        self.transcription_lock = threading.Lock()

    def load(self, archive_id):
        self.archives.load(archive_id)  # Validate identity and original archive existence.
        path = self.directory / (archive_id + ".json")
        if not path.exists():
            return {"schema": "wechat-memory.annotations.v1", "archive_id": archive_id, "revision": 0, "items": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, data):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".annotations-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.directory / (data["archive_id"] + ".json"))
        finally:
            Path(temporary).unlink(missing_ok=True)
        return data

    def message(self, archive_id, conversation, message_id):
        record = self.archives.load(archive_id)
        message = next((m for m in record["messages"] if m["conversation"] == conversation and m["id"] == message_id), None)
        if not message:
            raise ValueError("消息不存在")
        return message

    def annotate(self, archive_id, conversation, message_id, people, caption, transcript, expected_revision):
        message = self.message(archive_id, conversation, message_id)
        if not isinstance(people, list) or len(people) > 30 or any(not isinstance(p, str) or not p.strip() or len(p) > 80 for p in people):
            raise ValueError("人物标签无效（最多 30 个，每个 80 字）")
        if not isinstance(caption, str) or len(caption) > 2000 or not isinstance(transcript, str) or len(transcript) > 30000:
            raise ValueError("说明或转写过长")
        if transcript and message["type"] != "audio":
            raise ValueError("仅语音消息可填写转写")
        with self.lock:
            data = self.load(archive_id)
            if type(expected_revision) is not int or data["revision"] != expected_revision:
                raise ValueError("档案注释已变化，请刷新后重试，避免覆盖他人修改")
            item = next((x for x in data["items"] if x["conversation"] == conversation and x["message_id"] == message_id), None)
            if item is None:
                item = {"conversation": conversation, "message_id": message_id, "history": []}
                data["items"].append(item)
            item["history"].append({k: v for k, v in item.items() if k != "history"})
            item.update({"people": sorted(set(p.strip() for p in people)), "caption": caption, "transcript": transcript,
                         "transcript_status": "user_reviewed" if transcript else "empty", "updated_at": datetime.now(timezone.utc).isoformat()})
            data["revision"] += 1
            return self._save(data)

    def transcribe(self, archive_id, conversation, message_id, media_root, reference, model_dir):
        m = self.message(archive_id, conversation, message_id)
        if m["type"] != "audio" or reference not in m["media"]:
            raise ValueError("请选择该语音消息已有的附件引用")
        if not isinstance(media_root, str) or not Path(media_root).is_absolute() or not isinstance(model_dir, str) or not Path(model_dir).is_absolute():
            raise ValueError("附件根目录与模型目录须为本机绝对路径")
        root, model = Path(media_root).resolve(), Path(model_dir).resolve()
        audio = (root / reference).resolve()
        if not audio.is_relative_to(root) or not audio.is_file() or audio.suffix.lower() != ".wav":
            raise ValueError("仅支持指定目录内的 WAV；微信 SILK/加密语音请先用可信导出工具解码为 WAV，并关联正确附件路径")
        if audio.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("单条 WAV 限制 20 MB")
        if not all((model / name).is_file() for name in ("model.bin", "config.json", "tokenizer.json")):
            raise ValueError("模型目录需要完整 faster-whisper 模型（model.bin、config.json、tokenizer.json）；不会自动联网下载")
        if not self.transcription_lock.acquire(blocking=False):
            raise ValueError("已有语音正在转写，请等待完成")
        try:
            with audio.open("rb") as stream:
                raw = stream.read(20 * 1024 * 1024 + 1)
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("语音超过大小限制")
            try:
                with wave.open(io.BytesIO(raw)) as wav:
                    if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000 or wav.getnframes() > 16000 * 600:
                        raise ValueError("请提供 16 kHz、单声道、16-bit PCM WAV，最长 10 分钟")
                    frames = wav.readframes(wav.getnframes())
            except (wave.Error, EOFError):
                raise ValueError("WAV 文件格式损坏或尚未解码") from None
            try:
                import numpy as np
                from faster_whisper import WhisperModel
            except ImportError:
                raise ValueError("语音组件未安装：源码版需安装 .[speech]；请使用包含语音组件的新安装版") from None
            # ndarray input avoids opening any media-provided network URL or playlist.
            engine = WhisperModel(str(model), device="cpu", compute_type="int8", local_files_only=True, cpu_threads=4)
            segments, info = engine.transcribe(np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768,
                                                language="zh", beam_size=5, vad_filter=True)
            result = [{"start_seconds": round(s.start, 3), "end_seconds": round(s.end, 3), "text": s.text} for s in segments]
            text = "".join(s["text"] for s in result).strip()
            with self.lock:
                data = self.load(archive_id)
                item = next((x for x in data["items"] if x["conversation"] == conversation and x["message_id"] == message_id), None)
                if item is None:
                    item = {"conversation": conversation, "message_id": message_id, "people": [], "caption": "", "transcript": "", "history": []}
                    data["items"].append(item)
                if item.get("asr_candidate"):
                    item.setdefault("asr_history", []).append(item["asr_candidate"])
                item["asr_candidate"] = {"text": text, "segments": result, "source_sha256": hashlib.sha256(raw).hexdigest(),
                    "reference": reference, "engine": "faster-whisper/cpu/int8", "model_name": model.name,
                    "model_config_sha256": hashlib.sha256((model / "config.json").read_bytes()).hexdigest(),
                    "language": info.language, "status": "unreviewed", "created_at": datetime.now(timezone.utc).isoformat()}
                data["revision"] += 1
                return self._save(data)  # Does not overwrite a reviewed transcript.
        finally:
            self.transcription_lock.release()

    def view(self, archive_id):
        data = self.load(archive_id)
        rows = self.archives.load(archive_id)["messages"]
        index = {(x["conversation"], x["message_id"]): x for x in data["items"]}
        memories, people = defaultdict(list), defaultdict(list)
        for m in rows:
            key = {"conversation": m["conversation"], "message_id": m["id"]}
            annotation = index.get((m["conversation"], m["id"]), {})
            if m["type"] in ("image", "video", "audio") or annotation.get("caption"):
                memories[m["timestamp"][:10]].append(key)
            for person in annotation.get("people", []):
                people[person].append(key)
        return {**data, "memories": [{"date": day, "items": items, "date_source": "消息发送日期（不是照片拍摄日期）"} for day, items in sorted(memories.items())],
                "people": [{"name": name, "items": items, "source": "用户手动标签，非人脸识别"} for name, items in sorted(people.items())]}

    def enriched(self, archive_id, annotations=None):
        """A clearly labelled derived view; immutable original is never rewritten."""
        data = annotations if annotations is not None else self.load(archive_id)
        by_id = {(x["conversation"], x["message_id"]): x for x in data["items"]}
        rows = []
        for m in self.archives.load(archive_id)["messages"]:
            item = by_id.get((m["conversation"], m["id"]), {})
            transcript = item.get("transcript", "")
            rows.append({**m, "text": m["text"] + ("\n[用户核对的语音转写，非原始文字]\n" + transcript if transcript else "")})
        return rows

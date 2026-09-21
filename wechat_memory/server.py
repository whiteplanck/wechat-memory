"""Loopback-only UI server backed by durable local JSON archives."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from socketserver import TCPServer
from urllib.parse import urlsplit
import webbrowser

from .core import normalize, tree, statistics, markdown, calendar, chat_photo_events
from .photos import scan_photos
from .providers import analyze
from .storage import ArchiveStore
from .importers import import_records
from .bundles import create_bundle, analysis_material
from .windows_exporter import WindowsExporter
from .console import configure_console

STATIC = Path(__file__).parent / "web"
MAX_BODY = 20 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log paths or chat content.

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {"error": "仅允许本机地址访问"})
        name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(urlsplit(self.path).path)
        if not name:
            return self.reply(404, {"error": "不存在的页面"})
        body = (STATIC / name).read_bytes()
        if name == "index.html":
            body = body.replace(b"__SESSION_TOKEN__", self.server.token.encode())
        mime = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[name]
        self.reply(200, body, mime + "; charset=utf-8")

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self.valid_host() or self.headers.get("Origin") not in (None, origin) or not secrets.compare_digest(self.headers.get("X-Session-Token", ""), self.server.token):
            return self.reply(403, {"error": "会话验证失败，请重新打开本地页面"})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"error": "请求必须使用 JSON"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, {"error": "单次导入限制为 20 MB，请拆分记录"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("请求必须是对象")
            if self.path == "/api/windows/status":
                result = self.server.exporter.status()
            elif self.path == "/api/windows/sessions":
                result = self.server.exporter.list_sessions(data.get("keyword", ""))
            elif self.path == "/api/windows/export":
                result = self.server.exporter.export(data.get("id"))
            elif self.path == "/api/archives":
                result = self.server.store.list()
            elif self.path == "/api/archive":
                record = self.server.store.load(data.get("id"))
                result = {"messages": record["messages"], "archive": self.server.store.summary(record), **record.get("import_info", {})}
            elif self.path == "/api/bundle":
                media_root = data.get("media_root")
                if media_root and (not isinstance(media_root, str) or not Path(media_root).expanduser().is_absolute()):
                    raise ValueError("附件根目录必须是绝对路径")
                result = create_bundle(self.server.store, data.get("id"), media_root)
            elif self.path == "/api/material":
                messages = normalize(data.get("messages"))
                stats, coverage, prompt = analysis_material(messages)
                result = {"stats": stats, "coverage": coverage, "content": prompt}
            elif self.path == "/api/photos":
                folder = data.get("folder")
                if not isinstance(folder, str) or not folder.strip():
                    raise ValueError("请填写照片文件夹的绝对路径")
                if not Path(folder).is_absolute():
                    raise ValueError("请使用绝对路径")
                events, skipped = scan_photos(folder)
                result = {"events": events, "skipped": skipped, "ics": calendar(events)}
            elif self.path in ("/api/import", "/api/export", "/api/analyze"):
                if self.path == "/api/import":
                    original = data.get("raw", data.get("messages"))
                    imported = import_records(original, data.get("format", "auto"), data.get("contact", ""), data.get("timezone", "+08:00"))
                    messages = imported["messages"]
                    result = {**imported, "tree": tree(messages), "stats": statistics(messages), "events": chat_photo_events(messages)}
                    if data.get("save") is not False:
                        result["archive"] = self.server.store.save(messages, data.get("label", "聊天档案"), original,
                                                                 {"source": imported["source"], "warnings": imported["warnings"]})
                elif self.path == "/api/export":
                    messages = normalize(data.get("messages"))
                    fmt = data.get("format")
                    if fmt == "markdown":
                        content = markdown(messages)
                    elif fmt == "json":
                        content = json.dumps({"messages": messages}, ensure_ascii=False, indent=2)
                    elif fmt == "ics":
                        content = calendar(chat_photo_events(messages))
                    else:
                        raise ValueError("不支持的导出格式")
                    result = {"content": content}
                else:
                    messages = normalize(data.get("messages"))
                    model = data.get("model")
                    if not isinstance(model, str) or not model.strip():
                        raise ValueError("请填写已安装的 Ollama 模型名")
                    # UI intentionally uses only the local model endpoint.
                    result = {"content": analyze(messages, model.strip())}
            else:
                return self.reply(404, {"error": "不存在的接口"})
            self.reply(200, result)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception:
            self.reply(500, {"error": "处理失败，请检查文件格式或本地模型服务"})


class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # Avoid reverse DNS lookup during local startup.
        TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def make_server(port=8765, data_dir=None):
    server = LocalServer(("127.0.0.1", port), Handler)
    server.token = secrets.token_urlsafe(32)
    server.daemon_threads = True
    server.store = ArchiveStore(data_dir)
    server.exporter = WindowsExporter(server.store)
    return server


def main(argv=None):
    configure_console()
    parser = argparse.ArgumentParser(description="启动微信记忆本地应用")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--data-dir", help="本地档案目录，默认 ~/Documents/WeChatMemory")
    args = parser.parse_args(argv)
    try:
        server = make_server(args.port, args.data_dir)
    except OSError as exc:
        parser.exit(1, f"无法启动：{exc}；可以使用 --port 指定其他端口。\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"微信记忆已启动：{url}\n关闭服务请按 Ctrl+C。", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

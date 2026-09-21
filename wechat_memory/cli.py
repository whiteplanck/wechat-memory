import argparse
import json
from pathlib import Path
import sys
from urllib.error import URLError

from .core import normalize, tree, statistics, markdown, calendar, chat_photo_events
from .photos import scan_photos
from .providers import analyze


def write(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Avoid silently replacing an existing archive or report.
    with target.open("x", encoding="utf-8", newline="") as output:
        output.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description="微信聊天档案核心：导出、目录、统计、AI 与照片日历")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "tree", "stats", "calendar", "analyze"):
        p = sub.add_parser(command)
        p.add_argument("input", help="标准消息 JSON 文件")
        p.add_argument("--output", required=True)
        p.add_argument("--conversation")
        p.add_argument("--day", help="按消息原始时区的 YYYY-MM-DD 过滤")
        if command == "export":
            p.add_argument("--format", choices=("json", "markdown"), default="markdown")
        if command == "analyze":
            p.add_argument("--model", required=True)
            p.add_argument("--endpoint", default="http://127.0.0.1:11434")
            p.add_argument("--allow-remote", action="store_true")
    p = sub.add_parser("photos")
    p.add_argument("folder")
    p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if Path(args.output).exists():
            raise ValueError("输出文件已存在，请更换文件名")
        if args.command == "photos":
            events, skipped = scan_photos(args.folder)
            content = calendar(events)
            print(json.dumps({"events": len(events), "skipped": skipped}, ensure_ascii=False), file=sys.stderr)
        else:
            messages = normalize(json.loads(Path(args.input).read_text(encoding="utf-8")))
            if args.conversation:
                messages = [m for m in messages if m["conversation"] == args.conversation]
            if args.day:
                from datetime import date
                date.fromisoformat(args.day)
                messages = [m for m in messages if m["timestamp"][:10] == args.day]
            if args.command == "export":
                content = markdown(messages) if args.format == "markdown" else json.dumps({"messages": messages}, ensure_ascii=False, indent=2)
            elif args.command == "tree":
                content = json.dumps(tree(messages), ensure_ascii=False, indent=2)
            elif args.command == "stats":
                content = json.dumps(statistics(messages), ensure_ascii=False, indent=2)
            elif args.command == "calendar":
                content = calendar(chat_photo_events(messages))
            else:
                content = analyze(messages, args.model, args.endpoint, args.allow_remote)
        write(args.output, content)
        print(f"已生成：{args.output}")
        return 0
    except (OSError, ValueError, URLError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

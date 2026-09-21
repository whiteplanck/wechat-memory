"""Windows WeFlow bridge. Only selected sessions are exported; no AI commands."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from threading import Lock
import uuid

from .importers import import_records
from .storage import ArchiveStore

WEFLOW_VERSION = "1.7.0"
MIN_NODE = (22, 13, 0)
MAX_EXPORT_BYTES = 256 * 1024 * 1024


def tools_directory():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "WeChatMemory" / "tools" / "weflow"


def safe_session_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]{0,199}", value))


class WindowsExporter:
    def __init__(self, store, tool_dir=None):
        self.store = store
        self.tool_dir = Path(tool_dir) if tool_dir else tools_directory()
        self.entry = self.tool_dir / "node_modules" / "weflow-cli" / "cli.cjs"
        self.sessions = {}
        self.lock = Lock()

    @staticmethod
    def require_windows():
        if sys.platform != "win32":
            raise ValueError("微信直接提取目前仅支持 Windows。请把应用放到已登录微信的 Windows 电脑上运行。")

    @staticmethod
    def environment():
        env = os.environ.copy()
        # The upstream tool searches PATH for a Python with sqlcipher3 installed.
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_COLOR"] = "1"
        return env

    def runtime(self):
        self.require_windows()
        node = shutil.which("node")
        if not node:
            raise ValueError("未找到 Node.js；请安装 Node.js 22.13+ 后重新运行安装脚本。")
        version = self._run([node, "--version"], 15).strip().lstrip("v")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match or tuple(map(int, match.groups())) < MIN_NODE:
            raise ValueError("需要 Node.js 22.13 或以上版本。")
        return node, version

    def command(self):
        node, _ = self.runtime()
        try:
            metadata = json.loads((self.entry.parent / "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("提取组件未安装，请先运行 setup-windows.cmd。") from exc
        if not self.entry.is_file() or metadata.get("version") != WEFLOW_VERSION:
            raise ValueError(f"需要已核对的 weflow-cli {WEFLOW_VERSION}，请重新运行 setup-windows.cmd。")
        # Execute JS through node.exe directly, never through a .cmd shell shim.
        return [node, str(self.entry)]

    def _run(self, command, timeout):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", env=self.environment(), creationflags=flags)
            try:
                stdout, _stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                else:
                    proc.kill()
                proc.communicate(timeout=15)
                raise ValueError("提取工具运行超时；已停止本次任务。请先在初始化窗口确认微信数据可访问。")
        except OSError as exc:
            raise ValueError("无法启动提取组件，请重新运行安装脚本。") from exc
        if proc.returncode:
            # Never reflect raw process output: it can contain account data/keys.
            raise ValueError("提取工具执行失败。请先登录 Windows 微信，运行 init-wechat-windows.cmd 完成初始化，再检测环境。")
        return stdout

    def invoke(self, args, timeout=120):
        output = self._run(self.command() + args, timeout)
        try:
            result = json.loads(output)
        except ValueError as exc:
            raise ValueError("提取工具未返回有效 JSON；未将控制台输出写入档案。请检查组件版本。") from exc
        if not isinstance(result, dict) or result.get("success") is not True:
            raise ValueError("提取工具未报告成功，请运行初始化脚本后重试。")
        return result

    def status(self):
        result = {"supported": sys.platform == "win32", "provider": "weflow-cli", "required_version": WEFLOW_VERSION,
                  "ready": False, "initialized": False, "installed": False}
        if not result["supported"]:
            return {**result, "message": "请在已登录微信的 Windows 10/11 x64 电脑上运行此应用。"}
        try:
            _, result["node_version"] = self.runtime()
            self.command()
            result["installed"] = True
            check = self.invoke(["check", "--json"])
            required = check.get("dependencies", {}).get("required", {})
            result["missing_dependencies"] = [key for key in ("sqlcipher3", "html2text", "zstandard", "cryptography") if required.get(key) is not True]
            result["initialized"] = check.get("configuration", {}).get("initialized") is True
            result["ready"] = result["initialized"] and not result["missing_dependencies"]
            result["message"] = "环境已就绪，请读取会话以验证数据访问。" if result["ready"] else "请先运行安装及初始化脚本，再重新检测。"
        except ValueError as exc:
            result["message"] = str(exc)
        return result

    def list_sessions(self, keyword=""):
        self.require_windows()
        if not isinstance(keyword, str) or len(keyword) > 100 or "\x00" in keyword:
            raise ValueError("会话关键词必须不超过 100 字")
        if not self.lock.acquire(blocking=False):
            raise ValueError("已有提取任务正在运行，请完成后重试。")
        try:
            args = ["sessions", "--json", "--limit", "1000"]
            if keyword:
                args += ["--keyword", keyword]
            data = self.invoke(args)
            rows = data.get("sessions")
            if not isinstance(rows, list):
                raise ValueError("提取工具返回了无效的会话列表")
            self.sessions = {}
            for row in rows:
                if not isinstance(row, dict) or not safe_session_id(row.get("username")):
                    raise ValueError("会话 ID 格式异常，已停止读取。")
                identity = row["username"]
                self.sessions[identity] = {"id": identity, "name": str(row.get("displayName") or identity)}
            return {"sessions": list(self.sessions.values()), "limit": 1000,
                    "message": "列表最多显示 1000 个会话，可使用关键词筛选。空列表不代表数据已成功读取。"}
        finally:
            self.lock.release()

    def export(self, identity):
        self.require_windows()
        if not safe_session_id(identity) or identity not in self.sessions:
            raise ValueError("请先读取会话，并从列表中选择要提取的会话。")
        if not self.lock.acquire(blocking=False):
            raise ValueError("已有提取任务正在运行，请完成后重试。")
        raw_dir = None
        try:
            name = self.sessions[identity]["name"]
            # Resolve the tool before creating any output directory.
            self.command()
            raw_dir = self.store.directory / "raw" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10])
            raw_dir.mkdir(parents=True, mode=0o700)
            result = self.invoke(["export", identity, "json", "--output", str(raw_dir), "--limit", "0",
                                  "--contract", "weflow-v1", "--json", "--non-interactive"], timeout=600)
            returned = result.get("path")
            if not isinstance(returned, str):
                raise ValueError("提取工具没有返回输出文件")
            path = Path(returned).resolve()
            if not path.is_relative_to(raw_dir.resolve()) or path.suffix.lower() != ".json" or not path.is_file():
                raise ValueError("输出文件不在本次提取目录内，已拒绝读取")
            if path.stat().st_size > MAX_EXPORT_BYTES:
                raise ValueError("原始 JSON 已保存，但超过当前 256 MB 归档上限，请按范围拆分")
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict) or raw.get("schema") != "weflow-message/v1":
                raise ValueError("输出不符合约定的 weflow-message/v1 格式")
            imported = import_records(raw, "weflow-cli", name)
            count = len(imported["messages"])
            coverage = raw.get("coverage", {})
            if not count or result.get("count") != count or coverage.get("returned") != count or coverage.get("requestedLimit") != 0 or coverage.get("mayHaveMore") is not False:
                raise ValueError("提取条数或覆盖范围校验失败；原始输出已保留，未标记为归档成功")
            warnings = imported["warnings"] + ["提取范围为这台 Windows 电脑上可读取的数据，不保证包含手机的全部历史记录。", "JSON 提取不保证包含照片、视频、语音原文件；请另行核对附件。"]
            archive = self.store.save(imported["messages"], name, raw, {"source": "weflow-cli", "warnings": warnings, "raw_path": str(path)})
            return {"archive": archive, "count": count, "raw_path": str(path), "warnings": warnings}
        except (ValueError, OSError, TypeError) as exc:
            if raw_dir:
                raise ValueError(f"{exc}。本次原始输出目录：{raw_dir}") from exc
            raise
        finally:
            self.lock.release()

    def setup(self):
        node, _ = self.runtime()
        npm_shim = shutil.which("npm")
        npm_cli = Path(npm_shim).parent / "node_modules" / "npm" / "bin" / "npm-cli.js" if npm_shim else None
        if not npm_cli or not npm_cli.is_file():
            raise ValueError("未找到 Node.js 自带的 npm-cli.js，请使用 Node.js 官方 Windows 安装程序安装。")
        self.tool_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([node, str(npm_cli), "install", "--prefix", str(self.tool_dir), "--no-audit", "--no-fund", f"weflow-cli@{WEFLOW_VERSION}"], check=True, env=self.environment())
        subprocess.run([sys.executable, "-m", "pip", "install", "sqlcipher3==0.6.2", "pymem", "cryptography", "html2text", "zstandard", "numpy", "pycryptodome"], check=True)
        print("安装完成。请登录微信，然后运行 init-wechat-windows.cmd。")

    def initialize(self, data_path=None):
        command = self.command() + ["init"]
        if data_path:
            command += ["--path", data_path]
        # Upstream init requires a real interactive console. No output capture.
        subprocess.run(command, check=True, env=self.environment())


def main():
    parser = argparse.ArgumentParser(description="Windows 微信提取组件管理")
    parser.add_argument("action", choices=("setup", "init", "check"))
    parser.add_argument("--path", help="初始化时指定微信数据目录")
    args = parser.parse_args()
    exporter = WindowsExporter(ArchiveStore())
    try:
        if args.action == "setup":
            exporter.setup()
        elif args.action == "init":
            exporter.initialize(args.path)
        else:
            print(json.dumps(exporter.status(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"操作未完成：{exc}\n")


if __name__ == "__main__":
    main()

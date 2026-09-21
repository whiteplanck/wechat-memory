"""Assemble isolated runtimes; compile with installer/windows.iss afterwards."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen
import zipfile

PYTHON_VERSION = "3.13.15"
PYTHON_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"


def main():
    if sys.platform != "win32" or sys.version_info[:2] != (3, 13):
        raise SystemExit("Build requires Windows x64 and Python 3.13")
    from wechat_memory.windows_exporter import tools_directory, WEFLOW_VERSION
    root = Path(__file__).resolve().parents[1]
    target = root / "build" / "windows-app"
    target.mkdir(parents=True, exist_ok=False)
    runtime = target / "runtime" / "python"
    runtime.mkdir(parents=True)
    download = root / "build" / "python-embed.zip"
    with urlopen(f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip", timeout=90) as response:
        archive = response.read(30 * 1024 * 1024)
    if hashlib.sha256(archive).hexdigest() != PYTHON_SHA256:
        raise SystemExit("Embedded Python SHA256 mismatch")
    download.write_bytes(archive)
    with zipfile.ZipFile(download) as package:
        package.extractall(runtime)
    (runtime / "python313._pth").write_text("python313.zip\n.\nLib\\site-packages\n..\\..\nimport site\n", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary=:all:", "--target", str(runtime / "Lib" / "site-packages"),
                    "Pillow>=11,<13", "sqlcipher3==0.6.2", "pymem", "cryptography", "html2text", "zstandard", "numpy", "pycryptodome"], check=True)
    shutil.copytree(root / "wechat_memory", target / "wechat_memory", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(root / "docs", target / "docs")
    shutil.copytree(root / "examples", target / "examples")
    shutil.copy2(root / "README.md", target / "README.md")
    source_tool = tools_directory()
    metadata = json.loads((source_tool / "node_modules" / "weflow-cli" / "package.json").read_text(encoding="utf-8"))
    if metadata["version"] != WEFLOW_VERSION:
        raise SystemExit("Wrong extraction component version")
    shutil.copytree(source_tool, target / "tools" / "weflow")
    node = Path(shutil.which("node"))
    bundled_node = target / "runtime" / "node"
    bundled_node.mkdir()
    shutil.copy2(node, bundled_node / "node.exe")
    shutil.copy2(node.parent / "LICENSE", bundled_node / "LICENSE")
    (target / "WINDOWS-INSTALL.txt").write_text(
        "微信记忆 / Windows 10、11 x64\n\n"
        "此安装包内置 Python、Node.js 和提取组件，无需另外安装运行环境。\n"
        "1. 打开桌面 WeChat Memory 快捷方式，应用会打开本地网页。\n"
        "2. 首次提取：登录自己的微信，在开始菜单打开 Initialize WeChat，按提示初始化。\n"
        "   如果提示权限不足，可右键该快捷方式，以管理员身份运行。\n"
        "3. 网页内选择 Windows 提取，检测环境、选择会话，再提取保存。\n"
        "4. 使用期间请保留控制台窗口；关闭该窗口即停止本地服务。\n\n"
        "聊天默认保存到用户目录 Documents\\WeChatMemory。卸载不删除聊天或提取工具的用户配置。\n"
        "AI 分析默认本地，可手动选 DeepSeek 并粘贴 Key；每次云端发送需确认。\n"
        "此包未购买代码签名证书，Windows 可能提示未知发布者。请核对来源和 SHA256，不要关闭安全软件。\n"
        "真实微信账号提取仍需本机验证，不保证手机全部历史及媒体附件。\n", encoding="utf-8-sig")
    versions = {"python": PYTHON_VERSION, "python_archive_sha256": PYTHON_SHA256, "weflow-cli": WEFLOW_VERSION,
                "node": subprocess.check_output([str(node), "--version"], text=True).strip(),
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()}
    (target / "BUILD-INFO.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
    subprocess.run([str(runtime / "python.exe"), "-c", "import sys; print(sys.path); import wechat_memory, PIL, sqlcipher3; print(wechat_memory.__file__)"], cwd=root.parent, check=True)
    manifest = [hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(target).as_posix()
                for path in sorted(target.rglob("*")) if path.is_file()]
    (target / "SHA256SUMS.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()

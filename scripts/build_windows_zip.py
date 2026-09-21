"""Build a source launcher kit; never include archives, configs or dependencies."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def build(output):
    root = Path(__file__).resolve().parents[1]
    names = ["README.md", "pyproject.toml", "setup-windows.cmd", "init-wechat-windows.cmd", "start-windows.cmd", "docs/windows.md", "docs/reference-notes.md", "examples/demo.json"]
    files = [root / name for name in names]
    files += sorted((root / "wechat_memory").glob("*.py"))
    files += sorted(p for p in (root / "wechat_memory" / "web").iterdir() if p.suffix in {".html", ".js", ".css"})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            if path.suffix == ".cmd":
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            archive.writestr("WeChatMemory/" + relative, data)
            manifest.append(hashlib.sha256(data).hexdigest() + "  " + relative)
        archive.writestr("WeChatMemory/SHA256SUMS.txt", "\n".join(manifest) + "\n")
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/WeChatMemory-Windows.zip")
    build(parser.parse_args().output)

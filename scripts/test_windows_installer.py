"""CI uses only synthetic records, never a real WeChat login or API key."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import Request, urlopen


def main():
    root = Path(__file__).resolve().parents[1]
    setup = root / "dist" / "WeChatMemory-Setup-0.2.0-x64.exe"
    with tempfile.TemporaryDirectory(prefix="wechat-installer-test-") as temp:
        base = Path(temp)
        install = base / "Installed App"
        data = base / "User Data"
        subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=", f"/DIR={install}"], check=True, timeout=180)
        python = install / "runtime" / "python" / "python.exe"
        # Remove build-machine Node and Python from PATH. No system runtimes needed.
        env = os.environ.copy()
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        env["PYTHONIOENCODING"] = "utf-8"
        assert (install / "wechat_memory" / "__init__.py").is_file(), "Application package missing"
        print((install / "runtime" / "python" / "python313._pth").read_text(encoding="utf-8"), flush=True)
        subprocess.run([str(python), "-c", "import sys; print(sys.path)"], cwd=base, env=env, check=True)
        check = subprocess.check_output([str(python), "-m", "wechat_memory.windows_exporter", "check"], cwd=base, env=env, text=True, encoding="utf-8", timeout=150)
        status = json.loads(check)
        assert status["installed"] and not status.get("missing_dependencies", ["missing"]), status
        process = subprocess.Popen([str(python), "-u", "-m", "wechat_memory.server", "--no-browser", "--port", "0", "--data-dir", str(data)],
                                   cwd=base, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    line = pool.submit(process.stdout.readline).result(timeout=30)
                except concurrent.futures.TimeoutError:
                    process.kill()
                    raise
            origin = re.search(r"http://127\.0\.0\.1:\d+", line).group(0)
            with urlopen(origin, timeout=10) as response:
                html = response.read().decode("utf-8")
            token = re.search(r'name="session-token" content="([^"]+)"', html).group(1)
            for asset in ("app.js", "style.css"):
                with urlopen(origin + "/" + asset, timeout=10) as response:
                    assert len(response.read()) > 100
            demo = json.loads((install / "examples" / "demo.json").read_text(encoding="utf-8"))
            req = Request(origin + "/api/import", data=json.dumps({"messages": demo["messages"], "label": "installer synthetic test"}).encode(),
                          headers={"Content-Type": "application/json", "X-Session-Token": token, "Origin": origin})
            with urlopen(req, timeout=10) as response:
                result = json.load(response)
            saved = Path(result["archive"]["path"])
            assert saved.is_file() and saved.is_relative_to(data)
        finally:
            process.terminate()
            process.communicate(timeout=15)
        subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True, timeout=180)
        assert saved.is_file(), "Uninstall must preserve archives"
        assert not python.exists(), "Bundled runtime was not uninstalled"
        print("PASS: silent install, bundled Python/Node, extraction dependencies, UI assets, synthetic archive, uninstall preserves data")


if __name__ == "__main__":
    main()

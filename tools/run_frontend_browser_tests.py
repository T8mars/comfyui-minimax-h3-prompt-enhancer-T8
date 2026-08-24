from __future__ import annotations

import argparse
import functools
import http.server
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "frontend" / "browser_harness.html"
PERFORMANCE_HARNESS = ROOT / "tests" / "frontend" / "performance_harness.html"


def browser_path(explicit: str = "") -> str:
    candidates = [
        explicit,
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
        shutil.which("chrome") or "",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for value in candidates:
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    raise RuntimeError("Chrome/Chromium/Edge was not found for the frontend browser gate.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight real-browser frontend contract tests.")
    parser.add_argument("--browser", default="")
    args = parser.parse_args()
    executable = browser_path(args.browser)
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
        }

        def log_message(self, _format, *args):
            return

        def do_GET(self):
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}/tests/frontend"
    def run_page(filename: str, *, virtual_time: bool):
        with tempfile.TemporaryDirectory(prefix="t8-browser-test-") as profile:
            command = [
                executable,
                "--headless=new",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--no-first-run",
                f"--user-data-dir={profile}",
                "--dump-dom",
            ]
            if virtual_time:
                command.insert(-2, "--virtual-time-budget=2500")
            command.append(f"{base_url}/{filename}")
            return subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
    try:
        completed = run_page(HARNESS.name, virtual_time=True)
        performance = run_page(PERFORMANCE_HARNESS.name, virtual_time=False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    if completed.returncode != 0 or 'data-status="pass"' not in completed.stdout:
        detail = completed.stdout[-4000:] or completed.stderr[-4000:]
        raise RuntimeError(f"Frontend browser contracts failed (exit={completed.returncode}):\n{detail}")
    if performance.returncode != 0 or 'data-status="pass"' not in performance.stdout:
        detail = performance.stdout[-4000:] or performance.stderr[-4000:]
        raise RuntimeError(f"Frontend performance baseline failed (exit={performance.returncode}):\n{detail}")
    metrics = re.search(r"PASS\s*(\{[^<]+\})", performance.stdout)
    suffix = f" {metrics.group(1)}" if metrics else ""
    print(f"Frontend browser contracts: PASS{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

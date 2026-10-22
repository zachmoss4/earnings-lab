#!/usr/bin/env python3
"""Bootstrap a local environment and launch the loopback-only application."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Launch Earnings Lab on your computer.")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit("Install Python 3.12 or newer, then run this launcher again.")
    url = f"http://127.0.0.1:{args.port}"
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
            import json
            health = json.load(response)
            if health.get("local_only") and health.get("version") == "0.1.3":
                print("Earnings Lab is already running at", url)
                if not args.no_browser:
                    webbrowser.open(url)
                return
    except Exception:
        pass
    env_path = ROOT / ".venv"
    py = env_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        print("Preparing the local Python environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_path)
    installed = subprocess.run([str(py), "-c", "import numpy,pandas,yfinance"], capture_output=True).returncode == 0
    expected = hashlib.sha256((ROOT / "requirements-tested.txt").read_bytes()).hexdigest()
    stamp = env_path / "earnings-lab-requirements.sha256"
    if not installed or not stamp.exists() or stamp.read_text().strip() != expected:
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
        stamp.write_text(expected)
    if not (ROOT / "dist/index.html").exists():
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("This source checkout needs Node.js to build the interface. Install Node 22.12+ or use the prepared GitHub release ZIP.")
        subprocess.run([npm, "ci"], cwd=ROOT, check=True)
        subprocess.run([npm, "run", "build"], cwd=ROOT, check=True)
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print("Keep this window open while using Earnings Lab. Ctrl+C stops the app.", flush=True)
    try:
        subprocess.run([str(py), "-m", "earnings_lab.server", "--port", str(args.port)], cwd=ROOT, check=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


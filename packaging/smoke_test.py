"""Launch a packaged build and verify it serves the Streamlit health endpoint."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def wait_for_health(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200 and response.read().decode().strip() == "ok":
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(1.0)
    return False


def kill_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", help="Path to the packaged launcher executable")
    parser.add_argument("--port", type=int, default=8617)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()

    binary = Path(args.binary)
    if not binary.is_file():
        print(f"smoke test: binary not found: {binary}")
        return 1

    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(args.port)
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    popen_kwargs = {"env": env, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True}
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen([str(binary)], **popen_kwargs)
    try:
        healthy = wait_for_health(args.port, args.timeout)
        if healthy:
            print(f"smoke test OK: {binary.name} served /_stcore/health on port {args.port}")
            return 0
        print(f"smoke test FAILED: no healthy response within {args.timeout:.0f}s")
        kill_tree(process)
        output = process.stdout.read() if process.stdout else ""
        if output:
            print("---- launcher output ----")
            print(output[-4000:])
        return 1
    finally:
        kill_tree(process)


if __name__ == "__main__":
    sys.exit(main())

"""Entry point for the packaged app: boots Streamlit with consumer-friendly defaults.

Used both by the PyInstaller build (frozen) and for local testing:
    python packaging/launcher.py
    python packaging/launcher.py --self-check
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

APP_NAME = "Icarus Easy Mod"
DEFAULT_PORT = 8501

THEME_ENV = {
    "STREAMLIT_THEME_BASE": "dark",
    "STREAMLIT_THEME_PRIMARY_COLOR": "#f2b544",
    "STREAMLIT_THEME_BACKGROUND_COLOR": "#0d1117",
    "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR": "#151a22",
    "STREAMLIT_THEME_TEXT_COLOR": "#e8e6e1",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    "STREAMLIT_CLIENT_TOOLBAR_MODE": "minimal",
    "STREAMLIT_GLOBAL_DEVELOPMENT_MODE": "false",
    "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
}


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def app_script() -> Path:
    base = resource_dir()
    for candidate in (base / "app" / "app.py", base / "app.py"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find app.py next to {base}")


def free_port(start: int, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def configure_environment(port: int) -> None:
    for key, value in THEME_ENV.items():
        os.environ.setdefault(key, value)
    os.environ.setdefault("STREAMLIT_SERVER_PORT", str(port))
    os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")
    os.environ.setdefault("STREAMLIT_BROWSER_SERVER_ADDRESS", "127.0.0.1")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "false")


def set_console_title() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(f"{APP_NAME} - close this window to quit")
        except Exception:
            pass


def banner(port: int) -> None:
    print("=" * 62)
    print(f"  {APP_NAME}")
    print("=" * 62)
    print(f"  The app is opening in your browser at http://localhost:{port}")
    print("  Keep this window open while you use the app.")
    print("  Close this window (or press Ctrl+C) to stop it.")
    print("=" * 62)


def self_check() -> int:
    """Verify the bundled environment can do its core jobs. Used by build scripts."""
    try:
        import tempfile

        import paramiko  # noqa: F401  (SFTP + cryptography stack)
        import repak

        from icarus_manager import catalog  # noqa: F401  (requests + bs4 stack)
        from icarus_manager.uepak import PakFile, PakWriter

        with tempfile.TemporaryDirectory() as tmp:
            pak_path = Path(tmp) / "SelfCheck_P.pak"
            writer = PakWriter(pak_path)
            writer.add_file("Data/SelfCheck.json", b'{"Rows": []}')
            writer.save()

            reader = repak.PakBuilder().reader(str(pak_path))
            try:
                data = reader.get("Data/SelfCheck.json")
            finally:
                reader.close()
            assert data == b'{"Rows": []}', f"repak returned {data!r}"
            assert PakFile(pak_path).read_file("Data/SelfCheck.json") == b'{"Rows": []}'

        print("self-check OK: repak, uepak, paramiko and catalog imports all work")
        return 0
    except Exception as exc:
        print(f"self-check FAILED: {exc!r}")
        return 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    port = int(os.environ.get("STREAMLIT_SERVER_PORT") or 0) or free_port(DEFAULT_PORT)
    configure_environment(port)
    set_console_title()
    banner(port)

    import streamlit.web.bootstrap as bootstrap

    flag_options = {
        "server.port": port,
        "server.address": "127.0.0.1",
        "server.headless": False,
        "browser.serverAddress": "127.0.0.1",
        "global.developmentMode": False,
    }
    try:
        bootstrap.load_config_options(flag_options=flag_options)
        bootstrap.run(str(app_script()), False, [], flag_options)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print()
        print(f"{APP_NAME} failed to start: {exc!r}")
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            input("Press Enter to close this window...")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

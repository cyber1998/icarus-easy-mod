"""Persist the connection profile locally. Passwords are never stored."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".icarus_server_mod_manager"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROFILE_FIELDS = ("protocol", "host", "port", "username", "remote_path", "local_mods_path")


def load_profile() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in PROFILE_FIELDS if key in data}


def save_profile(profile: dict[str, Any]) -> None:
    clean = {key: profile[key] for key in PROFILE_FIELDS if key in profile}
    existing = load_profile()
    existing.update(clean)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass

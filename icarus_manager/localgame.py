"""Install copies of mods into the local (client) Icarus game folder."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Optional

GAME_REL = Path("steamapps") / "common" / "Icarus" / "Icarus" / "Content" / "Paks"


class LocalGameError(Exception):
    """Raised when the local game folder cannot be used."""


def _windows_steam_root() -> Optional[Path]:
    try:
        import winreg
    except ImportError:
        return None
    for hive, key_name in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, "SteamPath" if hive == winreg.HKEY_CURRENT_USER else "InstallPath")
                return Path(value)
        except OSError:
            continue
    return None


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == "win32":
        registry_root = _windows_steam_root()
        if registry_root:
            roots.append(registry_root)
        roots.append(Path("C:/Program Files (x86)/Steam"))
        roots.append(Path("C:/Program Files/Steam"))
    elif sys.platform == "darwin":
        roots.append(Path.home() / "Library/Application Support/Steam")
    else:
        roots.extend(
            [
                Path.home() / ".local/share/Steam",
                Path.home() / ".steam/steam",
                Path.home() / ".steam/root",
                Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam",
            ]
        )
    return roots


def _library_paths_from_vdf(vdf_path: Path) -> list[Path]:
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    paths: list[Path] = []
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        paths.append(Path(match.group(1).replace("\\\\", "\\")))
    for match in re.finditer(r'^\s*"\d+"\s+"([^"]+)"', text, re.MULTILINE):
        value = match.group(1)
        if "\\" in value or "/" in value:
            paths.append(Path(value.replace("\\\\", "\\")))
    return paths


def libraries() -> list[Path]:
    """Every Steam library root that exists on this machine."""
    libs: list[Path] = []
    seen: set[str] = set()
    for root in _steam_roots():
        if not root.is_dir():
            continue
        candidates = [root, *_library_paths_from_vdf(root / "steamapps" / "libraryfolders.vdf")]
        for library in candidates:
            key = str(library).lower()
            if key not in seen:
                seen.add(key)
                libs.append(library)
    return libs


def find_icarus_paks(library: Path) -> Optional[Path]:
    paks = library / GAME_REL
    return paks if paks.is_dir() else None


def detect_local_mods_path() -> Optional[Path]:
    """Look for the Icarus game folder inside the Steam libraries on this computer."""
    for library in libraries():
        paks = find_icarus_paks(library)
        if paks:
            return paks / "mods"
    return None


def normalize_local_path(raw: str) -> Optional[Path]:
    """Accept a path to the mods folder, Paks, Content, Icarus content folder or game root."""
    if not raw or not raw.strip():
        return None
    path = Path(raw.strip().strip('"').strip("'"))
    parts = [part.lower() for part in path.parts]
    if not parts:
        return None
    if parts[-1] == "mods":
        return path
    if parts[-1] == "paks":
        return path / "mods"
    if parts[-1] == "content":
        return path / "Paks" / "mods"
    if parts[-1] == "icarus":
        if (path / "Icarus").is_dir():
            return path / "Icarus" / "Content" / "Paks" / "mods"
        return path / "Content" / "Paks" / "mods"
    return None


def ensure_mods_dir(mods_path: Path) -> Path:
    """Create the mods folder if its parent Paks folder exists."""
    if mods_path.is_dir():
        return mods_path
    if mods_path.parent.is_dir():
        mods_path.mkdir(parents=True, exist_ok=True)
        return mods_path
    raise LocalGameError(
        f"Folder not found: {mods_path}. Point the app at your Icarus game folder "
        "(for example .../steamapps/common/Icarus/Icarus/Content/Paks/mods) or at its Paks folder."
    )


def copy_paks(paks: list[Path], mods_dir: Path) -> tuple[list[str], list[str]]:
    """Copy pak files into the local mods folder, replacing older versions."""
    copied: list[str] = []
    failures: list[str] = []
    try:
        mods_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [], [f"Could not create local folder {mods_dir}: {exc}"]
    for pak in paks:
        try:
            shutil.copy2(pak, mods_dir / pak.name)
            copied.append(pak.name)
        except OSError as exc:
            failures.append(f"{pak.name}: {exc}")
    return copied, failures

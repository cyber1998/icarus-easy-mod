"""Extract base game data tables from the local Icarus installation.

Icarus ships its data tables as JSON files inside the game's .pak files. EXMOD
mods only carry row-level deltas, so merging them requires the current base
tables; this module finds and extracts them using the repak library, which
handles Oodle-compressed paks the same way the community tooling does.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import repak
except ImportError:  # pragma: no cover
    repak = None

CACHE_DIR = Path.home() / ".icarus_easy_mod" / "base_data"
OODLE_CACHE_DIR = Path.home() / ".icarus_easy_mod" / "oodle"
OODLE_LIBRARY_NAMES = {
    "win32": "oo2core_9_win64.dll",
    "linux": "liboo2corelinux64.so.9",
    "darwin": "liboo2coremac64.2.9.10.dylib",
}


class GameDataError(Exception):
    """Raised when base game data cannot be located or read."""


@dataclass
class TableSource:
    target: str
    entry_path: str
    pak_path: Path


@dataclass
class BaseTables:
    sources: dict[str, TableSource] = field(default_factory=dict)
    tables: dict[str, dict] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


_scan_cache: dict[tuple, list[tuple[Path, str]]] = {}


def paks_dir_for(local_mods_path: Path | str) -> Path:
    return Path(local_mods_path).parent


def _looks_like_data_file(entry: str) -> bool:
    lowered = entry.lower()
    if not lowered.endswith(".json"):
        return False
    basename = posixpath.basename(lowered)
    return basename.startswith("d_") or "/data/" in lowered


def _paks_signature(paks_dir: Path) -> tuple:
    signature = []
    for pak_path in sorted(paks_dir.glob("*.pak")):
        try:
            stat = pak_path.stat()
            signature.append((pak_path.name, stat.st_mtime_ns, stat.st_size))
        except OSError:
            continue
    return tuple(signature)


def _find_oodle_dll(local_mods_path: Path) -> Optional[Path]:
    paks_dir = paks_dir_for(local_mods_path)
    inner_icarus = paks_dir.parent.parent
    candidates = list(inner_icarus.glob("Binaries/Win64/oo2core_*_win64.dll"))
    candidates += list(inner_icarus.glob("Binaries/Win64/oo2core_*.dll"))
    engine_dir = inner_icarus.parent / "Engine/Binaries/ThirdParty/Oodle"
    if engine_dir.is_dir():
        candidates += list(engine_dir.glob("**/oo2core_*_win64.dll"))
    return candidates[0] if candidates else None


def _oodle_library_name() -> str:
    if sys.platform == "win32":
        return OODLE_LIBRARY_NAMES["win32"]
    if sys.platform.startswith("linux"):
        return OODLE_LIBRARY_NAMES["linux"]
    return OODLE_LIBRARY_NAMES["darwin"]


def oodle_cache_target() -> Path:
    return OODLE_CACHE_DIR / _oodle_library_name()


def _prepare_oodle(local_mods_path: Path) -> None:
    """Point repak at the best available Oodle library.

    Order: an explicit user override, then the copy shipped inside the Icarus
    install, then our writable cache (where repak downloads it on first use;
    important for packaged builds installed to read-only locations).
    """
    if os.environ.get("REPAK_OODLE_PATH"):
        return
    dll = _find_oodle_dll(local_mods_path)
    if dll is not None:
        os.environ["REPAK_OODLE_PATH"] = str(dll)
        return
    target = oodle_cache_target()
    if target.is_file():
        os.environ["REPAK_OODLE_PATH"] = str(target)
        return
    try:
        OODLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["REPAK_OODLE_PATH"] = str(target)
    except OSError:
        pass


def _scan_paks(paks_dir: Path) -> list[tuple[Path, str]]:
    if repak is None:
        raise GameDataError(
            "The 'repak' package is required to read game data. Install it with: pip install repak"
        )
    signature = (str(paks_dir), _paks_signature(paks_dir))
    cached = _scan_cache.get(signature)
    if cached is not None:
        return cached
    entries: list[tuple[Path, str]] = []
    for pak_path in sorted(paks_dir.glob("*.pak")):
        try:
            reader = repak.PakBuilder().reader(str(pak_path))
        except Exception:
            continue
        try:
            for entry in reader.entries():
                if _looks_like_data_file(entry):
                    entries.append((pak_path, entry))
        finally:
            reader.close()
    _scan_cache.clear()
    _scan_cache[signature] = entries
    return entries


def _resolve_target(target: str, entries: list[tuple[Path, str]]) -> Optional[tuple[Path, str]]:
    normalized = target.replace("\\", "/").strip().lower()
    if not normalized:
        return None
    basename = posixpath.basename(normalized)
    if not basename:
        return None

    table_name = basename
    category_tokens: list[str] = []
    if "-d_" in basename:
        prefix, table_tail = basename.split("-d_", 1)
        table_name = "d_" + table_tail
        category_tokens = [token for token in prefix.split("-") if token]

    relative = normalized
    for prefix in ("icarus/content/", "/icarus/content/"):
        if relative.startswith(prefix):
            relative = relative[len(prefix) :]
            break

    matches = [(pak, entry) for pak, entry in entries if entry.lower().endswith(relative)]
    if not matches:
        matches = [
            (pak, entry)
            for pak, entry in entries
            if posixpath.basename(entry).lower() == table_name
        ]
    if not matches:
        return None
    if len(matches) > 1 and category_tokens:
        def score(item: tuple[Path, str]) -> tuple:
            directory = posixpath.dirname(item[1]).lower()
            hits = sum(1 for token in category_tokens if token in directory)
            return (-hits, len(item[1]), item[1])

        best = sorted(matches, key=score)[0]
        if any(token in posixpath.dirname(best[1]).lower() for token in category_tokens):
            return best
    matches.sort(key=lambda item: (len(item[1]), item[1]))
    return matches[0]


def _cache_file(pak_path: Path, entry: str) -> Path:
    try:
        mtime = pak_path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    key = hashlib.sha1(f"{pak_path}|{entry}|{mtime}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _load_table(pak_path: Path, entry: str) -> dict:
    cache_file = _cache_file(pak_path, entry)
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    reader = repak.PakBuilder().reader(str(pak_path))
    try:
        raw = reader.get(entry)
    except Exception as exc:
        message = str(exc)
        if "oodle" in message.lower():
            raise GameDataError(
                "This game pak uses Oodle compression and the Oodle runtime could not be "
                "loaded. repak normally downloads it automatically; alternatively set "
                "REPAK_OODLE_PATH to your game's oo2core DLL."
            ) from exc
        raise
    finally:
        reader.close()

    try:
        parsed = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise GameDataError(f"'{entry}' inside {pak_path.name} is not valid JSON.") from exc

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(parsed), encoding="utf-8")
    except OSError:
        pass
    return parsed


def extract_base_tables(local_mods_path: Path | str, targets: list[str]) -> BaseTables:
    """Locate and extract the base tables named by the mods' target files."""
    paks_dir = paks_dir_for(local_mods_path)
    if not paks_dir.is_dir():
        raise GameDataError(
            f"Game paks folder not found at {paks_dir}. Is Icarus installed on this computer?"
        )
    _prepare_oodle(Path(local_mods_path))
    try:
        entries = _scan_paks(paks_dir)
    except GameDataError:
        raise
    except Exception as exc:
        raise GameDataError(f"Could not read the game's pak files: {exc}") from exc
    if not entries:
        raise GameDataError(
            f"No readable data tables were found in {paks_dir}. "
            "Make sure Icarus is fully installed and updated."
        )

    result = BaseTables()
    for target in targets:
        found = _resolve_target(target, entries)
        if found is None:
            result.missing.append(target)
            continue
        pak_path, entry = found
        try:
            result.tables[target] = _load_table(pak_path, entry)
        except GameDataError:
            raise
        except Exception as exc:
            raise GameDataError(f"Could not read '{entry}' from {pak_path.name}: {exc}") from exc
        result.sources[target] = TableSource(target=target, entry_path=entry, pak_path=pak_path)
    return result

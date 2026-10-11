"""Parse Icarus EXMOD / EXMODZ mod packages.

An EXMOD is a JSON document describing row-level changes an author made to the
game's data tables. An EXMODZ is the same JSON inside a zip (or gzip, or raw).
Two generations of the format exist and are both handled here:

- Newer ("Rows" / "File_Items" / "CurrentFile" keys)
- Older ("Files" / "Items" / "FileName" keys)
"""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class ExModError(Exception):
    """Raised when an EXMOD/EXMODZ package cannot be parsed."""


@dataclass
class ExModChange:
    target_file: str
    item_count: int
    sample_names: list[str] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)


@dataclass
class ExModInfo:
    name: str
    author: str
    version: str
    description: str
    week: str
    changes: list[ExModChange] = field(default_factory=list)
    blueprint_assets: list[str] = field(default_factory=list)
    archive_format: str = ""

    @property
    def total_items(self) -> int:
        return sum(change.item_count for change in self.changes)


def load_exmod(path: str | Path) -> ExModInfo:
    """Load an .EXMODZ or .EXMOD file in any of its supported packings."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExModError(f"Could not read {path.name}: {exc}") from exc
    if raw[:2] == b"PK":
        info = _parse_zip(raw)
        info.archive_format = "zip"
        return info
    if raw[:2] == b"\x1f\x8b":
        try:
            payload = json.loads(gzip.decompress(raw))
        except (OSError, ValueError) as exc:
            raise ExModError("EXMODZ file contains invalid gzip data.") from exc
        info = parse_exmod(payload)
        info.archive_format = "gzip"
        return info
    try:
        info = parse_exmod(json.loads(raw))
    except ValueError as exc:
        raise ExModError("File is not a valid EXMOD package.") from exc
    info.archive_format = "json"
    return info


def _parse_zip(raw: bytes) -> ExModInfo:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ExModError("File is not a valid zip archive.") from exc
    with archive:
        members = archive.namelist()
        exmod_member = next((name for name in members if name.lower().endswith(".exmod")), None)
        if exmod_member is None:
            raise ExModError("No .EXMOD file was found inside the archive.")
        try:
            payload = json.loads(archive.read(exmod_member))
        except ValueError as exc:
            raise ExModError("The .EXMOD file inside the archive is not valid JSON.") from exc
    info = parse_exmod(payload)
    info.blueprint_assets = [
        name for name in members if name.lower().endswith((".uasset", ".uexp", ".ubulk"))
    ]
    return info


def parse_exmod(payload: dict) -> ExModInfo:
    if not isinstance(payload, dict):
        raise ExModError("EXMOD payload is not a JSON object.")
    changes: list[ExModChange] = []
    for row in payload.get("Rows") or []:
        if isinstance(row, dict):
            change = _change_from_row(
                row.get("CurrentFile") or row.get("FileName") or "",
                row.get("File_Items") or row.get("Items") or [],
            )
            if change is not None:
                changes.append(change)
    for row in payload.get("Files") or []:
        if isinstance(row, dict):
            change = _change_from_row(
                row.get("FileName") or row.get("CurrentFile") or "",
                row.get("Items") or row.get("File_Items") or [],
            )
            if change is not None:
                changes.append(change)
    return ExModInfo(
        name=str(payload.get("ModName") or payload.get("name") or "Unknown mod").strip(),
        author=str(payload.get("Author") or payload.get("author") or "").strip(),
        version=str(payload.get("Version") or payload.get("version") or "").strip(),
        description=str(payload.get("Description") or payload.get("description") or "").strip(),
        week=str(payload.get("week") or payload.get("Week") or "").strip(),
        changes=changes,
    )


def _change_from_row(target: object, items: object) -> Optional[ExModChange]:
    target_file = str(target).strip()
    if not target_file or not isinstance(items, list):
        return None
    item_dicts = [item for item in items if isinstance(item, dict)]
    sample_names = [str(item.get("Name")) for item in item_dicts if item.get("Name")][:5]
    return ExModChange(target_file, len(items), sample_names, item_dicts)


def describe(path: str | Path) -> Optional[str]:
    """A human-readable explanation for an EXMOD archive, or None if it is not one."""
    try:
        info = load_exmod(path)
    except (ExModError, OSError):
        return None
    label = f"'{info.name}'"
    if info.author:
        label += f" by {info.author}"
    if info.changes:
        targets = ", ".join(change.target_file for change in info.changes[:3])
        if len(info.changes) > 3:
            targets += f", and {len(info.changes) - 3} more"
        detail = (
            f"{label} is an EXMOD data mod that changes {len(info.changes)} game data "
            f"file(s) ({targets}) with {info.total_items} row change(s)."
        )
    else:
        detail = f"{label} is an EXMOD data mod."
    return (
        f"{detail} EXMODZ mods must be merged into a .pak with Icarus Mod Manager "
        "(Windows tool) before a dedicated server can load them."
    )

"""Convert EXMOD data mods into a loadable _P.pak.

Pipeline: extract the base tables the mods touch from the local game install,
merge the row deltas, and pack the merged tables into a new pak that can be
uploaded to the server and copied into the local game.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from icarus_manager import game_data
from icarus_manager.exmod import ExModInfo
from icarus_manager.exmod_merge import MergeReport, merge_mods
from icarus_manager.uepak import PakWriter


class ConversionError(Exception):
    """Raised when EXMOD mods cannot be converted into a pak."""


@dataclass
class ConversionResult:
    pak_path: Path
    report: MergeReport
    mods: list[ExModInfo] = field(default_factory=list)


def pak_filename(mods: list[ExModInfo]) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]", "", mods[0].name).strip().replace(" ", "_")
    base = base.strip("._") or "IcarusMod"
    if len(mods) > 1:
        base += "_Combined"
    return f"{base}_P.pak"


def convert_mods(
    mods: list[ExModInfo], local_mods_path: Path | str, workdir: Path | str
) -> ConversionResult:
    if not mods:
        raise ConversionError("No EXMOD mods were provided.")
    targets = sorted({change.target_file for mod in mods for change in mod.changes if change.target_file})
    if not targets:
        raise ConversionError("These mods do not contain any data changes to convert.")

    try:
        base = game_data.extract_base_tables(local_mods_path, targets)
    except game_data.GameDataError as exc:
        raise ConversionError(str(exc)) from exc
    if not base.tables:
        raise ConversionError(
            f"None of the {len(targets)} game files these mods change were found in "
            "your local Icarus install. Make sure the game is fully updated."
        )

    merged, report = merge_mods(mods, base.tables)
    report.missing = base.missing

    workdir_path = Path(workdir)
    workdir_path.mkdir(parents=True, exist_ok=True)
    out_path = workdir_path / pak_filename(mods)
    writer = PakWriter(out_path)
    for target, table in merged.items():
        source = base.sources[target]
        payload = json.dumps(table, indent=4).encode("utf-8")
        writer.add_file(source.entry_path, payload)
    writer.save()

    return ConversionResult(pak_path=out_path, report=report, mods=mods)

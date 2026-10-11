"""Merge EXMOD row changes onto base game data tables.

Follows Icarus Mod Manager semantics: each mod's changed row values are applied
on top of the base table (and previous mods); later mods win conflicts; rows
that do not exist in the base are appended.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from icarus_manager.exmod import ExModInfo


@dataclass
class FileMergeStats:
    target: str
    changed: int = 0
    added: int = 0


@dataclass
class MergeReport:
    files: dict[str, FileMergeStats] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def total_changed(self) -> int:
        return sum(stats.changed for stats in self.files.values())

    @property
    def total_added(self) -> int:
        return sum(stats.added for stats in self.files.values())


def _rows_of(table: object) -> list | None:
    if isinstance(table, list):
        return table
    if isinstance(table, dict) and isinstance(table.get("Rows"), list):
        return table["Rows"]
    return None


def merge_mods(
    mods: list[ExModInfo], base_tables: dict[str, dict]
) -> tuple[dict[str, dict], MergeReport]:
    """Apply each mod's changes to the base tables, returning the merged tables."""
    merged = dict(base_tables)
    report = MergeReport()
    touched_by: dict[str, dict[str, str]] = {}

    for mod in mods:
        for change in mod.changes:
            table = merged.get(change.target_file)
            if table is None:
                continue
            rows = _rows_of(table)
            if rows is None:
                continue

            stats = report.files.setdefault(change.target_file, FileMergeStats(change.target_file))
            index = {
                row.get("Name"): row
                for row in rows
                if isinstance(row, dict) and row.get("Name") is not None
            }
            lower_index = {str(name).lower(): row for name, row in index.items()}
            touched = touched_by.setdefault(change.target_file, {})

            for item in change.items:
                name = item.get("Name")
                row = index.get(name) if name is not None else None
                if row is None and name is not None:
                    row = lower_index.get(str(name).lower())
                if row is not None and name is not None:
                    previous = touched.get(str(name))
                    if previous is not None and previous != mod.name:
                        report.conflicts.append(
                            f"{change.target_file}: '{name}' changed by both "
                            f"'{previous}' and '{mod.name}' (later mod wins)"
                        )
                    touched[str(name)] = mod.name
                    for key, value in item.items():
                        row[key] = value
                    stats.changed += 1
                else:
                    new_row = dict(item)
                    rows.append(new_row)
                    if name is not None:
                        touched[str(name)] = mod.name
                    stats.added += 1

    return merged, report

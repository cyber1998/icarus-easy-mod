"""Unpack downloaded mod archives and locate loadable pak files."""

from __future__ import annotations

import zipfile
from pathlib import Path

from icarus_manager import exmod

PAK_EXTS = {".pak", ".ucas", ".utoc"}
MAX_MEMBER_COUNT = 5000
MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024


class ArchiveError(Exception):
    """Raised when a mod file cannot be prepared for upload."""


def unpack_to_paks(source: Path, workdir: Path) -> list[Path]:
    """Return the pak files contained in ``source``, extracting archives if needed."""
    suffix = source.suffix.lower()
    if suffix in PAK_EXTS:
        return [source]
    if suffix in (".zip", ".exmodz"):
        return _extract_zip_paks(source, workdir)
    if suffix == ".exmod":
        detail = exmod.describe(source)
        raise ArchiveError(detail or "This is a raw EXMOD file with no .pak inside.")
    if suffix == ".rar":
        raise ArchiveError(
            "RAR archives are not supported. Extract the .pak with 7-Zip or WinRAR "
            "and upload the .pak file directly."
        )
    raise ArchiveError(f"Unsupported file type '{source.suffix}'. Supported: .pak, .zip, .exmodz")


def _extract_zip_paks(zip_path: Path, workdir: Path) -> list[Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"{zip_path.name} is not a valid zip archive.") from exc

    extracted: list[Path] = []
    used_names: set[str] = set()
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_MEMBER_COUNT:
            raise ArchiveError("Archive contains too many files to process safely.")
        total = sum(i.file_size for i in infos)
        if total > MAX_TOTAL_SIZE:
            raise ArchiveError("Archive is too large to process safely.")
        if any(i.filename.lower().endswith(".exmod") for i in infos):
            detail = exmod.describe(zip_path)
            raise ArchiveError(
                detail
                or "This archive contains an EXMOD data mod, which must be merged into "
                "a .pak with Icarus Mod Manager before a dedicated server can use it."
            )
        for info in infos:
            name = info.filename.replace("\\", "/")
            member = Path(name)
            if member.is_absolute() or ".." in member.parts:
                continue
            if member.suffix.lower() == ".exmodz":
                raise ArchiveError(
                    "This archive contains EXMODZ files, which must be merged into a "
                    ".pak with Icarus Mod Manager before a dedicated server can use them."
                )
            if member.suffix.lower() not in PAK_EXTS:
                continue
            target_name = member.name
            counter = 1
            while target_name.lower() in used_names:
                counter += 1
                target_name = f"{member.stem}_{counter}{member.suffix}"
            used_names.add(target_name.lower())
            target = workdir / target_name
            with archive.open(info) as src, open(target, "wb") as dst:
                while chunk := src.read(1024 * 256):
                    dst.write(chunk)
            extracted.append(target)

    if not extracted:
        detail = exmod.describe(zip_path)
        if detail:
            raise ArchiveError(detail)
        raise ArchiveError("No .pak files were found inside the archive.")
    return extracted

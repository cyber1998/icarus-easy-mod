"""Minimal pure-Python reader/writer for Icarus .pak files (UE4 pak format v11).

The on-disk layout was cross-checked against NetPak by Crystal Ferrai
(https://github.com/CrystalFerrai/NetPak, Apache-2.0), the library used by the
Icarus community to build mod paks that the game loads directly.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = 0x5A6F12E1
FOOTER_SIZE = 221
PAK_VERSION = 11
ROOT_PREFIX = "../../../"
DEFAULT_MOUNT_POINT = ROOT_PREFIX + "Icarus/Content/"


class PakError(Exception):
    """Raised when a pak file cannot be read or written."""


def _make_crc_table() -> list[int]:
    table = []
    for index in range(256):
        value = index
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
        table.append(value)
    return table


_CRC_TABLE = _make_crc_table()


def ue_str_crc32(text: str) -> int:
    """UE4 FCrc::StrCrc32 (complemented CRC32, one 32-bit code unit per char)."""
    crc = 0xFFFFFFFF
    for char in text:
        code = ord(char)
        for shift in (0, 8, 16, 24):
            crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ ((code >> shift) & 0xFF)) & 0xFF]
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def _fnv64(text: str, seed: int = 0) -> int:
    """UE4 FFnv::MemFnv64 over the lower-cased string, salted with the path hash seed."""
    offset = 0xCBF29CE484222325
    prime = 0x100000001B3
    mask = 0xFFFFFFFFFFFFFFFF
    value = (offset + seed) & mask
    for char in text.lower():
        code = ord(char)
        value ^= code & 0xFF
        value = (value * prime) & mask
        value ^= (code >> 8) & 0xFF
        value = (value * prime) & mask
    return value


def _read_fstring(buf: bytes, pos: int) -> tuple[str, int]:
    (length,) = struct.unpack_from("<i", buf, pos)
    pos += 4
    if length == 0:
        return "", pos
    if length < 0:
        count = -length * 2
        data = buf[pos : pos + count]
        return data[:-2].decode("utf-16-le", errors="replace"), pos + count
    data = buf[pos : pos + length]
    return data[:-1].decode("ascii", errors="replace"), pos + length


def _write_fstring(value: str) -> bytes:
    try:
        data = value.encode("ascii")
        return struct.pack("<i", len(data) + 1) + data + b"\x00"
    except UnicodeEncodeError:
        data = value.encode("utf-16-le")
        return struct.pack("<i", -(len(data) // 2 + 1)) + data + b"\x00\x00"


@dataclass
class PakInfo:
    version: int
    index_offset: int
    index_size: int
    index_hash: bytes
    compression_methods: list[str] = field(default_factory=lambda: ["None"])


@dataclass
class PakEntry:
    path: str
    offset: int
    size: int
    compressed_size: int
    compression: str
    block_lengths: list[int] = field(default_factory=list)
    encrypted: bool = False

    @property
    def record_size(self) -> int:
        size = 53
        if self.compression != "None":
            size += 4 + 16 * len(self.block_lengths)
        return size


class PakFile:
    """Reads Icarus .pak files (uncompressed, zlib or gzip entries)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data = self.path.read_bytes()
        self.info = self._read_footer()
        self.mount_point = ""
        self.entries: dict[str, PakEntry] = {}
        self._read_index()

    def _read_footer(self) -> PakInfo:
        if len(self._data) < FOOTER_SIZE:
            raise PakError("File is too small to be a pak file.")
        footer = self._data[-FOOTER_SIZE:]
        magic = struct.unpack_from("<I", footer, 17)[0]
        if magic != MAGIC:
            raise PakError("Not an Icarus/UE4 pak file (bad magic).")
        encrypted = footer[16] != 0
        if encrypted:
            raise PakError("Encrypted pak files are not supported.")
        version = struct.unpack_from("<h", footer, 21)[0]
        if version != PAK_VERSION:
            raise PakError(f"Unsupported pak version {version} (expected {PAK_VERSION}).")
        index_offset, index_size = struct.unpack_from("<qq", footer, 25)
        index_hash = footer[41:61]
        methods = ["None"]
        for index in range(5):
            name = footer[61 + index * 32 : 61 + (index + 1) * 32].split(b"\x00")[0]
            if name:
                methods.append(name.decode("ascii", errors="replace"))
        return PakInfo(version, index_offset, index_size, index_hash, methods)

    def _read_index(self) -> None:
        buf = self._data
        pos = self.info.index_offset
        self.mount_point, pos = _read_fstring(buf, pos)
        (num_entries,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        (seed,) = struct.unpack_from("<Q", buf, pos)
        pos += 8
        self.path_hash_seed = seed
        (has_path_hash,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        if has_path_hash == 1:
            pos += 16 + 20
        (has_directory_index,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        if has_directory_index != 1:
            raise PakError("Pak has no directory index; cannot list contents.")
        directory_offset, _directory_size = struct.unpack_from("<qq", buf, pos)
        pos += 16 + 20
        (encoded_size,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        encoded = buf[pos : pos + encoded_size]
        pos += encoded_size
        (unencoded_count,) = struct.unpack_from("<i", buf, pos)
        if unencoded_count != 0:
            raise PakError("Pak uses an unsupported unencoded index format.")

        dpos = directory_offset
        (directory_count,) = struct.unpack_from("<i", buf, dpos)
        dpos += 4
        for _ in range(directory_count):
            directory, dpos = _read_fstring(buf, dpos)
            (file_count,) = struct.unpack_from("<i", buf, dpos)
            dpos += 4
            for _ in range(file_count):
                filename, dpos = _read_fstring(buf, dpos)
                (entry_offset,) = struct.unpack_from("<i", buf, dpos)
                dpos += 4
                if entry_offset == -0x80000000:
                    continue
                path = filename if directory in ("/", "") else directory + filename
                entry = self._decode_entry(encoded, entry_offset)
                entry.path = path
                self.entries[path] = entry

    def _decode_entry(self, encoded: bytes, offset: int) -> PakEntry:
        (flags,) = struct.unpack_from("<I", encoded, offset)
        pos = offset + 4
        method_index = (flags >> 23) & 0x3F
        if method_index >= len(self.info.compression_methods):
            raise PakError("Entry uses an unknown compression method.")
        compression = self.info.compression_methods[method_index]
        if (flags & 0x3F) == 0x3F:
            pos += 4
        if flags & (1 << 31):
            (entry_offset,) = struct.unpack_from("<I", encoded, pos)
            pos += 4
        else:
            (entry_offset,) = struct.unpack_from("<q", encoded, pos)
            pos += 8
        if not flags & (1 << 30):
            raise PakError("Entry is too large for this reader.")
        (uncompressed_size,) = struct.unpack_from("<I", encoded, pos)
        pos += 4
        encrypted = bool(flags & (1 << 22))
        block_lengths: list[int] = []
        compressed_size = uncompressed_size
        if compression != "None":
            if not flags & (1 << 29):
                raise PakError("Compressed entry is too large for this reader.")
            (compressed_size,) = struct.unpack_from("<I", encoded, pos)
            pos += 4
            block_count = (flags >> 6) & 0xFFFF
            if block_count >= 2:
                for _ in range(block_count):
                    (length,) = struct.unpack_from("<i", encoded, pos)
                    pos += 4
                    block_lengths.append(length)
            elif block_count == 1:
                block_lengths.append(compressed_size)
        return PakEntry(
            path="",
            offset=entry_offset,
            size=uncompressed_size,
            compressed_size=compressed_size,
            compression=compression,
            block_lengths=block_lengths,
            encrypted=encrypted,
        )

    def list_files(self) -> list[str]:
        return list(self.entries.keys())

    def read_file(self, path: str) -> bytes:
        entry = self.entries.get(path)
        if entry is None:
            raise PakError(f"'{path}' is not in the pak.")
        if entry.encrypted:
            raise PakError(f"'{path}' is encrypted.")
        start = entry.offset + entry.record_size
        if entry.compression == "None":
            return self._data[start : start + entry.size]
        if entry.compression in ("Zlib", "Gzip"):
            wbits = 15 if entry.compression == "Zlib" else 31
            output = bytearray()
            position = start
            for length in entry.block_lengths:
                chunk = self._data[position : position + length]
                position += length
                output += zlib.decompress(chunk, wbits)
            if len(output) != entry.size:
                raise PakError(f"'{path}' failed to decompress correctly.")
            return bytes(output)
        raise PakError(
            f"'{path}' is compressed with {entry.compression}, which cannot be decoded "
            "without the proprietary Oodle library."
        )


class PakWriter:
    """Writes uncompressed Icarus .pak files that mirror NetPak's output layout."""

    def __init__(self, path: str | Path, mount_point: str = DEFAULT_MOUNT_POINT) -> None:
        self.path = Path(path)
        self.mount_point = mount_point
        self.relative_mount = (
            mount_point[len(ROOT_PREFIX) :] if mount_point.startswith(ROOT_PREFIX) else mount_point
        )
        self.path_hash_seed = ue_str_crc32(self.path.name.lower())
        self._entries: list[tuple[str, bytes]] = []

    def add_file(self, pak_path: str, data: bytes) -> None:
        normalized = pak_path.replace("\\", "/")
        if normalized.startswith(self.mount_point):
            normalized = normalized[len(self.mount_point) :]
        elif self.relative_mount and normalized.startswith(self.relative_mount):
            normalized = normalized[len(self.relative_mount) :]
        normalized = normalized.lstrip("/")
        if not normalized:
            raise PakError("Entry path cannot be empty.")
        self._entries.append((normalized, bytes(data)))

    def save(self) -> None:
        stream = bytearray()
        encoded = bytearray()
        file_index: list[tuple[str, str, str, int]] = []

        for pak_path, data in self._entries:
            entry_offset = len(stream)
            stream += struct.pack("<qqqi", 0, len(data), len(data), 0)
            stream += hashlib.sha1(data).digest()
            stream += struct.pack("<Bi", 0, 0)
            stream += data

            encoded_offset = len(encoded)
            flags = (1 << 31) | (1 << 30) | (1 << 29)
            encoded += struct.pack("<I", flags)
            encoded += struct.pack("<I", entry_offset)
            encoded += struct.pack("<I", len(data))

            directory, filename = _split_pak_path(pak_path)
            file_index.append((pak_path, directory, filename, encoded_offset))

        directory_map: dict[str, list[tuple[str, int]]] = {"/": []}
        for _pak_path, directory, filename, encoded_offset in file_index:
            if directory not in directory_map:
                chain: list[str] = []
                current = directory
                while len(current) > 1 and current not in directory_map:
                    chain.append(current)
                    current = _parent_directory(current)
                for missing in reversed(chain):
                    directory_map[missing] = []
            directory_map[directory].append((filename, encoded_offset))

        index_offset = len(stream)
        stream += _write_fstring(self.mount_point)
        stream += struct.pack("<i", len(self._entries))
        stream += struct.pack("<Q", self.path_hash_seed)
        stream += struct.pack("<i", 1)
        path_hash_header_at = len(stream)
        stream += b"\x00" * 36
        stream += struct.pack("<i", 1)
        directory_header_at = len(stream)
        stream += b"\x00" * 36
        stream += struct.pack("<i", len(encoded))
        stream += encoded
        stream += struct.pack("<i", 0)
        index_size = len(stream) - index_offset

        path_hash_offset = len(stream)
        stream += struct.pack("<i", len(self._entries))
        for pak_path, _directory, _filename, encoded_offset in file_index:
            stream += struct.pack("<Qi", _fnv64(pak_path, self.path_hash_seed), encoded_offset)
        stream += struct.pack("<i", 0)
        path_hash_size = len(stream) - path_hash_offset

        directory_offset = len(stream)
        stream += struct.pack("<i", len(directory_map))
        for directory, files in directory_map.items():
            stream += _write_fstring(directory)
            stream += struct.pack("<i", len(files))
            for filename, encoded_offset in files:
                stream += _write_fstring(filename)
                stream += struct.pack("<i", encoded_offset)
        directory_size = len(stream) - directory_offset

        stream[path_hash_header_at : path_hash_header_at + 36] = (
            struct.pack("<qq", path_hash_offset, path_hash_size)
            + hashlib.sha1(bytes(stream[path_hash_offset : path_hash_offset + path_hash_size])).digest()
        )
        stream[directory_header_at : directory_header_at + 36] = (
            struct.pack("<qq", directory_offset, directory_size)
            + hashlib.sha1(bytes(stream[directory_offset : directory_offset + directory_size])).digest()
        )
        index_hash = hashlib.sha1(bytes(stream[index_offset : index_offset + index_size])).digest()

        stream += b"\x00" * 16
        stream += b"\x00"
        stream += struct.pack("<I", MAGIC)
        stream += struct.pack("<hh", PAK_VERSION, 0)
        stream += struct.pack("<qq", index_offset, index_size)
        stream += index_hash
        stream += b"\x00" * 160

        self.path.write_bytes(bytes(stream))


def _split_pak_path(pak_path: str) -> tuple[str, str]:
    last_slash = pak_path.rfind("/")
    if last_slash < 0:
        return "/", pak_path
    return pak_path[: last_slash + 1], pak_path[last_slash + 1 :]


def _parent_directory(directory: str) -> str:
    trimmed = directory.rstrip("/")
    last_slash = trimmed.rfind("/")
    if last_slash < 0:
        return "/"
    return trimmed[: last_slash + 1]

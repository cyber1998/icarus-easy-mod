import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

from icarus_manager.uepak import (
    PakError,
    PakFile,
    PakWriter,
    _fnv64,
    _read_fstring,
)

REAL_PAK = os.environ.get("ICARUS_TEST_PAK", "/tmp/laanp.pak")


class RoundTripTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_sample(self, name="Sample_P.pak"):
        path = self.root / name
        writer = PakWriter(path)
        writer.add_file("data/MetaWorkshop/D_WorkshopItems.json", b'{"Rows": []}')
        writer.add_file("Readme (Sample).txt", b"hello readme")
        writer.add_file("nested/deep/binary.bin", bytes(range(256)))
        writer.save()
        return path

    def test_round_trip(self):
        path = self._write_sample()
        pak = PakFile(path)
        self.assertEqual(pak.mount_point, "../../../Icarus/Content/")
        self.assertEqual(
            sorted(pak.list_files()),
            [
                "Readme (Sample).txt",
                "data/MetaWorkshop/D_WorkshopItems.json",
                "nested/deep/binary.bin",
            ],
        )
        self.assertEqual(pak.read_file("data/MetaWorkshop/D_WorkshopItems.json"), b'{"Rows": []}')
        self.assertEqual(pak.read_file("Readme (Sample).txt"), b"hello readme")
        self.assertEqual(pak.read_file("nested/deep/binary.bin"), bytes(range(256)))

    def test_add_file_strips_mount_point(self):
        path = self.root / "Sample_P.pak"
        writer = PakWriter(path)
        writer.add_file("../../../Icarus/Content/data/Thing.json", b"{}")
        writer.save()
        pak = PakFile(path)
        self.assertIn("data/Thing.json", pak.entries)

    def test_path_hash_index_is_consistent(self):
        path = self._write_sample()
        pak = PakFile(path)
        buf = pak._data
        pos = pak.info.index_offset
        _mount, pos = _read_fstring(buf, pos)
        pos += 4
        seed, = struct.unpack_from("<Q", buf, pos)
        pos += 8
        has_path_hash, = struct.unpack_from("<i", buf, pos)
        pos += 4
        self.assertEqual(has_path_hash, 1)
        path_hash_offset, path_hash_size = struct.unpack_from("<qq", buf, pos)
        count, = struct.unpack_from("<i", buf, path_hash_offset)
        stored = {
            struct.unpack_from("<Qi", buf, path_hash_offset + 4 + i * 12)[0] for i in range(count)
        }
        expected = {_fnv64(name, seed) for name in pak.entries}
        self.assertEqual(stored, expected)
        self.assertEqual(path_hash_size, 4 + count * 12 + 4)

    def test_missing_file_raises(self):
        pak = PakFile(self._write_sample())
        with self.assertRaises(PakError):
            pak.read_file("nope.pak")

    def test_invalid_file_raises(self):
        bad = self.root / "garbage.pak"
        bad.write_bytes(b"this is not a pak file" * 50)
        with self.assertRaises(PakError):
            PakFile(bad)

    def test_inline_record_sha1_matches_data(self):
        path = self._write_sample()
        pak = PakFile(path)
        entry = pak.entries["Readme (Sample).txt"]
        inline_sha = pak._data[entry.offset + 28 : entry.offset + 48]
        self.assertEqual(inline_sha, hashlib.sha1(b"hello readme").digest())


@unittest.skipUnless(
    os.path.exists(REAL_PAK),
    "real community pak not available (set ICARUS_TEST_PAK to a mod .pak to enable)",
)
class RealPakTest(unittest.TestCase):
    def test_reads_real_mod_pak(self):
        pak = PakFile(REAL_PAK)
        self.assertTrue(pak.mount_point.endswith("Icarus/Content/"))
        self.assertGreaterEqual(len(pak.entries), 1)
        json_names = [name for name in pak.entries if name.endswith(".json")]
        self.assertTrue(json_names)
        data = pak.read_file(json_names[0])
        parsed = json.loads(data)
        self.assertIn("Rows", parsed)
        entry = pak.entries[json_names[0]]
        inline_sha = pak._data[entry.offset + 28 : entry.offset + 48]
        self.assertEqual(inline_sha, hashlib.sha1(data).digest())


try:
    import repak

    HAVE_REPAK = True
except ImportError:
    HAVE_REPAK = False


@unittest.skipUnless(HAVE_REPAK, "repak not installed")
class RepakCrossValidationTest(unittest.TestCase):
    def test_repak_reads_paks_written_by_us(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Cross_P.pak"
            writer = PakWriter(path)
            writer.add_file("Data/Items/D_ItemsStatic.json", b'{"Rows": [{"Name": "Wood"}]}')
            writer.add_file("Readme.txt", b"hello")
            writer.save()

            reader = repak.PakBuilder().reader(str(path))
            try:
                self.assertEqual(reader.version, repak.Version.V11)
                self.assertEqual(
                    sorted(reader.entries()),
                    ["Data/Items/D_ItemsStatic.json", "Readme.txt"],
                )
                self.assertEqual(
                    reader.get("Data/Items/D_ItemsStatic.json"),
                    b'{"Rows": [{"Name": "Wood"}]}',
                )
            finally:
                reader.close()


if __name__ == "__main__":
    unittest.main()

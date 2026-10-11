import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from icarus_manager.archives import ArchiveError, unpack_to_paks


class UnpackToPaksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _zip(self, name, entries):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            for entry_name, data in entries.items():
                archive.writestr(entry_name, data)
        return path

    def test_raw_pak_passthrough(self):
        pak = self.root / "My_Mod_P.pak"
        pak.write_bytes(b"pakdata")
        result = unpack_to_paks(pak, self.root / "work")
        self.assertEqual(result, [pak])

    def test_zip_extracts_paks_flattened(self):
        zip_path = self._zip(
            "mod.zip",
            {
                "mod/My_Mod_P.pak": b"pak1",
                "mod/readme.txt": b"ignore me",
                "other/sub/Extras_P.pak": b"pak2",
            },
        )
        paks = unpack_to_paks(zip_path, self.root / "work")
        self.assertEqual(sorted(p.name for p in paks), ["Extras_P.pak", "My_Mod_P.pak"])
        self.assertEqual({p.read_bytes() for p in paks}, {b"pak1", b"pak2"})

    def test_zip_path_traversal_is_skipped(self):
        zip_path = self._zip(
            "evil.zip",
            {
                "../../evil_P.pak": b"bad",
                "good_P.pak": b"good",
            },
        )
        paks = unpack_to_paks(zip_path, self.root / "work")
        self.assertEqual([p.name for p in paks], ["good_P.pak"])
        self.assertFalse((self.root.parent / "evil_P.pak").exists())

    def test_zip_with_duplicate_names_renames(self):
        zip_path = self._zip(
            "dupes.zip",
            {
                "a/My_Mod_P.pak": b"one",
                "b/My_Mod_P.pak": b"two",
            },
        )
        paks = unpack_to_paks(zip_path, self.root / "work")
        self.assertEqual(len(paks), 2)
        self.assertEqual(len({p.name for p in paks}), 2)

    def test_zip_without_paks_raises(self):
        zip_path = self._zip("empty.zip", {"readme.txt": b"nothing here"})
        with self.assertRaises(ArchiveError):
            unpack_to_paks(zip_path, self.root / "work")

    def test_zip_with_exmodz_raises(self):
        zip_path = self._zip("exmod.zip", {"MyMod.EXMODZ": b"exmod"})
        with self.assertRaises(ArchiveError):
            unpack_to_paks(zip_path, self.root / "work")

    def test_exmodz_raises(self):
        path = self.root / "MyMod.EXMODZ"
        path.write_bytes(b"exmod")
        with self.assertRaises(ArchiveError):
            unpack_to_paks(path, self.root / "work")

    def test_exmodz_data_only_reports_description(self):
        payload = {
            "name": "Data Mod",
            "author": "Someone",
            "Rows": [{"CurrentFile": "UI-D_MapIcons.json", "File_Items": [{"Name": "Grid"}]}],
        }
        path = self._zip("DataMod.EXMODZ", {"Extracted Mods/DataMod.EXMOD": json.dumps(payload).encode()})
        with self.assertRaises(ArchiveError) as ctx:
            unpack_to_paks(path, self.root / "work")
        message = str(ctx.exception)
        self.assertIn("Data Mod", message)
        self.assertIn("Icarus Mod Manager", message)
        self.assertIn("UI-D_MapIcons.json", message)

    def test_exmodz_with_bundled_pak_is_extracted(self):
        path = self._zip("Bundled.EXMODZ", {"SomeMod_P.pak": b"pakdata", "readme.txt": b"x"})
        paks = unpack_to_paks(path, self.root / "work")
        self.assertEqual([p.name for p in paks], ["SomeMod_P.pak"])

    def test_exmodz_with_exmod_and_pak_still_raises(self):
        payload = {"name": "Mixed Mod", "Rows": []}
        path = self._zip(
            "Mixed.EXMODZ",
            {
                "Extracted Mods/Mixed.EXMOD": json.dumps(payload).encode(),
                "Mixed_P.pak": b"pakdata",
            },
        )
        with self.assertRaises(ArchiveError) as ctx:
            unpack_to_paks(path, self.root / "work")
        self.assertIn("Mixed Mod", str(ctx.exception))

    def test_raw_exmod_file_raises(self):
        path = self.root / "MyMod.EXMOD"
        path.write_text(json.dumps({"name": "Raw Mod", "Rows": []}))
        with self.assertRaises(ArchiveError) as ctx:
            unpack_to_paks(path, self.root / "work")
        self.assertIn("Raw Mod", str(ctx.exception))

    def test_rar_raises(self):
        path = self.root / "MyMod.rar"
        path.write_bytes(b"rar")
        with self.assertRaises(ArchiveError):
            unpack_to_paks(path, self.root / "work")

    def test_unsupported_extension_raises(self):
        path = self.root / "MyMod.7z"
        path.write_bytes(b"7z")
        with self.assertRaises(ArchiveError):
            unpack_to_paks(path, self.root / "work")

    def test_ucas_and_utoc_are_collected(self):
        zip_path = self._zip(
            "ue5.zip",
            {
                "mod/MyMod_P.pak": b"pak",
                "mod/MyMod_P.ucas": b"ucas",
                "mod/MyMod_P.utoc": b"utoc",
            },
        )
        paks = unpack_to_paks(zip_path, self.root / "work")
        self.assertEqual(
            sorted(p.name for p in paks), ["MyMod_P.pak", "MyMod_P.ucas", "MyMod_P.utoc"]
        )


if __name__ == "__main__":
    unittest.main()

import gzip
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from icarus_manager import exmod

NEW_FORMAT = {
    "name": "Always Show Buildings On Map",
    "author": "AgentKush",
    "version": "1.0",
    "description": "Always shows player-built structures on the map.",
    "fileName": "Always_show_buildings_on_map",
    "week": "All",
    "Rows": [
        {
            "CurrentFile": "UI-D_MapIcons.json",
            "File_Items": [
                {"Name": "Grid", "bDisplayOnCompass": True},
                {"Name": "PlayerMarker", "bDisplayOnCompass": True},
            ],
        },
    ],
}

OLD_FORMAT = {
    "ModName": "Old Style Stack Mod",
    "Author": "Jimk72",
    "Version": "2.1",
    "Files": [
        {
            "FileName": "Icarus/Content/Data/Items/D_ItemsStatic.json",
            "Items": [
                {"Name": "Wood", "MaxStackSize": 200},
                {"Name": "Stone", "MaxStackSize": 200},
                {"Name": "Iron", "MaxStackSize": 200},
            ],
        },
    ],
}


class ParseTest(unittest.TestCase):
    def test_new_format(self):
        info = exmod.parse_exmod(NEW_FORMAT)
        self.assertEqual(info.name, "Always Show Buildings On Map")
        self.assertEqual(info.author, "AgentKush")
        self.assertEqual(info.version, "1.0")
        self.assertEqual(info.week, "All")
        self.assertEqual(len(info.changes), 1)
        change = info.changes[0]
        self.assertEqual(change.target_file, "UI-D_MapIcons.json")
        self.assertEqual(change.item_count, 2)
        self.assertEqual(change.sample_names, ["Grid", "PlayerMarker"])
        self.assertEqual(info.total_items, 2)

    def test_full_item_payloads_are_kept_for_merging(self):
        info = exmod.parse_exmod(NEW_FORMAT)
        items = info.changes[0].items
        self.assertEqual(items[0]["Name"], "Grid")
        self.assertTrue(items[0]["bDisplayOnCompass"])

    def test_old_format(self):
        info = exmod.parse_exmod(OLD_FORMAT)
        self.assertEqual(info.name, "Old Style Stack Mod")
        self.assertEqual(info.author, "Jimk72")
        self.assertEqual(len(info.changes), 1)
        self.assertEqual(info.changes[0].target_file, "Icarus/Content/Data/Items/D_ItemsStatic.json")
        self.assertEqual(info.changes[0].item_count, 3)

    def test_sample_names_limited(self):
        payload = {
            "name": "Many",
            "Rows": [
                {
                    "CurrentFile": "X.json",
                    "File_Items": [{"Name": f"Item{i}"} for i in range(20)],
                }
            ],
        }
        info = exmod.parse_exmod(payload)
        self.assertEqual(info.changes[0].item_count, 20)
        self.assertEqual(len(info.changes[0].sample_names), 5)


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _exmodz(self, payload, extra_members=None, name="TestMod.EXMODZ"):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Extracted Mods/TestMod.EXMOD", json.dumps(payload))
            for member, data in (extra_members or {}).items():
                archive.writestr(member, data)
        return path

    def test_load_exmodz(self):
        path = self._exmodz(NEW_FORMAT, {"TestMod/BP/Thing.uasset": b"asset"})
        info = exmod.load_exmod(path)
        self.assertEqual(info.name, "Always Show Buildings On Map")
        self.assertEqual(info.archive_format, "zip")
        self.assertEqual(info.blueprint_assets, ["TestMod/BP/Thing.uasset"])

    def test_load_gzip(self):
        path = self.root / "TestMod.EXMODZ"
        path.write_bytes(gzip.compress(json.dumps(OLD_FORMAT).encode()))
        info = exmod.load_exmod(path)
        self.assertEqual(info.archive_format, "gzip")
        self.assertEqual(info.name, "Old Style Stack Mod")

    def test_load_plain_json(self):
        path = self.root / "TestMod.EXMOD"
        path.write_text(json.dumps(NEW_FORMAT))
        info = exmod.load_exmod(path)
        self.assertEqual(info.archive_format, "json")
        self.assertEqual(info.name, "Always Show Buildings On Map")

    def test_describe_exmodz(self):
        path = self._exmodz(NEW_FORMAT)
        message = exmod.describe(path)
        self.assertIsNotNone(message)
        self.assertIn("Always Show Buildings On Map", message)
        self.assertIn("Icarus Mod Manager", message)
        self.assertIn("UI-D_MapIcons.json", message)

    def test_describe_plain_zip_returns_none(self):
        path = self.root / "not_a_mod.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("readme.txt", "hello")
        self.assertIsNone(exmod.describe(path))

    def test_corrupt_zip_raises(self):
        path = self.root / "broken.EXMODZ"
        path.write_bytes(b"PK\x03\x04 not really a zip")
        with self.assertRaises(exmod.ExModError):
            exmod.load_exmod(path)


if __name__ == "__main__":
    unittest.main()

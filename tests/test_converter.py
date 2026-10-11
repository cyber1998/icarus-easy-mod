import json
import tempfile
import unittest
from pathlib import Path

from icarus_manager import converter
from icarus_manager.exmod import ExModChange, ExModInfo
from icarus_manager.uepak import PakFile, PakWriter

try:
    import repak

    HAVE_REPAK = True
except ImportError:
    HAVE_REPAK = False


def make_mod(name, changes):
    return ExModInfo(name=name, author="tester", version="1.0", description="", week="", changes=changes)


def change(target, items):
    return ExModChange(target, len(items), [item.get("Name") for item in items[:5]], items)


@unittest.skipUnless(HAVE_REPAK, "repak not installed")
class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paks_dir = self.root / "paks"
        self.paks_dir.mkdir()
        writer = PakWriter(self.paks_dir / "Icarus-WindowsServer.pak")
        writer.add_file(
            "Data/Items/D_ItemsStatic.json",
            json.dumps(
                {
                    "RowStruct": "/Script/Icarus.ItemStatic",
                    "Rows": [
                        {"Name": "Wood", "MaxStackSize": 100},
                        {"Name": "Stone", "MaxStackSize": 50},
                    ],
                }
            ).encode(),
        )
        writer.save()
        self.local_mods = self.paks_dir / "mods"
        self.workdir = self.root / "work"

        from icarus_manager import game_data

        self.game_data = game_data
        self.original_cache = game_data.CACHE_DIR
        game_data.CACHE_DIR = self.root / "cache"
        game_data._scan_cache.clear()

    def tearDown(self):
        self.game_data.CACHE_DIR = self.original_cache
        self.game_data._scan_cache.clear()
        self.tmp.cleanup()

    def test_converts_and_packs_merged_tables(self):
        first = make_mod("MoreStacks", [change("Items-D_ItemsStatic.json", [{"Name": "Wood", "MaxStackSize": 200}])])
        second = make_mod("StoneFix", [change("Items-D_ItemsStatic.json", [{"Name": "Stone", "MaxStackSize": 999}])])
        result = converter.convert_mods([first, second], self.local_mods, self.workdir)

        self.assertTrue(result.pak_path.exists())
        self.assertTrue(result.pak_path.name.endswith("_P.pak"))
        self.assertIn("Combined", result.pak_path.name)
        self.assertEqual(result.report.total_changed, 2)

        pak = PakFile(result.pak_path)
        self.assertEqual(pak.list_files(), ["Data/Items/D_ItemsStatic.json"])
        table = json.loads(pak.read_file("Data/Items/D_ItemsStatic.json"))
        rows = {row["Name"]: row for row in table["Rows"]}
        self.assertEqual(rows["Wood"]["MaxStackSize"], 200)
        self.assertEqual(rows["Stone"]["MaxStackSize"], 999)
        self.assertEqual(table["RowStruct"], "/Script/Icarus.ItemStatic")

        reader = repak.PakBuilder().reader(str(result.pak_path))
        try:
            raw = reader.get("Data/Items/D_ItemsStatic.json")
        finally:
            reader.close()
        self.assertEqual(json.loads(raw)["Rows"][0]["Name"], "Wood")

    def test_single_mod_name_has_no_combined_suffix(self):
        mod = make_mod("Only Mod", [change("Items-D_ItemsStatic.json", [{"Name": "Wood", "MaxStackSize": 200}])])
        result = converter.convert_mods([mod], self.local_mods, self.workdir)
        self.assertEqual(result.pak_path.name, "Only_Mod_P.pak")

    def test_no_local_game_raises(self):
        mod = make_mod("M", [change("Items-D_ItemsStatic.json", [{"Name": "Wood"}])])
        missing_paths = self.root / "missing" / "Icarus" / "Content" / "Paks" / "mods"
        with self.assertRaises(converter.ConversionError):
            converter.convert_mods([mod], missing_paths, self.workdir)

    def test_no_matching_tables_raises(self):
        mod = make_mod("M", [change("D_NotInGame.json", [{"Name": "X"}])])
        with self.assertRaises(converter.ConversionError):
            converter.convert_mods([mod], self.local_mods, self.workdir)

    def test_mods_without_changes_raise(self):
        mod = make_mod("Empty", [])
        with self.assertRaises(converter.ConversionError):
            converter.convert_mods([mod], self.local_mods, self.workdir)

    def test_missing_targets_are_reported(self):
        mod = make_mod(
            "M",
            [
                change("Items-D_ItemsStatic.json", [{"Name": "Wood", "MaxStackSize": 5}]),
                change("D_NotInGame.json", [{"Name": "X"}]),
            ],
        )
        result = converter.convert_mods([mod], self.local_mods, self.workdir)
        self.assertEqual(result.report.missing, ["D_NotInGame.json"])
        self.assertIn("Data/Items/D_ItemsStatic.json", PakFile(result.pak_path).entries)


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path

from icarus_manager import game_data
from icarus_manager.uepak import PakWriter

try:
    import repak  # noqa: F401

    HAVE_REPAK = True
except ImportError:
    HAVE_REPAK = False


@unittest.skipUnless(HAVE_REPAK, "repak not installed")
class GameDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paks_dir = self.root / "paks"
        self.paks_dir.mkdir()
        writer = PakWriter(self.paks_dir / "Icarus-WindowsServer.pak")
        writer.add_file(
            "Data/Items/D_ItemsStatic.json",
            json.dumps({"Rows": [{"Name": "Wood", "MaxStackSize": 100}]}).encode(),
        )
        writer.add_file("data/MetaWorkshop/D_WorkshopItems.json", json.dumps({"Rows": []}).encode())
        writer.add_file("Data/UI/D_MapIcons.json", json.dumps({"Rows": [{"Name": "Grid"}]}).encode())
        writer.add_file("Readme.txt", b"not a data file")
        writer.save()
        self.local_mods = self.paks_dir / "mods"

        self.original_cache = game_data.CACHE_DIR
        game_data.CACHE_DIR = self.root / "cache"
        game_data._scan_cache.clear()

    def tearDown(self):
        game_data.CACHE_DIR = self.original_cache
        game_data._scan_cache.clear()
        self.tmp.cleanup()

    def test_new_style_category_targets(self):
        result = game_data.extract_base_tables(
            self.local_mods, ["Items-D_ItemsStatic.json", "UI-D_MapIcons.json"]
        )
        self.assertEqual(result.missing, [])
        self.assertEqual(result.tables["Items-D_ItemsStatic.json"]["Rows"][0]["Name"], "Wood")
        self.assertEqual(result.tables["UI-D_MapIcons.json"]["Rows"][0]["Name"], "Grid")
        self.assertEqual(
            result.sources["Items-D_ItemsStatic.json"].entry_path, "Data/Items/D_ItemsStatic.json"
        )

    def test_old_style_full_path_target(self):
        target = "Icarus/Content/Data/Items/D_ItemsStatic.json"
        result = game_data.extract_base_tables(self.local_mods, [target])
        self.assertEqual(result.missing, [])
        self.assertEqual(result.sources[target].entry_path, "Data/Items/D_ItemsStatic.json")

    def test_case_insensitive_target(self):
        target = "data/metaworkshop/d_workshopitems.json"
        result = game_data.extract_base_tables(self.local_mods, [target])
        self.assertEqual(result.missing, [])
        self.assertEqual(result.sources[target].entry_path, "data/MetaWorkshop/D_WorkshopItems.json")

    def test_missing_target_reported(self):
        result = game_data.extract_base_tables(self.local_mods, ["D_DoesNotExist.json"])
        self.assertEqual(result.missing, ["D_DoesNotExist.json"])
        self.assertEqual(result.tables, {})

    def test_extraction_is_cached(self):
        first = game_data.extract_base_tables(self.local_mods, ["Items-D_ItemsStatic.json"])
        second = game_data.extract_base_tables(self.local_mods, ["Items-D_ItemsStatic.json"])
        self.assertEqual(first.tables, second.tables)
        self.assertTrue(any(game_data.CACHE_DIR.glob("*.json")))

    def test_no_paks_raises(self):
        empty = self.root / "empty"
        (empty / "mods").mkdir(parents=True)
        with self.assertRaises(game_data.GameDataError):
            game_data.extract_base_tables(empty / "mods", ["D_X.json"])

    def test_non_data_entries_are_ignored(self):
        result = game_data.extract_base_tables(self.local_mods, ["Readme.txt"])
        self.assertEqual(result.missing, ["Readme.txt"])


class OodleResolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original_cache_dir = game_data.OODLE_CACHE_DIR
        game_data.OODLE_CACHE_DIR = self.root / "oodle"
        self.original_env = os.environ.pop("REPAK_OODLE_PATH", None)
        self.original_find = game_data._find_oodle_dll

    def tearDown(self):
        game_data.OODLE_CACHE_DIR = self.original_cache_dir
        game_data._find_oodle_dll = self.original_find
        if self.original_env is not None:
            os.environ["REPAK_OODLE_PATH"] = self.original_env
        else:
            os.environ.pop("REPAK_OODLE_PATH", None)
        self.tmp.cleanup()

    def test_user_override_is_respected(self):
        os.environ["REPAK_OODLE_PATH"] = "/custom/oodle"
        game_data._prepare_oodle(Path("/nonexistent"))
        self.assertEqual(os.environ["REPAK_OODLE_PATH"], "/custom/oodle")

    def test_game_dll_wins_over_cache(self):
        game_data._find_oodle_dll = lambda _path: Path("/game/oo2core_9_win64.dll")
        game_data._prepare_oodle(Path("/nonexistent"))
        self.assertEqual(os.environ["REPAK_OODLE_PATH"], "/game/oo2core_9_win64.dll")

    def test_existing_cache_file_is_used(self):
        game_data._find_oodle_dll = lambda _path: None
        target = game_data.oodle_cache_target()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"stub")
        game_data._prepare_oodle(Path("/nonexistent"))
        self.assertEqual(os.environ["REPAK_OODLE_PATH"], str(target))

    def test_missing_cache_points_at_writable_target(self):
        game_data._find_oodle_dll = lambda _path: None
        game_data._prepare_oodle(Path("/nonexistent"))
        target = game_data.oodle_cache_target()
        self.assertEqual(os.environ["REPAK_OODLE_PATH"], str(target))
        self.assertTrue(target.parent.is_dir())


if __name__ == "__main__":
    unittest.main()

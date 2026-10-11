import tempfile
import unittest
from pathlib import Path

from icarus_manager import localgame


class NormalizeLocalPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mods_path_passthrough(self):
        path = self.root / "Icarus/Content/Paks/mods"
        self.assertEqual(localgame.normalize_local_path(str(path)), path)

    def test_paks_path(self):
        path = self.root / "Icarus/Content/Paks"
        self.assertEqual(localgame.normalize_local_path(str(path)), path / "mods")

    def test_content_path(self):
        path = self.root / "Icarus/Content"
        self.assertEqual(localgame.normalize_local_path(str(path)), path / "Paks" / "mods")

    def test_inner_icarus_path(self):
        path = self.root / "steamapps/common/Icarus/Icarus"
        self.assertEqual(localgame.normalize_local_path(str(path)), path / "Content" / "Paks" / "mods")

    def test_outer_game_folder(self):
        outer = self.root / "steamapps/common/Icarus"
        (outer / "Icarus").mkdir(parents=True)
        self.assertEqual(
            localgame.normalize_local_path(str(outer)),
            outer / "Icarus" / "Content" / "Paks" / "mods",
        )

    def test_quotes_are_stripped(self):
        path = self.root / "Paks"
        self.assertEqual(localgame.normalize_local_path(f'"{path}"'), path / "mods")

    def test_empty_and_unrelated_paths(self):
        self.assertIsNone(localgame.normalize_local_path(""))
        self.assertIsNone(localgame.normalize_local_path("   "))
        self.assertIsNone(localgame.normalize_local_path(str(self.root / "Downloads")))


class FindGameTest(unittest.TestCase):
    def test_finds_icarus_paks_inside_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            paks = library / "steamapps/common/Icarus/Icarus/Content/Paks"
            paks.mkdir(parents=True)
            self.assertEqual(localgame.find_icarus_paks(library), paks)
            self.assertIsNone(localgame.find_icarus_paks(library / "unrelated"))


class EnsureModsDirTest(unittest.TestCase):
    def test_creates_mods_when_paks_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            paks = Path(tmp) / "Icarus/Content/Paks"
            paks.mkdir(parents=True)
            mods = localgame.ensure_mods_dir(paks / "mods")
            self.assertTrue(mods.is_dir())

    def test_raises_when_paks_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(localgame.LocalGameError):
                localgame.ensure_mods_dir(Path(tmp) / "nope/mod/Content/Paks/mods")


class CopyPaksTest(unittest.TestCase):
    def test_copies_and_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "My_Mod_P.pak"
            source.write_bytes(b"version one")
            mods = root / "game/Icarus/Content/Paks/mods"

            copied, failures = localgame.copy_paks([source], mods)
            self.assertEqual(copied, ["My_Mod_P.pak"])
            self.assertEqual(failures, [])
            self.assertEqual((mods / source.name).read_bytes(), b"version one")

            source.write_bytes(b"version two")
            copied, failures = localgame.copy_paks([source], mods)
            self.assertEqual(copied, ["My_Mod_P.pak"])
            self.assertEqual((mods / source.name).read_bytes(), b"version two")

    def test_missing_source_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            mods = Path(tmp) / "mods"
            copied, failures = localgame.copy_paks([Path(tmp) / "missing_P.pak"], mods)
            self.assertEqual(copied, [])
            self.assertEqual(len(failures), 1)


if __name__ == "__main__":
    unittest.main()

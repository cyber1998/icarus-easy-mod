import tempfile
import unittest
from pathlib import Path

from icarus_manager import settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = settings.CONFIG_DIR
        self.original_file = settings.CONFIG_FILE
        settings.CONFIG_DIR = Path(self.tmp.name)
        settings.CONFIG_FILE = settings.CONFIG_DIR / "config.json"

    def tearDown(self):
        settings.CONFIG_DIR = self.original_dir
        settings.CONFIG_FILE = self.original_file
        self.tmp.cleanup()

    def test_save_merges_with_existing_profile(self):
        settings.save_profile({"host": "ftp.example.com", "port": 21, "username": "u"})
        settings.save_profile({"local_mods_path": "/tmp/game/mods"})
        profile = settings.load_profile()
        self.assertEqual(profile["host"], "ftp.example.com")
        self.assertEqual(profile["port"], 21)
        self.assertEqual(profile["local_mods_path"], "/tmp/game/mods")

    def test_password_is_never_saved(self):
        settings.save_profile({"host": "h", "password": "secret"})
        self.assertNotIn("password", settings.load_profile())


if __name__ == "__main__":
    unittest.main()

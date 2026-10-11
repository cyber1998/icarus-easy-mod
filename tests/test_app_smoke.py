import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from icarus_manager import settings

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


class AppSmokeTest(unittest.TestCase):
    def test_app_boots_without_exceptions(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self.assertEqual(
            len(at.exception), 0, [exception.value for exception in at.exception]
        )

    def test_pages_render_without_connection(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        for page in ("Browse Mods", "Upload Local Files", "Installed Mods", "Help"):
            at.sidebar.radio[0].set_value(page)
            at.run()
            self.assertEqual(
                len(at.exception), 0, [exception.value for exception in at.exception]
            )

    def test_browse_works_without_connection(self):
        at = AppTest.from_file(APP_PATH, default_timeout=60).run()
        at.sidebar.radio[0].set_value("Browse Mods")
        at.run()
        self.assertEqual(len(at.exception), 0, [exception.value for exception in at.exception])
        self.assertTrue(
            any("browse" in info.value.lower() for info in at.info),
            "expected a notice that browsing works without connecting",
        )
        if not at.error:
            self.assertTrue(
                any("to server" in (button.label or "") for button in at.button),
                "expected the install button to be present without a connection",
            )

    def test_browse_selection_updates_counter(self):
        at = AppTest.from_file(APP_PATH, default_timeout=60).run()
        at.sidebar.radio[0].set_value("Browse Mods")
        at.run()
        if at.error or not at.checkbox:
            self.skipTest("catalog unavailable")
        at.checkbox[0].check().run()
        self.assertEqual(len(at.exception), 0, [exception.value for exception in at.exception])
        self.assertTrue(
            any("Add 1 selected" in (button.label or "") for button in at.button),
            "expected the footer to count the selected mod",
        )
        next_buttons = [button for button in at.button if button.label == "Next"]
        if next_buttons:
            next_buttons[0].click().run()
            at.checkbox[0].check().run()
            self.assertTrue(
                any("Add 2 selected" in (button.label or "") for button in at.button),
                "expected selection to survive page changes",
            )

    def test_connect_form_requires_fields(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.button[0].click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.error)


class LocalFolderFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = settings.CONFIG_DIR
        self.original_file = settings.CONFIG_FILE
        settings.CONFIG_DIR = Path(self.tmp.name) / "config"
        settings.CONFIG_FILE = settings.CONFIG_DIR / "config.json"
        paks = Path(self.tmp.name) / "game/Icarus/Content/Paks"
        paks.mkdir(parents=True)
        self.mods_path = paks / "mods"

    def tearDown(self):
        settings.CONFIG_DIR = self.original_dir
        settings.CONFIG_FILE = self.original_file
        self.tmp.cleanup()

    def test_saving_local_folder(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input(key="local_path_input").set_value(str(self.mods_path))
        [button for button in at.button if button.label == "Save local folder"][0].click().run()
        self.assertEqual(len(at.exception), 0, [exception.value for exception in at.exception])
        self.assertEqual(at.session_state["local_mods_path"], str(self.mods_path))
        self.assertTrue(self.mods_path.is_dir())

    def test_invalid_local_folder_shows_error(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input(key="local_path_input").set_value("/definitely/not/an/icarus/folder")
        [button for button in at.button if button.label == "Save local folder"][0].click().run()
        self.assertEqual(len(at.exception), 0, [exception.value for exception in at.exception])
        self.assertNotEqual(at.session_state.get("local_mods_path"), "/definitely/not/an/icarus/folder")
        self.assertTrue(at.error)


if __name__ == "__main__":
    unittest.main()

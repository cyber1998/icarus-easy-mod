import unittest

from icarus_manager.util import base_mod_key, human_size


class HumanSizeTest(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(human_size(500), "500 B")

    def test_kilobytes(self):
        self.assertEqual(human_size(2048), "2.0 KB")

    def test_megabytes(self):
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")


class BaseModKeyTest(unittest.TestCase):
    def test_strips_version_week_and_pak_suffix(self):
        self.assertEqual(base_mod_key("laanp-WorkshopFree_v1_w253_P.pak"), "laanp-workshopfree")

    def test_catalog_name_matches_file_name(self):
        self.assertEqual(base_mod_key("laanp-WorkshopFree"), base_mod_key("laanp-WorkshopFree_v1_w253_P.pak"))

    def test_underscores_and_spaces_normalized(self):
        self.assertEqual(base_mod_key("Turret Variants_v2.PAK"), "turret-variants")

    def test_plain_name_unchanged(self):
        self.assertEqual(base_mod_key("Simple.pak"), "simple")

    def test_trailing_version_number(self):
        self.assertEqual(base_mod_key("AnimuAll200_P.pak"), "animuall")


if __name__ == "__main__":
    unittest.main()

import unittest

from icarus_manager.exmod import ExModChange, ExModInfo
from icarus_manager.exmod_merge import merge_mods


def make_mod(name, changes):
    return ExModInfo(name=name, author="tester", version="1.0", description="", week="", changes=changes)


def change(target, items):
    return ExModChange(target, len(items), [item.get("Name") for item in items[:5]], items)


class MergeTest(unittest.TestCase):
    def test_changed_rows_overlay_and_added(self):
        base = {
            "Rows": [
                {"Name": "Wood", "MaxStackSize": 100, "Weight": 5},
                {"Name": "Stone", "MaxStackSize": 50},
            ]
        }
        mod = make_mod(
            "MoreStacks",
            [change("D_ItemsStatic.json", [{"Name": "Wood", "MaxStackSize": 200}, {"Name": "NewItem", "MaxStackSize": 1}])],
        )
        merged, report = merge_mods([mod], {"D_ItemsStatic.json": base})
        rows = {row["Name"]: row for row in merged["D_ItemsStatic.json"]["Rows"]}
        self.assertEqual(rows["Wood"]["MaxStackSize"], 200)
        self.assertEqual(rows["Wood"]["Weight"], 5)
        self.assertEqual(rows["Stone"]["MaxStackSize"], 50)
        self.assertIn("NewItem", rows)
        stats = report.files["D_ItemsStatic.json"]
        self.assertEqual(stats.changed, 1)
        self.assertEqual(stats.added, 1)
        self.assertEqual(report.total_changed, 1)
        self.assertEqual(report.total_added, 1)

    def test_later_mod_wins_and_conflict_reported(self):
        base = {"Rows": [{"Name": "Wood", "MaxStackSize": 100}]}
        first = make_mod("First", [change("t.json", [{"Name": "Wood", "MaxStackSize": 2}])])
        second = make_mod("Second", [change("t.json", [{"Name": "Wood", "MaxStackSize": 3}])])
        merged, report = merge_mods([first, second], {"t.json": base})
        self.assertEqual(merged["t.json"]["Rows"][0]["MaxStackSize"], 3)
        self.assertEqual(len(report.conflicts), 1)
        self.assertIn("Second", report.conflicts[0])

    def test_case_insensitive_row_match(self):
        base = {"Rows": [{"Name": "wood"}]}
        mod = make_mod("M", [change("t.json", [{"Name": "Wood", "MaxStackSize": 1}])])
        merged, report = merge_mods([mod], {"t.json": base})
        self.assertEqual(len(merged["t.json"]["Rows"]), 1)
        self.assertEqual(report.files["t.json"].changed, 1)
        self.assertEqual(report.files["t.json"].added, 0)

    def test_bare_list_table(self):
        base = [{"Name": "A"}]
        mod = make_mod("M", [change("t.json", [{"Name": "A", "V": 1}])])
        merged, report = merge_mods([mod], {"t.json": base})
        self.assertEqual(merged["t.json"][0]["V"], 1)

    def test_missing_target_is_skipped(self):
        mod = make_mod("M", [change("absent.json", [{"Name": "A", "V": 1}])])
        merged, report = merge_mods([mod], {})
        self.assertEqual(merged, {})
        self.assertEqual(report.files, {})

    def test_multiple_targets(self):
        base = {"a.json": {"Rows": [{"Name": "R"}]}, "b.json": {"Rows": [{"Name": "S"}]}}
        mod = make_mod(
            "M",
            [
                change("a.json", [{"Name": "R", "V": 1}]),
                change("b.json", [{"Name": "S", "V": 2}]),
            ],
        )
        merged, report = merge_mods([mod], base)
        self.assertEqual(merged["a.json"]["Rows"][0]["V"], 1)
        self.assertEqual(merged["b.json"]["Rows"][0]["V"], 2)
        self.assertEqual(report.total_changed, 2)


if __name__ == "__main__":
    unittest.main()

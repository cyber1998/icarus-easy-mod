import unittest

from icarus_manager import catalog

SAMPLE_HTML = """
<html><body>
<div>
  <form action="/" method="get"><input name="query" /></form>
  <select name="author">
    <option value="">Filter By Author</option>
    <option value="">All</option>
    <option value="laanp">laanp</option>
    <option value="jimk72">Jimk72</option>
  </select>
</div>
<turbo-frame id="mods">
  <div>544 mods (page 1 of 28)</div>
  <table><tbody>
    <tr id="mod_abc" data-mods-path-param="/mods/laanp/laanp-workshopfree">
      <td>laanp-WorkshopFree</td>
      <td><button data-mods-url-param="https://github.com/laanp/releases/download/v1_w253/laanp-WorkshopFree_v1_w253_P.pak" data-mods-file-name-param="laanp-WorkshopFree_v1_w253_P.pak">PAK</button></td>
      <td>laanp</td>
      <td>1.0</td>
      <td>1 day ago</td>
      <td><span>w253</span></td>
      <td title="desc">All items in the Workshop are free.</td>
    </tr>
    <tr id="mod_def" data-mods-path-param="/mods/agentkush/some-exmod">
      <td>Some EXMOD</td>
      <td><button data-mods-url-param="https://github.com/agentkush/releases/download/v1/Some.EXMODZ" data-mods-file-name-param="Some.EXMODZ">EXMODZ</button></td>
      <td>AgentKush</td>
      <td>2.0</td>
      <td>3 days ago</td>
      <td>w252</td>
      <td>An EXMODZ mod.</td>
    </tr>
  </tbody></table>
</turbo-frame>
</body></html>
"""


class ParseCatalogTest(unittest.TestCase):
    def test_parses_rows_and_totals(self):
        result = catalog.parse_catalog(SAMPLE_HTML)
        self.assertEqual(result.total_mods, 544)
        self.assertEqual(result.page, 1)
        self.assertEqual(result.total_pages, 28)
        self.assertEqual(len(result.mods), 2)

        first = result.mods[0]
        self.assertEqual(first.name, "laanp-WorkshopFree")
        self.assertEqual(first.author, "laanp")
        self.assertEqual(first.version, "1.0")
        self.assertEqual(first.week, "w253")
        self.assertEqual(first.download_type, "PAK")
        self.assertTrue(first.download_url.endswith("_P.pak"))
        self.assertEqual(first.filename, "laanp-WorkshopFree_v1_w253_P.pak")
        self.assertEqual(first.detail_url, "https://www.projectdaedalus.app/mods/laanp/laanp-workshopfree")

        second = result.mods[1]
        self.assertEqual(second.download_type, "EXMODZ")
        self.assertEqual(second.filename, "Some.EXMODZ")

    def test_parses_authors(self):
        result = catalog.parse_catalog(SAMPLE_HTML)
        self.assertIn(("laanp", "laanp"), result.authors)
        self.assertIn(("jimk72", "Jimk72"), result.authors)
        self.assertNotIn(("", "All"), result.authors)

    def test_local_filters(self):
        mods = catalog.parse_catalog(SAMPLE_HTML).mods
        paks = catalog._apply_local_filters(mods, "", "pak")
        self.assertEqual([m.name for m in paks], ["laanp-WorkshopFree"])
        search = catalog._apply_local_filters(mods, "workshop", "all")
        self.assertEqual([m.name for m in search], ["laanp-WorkshopFree"])


class LiveCatalogTest(unittest.TestCase):
    def test_fetch_pak_mods(self):
        try:
            result = catalog.fetch_catalog(download_type="pak")
        except catalog.CatalogError as exc:
            raise unittest.SkipTest(f"network unavailable: {exc}")
        self.assertGreater(len(result.mods), 50)
        first = result.mods[0]
        self.assertTrue(first.name)
        self.assertTrue(first.download_url)
        self.assertTrue(first.filename)
        self.assertTrue(result.authors)

    def test_search_query(self):
        try:
            result = catalog.fetch_catalog(query="laanp", download_type="pak")
        except catalog.CatalogError as exc:
            raise unittest.SkipTest(f"network unavailable: {exc}")
        self.assertGreater(len(result.mods), 3)
        self.assertTrue(all("laanp" in mod.author.lower() for mod in result.mods))


if __name__ == "__main__":
    unittest.main()

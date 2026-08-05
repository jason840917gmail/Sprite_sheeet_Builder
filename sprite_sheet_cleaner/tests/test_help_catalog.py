from __future__ import annotations

from pathlib import Path
import unittest

from sprite_sheet_cleaner.app.services.help_catalog import HelpCatalog


class HelpCatalogTests(unittest.TestCase):
    def test_bundled_index_loads_all_markdown_documents(self) -> None:
        catalog = HelpCatalog(Path(__file__).parents[2] / "help")

        self.assertGreaterEqual(len(catalog.documents), 5)
        self.assertIn("Source Background", catalog.read("right-panel"))
        self.assertIn("F1", catalog.read("keyboard-shortcuts"))

    def test_unknown_document_id_is_rejected(self) -> None:
        catalog = HelpCatalog(Path(__file__).parents[2] / "help")

        with self.assertRaises(KeyError):
            catalog.read("missing")


if __name__ == "__main__":
    unittest.main()

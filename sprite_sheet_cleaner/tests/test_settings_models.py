from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.sheet_settings import SheetSettings
from sprite_sheet_cleaner.app.models.source_processing_settings import SourceProcessingSettings
from sprite_sheet_cleaner.app.models.tile_settings import TileSettings


class SettingsModelTests(unittest.TestCase):
    def test_legacy_settings_expose_scoped_views(self) -> None:
        settings = AppSettings(
            tile_width=64,
            tile_height=96,
            sheet_columns=3,
            sheet_rows=2,
            background_color=(10, 20, 30),
            tolerance=12,
            edge_bleed=2,
            tile_background_engine="smart_solid",
        )

        source = settings.source_processing_settings()
        tile = settings.tile_settings()
        sheet = settings.sheet_settings()

        self.assertIsInstance(source, SourceProcessingSettings)
        self.assertEqual(source.background_color, (10, 20, 30))
        self.assertEqual(source.edge_bleed, 2)
        self.assertEqual(settings.tile_processing_settings().engine, "smart_solid")
        self.assertIsInstance(tile, TileSettings)
        self.assertEqual((tile.tile_width, tile.tile_height), (64, 96))
        self.assertIsInstance(sheet, SheetSettings)
        self.assertEqual((sheet.sheet_columns, sheet.sheet_rows), (3, 2))

    def test_scoped_settings_validate_threshold_order(self) -> None:
        with self.assertRaises(ValueError):
            SourceProcessingSettings(transparent_threshold=80, foreground_threshold=20).validated()

    def test_tile_background_engine_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            AppSettings(tile_background_engine="unknown").validated()


if __name__ == "__main__":
    unittest.main()

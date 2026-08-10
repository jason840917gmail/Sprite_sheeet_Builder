from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet, sheet_capacity, sheet_dimensions
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem


def tile(name: str, color: tuple[int, int, int, int]) -> TileItem:
    return TileItem(
        name=name,
        source_rect=(0, 0, 4, 4),
        source_size=(4, 4),
        final_size=(4, 4),
        image_rgba=Image.new("RGBA", (4, 4), color),
    )


class SheetBuilderTests(unittest.TestCase):
    def test_sheet_dimensions_use_bucket_size_not_selection_size(self) -> None:
        settings = AppSettings(
            tile_width=256,
            tile_height=256,
            bucket_tile_width=64,
            bucket_tile_height=64,
            sheet_columns=8,
            sheet_rows=8,
        )

        self.assertEqual(sheet_dimensions(settings), (512, 512))

    def test_sheet_dimensions_and_capacity(self) -> None:
        settings = AppSettings(tile_width=4, tile_height=6, sheet_columns=3, sheet_rows=2)

        self.assertEqual(sheet_dimensions(settings), (12, 12))
        self.assertEqual(sheet_capacity(settings), 6)

    def test_build_sheet_pastes_tiles_in_grid_order(self) -> None:
        settings = AppSettings(tile_width=4, tile_height=4, sheet_columns=2, sheet_rows=2)
        tiles = [
            tile("red", (255, 0, 0, 255)),
            tile("green", (0, 255, 0, 255)),
            tile("blue", (0, 0, 255, 255)),
            tile("white", (255, 255, 255, 255)),
        ]

        sheet = build_sheet(tiles, settings)

        self.assertEqual(sheet.size, (8, 8))
        self.assertEqual(sheet.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(sheet.getpixel((4, 0)), (0, 255, 0, 255))
        self.assertEqual(sheet.getpixel((0, 4)), (0, 0, 255, 255))
        self.assertEqual(sheet.getpixel((4, 4)), (255, 255, 255, 255))

    def test_build_sheet_rejects_overflow_by_default(self) -> None:
        settings = AppSettings(tile_width=4, tile_height=4, sheet_columns=2, sheet_rows=2)
        tiles = [tile(str(index), (index, 0, 0, 255)) for index in range(5)]

        with self.assertRaises(ValueError):
            build_sheet(tiles, settings)

    def test_build_sheet_preserves_semitransparent_rgba(self) -> None:
        settings = AppSettings(tile_width=2, tile_height=2, sheet_columns=1, sheet_rows=1)
        tiles = [
            TileItem(
                name="soft",
                source_rect=(0, 0, 2, 2),
                source_size=(2, 2),
                final_size=(2, 2),
                image_rgba=Image.new("RGBA", (2, 2), (100, 50, 25, 128)),
            )
        ]

        result = build_sheet(tiles, settings)

        self.assertEqual(result.getpixel((0, 0)), (100, 50, 25, 128))


if __name__ == "__main__":
    unittest.main()


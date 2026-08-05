from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.export_manager import export_individual_tiles
from sprite_sheet_cleaner.app.models.tile_item import TileItem


class ExportManagerTests(unittest.TestCase):
    def test_individual_export_reopens_as_rgba_png(self) -> None:
        tile = TileItem(
            name="hero",
            source_rect=(0, 0, 2, 2),
            source_size=(2, 2),
            final_size=(2, 2),
            image_rgba=Image.new("RGBA", (2, 2), (12, 34, 56, 128)),
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = export_individual_tiles(directory, [tile])
            with Image.open(paths[0]) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0)), (12, 34, 56, 128))


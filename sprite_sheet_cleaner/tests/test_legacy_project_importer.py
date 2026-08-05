from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.services.legacy_project_importer import load_legacy_project_into_model
from sprite_sheet_cleaner.app.core.project_model import ProjectModel


class LegacyProjectImporterTests(unittest.TestCase):
    def test_legacy_import_reconstructs_tile_pixels_with_legacy_alpha_behavior(self) -> None:
        source = Image.new("RGBA", (2, 2), (20, 40, 60, 128))
        data = {
            "source_image_path": "source.png",
            "settings": AppSettings(tile_width=2, tile_height=2, remove_background=False).to_dict(),
            "tiles": [{"name": "soft", "source_rect": [0, 0, 2, 2]}],
        }
        model = ProjectModel()

        load_legacy_project_into_model(data, source, model)

        self.assertEqual(model.tiles[0].image_rgba.getpixel((0, 0)), (10, 20, 30, 64))

    def test_legacy_import_rejects_invalid_tile_metadata(self) -> None:
        with self.assertRaises(ValueError):
            load_legacy_project_into_model({"settings": {}, "tiles": [{"source_rect": [1, 2]}]}, Image.new("RGBA", (4, 4)), ProjectModel())


if __name__ == "__main__":
    unittest.main()

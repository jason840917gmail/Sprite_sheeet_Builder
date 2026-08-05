from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.services.project_service import load_model_project, save_model_project


class ProjectServiceTests(unittest.TestCase):
    def test_model_round_trip_restores_exact_tile_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Image.new("RGBA", (4, 4), "white")
            model = ProjectModel(source_image_path="source.png", settings=AppSettings(tile_width=2, tile_height=2))
            model.tiles.append(
                TileItem(
                    name="soft",
                    source_rect=(0, 0, 2, 2),
                    source_size=(2, 2),
                    final_size=(2, 2),
                    image_rgba=Image.new("RGBA", (2, 2), (100, 50, 25, 128)),
                )
            )
            path = save_model_project(Path(directory) / "project.sscproj", model)

            restored = ProjectModel()
            load_model_project(path, restored)

            self.assertEqual(len(restored.tiles), 1)
            self.assertEqual(restored.tiles[0].image_rgba.getpixel((0, 0)), (100, 50, 25, 128))
            self.assertEqual(restored.settings.tile_width, 2)


if __name__ == "__main__":
    unittest.main()

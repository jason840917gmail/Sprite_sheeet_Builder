from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.tile_transform import render_tile_transform
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
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

    def test_round_trip_preserves_editable_base_transform_and_video_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(
                tile_width=5,
                tile_height=5,
                bucket_tile_width=5,
                bucket_tile_height=5,
                remove_background=False,
                edge_bleed=0,
            ).validated()
            base = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
            base.putpixel((3, 2), (255, 0, 0, 255))
            transform = TileTransform(angle_degrees=90, resample_mode="nearest")
            rendered = render_tile_transform(base, settings.bucket_settings(), transform)
            model = ProjectModel(source_type="video", settings=settings)
            model.tiles.append(
                TileItem(
                    name="frame_0003",
                    source_rect=(0, 0, 5, 5),
                    source_size=(5, 5),
                    final_size=(5, 5),
                    image_rgba=rendered,
                    source_type="video",
                    source_frame_index=3,
                    source_timestamp_ms=100,
                    source_path="demo.mp4",
                    resize_size=(5, 5),
                    resize_mode="fit",
                    base_image_rgba=base,
                    transform=transform,
                )
            )

            path = save_model_project(Path(directory) / "transform.sscproj", model)
            restored = ProjectModel()
            load_model_project(path, restored)

            tile = restored.tiles[0]
            self.assertEqual(tile.base_image_rgba.getpixel((3, 2)), (255, 0, 0, 255))
            self.assertEqual(tile.transform, transform)
            self.assertEqual(tile.image_rgba.tobytes(), rendered.tobytes())
            self.assertEqual((tile.source_type, tile.source_frame_index, tile.source_timestamp_ms), ("video", 3, 100))
            self.assertEqual((tile.source_path, tile.resize_size, tile.resize_mode), ("demo.mp4", (5, 5), "fit"))


if __name__ == "__main__":
    unittest.main()

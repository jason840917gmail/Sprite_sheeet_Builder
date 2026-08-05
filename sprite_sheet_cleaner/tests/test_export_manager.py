from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.core.export_manager import export_individual_tiles, export_metadata
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.video_source import FrameRef
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
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

    def test_export_metadata_contains_sheet_and_video_frame_coordinates(self) -> None:
        settings = AppSettings(
            tile_width=16,
            tile_height=16,
            sheet_columns=2,
            sheet_rows=1,
            remove_background=False,
        )
        model = ProjectModel(settings=settings)
        model.add_video_frames(
            [(FrameRef(12, 400), Image.new("RGBA", (16, 16), (255, 0, 0, 255)))],
            source_path="clip.mp4",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = export_metadata(
                Path(temp_dir) / "clip.json",
                model.tiles,
                settings,
                source_path="clip.mp4",
                video_metadata={"fps": 30.0},
                animation_fps=12.0,
            )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["sheet"], {"tile_width": 16, "tile_height": 16, "columns": 2, "rows": 1})
        self.assertEqual(data["animation_fps"], 12.0)
        self.assertEqual(data["frames"][0]["sheet_rect"], [0, 0, 16, 16])
        self.assertEqual(data["frames"][0]["source_path"], "clip.mp4")
        self.assertEqual(data["frames"][0]["source_frame_index"], 12)
        self.assertEqual(data["frames"][0]["source_timestamp_ms"], 400)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

from PIL import Image

from sprite_sheet_cleaner.app.core.project_model import ProjectModel, split_selection_grid_rect
from sprite_sheet_cleaner.app.models.app_settings import AppSettings


class ProjectModelTests(unittest.TestCase):
    def test_split_selection_grid_rect_uses_row_major_tile_cells(self) -> None:
        rects = split_selection_grid_rect((10, 20, 64, 128), 64, 64, 1, 2)

        self.assertEqual(rects, [(10, 20, 64, 64), (10, 84, 64, 64)])

    def test_add_tiles_from_selection_adds_each_selected_grid_cell(self) -> None:
        source = Image.new("RGBA", (2, 4), (0, 0, 0, 0))
        for y in range(2):
            for x in range(2):
                source.putpixel((x, y), (255, 0, 0, 255))
        for y in range(2, 4):
            for x in range(2):
                source.putpixel((x, y), (0, 0, 255, 255))

        model = ProjectModel(
            settings=AppSettings(
                tile_width=2,
                tile_height=2,
                selection_columns=1,
                selection_rows=2,
                remove_background=False,
            )
        )

        added = model.add_tiles_from_selection(source, (0, 0, 2, 4))

        self.assertEqual(len(added), 2)
        self.assertEqual([tile.source_rect for tile in added], [(0, 0, 2, 2), (0, 2, 2, 2)])
        self.assertEqual(added[0].image_rgba.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(added[1].image_rgba.getpixel((0, 0)), (0, 0, 255, 255))

    def test_add_tiles_from_rects_is_atomic_when_processing_fails(self) -> None:
        source = Image.new("RGBA", (4, 2), (255, 0, 0, 255))
        model = ProjectModel(settings=AppSettings(tile_width=2, tile_height=2, remove_background=False))

        with patch(
            "sprite_sheet_cleaner.app.core.project_model.process_crop",
            side_effect=[Image.new("RGBA", (2, 2)), RuntimeError("processing failed")],
        ):
            with self.assertRaisesRegex(RuntimeError, "processing failed"):
                model.add_tiles_from_rects(source, [(0, 0, 2, 2), (2, 0, 2, 2)])

        self.assertEqual(model.tiles, [])

    def test_legacy_true_match_setting_migrates_without_using_selection_dimensions(self) -> None:
        settings = AppSettings.from_dict(
            {
                "selection_columns": 5,
                "selection_rows": 3,
                "sheet_columns": 9,
                "sheet_rows": 8,
                "match_sheet_to_selection": True,
            }
        )

        self.assertTrue(settings.match_sheet_to_grid)
        self.assertEqual((settings.sheet_columns, settings.sheet_rows), (9, 8))

    def test_corrected_match_setting_wins_over_legacy_field(self) -> None:
        settings = AppSettings.from_dict(
            {
                "match_sheet_to_selection": True,
                "match_sheet_to_grid": False,
            }
        )

        self.assertFalse(settings.match_sheet_to_grid)

    def test_old_project_settings_keep_independent_sheet_dimensions(self) -> None:
        settings = AppSettings.from_dict(
            {
                "selection_columns": 5,
                "selection_rows": 3,
                "sheet_columns": 9,
                "sheet_rows": 8,
            }
        )

        self.assertFalse(settings.match_sheet_to_grid)
        self.assertEqual((settings.sheet_columns, settings.sheet_rows), (9, 8))


if __name__ == "__main__":
    unittest.main()

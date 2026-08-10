from __future__ import annotations

import unittest
from unittest.mock import patch

from PIL import Image

from sprite_sheet_cleaner.app.core.video_source import FrameRef
from sprite_sheet_cleaner.app.core.project_model import ProjectModel, split_selection_grid_rect
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings


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
            "sprite_sheet_cleaner.app.core.project_model.process_crop_to_bucket",
            side_effect=[
                (Image.new("RGBA", (2, 2)), Image.new("RGBA", (2, 2))),
                RuntimeError("processing failed"),
            ],
        ):
            with self.assertRaisesRegex(RuntimeError, "processing failed"):
                model.add_tiles_from_rects(source, [(0, 0, 2, 2), (2, 0, 2, 2)])

        self.assertEqual(model.tiles, [])

    def test_selection_size_is_independent_from_bucket_output_size(self) -> None:
        source = Image.new("RGBA", (256, 256), (25, 50, 75, 255))
        model = ProjectModel(
            settings=AppSettings(
                tile_width=256,
                tile_height=256,
                bucket_tile_width=64,
                bucket_tile_height=64,
                bucket_resize_mode="fit",
                remove_background=False,
                edge_bleed=0,
            )
        )

        tile = model.add_tile_from_crop(source, (0, 0, 256, 256))

        self.assertEqual(tile.source_size, (256, 256))
        self.assertEqual(tile.final_size, (64, 64))
        self.assertEqual(tile.image_rgba.size, (64, 64))

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

    def test_add_video_frames_preserves_source_order_and_skips_duplicate_indices(self) -> None:
        model = ProjectModel(
            settings=AppSettings(
                tile_width=2,
                tile_height=2,
                sheet_columns=4,
                sheet_rows=1,
                remove_background=False,
            )
        )
        red = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        blue = Image.new("RGBA", (2, 2), (0, 0, 255, 255))

        added = model.add_video_frames(
            [
                (FrameRef(7, 233), blue),
                (FrameRef(2, 67), red),
                (FrameRef(7, 233), blue),
            ],
            source_path="demo.mp4",
        )

        self.assertEqual([tile.source_frame_index for tile in added], [2, 7])
        self.assertEqual([tile.name for tile in added], ["frame_0002", "frame_0007"])
        self.assertEqual([tile.source_type for tile in added], ["video", "video"])
        self.assertEqual([tile.source_timestamp_ms for tile in added], [67, 233])
        self.assertEqual([tile.source_path for tile in added], ["demo.mp4", "demo.mp4"])

    def test_video_tile_metadata_round_trips_through_project_data(self) -> None:
        source = Image.new("RGBA", (2, 2), (40, 50, 60, 255))
        model = ProjectModel(
            source_type="video",
            source_image_path="demo.mp4",
            video_metadata={"fps": 30.0},
            video_settings={"sample_every": 2},
            settings=AppSettings(tile_width=2, tile_height=2, remove_background=False),
        )
        model.add_video_frames([(FrameRef(4, 133), source)], source_path="demo.mp4")
        tile_id = model.tiles[0].tile_id
        data = model.to_project_data()

        restored = ProjectModel()
        restored.load_project_data(data, source)

        self.assertEqual(restored.source_type, "video")
        self.assertEqual(restored.video_metadata, {"fps": 30.0})
        self.assertEqual(restored.video_settings, {"sample_every": 2})
        self.assertEqual(restored.tiles[0].tile_id, tile_id)
        self.assertEqual(restored.tiles[0].source_frame_index, 4)
        self.assertEqual(restored.tiles[0].source_timestamp_ms, 133)

    def test_video_resize_settings_are_applied_and_persisted_per_frame(self) -> None:
        source = Image.new("RGBA", (4, 2), (40, 50, 60, 255))
        model = ProjectModel(
            settings=AppSettings(tile_width=8, tile_height=8, remove_background=False),
        )
        resize_settings = FrameResizeSettings(4, 4, "fit")

        added = model.add_video_frames(
            [(FrameRef(3, 100), source)],
            source_path="demo.mp4",
            resize_settings_by_frame={3: resize_settings},
        )

        self.assertEqual(added[0].image_rgba.size, (8, 8))
        self.assertEqual(added[0].resize_size, (4, 4))
        self.assertEqual(added[0].resize_mode, "fit")
        self.assertEqual(model.to_project_data()["tiles"][0]["resize_size"], [4, 4])

    def test_video_reprocessing_can_resolve_each_tile_from_its_source_video(self) -> None:
        model = ProjectModel(
            settings=AppSettings(tile_width=2, tile_height=2, remove_background=False),
        )
        first = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        second = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
        model.add_video_frames([(FrameRef(1, 10), first)], source_path="first.mp4")
        model.add_video_frames([(FrameRef(1, 10), second)], source_path="second.mp4")

        model.reprocess_video_tiles(
            lambda _index: first,
            lambda source_path, _index: {"first.mp4": first, "second.mp4": second}[source_path],
        )

        self.assertEqual(model.tiles[0].image_rgba.getpixel((0, 0))[:3], (255, 0, 0))
        self.assertEqual(model.tiles[1].image_rgba.getpixel((0, 0))[:3], (0, 0, 255))

    def test_reprocessing_preserves_stable_tile_and_revision_ids(self) -> None:
        source = Image.new("RGBA", (2, 2), (40, 50, 60, 255))
        model = ProjectModel(settings=AppSettings(tile_width=2, tile_height=2, remove_background=False))
        tile = model.add_tile_from_crop(source, (0, 0, 2, 2))
        tile.source_revision_id = "revision-1"
        tile_id = tile.tile_id

        model.reprocess_tiles(source)

        self.assertEqual(model.tiles[0].tile_id, tile_id)
        self.assertEqual(model.tiles[0].source_revision_id, "revision-1")


if __name__ == "__main__":
    unittest.main()

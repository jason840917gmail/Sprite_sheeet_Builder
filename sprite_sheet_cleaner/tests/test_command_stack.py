from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.commands.bucket_commands import BucketStateCommand, clone_tiles
from sprite_sheet_cleaner.app.commands.command_stack import CommandStack
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.models.tile_item import TileItem


def make_tile(name: str) -> TileItem:
    return TileItem(name, (0, 0, 1, 1), (1, 1), (1, 1), Image.new("RGBA", (1, 1), "white"))


class CommandStackTests(unittest.TestCase):
    def test_bucket_state_undo_redo_restores_pixels_and_order(self) -> None:
        model = ProjectModel(tiles=[make_tile("one")])
        before = [tile for tile in model.tiles]
        after = [make_tile("one"), make_tile("two")]
        stack = CommandStack()

        stack.execute(BucketStateCommand(model, before, after))
        self.assertEqual([tile.name for tile in model.tiles], ["one", "two"])
        self.assertTrue(stack.undo())
        self.assertEqual([tile.name for tile in model.tiles], ["one"])
        self.assertTrue(stack.redo())
        self.assertEqual([tile.name for tile in model.tiles], ["one", "two"])

    def test_new_command_clears_redo_history(self) -> None:
        model = ProjectModel()
        stack = CommandStack()
        first = BucketStateCommand(model, [], [make_tile("one")])
        second = BucketStateCommand(model, [make_tile("one")], [])

        stack.execute(first)
        stack.undo()
        stack.execute(second)

        self.assertFalse(stack.can_redo)

    def test_bucket_snapshots_preserve_video_metadata(self) -> None:
        tile = TileItem(
            "frame",
            (0, 0, 1, 1),
            (1, 1),
            (1, 1),
            Image.new("RGBA", (1, 1), "white"),
            source_type="video",
            source_frame_index=12,
            source_timestamp_ms=400,
            source_path="clip.mp4",
            resize_size=(8, 8),
            resize_mode="fit",
        )

        copied = clone_tiles([tile])[0]

        self.assertEqual(copied.source_type, "video")
        self.assertEqual(copied.source_frame_index, 12)
        self.assertEqual(copied.source_timestamp_ms, 400)
        self.assertEqual(copied.source_path, "clip.mp4")
        self.assertEqual(copied.resize_size, (8, 8))
        self.assertEqual(copied.resize_mode, "fit")


if __name__ == "__main__":
    unittest.main()

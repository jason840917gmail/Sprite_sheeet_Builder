from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.commands.bucket_commands import BucketStateCommand
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


if __name__ == "__main__":
    unittest.main()

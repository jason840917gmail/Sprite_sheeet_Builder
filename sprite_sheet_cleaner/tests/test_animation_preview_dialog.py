from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

try:
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.models.tile_item import TileItem
    from sprite_sheet_cleaner.app.widgets.animation_preview_dialog import AnimationPreviewDialog
except ImportError:
    QApplication = None
    TileItem = None
    AnimationPreviewDialog = None


@unittest.skipUnless(
    QApplication is not None and AnimationPreviewDialog is not None,
    "PySide6 is not installed",
)
class AnimationPreviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self) -> AnimationPreviewDialog:
        tiles = [
            TileItem(
                name=f"frame-{index}",
                source_rect=(0, 0, 2, 2),
                source_size=(2, 2),
                final_size=(2, 2),
                image_rgba=Image.new("RGBA", (2, 2), (index, 0, 0, 255)),
            )
            for index in range(3)
        ]
        return AnimationPreviewDialog(tiles)

    def test_loop_mode_wraps_from_last_to_first(self) -> None:
        dialog = self._dialog()
        try:
            indices = []
            for _ in range(4):
                dialog._advance()
                indices.append(dialog._index)
            self.assertEqual(indices, [1, 2, 0, 1])
        finally:
            dialog.close()

    def test_ping_pong_mode_reverses_at_the_ends(self) -> None:
        dialog = self._dialog()
        try:
            dialog.mode_combo.setCurrentIndex(1)
            indices = []
            for _ in range(8):
                dialog._advance()
                indices.append(dialog._index)
            self.assertEqual(indices, [1, 2, 1, 0, 1, 2, 1, 0])
        finally:
            dialog.close()

    def test_repeat_off_stops_at_the_last_frame_for_both_modes(self) -> None:
        for mode_index in (0, 1):
            dialog = self._dialog()
            try:
                dialog.mode_combo.setCurrentIndex(mode_index)
                dialog.loop_check.setChecked(False)
                dialog._advance()
                dialog._advance()
                self.assertEqual(dialog._index, 2)
                dialog._advance()
                self.assertEqual(dialog._index, 2)
                self.assertFalse(dialog._timer.isActive())
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()

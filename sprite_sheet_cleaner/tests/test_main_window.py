from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from sprite_sheet_cleaner.app.main_window import MainWindow
except ImportError:
    QApplication = None
    QMessageBox = None
    MainWindow = None


@unittest.skipUnless(QApplication is not None and MainWindow is not None, "PySide6 is not installed")
class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_tool_actions_have_icons(self) -> None:
        window = MainWindow()
        try:
            self.assertFalse(window.pointer_action.icon().isNull())
            self.assertFalse(window.select_action.icon().isNull())
            self.assertFalse(window.grid_action.icon().isNull())
        finally:
            window.close()

    def test_open_image_auto_detects_background_color(self) -> None:
        image = Image.new("RGBA", (48, 48), (96, 0, 240, 255))
        for x in range(12, 36):
            for y in range(12, 36):
                image.putpixel((x, y), (20, 120, 30, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "auto-detect-source.png"
            image.save(image_path)

            window = MainWindow()
            try:
                window._load_source_image(image_path, clear_tiles=True)
                settings = window.settings_panel.settings()
            finally:
                window.close()

        self.assertEqual(settings.background_color, (96, 0, 240))
        self.assertEqual(settings.tolerance, 64)

    def test_clear_bucket_button_removes_all_tiles(self) -> None:
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        for x in range(4):
            for y in range(4):
                image.putpixel((x, y), (255, 0, 0, 255))
                image.putpixel((x + 4, y), (0, 255, 0, 255))

        window = MainWindow()
        try:
            window.source_image = image
            window.model.add_tile_from_crop(image, (0, 0, 4, 4))
            window.model.add_tile_from_crop(image, (4, 0, 4, 4))
            window._refresh_all(selected_index=0)

            self.assertTrue(window.bucket_panel.clear_button.isEnabled())
            self.assertEqual(window.bucket_panel.list_widget.count(), 2)

            with patch(
                "sprite_sheet_cleaner.app.main_window.QMessageBox.question",
                return_value=QMessageBox.Yes,
            ):
                window.bucket_panel.clear_button.click()

            self.assertEqual(len(window.model.tiles), 0)
            self.assertEqual(window.bucket_panel.list_widget.count(), 0)
            self.assertFalse(window.bucket_panel.clear_button.isEnabled())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

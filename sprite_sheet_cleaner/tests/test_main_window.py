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
    from sprite_sheet_cleaner.app.models.app_settings import AppSettings
    from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
    from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage
except ImportError:
    QApplication = None
    QMessageBox = None
    MainWindow = None
    AppSettings = None
    pil_to_qimage = None


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
            self.assertFalse(window.retouch_action.icon().isNull())
            self.assertFalse(window.rotate_action.icon().isNull())
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

    def _grid_window(
        self,
        *,
        sheet_columns: int = 2,
        sheet_rows: int = 2,
        image_size: tuple[int, int] = (4, 4),
        tile_size: int = 2,
        match_sheet_to_grid: bool = False,
    ) -> MainWindow:
        window = MainWindow()
        window.source_image = Image.new("RGBA", image_size, (255, 0, 0, 255))
        window.model.settings = AppSettings(
            tile_width=tile_size,
            tile_height=tile_size,
            sheet_columns=sheet_columns,
            sheet_rows=sheet_rows,
            match_sheet_to_grid=match_sheet_to_grid,
            remove_background=False,
        )
        window.settings_panel.set_settings(window.model.settings)
        window._apply_selection_geometry()
        window.source_viewer.set_image(pil_to_qimage(window.source_image))
        window._sync_sheet_to_grid()
        window._set_viewer_tool("grid")
        window._refresh_all()
        return window

    def test_add_all_adds_each_grid_cell_and_skips_existing_tiles(self) -> None:
        window = self._grid_window()
        try:
            window.model.add_tile_from_crop(window.source_image, (0, 0, 2, 2))
            window._refresh_all()

            window._add_all_grid_cells()

            self.assertEqual(
                [tile.source_rect for tile in window.model.tiles],
                [(0, 0, 2, 2), (2, 0, 2, 2), (0, 2, 2, 2), (2, 2, 2, 2)],
            )
        finally:
            window.close()

    def test_add_all_capacity_failure_adds_nothing(self) -> None:
        window = self._grid_window(sheet_columns=1, sheet_rows=2)
        try:
            with patch("sprite_sheet_cleaner.app.main_window.QMessageBox.warning") as warning:
                window._add_all_grid_cells()

            self.assertEqual(window.model.tiles, [])
            warning.assert_called_once()
            self.assertIn("requires 4 empty slots", warning.call_args.args[2])
        finally:
            window.close()

    def test_grid_drag_selection_adds_on_request_then_clears(self) -> None:
        window = self._grid_window()
        try:
            window.source_viewer._set_grid_selection_range((0, 0), (1, 0))

            window._add_selection_to_bucket()

            self.assertEqual([tile.source_rect for tile in window.model.tiles], [(0, 0, 2, 2), (2, 0, 2, 2)])
            self.assertEqual(window.source_viewer.selected_grid_rects(), [])
        finally:
            window.close()

    def test_grid_drag_never_changes_matched_final_sheet_dimensions(self) -> None:
        window = self._grid_window(
            sheet_columns=1,
            sheet_rows=1,
            image_size=(38, 38),
            tile_size=2,
            match_sheet_to_grid=True,
        )
        try:
            window.model.settings.selection_columns = 1
            window.model.settings.selection_rows = 1
            window.settings_panel.set_settings(window.model.settings)

            self.assertEqual(window.source_viewer.grid_dimensions(), (19, 19))
            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (19, 19))

            window.source_viewer._set_grid_selection_range((0, 0), (1, 1))

            self.assertEqual(len(window.source_viewer.selected_grid_rects()), 4)
            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (19, 19))
            self.assertEqual((window.settings_panel.sheet_columns.value(), window.settings_panel.sheet_rows.value()), (19, 19))
        finally:
            window.close()

    def test_match_grid_preserves_last_size_while_invalid_then_resynchronizes(self) -> None:
        window = self._grid_window(match_sheet_to_grid=True)
        try:
            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (2, 2))

            window.settings_panel.tile_width.setValue(8)
            self.assertIsNone(window.source_viewer.grid_dimensions())
            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (2, 2))
            self.assertFalse(window.settings_panel.sheet_columns.isEnabled())

            window.settings_panel.tile_width.setValue(1)
            self.assertEqual(window.source_viewer.grid_dimensions(), (4, 4))
            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (4, 4))
        finally:
            window.close()

    def test_match_grid_capacity_shrink_preserves_tiles_and_can_recover(self) -> None:
        window = self._grid_window(
            sheet_columns=4,
            sheet_rows=4,
            tile_size=1,
            match_sheet_to_grid=True,
        )
        try:
            window._add_all_grid_cells()
            self.assertEqual(len(window.model.tiles), 16)

            window.settings_panel.tile_width.setValue(2)

            self.assertEqual((window.model.settings.sheet_columns, window.model.settings.sheet_rows), (2, 2))
            self.assertEqual(len(window.model.tiles), 16)
            self.assertIn("Overflow: 12", window.final_preview.info_label.text())
            self.assertFalse(window.settings_panel.add_button.isEnabled())
            self.assertFalse(window.settings_panel.add_all_button.isEnabled())

            with patch("sprite_sheet_cleaner.app.main_window.QMessageBox.warning") as warning:
                window._export_sheet()
            warning.assert_called_once()

            window.settings_panel.match_sheet_to_grid.setChecked(False)
            window.settings_panel.sheet_columns.setValue(5)
            window.settings_panel.sheet_rows.setValue(4)

            self.assertNotIn("Overflow:", window.final_preview.info_label.text())
            self.assertTrue(window.settings_panel.add_button.isEnabled())
        finally:
            window.close()

    def test_bucket_output_resize_is_independent_and_undoable(self) -> None:
        window = MainWindow()
        try:
            image = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
            window.source_image = image
            window.model.settings = AppSettings(
                tile_width=4,
                tile_height=4,
                bucket_tile_width=4,
                bucket_tile_height=4,
                bucket_resize_mode="fit",
                remove_background=False,
                edge_bleed=0,
            ).validated()
            window.settings_panel.set_settings(window.model.settings)
            window.model.add_tile_from_crop(image, (0, 0, 4, 4))
            window._refresh_all(selected_index=0)

            window.settings_panel.bucket_tile_width.setValue(2)

            self.assertEqual((window.model.settings.tile_width, window.model.settings.tile_height), (4, 4))
            self.assertEqual(
                (window.model.settings.bucket_tile_width, window.model.settings.bucket_tile_height),
                (2, 2),
            )
            self.assertEqual(window.model.tiles[0].image_rgba.size, (2, 2))

            window._undo_bucket()

            self.assertEqual(
                (window.model.settings.bucket_tile_width, window.model.settings.bucket_tile_height),
                (4, 4),
            )
            self.assertEqual(window.model.tiles[0].image_rgba.size, (4, 4))
        finally:
            window.close()

    def test_rotate_tool_stages_apply_and_undo(self) -> None:
        window = MainWindow()
        try:
            image = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
            image.putpixel((3, 2), (255, 0, 0, 255))
            window.source_image = image
            window.model.settings = AppSettings(
                tile_width=5,
                tile_height=5,
                bucket_tile_width=5,
                bucket_tile_height=5,
                bucket_resize_mode="none",
                remove_background=False,
                edge_bleed=0,
            ).validated()
            window.model.add_tile_from_crop(image, (0, 0, 5, 5))
            window._refresh_all(selected_index=0)

            window._set_viewer_tool("rotate")
            window._tile_transform_preview_changed(
                TileTransform(angle_degrees=90, resample_mode="nearest")
            )

            self.assertEqual(window.source_viewer.current_tool(), "rotate")
            self.assertEqual(window.model.tiles[0].transform.angle_degrees, 0.0)
            self.assertTrue(window._transform_dirty)

            window._apply_tile_transform()

            self.assertEqual(window.model.tiles[0].transform.angle_degrees, 90.0)
            self.assertEqual(window.model.tiles[0].image_rgba.getpixel((2, 3)), (255, 0, 0, 255))

            window._undo_bucket()
            self.assertEqual(window.model.tiles[0].transform.angle_degrees, 0.0)
        finally:
            window.close()

    def test_fit_rotated_content_prevents_full_canvas_clipping(self) -> None:
        window = MainWindow()
        try:
            image = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
            window.source_image = image
            window.model.settings = AppSettings(
                tile_width=20,
                tile_height=20,
                bucket_tile_width=20,
                bucket_tile_height=20,
                bucket_resize_mode="none",
                remove_background=False,
                edge_bleed=0,
            ).validated()
            window.model.add_tile_from_crop(image, (0, 0, 20, 20))
            window._refresh_all(selected_index=0)
            window._set_viewer_tool("rotate")
            window._tile_transform_preview_changed(TileTransform(angle_degrees=45))

            self.assertTrue(window._transform_is_clipped(window.model.tiles[0], window._transform_working))

            window._fit_rotated_content()

            self.assertAlmostEqual(window._transform_working.scale_x, 2 ** -0.5, places=5)
            self.assertFalse(window._transform_is_clipped(window.model.tiles[0], window._transform_working))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

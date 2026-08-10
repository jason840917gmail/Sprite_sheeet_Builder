from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.widgets.settings_panel import SettingsPanel
except ImportError:
    QApplication = None
    SettingsPanel = None


@unittest.skipUnless(QApplication is not None and SettingsPanel is not None, "PySide6 is not installed")
class SettingsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_selection_grid_row_is_only_available_for_select_tool(self) -> None:
        panel = SettingsPanel()

        panel.set_action_context("select", True, 0, 10)
        self.assertFalse(panel.selection_grid_field.isHidden())
        self.assertFalse(panel._selection_grid_label.isHidden())

        panel.set_action_context("grid", True, 0, 10)
        self.assertTrue(panel.selection_grid_field.isHidden())
        self.assertTrue(panel._selection_grid_label.isHidden())

        panel.set_action_context("pointer", True, 0, 10)
        self.assertTrue(panel.selection_grid_field.isHidden())
        self.assertTrue(panel._selection_grid_label.isHidden())

    def test_match_grid_checkbox_uses_external_grid_dimensions_not_selection_grid(self) -> None:
        panel = SettingsPanel()
        panel.selection_columns.setValue(4)
        panel.selection_rows.setValue(3)

        panel.match_sheet_to_grid.setChecked(True)

        self.assertFalse(panel.sheet_columns.isEnabled())
        self.assertFalse(panel.sheet_rows.isEnabled())

        panel.set_matched_sheet_dimensions(19, 19)

        panel.selection_columns.setValue(7)
        panel.selection_rows.setValue(2)

        self.assertEqual((panel.sheet_columns.value(), panel.sheet_rows.value()), (19, 19))
        self.assertEqual((panel.settings().sheet_columns, panel.settings().sheet_rows), (19, 19))
        self.assertTrue(panel.settings().match_sheet_to_grid)

        panel.match_sheet_to_grid.setChecked(False)
        self.assertTrue(panel.sheet_columns.isEnabled())
        self.assertTrue(panel.sheet_rows.isEnabled())

    def test_add_all_is_only_visible_and_enabled_in_valid_grid_context(self) -> None:
        panel = SettingsPanel()

        panel.set_action_context("select", True, 0, 10)
        self.assertTrue(panel.add_all_button.isHidden())

        panel.set_action_context("grid", False, 0, 10)
        self.assertFalse(panel.add_all_button.isHidden())
        self.assertFalse(panel.add_all_button.isEnabled())

        panel.set_action_context("grid", True, 0, 10)
        self.assertTrue(panel.add_all_button.isEnabled())

        panel.set_action_context("grid", True, 10, 10)
        self.assertFalse(panel.add_all_button.isEnabled())

    def test_tile_remover_is_persisted_and_rembg_blocks_add_all(self) -> None:
        panel = SettingsPanel()

        panel.tile_background_engine.setCurrentIndex(panel.tile_background_engine.findData("rembg"))
        self.assertEqual(panel.settings().tile_background_engine, "rembg")

        panel.set_action_context("grid", True, 0, 10)
        self.assertFalse(panel.add_all_button.isEnabled())

        panel.remove_background.setChecked(False)
        self.assertFalse(panel.tile_background_engine.isEnabled())
        panel.set_action_context("grid", True, 0, 10)
        self.assertTrue(panel.add_all_button.isEnabled())

    def test_source_and_bucket_dimensions_are_independent(self) -> None:
        panel = SettingsPanel()
        panel.lock_tile_aspect.setChecked(False)
        panel.lock_bucket_aspect.setChecked(False)

        panel.tile_width.setValue(256)
        panel.tile_height.setValue(128)
        panel.bucket_tile_width.setValue(64)
        panel.bucket_tile_height.setValue(32)

        settings = panel.settings()
        self.assertEqual((settings.tile_width, settings.tile_height), (256, 128))
        self.assertEqual((settings.bucket_tile_width, settings.bucket_tile_height), (64, 32))
        self.assertEqual(settings.bucket_resize_mode, "fit")

    def test_bucket_symmetry_does_not_change_source_selection(self) -> None:
        panel = SettingsPanel()
        panel.tile_width.setValue(256)
        panel.bucket_tile_width.setValue(64)

        self.assertEqual(panel.bucket_tile_height.value(), 64)
        self.assertEqual(panel.tile_width.value(), 256)


if __name__ == "__main__":
    unittest.main()

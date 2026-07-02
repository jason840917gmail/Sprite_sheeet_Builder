from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from sprite_sheet_cleaner.app.models.app_settings import AppSettings


class SettingsPanel(QWidget):
    settingsChanged = Signal(object)
    addSelectionRequested = Signal()
    detectBackgroundRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._background_color = (255, 0, 255)
        self._updating = False
        self._last_tile_dimension = "width"

        self.tile_width = self._spin(1, 4096, 256)
        self.tile_height = self._spin(1, 4096, 256)
        self.tile_width.setMaximumWidth(88)
        self.tile_height.setMaximumWidth(88)
        self.tile_width.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.tile_height.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.lock_tile_aspect = QCheckBox("Sym")
        self.lock_tile_aspect.setChecked(True)
        self.lock_tile_aspect.setToolTip("Sym")
        self.selection_columns = self._spin(1, 128, 1)
        self.selection_rows = self._spin(1, 128, 1)
        self.selection_columns.setMaximumWidth(72)
        self.selection_rows.setMaximumWidth(72)
        self.selection_columns.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.selection_rows.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sheet_columns = self._spin(1, 128, 8)
        self.sheet_rows = self._spin(1, 128, 8)
        self.sheet_columns.setMaximumWidth(72)
        self.sheet_rows.setMaximumWidth(72)
        self.sheet_columns.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sheet_rows.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.remove_background = QCheckBox()
        self.remove_background.setChecked(True)
        self.color_button = QPushButton()
        self.color_button.setFixedWidth(72)
        self.detect_color_button = QPushButton("Detect")
        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 255)
        self.tolerance_slider.setValue(30)
        self.tolerance_spin = self._spin(0, 255, 30)
        self.tolerance_spin.setMaximumWidth(72)
        self.tolerance_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.trim_transparent = QCheckBox()
        self.trim_transparent.setChecked(False)
        self.scale_mode = QComboBox()
        self.scale_mode.addItem("None", "none")
        self.scale_mode.addItem("Scale down only", "scale_down_only")
        self.scale_mode.addItem("Scale to fit", "scale_to_fit")
        self.scale_mode.setCurrentIndex(0)
        self.padding = self._spin(0, 512, 0)
        self.anchor = QComboBox()
        self.anchor.addItem("Center", "center")
        self.anchor.addItem("Bottom-center", "bottom-center")
        self.add_button = QPushButton("Add Selection to Bucket")

        tolerance_row = QHBoxLayout()
        tolerance_row.setContentsMargins(0, 0, 0, 0)
        tolerance_row.setSpacing(6)
        tolerance_row.addWidget(self.tolerance_slider, 1)
        tolerance_row.addWidget(self.tolerance_spin)

        tile_size_row = QHBoxLayout()
        tile_size_row.setContentsMargins(0, 0, 0, 0)
        tile_size_row.setSpacing(6)
        tile_size_row.addWidget(self.tile_width)
        tile_size_row.addWidget(self.lock_tile_aspect)
        tile_size_row.addWidget(self.tile_height)
        tile_size_row.addStretch(1)

        selection_grid_row = QHBoxLayout()
        selection_grid_row.setContentsMargins(0, 0, 0, 0)
        selection_grid_row.setSpacing(6)
        selection_grid_row.addWidget(self.selection_columns)
        selection_grid_row.addWidget(QLabel("x"))
        selection_grid_row.addWidget(self.selection_rows)
        selection_grid_row.addStretch(1)

        final_tilesheet_row = QHBoxLayout()
        final_tilesheet_row.setContentsMargins(0, 0, 0, 0)
        final_tilesheet_row.setSpacing(6)
        final_tilesheet_row.addWidget(self.sheet_columns)
        final_tilesheet_row.addWidget(QLabel("x"))
        final_tilesheet_row.addWidget(self.sheet_rows)
        final_tilesheet_row.addStretch(1)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(6)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.detect_color_button)
        color_row.addStretch(1)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Tile / selection size", tile_size_row)
        form.addRow("Selection grid", selection_grid_row)
        form.addRow("Remove background", self.remove_background)
        form.addRow("Background color", color_row)
        form.addRow("Tolerance", tolerance_row)
        form.addRow("Trim transparent", self.trim_transparent)
        form.addRow("Scale mode", self.scale_mode)
        form.addRow("Padding", self.padding)
        form.addRow("Anchor", self.anchor)

        final_form = QFormLayout()
        final_form.setContentsMargins(0, 0, 0, 0)
        final_form.setHorizontalSpacing(10)
        final_form.setVerticalSpacing(8)
        final_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        final_form.addRow("Final tilesheet", final_tilesheet_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel("Settings")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self.add_button)
        layout.addLayout(final_form)
        layout.addStretch(1)

        self._update_color_button()
        self._connect_signals()

    def settings(self) -> AppSettings:
        return AppSettings(
            tile_width=self.tile_width.value(),
            tile_height=self.tile_height.value(),
            lock_tile_aspect=self.lock_tile_aspect.isChecked(),
            selection_columns=self.selection_columns.value(),
            selection_rows=self.selection_rows.value(),
            sheet_columns=self.sheet_columns.value(),
            sheet_rows=self.sheet_rows.value(),
            remove_background=self.remove_background.isChecked(),
            background_color=self._background_color,
            tolerance=self.tolerance_spin.value(),
            trim_transparent=self.trim_transparent.isChecked(),
            scale_mode=self.scale_mode.currentData(),
            padding=self.padding.value(),
            anchor=self.anchor.currentData(),
        ).validated()

    def set_settings(self, settings: AppSettings) -> None:
        self._updating = True
        self.tile_width.setValue(settings.tile_width)
        self.tile_height.setValue(settings.tile_height)
        self.lock_tile_aspect.setChecked(settings.lock_tile_aspect)
        self.selection_columns.setValue(settings.selection_columns)
        self.selection_rows.setValue(settings.selection_rows)
        self.sheet_columns.setValue(settings.sheet_columns)
        self.sheet_rows.setValue(settings.sheet_rows)
        self.remove_background.setChecked(settings.remove_background)
        self._background_color = settings.background_color
        self.tolerance_slider.setValue(settings.tolerance)
        self.tolerance_spin.setValue(settings.tolerance)
        self.trim_transparent.setChecked(settings.trim_transparent)
        scale_index = self.scale_mode.findData(settings.scale_mode)
        self.scale_mode.setCurrentIndex(max(scale_index, 0))
        self.padding.setValue(settings.padding)
        anchor_index = self.anchor.findData(settings.anchor)
        self.anchor.setCurrentIndex(max(anchor_index, 0))
        self._update_color_button()
        self._updating = False

    def set_detected_background_color(self, color: tuple[int, int, int], *, minimum_tolerance: int = 64) -> None:
        self._updating = True
        self._background_color = color
        self.remove_background.setChecked(True)
        if self.tolerance_spin.value() < minimum_tolerance:
            self.tolerance_slider.setValue(minimum_tolerance)
            self.tolerance_spin.setValue(minimum_tolerance)
        self._update_color_button()
        self._updating = False
        self._emit_settings_changed()

    def set_bucket_capacity_state(self, tile_count: int, capacity: int) -> None:
        if tile_count >= capacity:
            self.add_button.setEnabled(False)
            self.add_button.setText(f"Bucket Full ({tile_count}/{capacity})")
        else:
            self.add_button.setEnabled(True)
            self.add_button.setText("Add Selection to Bucket")

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _connect_signals(self) -> None:
        self.color_button.clicked.connect(self._choose_color)
        self.detect_color_button.clicked.connect(self.detectBackgroundRequested.emit)
        self.add_button.clicked.connect(self.addSelectionRequested.emit)
        self.tolerance_slider.valueChanged.connect(self.tolerance_spin.setValue)
        self.tolerance_spin.valueChanged.connect(self.tolerance_slider.setValue)

        for control in (
            self.selection_columns,
            self.selection_rows,
            self.sheet_columns,
            self.sheet_rows,
            self.tolerance_slider,
            self.tolerance_spin,
            self.padding,
        ):
            control.valueChanged.connect(self._emit_settings_changed)

        for control in (self.remove_background, self.trim_transparent):
            control.toggled.connect(self._emit_settings_changed)

        for control in (self.scale_mode, self.anchor):
            control.currentIndexChanged.connect(self._emit_settings_changed)

        self.tile_width.valueChanged.connect(self._tile_width_changed)
        self.tile_height.valueChanged.connect(self._tile_height_changed)
        self.lock_tile_aspect.toggled.connect(self._tile_lock_toggled)

    def _choose_color(self) -> None:
        current = QColor(*self._background_color)
        color = QColorDialog.getColor(current, self, "Background color")
        if color.isValid():
            self._background_color = (color.red(), color.green(), color.blue())
            self._update_color_button()
            self._emit_settings_changed()

    def _update_color_button(self) -> None:
        r, g, b = self._background_color
        self.color_button.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.color_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'black' if (r + g + b) > 382 else 'white'};"
        )

    def _tile_width_changed(self, value: int) -> None:
        self._last_tile_dimension = "width"
        self._sync_tile_dimensions("width", value)
        self._emit_settings_changed()

    def _tile_height_changed(self, value: int) -> None:
        self._last_tile_dimension = "height"
        self._sync_tile_dimensions("height", value)
        self._emit_settings_changed()

    def _tile_lock_toggled(self, checked: bool) -> None:
        if checked:
            source_value = self.tile_width.value() if self._last_tile_dimension == "width" else self.tile_height.value()
            self._sync_tile_dimensions(self._last_tile_dimension, source_value)
        self._emit_settings_changed()

    def _sync_tile_dimensions(self, changed: str, value: int) -> None:
        if self._updating or not self.lock_tile_aspect.isChecked():
            return

        self._updating = True
        if changed == "width" and self.tile_height.value() != value:
            self.tile_height.setValue(value)
        elif changed == "height" and self.tile_width.value() != value:
            self.tile_width.setValue(value)
        self._updating = False

    def _emit_settings_changed(self) -> None:
        if not self._updating:
            self.settingsChanged.emit(self.settings())

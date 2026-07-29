from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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

from sprite_sheet_cleaner.app.models.video_settings import VideoSettings


class VideoSettingsPanel(QWidget):
    """Controls for converting video frames into final sprite tiles."""

    settingsChanged = Signal(object)
    detectBackgroundRequested = Signal()
    applyToBucketRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._background_color = (255, 0, 255)
        self._updating = False

        self.frame_width = self._spin(1, 4096, 64)
        self.frame_height = self._spin(1, 4096, 64)
        self.frame_width.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.frame_height.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.frame_width.setMaximumWidth(86)
        self.frame_height.setMaximumWidth(86)
        self.lock_frame_aspect = QCheckBox("Sym")
        self.lock_frame_aspect.setChecked(True)

        self.resize_mode = QComboBox()
        self.resize_mode.addItem("Fit (preserve aspect)", "fit")
        self.resize_mode.addItem("Stretch (exact dimensions)", "stretch")
        self.resize_mode.addItem("Fill / crop", "fill")
        self.remove_background = QCheckBox()
        self.remove_background.setChecked(True)
        self.color_button = QPushButton()
        self.color_button.setFixedWidth(78)
        self.detect_color_button = QPushButton("Detect")
        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 255)
        self.tolerance_slider.setValue(30)
        self.tolerance_spin = self._spin(0, 255, 30)
        self.tolerance_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.tolerance_spin.setMaximumWidth(72)
        self.trim_transparent = QCheckBox()
        self.anchor = QComboBox()
        self.anchor.addItem("Center", "center")
        self.anchor.addItem("Bottom-center", "bottom-center")
        self.sheet_columns = self._spin(1, 128, 8)
        self.sheet_rows = self._spin(1, 128, 8)
        self.seed_frame_count = self._spin(1, 64, 10)
        self.apply_button = QPushButton("Apply to Existing Video Tiles")

        frame_size_row = QHBoxLayout()
        frame_size_row.setContentsMargins(0, 0, 0, 0)
        frame_size_row.setSpacing(6)
        frame_size_row.addWidget(self.frame_width)
        frame_size_row.addWidget(self.lock_frame_aspect)
        frame_size_row.addWidget(self.frame_height)
        frame_size_row.addWidget(QLabel("pixels"))
        frame_size_row.addStretch(1)

        tolerance_row = QHBoxLayout()
        tolerance_row.setContentsMargins(0, 0, 0, 0)
        tolerance_row.setSpacing(6)
        tolerance_row.addWidget(self.tolerance_slider, 1)
        tolerance_row.addWidget(self.tolerance_spin)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(6)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.detect_color_button)
        color_row.addStretch(1)

        sheet_row = QHBoxLayout()
        sheet_row.setContentsMargins(0, 0, 0, 0)
        sheet_row.setSpacing(6)
        sheet_row.addWidget(self.sheet_columns)
        sheet_row.addWidget(QLabel("x"))
        sheet_row.addWidget(self.sheet_rows)
        sheet_row.addStretch(1)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Frame output size", frame_size_row)
        form.addRow("Resize mode", self.resize_mode)
        form.addRow("Remove background", self.remove_background)
        form.addRow("Background color", color_row)
        form.addRow("Tolerance", tolerance_row)
        form.addRow("Trim transparent", self.trim_transparent)
        form.addRow("Anchor", self.anchor)
        form.addRow("Seed animation frames", self.seed_frame_count)
        form.addRow("Final tilesheet", sheet_row)

        title = QLabel("Video Tool")
        title.setStyleSheet("font-weight: 600;")
        description = QLabel(
            "Each clicked frame is added immediately. These controls define how new video frames become game-ready tiles."
        )
        description.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addWidget(self.apply_button)
        layout.addStretch(1)

        self._update_color_button()
        self._connect_signals()

    def settings(self) -> VideoSettings:
        return VideoSettings(
            frame_width=self.frame_width.value(),
            frame_height=self.frame_height.value(),
            lock_frame_aspect=self.lock_frame_aspect.isChecked(),
            resize_mode=self.resize_mode.currentData(),
            remove_background=self.remove_background.isChecked(),
            background_color=self._background_color,
            tolerance=self.tolerance_spin.value(),
            trim_transparent=self.trim_transparent.isChecked(),
            anchor=self.anchor.currentData(),
            sheet_columns=self.sheet_columns.value(),
            sheet_rows=self.sheet_rows.value(),
            seed_frame_count=self.seed_frame_count.value(),
        ).validated()

    def set_settings(self, settings: VideoSettings) -> None:
        settings.validated()
        self._updating = True
        self.frame_width.setValue(settings.frame_width)
        self.frame_height.setValue(settings.frame_height)
        self.lock_frame_aspect.setChecked(settings.lock_frame_aspect)
        resize_index = self.resize_mode.findData(settings.resize_mode)
        self.resize_mode.setCurrentIndex(max(resize_index, 0))
        self.remove_background.setChecked(settings.remove_background)
        self._background_color = settings.background_color
        self.tolerance_slider.setValue(settings.tolerance)
        self.tolerance_spin.setValue(settings.tolerance)
        self.trim_transparent.setChecked(settings.trim_transparent)
        anchor_index = self.anchor.findData(settings.anchor)
        self.anchor.setCurrentIndex(max(anchor_index, 0))
        self.sheet_columns.setValue(settings.sheet_columns)
        self.sheet_rows.setValue(settings.sheet_rows)
        self.seed_frame_count.setValue(settings.seed_frame_count)
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

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _connect_signals(self) -> None:
        self.color_button.clicked.connect(self._choose_color)
        self.detect_color_button.clicked.connect(self.detectBackgroundRequested.emit)
        self.apply_button.clicked.connect(self.applyToBucketRequested.emit)
        self.tolerance_slider.valueChanged.connect(self.tolerance_spin.setValue)
        self.tolerance_spin.valueChanged.connect(self.tolerance_slider.setValue)

        for control in (
            self.frame_width,
            self.frame_height,
            self.sheet_columns,
            self.sheet_rows,
            self.seed_frame_count,
            self.tolerance_slider,
            self.tolerance_spin,
        ):
            control.valueChanged.connect(self._emit_settings_changed)
        for control in (self.lock_frame_aspect, self.remove_background, self.trim_transparent):
            control.toggled.connect(self._emit_settings_changed)
        for control in (self.resize_mode, self.anchor):
            control.currentIndexChanged.connect(self._emit_settings_changed)
        self.frame_width.valueChanged.connect(lambda value: self._sync_frame_dimensions("width", value))
        self.frame_height.valueChanged.connect(lambda value: self._sync_frame_dimensions("height", value))
        self.lock_frame_aspect.toggled.connect(self._lock_aspect_toggled)

    def _choose_color(self) -> None:
        current = QColor(*self._background_color)
        color = QColorDialog.getColor(current, self, "Video background color")
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

    def _sync_frame_dimensions(self, changed: str, value: int) -> None:
        if self._updating or not self.lock_frame_aspect.isChecked():
            return
        self._updating = True
        if changed == "width":
            self.frame_height.setValue(value)
        else:
            self.frame_width.setValue(value)
        self._updating = False

    def _lock_aspect_toggled(self, checked: bool) -> None:
        if checked:
            self._updating = True
            self.frame_height.setValue(self.frame_width.value())
            self._updating = False
        self._emit_settings_changed()

    def _emit_settings_changed(self, *_args) -> None:
        if not self._updating:
            self.settingsChanged.emit(self.settings())

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.models.source_processing_settings import SourceProcessingSettings


class SourceBackgroundPanel(QWidget):
    settingsChanged = Signal(object)
    applyRequested = Signal()
    activateRequested = Signal()
    discardRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        self._background_color = (255, 0, 255)

        self.engine = QComboBox()
        self.engine.addItem("Exact Key", "exact_key")
        self.engine.addItem("Smart Solid", "smart_solid")
        self.engine.addItem("rembg (install model)", "rembg")
        self.engine.addItem("BEN2 (install model)", "ben2")
        for index in (2, 3):
            self.engine.model().item(index).setEnabled(False)
        self.engine.setToolTip("Optional AI engines become available after Model Manager installation.")

        self.color_button = QPushButton()
        self.color_button.setFixedWidth(82)
        self.detect_button = QPushButton("Detect")
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 255)
        self.tolerance.setValue(30)
        self.transparent_threshold = QSpinBox()
        self.transparent_threshold.setRange(0, 255)
        self.transparent_threshold.setValue(24)
        self.foreground_threshold = QSpinBox()
        self.foreground_threshold.setRange(1, 255)
        self.foreground_threshold.setValue(64)
        self.apply_button = QPushButton("Apply to Source")
        self.activate_button = QPushButton("Activate Revision")
        self.discard_button = QPushButton("Discard Candidate")
        self.cancel_button = QPushButton("Cancel")
        self.activate_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status_label = QLabel("Original source is active")
        self.status_label.setWordWrap(True)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.detect_button)
        color_row.addStretch(1)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Engine", self.engine)
        form.addRow("Background", color_row)
        form.addRow("Exact tolerance", self.tolerance)
        form.addRow("Transparent threshold", self.transparent_threshold)
        form.addRow("Foreground threshold", self.foreground_threshold)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.activate_button)
        actions.addWidget(self.discard_button)
        actions.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Source Background")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)

        self.color_button.clicked.connect(self._choose_color)
        self.detect_button.clicked.connect(self._show_detection_hint)
        self.engine.currentIndexChanged.connect(self._emit_settings_changed)
        self.tolerance.valueChanged.connect(self._emit_settings_changed)
        self.transparent_threshold.valueChanged.connect(self._emit_settings_changed)
        self.foreground_threshold.valueChanged.connect(self._emit_settings_changed)
        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.activate_button.clicked.connect(self.activateRequested.emit)
        self.discard_button.clicked.connect(self.discardRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self._update_color_button()

    def settings(self) -> SourceProcessingSettings:
        return SourceProcessingSettings(
            engine=self.engine.currentData(),
            background_color=self._background_color,
            tolerance=self.tolerance.value(),
            transparent_threshold=self.transparent_threshold.value(),
            foreground_threshold=self.foreground_threshold.value(),
        ).validated()

    def set_background_color(self, color: tuple[int, int, int]) -> None:
        self._background_color = tuple(int(channel) for channel in color)
        self._update_color_button()

    def set_candidate_state(self, ready: bool, message: str) -> None:
        self.activate_button.setEnabled(ready)
        self.discard_button.setEnabled(ready)
        self.status_label.setText(message)

    def set_job_running(self, running: bool, message: str = "") -> None:
        self.apply_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.engine.setEnabled(not running)
        self.color_button.setEnabled(not running)
        self.detect_button.setEnabled(not running)
        self.tolerance.setEnabled(not running)
        self.transparent_threshold.setEnabled(not running)
        self.foreground_threshold.setEnabled(not running)
        if message:
            self.status_label.setText(message)

    def _show_detection_hint(self) -> None:
        self.status_label.setText("Use Detect in the source toolbar to sample the current source border.")

    def _choose_color(self) -> None:
        current = QColor(*self._background_color)
        color = QColorDialog.getColor(current, self, "Background color")
        if not color.isValid():
            return
        self._background_color = (color.red(), color.green(), color.blue())
        self._update_color_button()
        self._emit_settings_changed()

    def _update_color_button(self) -> None:
        r, g, b = self._background_color
        self.color_button.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.color_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'black' if (r + g + b) > 382 else 'white'};"
        )

    def _emit_settings_changed(self, *_args) -> None:
        if not self._updating:
            self.settingsChanged.emit(self.settings())

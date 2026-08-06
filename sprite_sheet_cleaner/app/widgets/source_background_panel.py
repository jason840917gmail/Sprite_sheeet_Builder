from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.models.source_processing_settings import SourceProcessingSettings


class SourceBackgroundPanel(QWidget):
    settingsChanged = Signal(object)
    detectRequested = Signal()
    applyRequested = Signal()
    applyToBucketRequested = Signal()
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
        self.engine.setToolTip(
            "Choose how the source background is removed. Exact Key is for a known flat color; "
            "Smart Solid follows connected border background; rembg and BEN2 are optional AI engines. "
            "rembg/U2Net is intended for one isolated tile or object, not a complete sprite sheet."
        )
        self.compute = QComboBox()
        self.compute.addItem("Auto (CUDA, then CPU)", "auto")
        self.compute.addItem("NVIDIA CUDA only", "cuda")
        self.compute.addItem("CPU only", "cpu")
        self.compute.setToolTip(
            "Auto tries NVIDIA CUDA first and falls back to CPU. CUDA-only reports configuration problems "
            "instead of falling back."
        )

        self.color_button = QPushButton()
        self.color_button.setFixedWidth(82)
        self.color_button.setToolTip("Background color used by color-based removal engines.")
        self.detect_button = QPushButton("Detect")
        self.detect_button.setToolTip("Sample the current source border and set the background color automatically.")
        self.tolerance = QSlider(Qt.Horizontal)
        self.tolerance.setRange(0, 255)
        self.tolerance.setValue(30)
        self.tolerance.setToolTip("Exact Key color distance. Higher values remove a wider range of similar colors.")
        self.tolerance_value = QLabel()
        self.tolerance_value.setMinimumWidth(36)
        self.tolerance_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.transparent_threshold = QSlider(Qt.Horizontal)
        self.transparent_threshold.setRange(0, 255)
        self.transparent_threshold.setValue(24)
        self.transparent_threshold.setToolTip("Alpha below this value becomes fully transparent.")
        self.transparent_threshold_value = QLabel()
        self.transparent_threshold_value.setMinimumWidth(36)
        self.transparent_threshold_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.foreground_threshold = QSlider(Qt.Horizontal)
        self.foreground_threshold.setRange(1, 255)
        self.foreground_threshold.setValue(64)
        self.foreground_threshold.setToolTip("Alpha above this value stays solid; the middle range is feathered.")
        self.foreground_threshold_value = QLabel()
        self.foreground_threshold_value.setMinimumWidth(36)
        self.foreground_threshold_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.apply_button = QPushButton("Process")
        self.apply_button.setToolTip(
            "Process Source — create a reviewable candidate. The original source remains unchanged."
        )
        self.activate_button = QPushButton("Activate")
        self.activate_button.setToolTip(
            "Activate Revision — use the reviewed candidate for future tile extraction. Existing tiles stay unchanged."
        )
        self.apply_bucket_button = QPushButton("To Bucket")
        self.apply_bucket_button.setToolTip(
            "Apply to Bucket — reprocess existing bucket tiles with this candidate without activating it globally."
        )
        self.discard_button = QPushButton("Discard")
        self.discard_button.setToolTip("Discard Candidate — remove the pending candidate and keep the original active.")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setToolTip("Cancel the running background-removal job.")
        self.activate_button.setEnabled(False)
        self.apply_bucket_button.setEnabled(False)
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
        form.addRow("Compute", self.compute)
        form.addRow("Background", color_row)
        form.addRow("Exact tolerance", self._slider_row(self.tolerance, self.tolerance_value))
        form.addRow(
            "Transparent threshold",
            self._slider_row(self.transparent_threshold, self.transparent_threshold_value),
        )
        form.addRow(
            "Foreground threshold",
            self._slider_row(self.foreground_threshold, self.foreground_threshold_value),
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.activate_button)
        actions.addWidget(self.apply_bucket_button)
        actions.addWidget(self.discard_button)
        actions.addWidget(self.cancel_button)
        for button in (
            self.apply_button,
            self.activate_button,
            self.apply_bucket_button,
            self.discard_button,
            self.cancel_button,
        ):
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Source Background")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)

        self.color_button.clicked.connect(self._choose_color)
        self.detect_button.clicked.connect(self.detectRequested.emit)
        self.engine.currentIndexChanged.connect(self._emit_settings_changed)
        self.compute.currentIndexChanged.connect(self._emit_settings_changed)
        self.tolerance.valueChanged.connect(self._emit_settings_changed)
        self.transparent_threshold.valueChanged.connect(self._emit_settings_changed)
        self.foreground_threshold.valueChanged.connect(self._emit_settings_changed)
        self.tolerance.valueChanged.connect(self._update_threshold_labels)
        self.transparent_threshold.valueChanged.connect(self._update_threshold_labels)
        self.foreground_threshold.valueChanged.connect(self._update_threshold_labels)
        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.activate_button.clicked.connect(self.activateRequested.emit)
        self.apply_bucket_button.clicked.connect(self.applyToBucketRequested.emit)
        self.discard_button.clicked.connect(self.discardRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self._update_color_button()
        self._update_threshold_labels()

    def set_engine_available(self, engine_id: str, available: bool) -> None:
        for index in range(self.engine.count()):
            if self.engine.itemData(index) == engine_id:
                item = self.engine.model().item(index)
                if item is not None:
                    item.setEnabled(available)
                label = "rembg" if engine_id == "rembg" else "BEN2"
                self.engine.setItemText(index, label if available else f"{label} (install model)")
                return

    def settings(self) -> SourceProcessingSettings:
        return SourceProcessingSettings(
            engine=self.engine.currentData(),
            compute=self.compute.currentData(),
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
        self.apply_bucket_button.setEnabled(ready)
        self.discard_button.setEnabled(ready)
        self.status_label.setText(message)

    def set_job_running(self, running: bool, message: str = "") -> None:
        self.apply_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.engine.setEnabled(not running)
        self.apply_bucket_button.setEnabled(not running and self.discard_button.isEnabled())
        self.compute.setEnabled(not running)
        self.color_button.setEnabled(not running)
        self.detect_button.setEnabled(not running)
        self.tolerance.setEnabled(not running)
        self.transparent_threshold.setEnabled(not running)
        self.foreground_threshold.setEnabled(not running)
        if message:
            self.status_label.setText(message)

    def _choose_color(self) -> None:
        current = QColor(*self._background_color)
        color = QColorDialog.getColor(current, self, "Background color")
        if not color.isValid():
            return
        self._background_color = (color.red(), color.green(), color.blue())
        self._update_color_button()
        self._emit_settings_changed()

    def _slider_row(self, slider: QSlider, value_label: QLabel) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        return row

    def _update_threshold_labels(self, *_args) -> None:
        self.tolerance_value.setText(str(self.tolerance.value()))
        self.transparent_threshold_value.setText(str(self.transparent_threshold.value()))
        self.foreground_threshold_value.setText(str(self.foreground_threshold.value()))

    def _update_color_button(self) -> None:
        r, g, b = self._background_color
        self.color_button.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.color_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'black' if (r + g + b) > 382 else 'white'};"
        )

    def _emit_settings_changed(self, *_args) -> None:
        if not self._updating:
            self.settingsChanged.emit(self.settings())

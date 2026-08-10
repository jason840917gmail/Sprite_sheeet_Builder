from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.models.tile_transform import TileTransform, normalize_angle


class TileTransformPanel(QWidget):
    transformChanged = Signal(object)
    applyRequested = Signal()
    cancelRequested = Signal()
    fitContentRequested = Signal()
    fillCanvasRequested = Signal()
    fitRotatedRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False

        self.scale_x = self._double_spin(1.0, 800.0, 100.0, "%")
        self.scale_y = self._double_spin(1.0, 800.0, 100.0, "%")
        self.lock_scale = QCheckBox("Link X/Y")
        self.lock_scale.setChecked(True)
        self.angle = self._double_spin(-180.0, 180.0, 0.0, "°")
        self.pivot_x = self._double_spin(0.0, 100.0, 50.0, "%")
        self.pivot_y = self._double_spin(0.0, 100.0, 50.0, "%")
        self.resample_mode = QComboBox()
        self.resample_mode.addItem("Use bucket setting", None)
        self.resample_mode.addItem("Smooth", "smooth")
        self.resample_mode.addItem("Nearest (pixel art)", "nearest")

        scale_row = QWidget()
        scale_layout = QHBoxLayout(scale_row)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.setSpacing(6)
        scale_layout.addWidget(self.scale_x)
        scale_layout.addWidget(QLabel("x"))
        scale_layout.addWidget(self.scale_y)
        scale_layout.addWidget(self.lock_scale)

        pivot_row = QWidget()
        pivot_layout = QHBoxLayout(pivot_row)
        pivot_layout.setContentsMargins(0, 0, 0, 0)
        pivot_layout.setSpacing(6)
        pivot_layout.addWidget(self.pivot_x)
        pivot_layout.addWidget(QLabel("x"))
        pivot_layout.addWidget(self.pivot_y)

        quick_row = QHBoxLayout()
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.setSpacing(6)
        self.rotate_left = QPushButton("−90°")
        self.rotate_right = QPushButton("+90°")
        self.rotate_180 = QPushButton("180°")
        self.reset_angle = QPushButton("Reset Angle")
        for button in (self.rotate_left, self.rotate_right, self.rotate_180, self.reset_angle):
            quick_row.addWidget(button)

        fit_row = QHBoxLayout()
        fit_row.setContentsMargins(0, 0, 0, 0)
        fit_row.setSpacing(6)
        self.fit_content = QPushButton("Fit Content")
        self.fill_canvas = QPushButton("Fill Canvas")
        self.fit_rotated = QPushButton("Fit Rotated")
        fit_row.addWidget(self.fit_content)
        fit_row.addWidget(self.fill_canvas)
        fit_row.addWidget(self.fit_rotated)

        pivot_action_row = QHBoxLayout()
        pivot_action_row.setContentsMargins(0, 0, 0, 0)
        self.center_pivot = QPushButton("Center Pivot")
        self.reset_scale = QPushButton("Reset Scale")
        pivot_action_row.addWidget(self.center_pivot)
        pivot_action_row.addWidget(self.reset_scale)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Scale", scale_row)
        form.addRow("Angle", self.angle)
        form.addRow("Pivot", pivot_row)
        form.addRow("Resampling", self.resample_mode)

        self.status_label = QLabel("Select a bucket tile to transform.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #cfd8e3;")

        apply_row = QHBoxLayout()
        apply_row.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QPushButton("Apply Transform")
        self.cancel_button = QPushButton("Cancel")
        apply_row.addWidget(self.apply_button, 1)
        apply_row.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        title = QLabel("Bucket Tile Transform")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(quick_row)
        layout.addLayout(pivot_action_row)
        layout.addLayout(fit_row)
        layout.addWidget(self.status_label)
        layout.addLayout(apply_row)
        layout.addStretch(1)

        self.scale_x.valueChanged.connect(lambda value: self._scale_changed("x", value))
        self.scale_y.valueChanged.connect(lambda value: self._scale_changed("y", value))
        self.angle.valueChanged.connect(self._emit_transform)
        self.pivot_x.valueChanged.connect(self._emit_transform)
        self.pivot_y.valueChanged.connect(self._emit_transform)
        self.resample_mode.currentIndexChanged.connect(self._emit_transform)
        self.rotate_left.clicked.connect(lambda: self._rotate_by(-90.0))
        self.rotate_right.clicked.connect(lambda: self._rotate_by(90.0))
        self.rotate_180.clicked.connect(lambda: self._rotate_by(180.0))
        self.reset_angle.clicked.connect(lambda: self.angle.setValue(0.0))
        self.center_pivot.clicked.connect(self._center_pivot)
        self.reset_scale.clicked.connect(self._reset_scale)
        self.fit_content.clicked.connect(self.fitContentRequested.emit)
        self.fill_canvas.clicked.connect(self.fillCanvasRequested.emit)
        self.fit_rotated.clicked.connect(self.fitRotatedRequested.emit)
        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)

    def _double_spin(
        self,
        minimum: float,
        maximum: float,
        value: float,
        suffix: str,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(suffix)
        spin.setValue(value)
        return spin

    def transform(self) -> TileTransform:
        return TileTransform(
            scale_x=self.scale_x.value() / 100.0,
            scale_y=self.scale_y.value() / 100.0,
            angle_degrees=self.angle.value(),
            pivot_x=self.pivot_x.value() / 100.0,
            pivot_y=self.pivot_y.value() / 100.0,
            resample_mode=self.resample_mode.currentData(),
        ).validated()

    def set_transform(self, transform: TileTransform) -> None:
        transform = transform.copy().validated()
        self._updating = True
        self.scale_x.setValue(transform.scale_x * 100.0)
        self.scale_y.setValue(transform.scale_y * 100.0)
        self.angle.setValue(transform.angle_degrees)
        self.pivot_x.setValue(transform.pivot_x * 100.0)
        self.pivot_y.setValue(transform.pivot_y * 100.0)
        index = self.resample_mode.findData(transform.resample_mode)
        self.resample_mode.setCurrentIndex(max(0, index))
        self._updating = False

    def set_target(self, name: str | None, *, dirty: bool = False, clipped: bool = False) -> None:
        enabled = bool(name)
        for control in (
            self.scale_x,
            self.scale_y,
            self.lock_scale,
            self.angle,
            self.pivot_x,
            self.pivot_y,
            self.resample_mode,
            self.rotate_left,
            self.rotate_right,
            self.rotate_180,
            self.reset_angle,
            self.center_pivot,
            self.reset_scale,
            self.fit_content,
            self.fill_canvas,
            self.fit_rotated,
            self.apply_button,
            self.cancel_button,
        ):
            control.setEnabled(enabled)
        if not name:
            self.status_label.setText("Select a bucket tile to transform.")
            return
        state = "Unapplied changes" if dirty else "Ready"
        clipping = " · content may be clipped" if clipped else ""
        self.status_label.setText(f"{name} · {state}{clipping}")

    def _scale_changed(self, axis: str, value: float) -> None:
        if self._updating:
            return
        if self.lock_scale.isChecked():
            self._updating = True
            if axis == "x":
                self.scale_y.setValue(value)
            else:
                self.scale_x.setValue(value)
            self._updating = False
        self._emit_transform()

    def _rotate_by(self, delta: float) -> None:
        self.angle.setValue(normalize_angle(self.angle.value() + delta))

    def _center_pivot(self) -> None:
        self._updating = True
        self.pivot_x.setValue(50.0)
        self.pivot_y.setValue(50.0)
        self._updating = False
        self._emit_transform()

    def _reset_scale(self) -> None:
        self._updating = True
        self.scale_x.setValue(100.0)
        self.scale_y.setValue(100.0)
        self._updating = False
        self._emit_transform()

    def _emit_transform(self, *_args) -> None:
        if not self._updating:
            self.transformChanged.emit(self.transform())

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QFormLayout,
    QLabel,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)


class RetouchPanel(QWidget):
    modeChanged = Signal(str)
    targetChanged = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._color = (255, 0, 255)

        self.mode = QComboBox()
        self.mode.addItem("Erase", "erase")
        self.mode.addItem("Paint Color", "paint")
        self.mode.addItem("Clone Color", "clone")
        self.mode.setToolTip(
            "Erase makes pixels transparent. Paint Color applies the selected RGB color. "
            "Clone Color samples an RGB pixel with Shift+left-click, then paints that exact color."
        )

        self.target = QComboBox()
        self.target.addItem("Source Preview", "source")
        self.target.addItem("Selected Bucket Tile", "bucket")
        self.target.setToolTip("Choose whether brush strokes edit the source preview or the selected bucket tile.")

        self.brush_size = QSlider(Qt.Horizontal)
        self.brush_size.setRange(1, 512)
        self.brush_size.setValue(24)
        self.brush_size.setToolTip("Diameter of the soft brush in image pixels.")
        self.brush_size_value = QLabel()
        self.brush_size_value.setMinimumWidth(52)
        self.brush_size_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(1, 100)
        self.opacity.setValue(100)
        self.opacity.setToolTip("Strength of each brush stroke.")
        self.opacity_value = QLabel()
        self.opacity_value.setMinimumWidth(52)
        self.opacity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.color_button = QPushButton()
        self.color_button.setToolTip("Color used by Paint Color. Clone Color uses the last Shift+click sample.")
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()

        self.status_label = QLabel("Shift-click in Clone Color mode to sample a color, then click to paint it.")
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Mode", self.mode)
        form.addRow("Target", self.target)
        form.addRow("Brush size", self._slider_row(self.brush_size, self.brush_size_value))
        form.addRow("Opacity", self._slider_row(self.opacity, self.opacity_value))
        form.addRow("Paint color", self.color_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Paint Cleanup")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.mode.currentIndexChanged.connect(lambda: self.modeChanged.emit(str(self.mode.currentData())))
        self.target.currentIndexChanged.connect(lambda: self.targetChanged.emit(str(self.target.currentData())))
        self.brush_size.valueChanged.connect(self._update_value_labels)
        self.opacity.valueChanged.connect(self._update_value_labels)
        self._update_value_labels()

    def current_mode(self) -> str:
        return str(self.mode.currentData())

    def current_target(self) -> str:
        return str(self.target.currentData())

    def brush_radius(self) -> int:
        return max(1, self.brush_size.value() // 2)

    def brush_diameter(self) -> int:
        return max(1, self.brush_size.value())

    def brush_opacity(self) -> float:
        return self.opacity.value() / 100.0

    def color(self) -> tuple[int, int, int]:
        return self._color

    def set_color(self, color: tuple[int, int, int]) -> None:
        """Set the paint swatch from an RGB sample taken in the preview."""
        if len(color) != 3:
            raise ValueError("Paint color must contain exactly three RGB channels")
        self._color = tuple(max(0, min(255, int(channel))) for channel in color)
        self._update_color_button()

    def set_target_available(self, target_id: str, available: bool) -> None:
        for index in range(self.target.count()):
            if self.target.itemData(index) == target_id:
                item = self.target.model().item(index)
                if item is not None:
                    item.setEnabled(available)
                return

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _choose_color(self) -> None:
        current = QColor(*self._color)
        color = QColorDialog.getColor(current, self, "Paint color")
        if not color.isValid():
            return
        self._color = (color.red(), color.green(), color.blue())
        self._update_color_button()

    def _slider_row(self, slider: QSlider, value_label: QLabel) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        return row

    def _update_value_labels(self, *_args) -> None:
        self.brush_size_value.setText(f"{self.brush_size.value()} px")
        self.opacity_value.setText(f"{self.opacity.value()}%")

    def _update_color_button(self) -> None:
        r, g, b = self._color
        self.color_button.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.color_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'black' if (r + g + b) > 382 else 'white'};"
        )

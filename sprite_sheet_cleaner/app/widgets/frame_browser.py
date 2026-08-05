from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.core.video_source import FrameRef, VideoMetadata, VideoSource
from sprite_sheet_cleaner.app.core.animation_sampler import pick_animation_refs
from sprite_sheet_cleaner.app.models.video_settings import VideoSettings
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage


class _FrameListWidget(QListWidget):
    leftFrameClicked = Signal(object)
    rightFrameClicked = Signal(object)

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is not None and event.button() == Qt.RightButton:
            ref = item.data(Qt.UserRole)
            item.setSelected(False)
            if self.currentItem() is item:
                self.setCurrentRow(-1)
                item.setSelected(False)
            self.rightFrameClicked.emit(ref)
            event.accept()
            return

        if item is not None and event.button() == Qt.LeftButton:
            # Video browsing uses a click-to-add workflow. Keep previous frame
            # selections highlighted so each frame added to the bucket remains
            # visibly part of the current animation selection.
            item.setSelected(True)
            self.setCurrentItem(item)
            self.leftFrameClicked.emit(item.data(Qt.UserRole))
            event.accept()
            return

        super().mousePressEvent(event)


class _ExtractionSignals(QObject):
    frameReady = Signal(object, object)
    progressChanged = Signal(int, int)
    finished = Signal()
    failed = Signal(str)


class _ExtractionWorker(QRunnable):
    def __init__(self, path: str | Path, refs: list[FrameRef], cancel_event: threading.Event) -> None:
        super().__init__()
        self.path = str(path)
        self.refs = refs
        self.cancel_event = cancel_event
        self.signals = _ExtractionSignals()

    def run(self) -> None:
        try:
            with VideoSource(self.path) as source:
                total = len(self.refs)
                completed = 0
                for ref, image in source.read_frames(self.refs, cancel_event=self.cancel_event):
                    if self.cancel_event.is_set():
                        break
                    thumbnail = image.copy()
                    thumbnail.thumbnail((128, 96))
                    self.signals.frameReady.emit(ref, pil_to_qimage(thumbnail))
                    completed += 1
                    self.signals.progressChanged.emit(completed, total)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class FrameBrowser(QWidget):
    """Video sampling controls and a selectable thumbnail strip."""

    extractRequested = Signal()
    addSelectedRequested = Signal()
    seedAnimationRequested = Signal(object)
    frameActivated = Signal(object)
    selectionChanged = Signal(object)
    frameLeftClicked = Signal(object)
    frameRightClicked = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._metadata: VideoMetadata | None = None
        self._refs: list[FrameRef] = []
        self._cancel_event: threading.Event | None = None
        self._worker: _ExtractionWorker | None = None
        self._generation = 0
        self._pending_selected_indices: set[int] | None = None
        self._seed_frame_count = 10
        self._thread_pool = QThreadPool(self)

        self.metadata_label = QLabel("No video loaded")
        self.metadata_label.setStyleSheet("font-weight: 600;")
        self.start_frame = self._spin(0, 0, 0)
        self.end_frame = self._spin(0, 0, 0)
        self.sample_every = self._spin(1, 10000, 1)
        self.max_frames = self._spin(1, 4096, 256)
        self.extract_button = QPushButton("Extract Frames")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.select_all_button = QPushButton("All")
        self.clear_button = QPushButton("Clear")
        self.add_button = QPushButton("Add Selected to Bucket")
        self.seed_animation_button = QPushButton("Seed Animation")
        self.seed_animation_button.setToolTip(
            "Pick the configured number of evenly separated random frames, select them, and add them to the bucket"
        )
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        self.selection_label = QLabel("0 selected")

        self.list_widget = _FrameListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setFlow(QListWidget.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setIconSize(QSize(112, 84))
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setSpacing(6)
        self.list_widget.setMinimumHeight(112)
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background: #151b24;
                border: 1px solid #364152;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px;
                margin: 2px;
                border: 2px solid transparent;
                border-radius: 7px;
                color: #d9e1ec;
            }
            QListWidget::item:hover {
                background: #26344a;
                border-color: #6680a3;
            }
            QListWidget::item:selected,
            QListWidget::item:selected:active {
                background: #1f6feb;
                border: 2px solid #a9d5ff;
                color: #ffffff;
            }
            QListWidget::item:selected:!active {
                background: #1558ad;
                border: 2px solid #83bfff;
                color: #ffffff;
            }
            """
        )

        metadata_row = QHBoxLayout()
        metadata_row.setContentsMargins(0, 0, 0, 0)
        metadata_row.addWidget(self.metadata_label, 1)
        metadata_row.addWidget(self.selection_label)

        sampling_row = QHBoxLayout()
        sampling_row.setContentsMargins(0, 0, 0, 0)
        sampling_row.setSpacing(6)
        sampling_row.addWidget(QLabel("Start"))
        sampling_row.addWidget(self.start_frame)
        sampling_row.addWidget(QLabel("End"))
        sampling_row.addWidget(self.end_frame)
        sampling_row.addWidget(QLabel("Every"))
        sampling_row.addWidget(self.sample_every)
        sampling_row.addWidget(QLabel("Max"))
        sampling_row.addWidget(self.max_frames)
        sampling_row.addWidget(self.extract_button)
        sampling_row.addWidget(self.cancel_button)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
        action_row.addWidget(self.select_all_button)
        action_row.addWidget(self.clear_button)
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.seed_animation_button)
        action_row.addWidget(self.progress, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(metadata_row)
        layout.addLayout(sampling_row)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(action_row)

        self.extract_button.clicked.connect(self.extractRequested.emit)
        self.cancel_button.clicked.connect(self.cancel_extraction)
        self.select_all_button.clicked.connect(self.select_all)
        self.clear_button.clicked.connect(self.clear_selection)
        self.add_button.clicked.connect(self.addSelectedRequested.emit)
        self.seed_animation_button.clicked.connect(
            lambda: self.seedAnimationRequested.emit(self.seed_animation_refs())
        )
        self.list_widget.currentItemChanged.connect(self._current_item_changed)
        self.list_widget.itemSelectionChanged.connect(self._selection_changed)
        self.list_widget.leftFrameClicked.connect(self.frameLeftClicked.emit)
        self.list_widget.rightFrameClicked.connect(self.frameRightClicked.emit)
        self.setEnabled(False)

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setMaximumWidth(82)
        return spin

    def set_metadata(self, metadata: VideoMetadata) -> None:
        self._metadata = metadata
        self.start_frame.setRange(0, max(0, metadata.frame_count - 1))
        self.end_frame.setRange(0, max(0, metadata.frame_count - 1))
        self.start_frame.setValue(0)
        self.end_frame.setValue(max(0, metadata.frame_count - 1))
        self.metadata_label.setText(
            f"Video {metadata.width}x{metadata.height} | "
            f"{metadata.fps:.2f} FPS | {metadata.frame_count} frames | "
            f"{metadata.duration_seconds:.2f}s"
        )
        self.setEnabled(True)

    def metadata(self) -> VideoMetadata | None:
        return self._metadata

    def sampling_settings(self) -> VideoSettings:
        return VideoSettings(
            start_frame=self.start_frame.value(),
            end_frame=self.end_frame.value(),
            sample_every=self.sample_every.value(),
            max_frames=self.max_frames.value(),
        ).validated()

    def set_sampling_settings(self, settings: VideoSettings) -> None:
        if self._metadata is None:
            return
        self.start_frame.setValue(max(0, min(settings.start_frame, self._metadata.frame_count - 1)))
        end_frame = settings.end_frame if settings.end_frame is not None else self._metadata.frame_count - 1
        self.end_frame.setValue(max(0, min(end_frame, self._metadata.frame_count - 1)))
        self.sample_every.setValue(max(1, settings.sample_every))
        self.max_frames.setValue(max(1, settings.max_frames))

    def start_extraction(self, path: str | Path, refs: list[FrameRef]) -> None:
        self.cancel_extraction()
        self.clear_frames()
        generation = self._generation
        self._cancel_event = threading.Event()
        self._worker = _ExtractionWorker(path, refs, self._cancel_event)
        self._worker.signals.frameReady.connect(
            lambda ref, image, token=generation: self._add_frame_if_current(token, ref, image)
        )
        self._worker.signals.progressChanged.connect(
            lambda completed, total, token=generation: self._set_progress_if_current(token, completed, total)
        )
        self._worker.signals.failed.connect(lambda message, token=generation: self._show_error_if_current(token, message))
        self._worker.signals.finished.connect(lambda token=generation: self._extraction_finished(token))
        self.extract_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(refs))
        self.progress.setValue(0)
        self._thread_pool.start(self._worker)

    def cancel_extraction(self) -> None:
        self._generation += 1
        if self._cancel_event is not None:
            self._cancel_event.set()
        self._cancel_event = None
        self._worker = None
        self.extract_button.setEnabled(self._metadata is not None)
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)

    def clear_frames(self) -> None:
        self._refs = []
        self.list_widget.clear()
        self.selection_label.setText("0 selected")
        self.seed_animation_button.setEnabled(False)

    def frames(self) -> list[FrameRef]:
        return list(self._refs)

    def seed_animation_refs(self) -> list[FrameRef]:
        total_frames = self._metadata.frame_count if self._metadata is not None else len(self._refs)
        return pick_animation_refs(self._refs, total_frames, target_count=self._seed_frame_count)

    def set_seed_frame_count(self, count: int) -> None:
        self._seed_frame_count = max(1, int(count))

    def selected_refs(self) -> list[FrameRef]:
        refs = [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]
        return sorted((ref for ref in refs if isinstance(ref, FrameRef)), key=lambda ref: ref.index)

    def select_indices(self, indices: set[int] | list[int] | tuple[int, ...]) -> None:
        selected = {int(index) for index in indices}
        self._pending_selected_indices = selected
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            ref = item.data(Qt.UserRole)
            item.setSelected(isinstance(ref, FrameRef) and ref.index in selected)
        if self.list_widget.count():
            self._pending_selected_indices = None

    def current_ref(self) -> FrameRef | None:
        item = self.list_widget.currentItem()
        ref = item.data(Qt.UserRole) if item is not None else None
        return ref if isinstance(ref, FrameRef) else None

    def select_all(self) -> None:
        self.list_widget.selectAll()

    def clear_selection(self) -> None:
        self.list_widget.clearSelection()

    def _add_frame(self, ref: FrameRef, image: QImage) -> None:
        """Add a frame directly for lightweight UI tests and local previews."""
        self._add_frame_if_current(self._generation, ref, image)

    def _add_frame_if_current(self, generation: int, ref: FrameRef, image: QImage) -> None:
        if generation != self._generation:
            return
        pixmap = QPixmap.fromImage(image)
        item = QListWidgetItem(QIcon(pixmap), f"{ref.index:04d}\n{ref.timestamp_ms} ms")
        item.setData(Qt.UserRole, ref)
        item.setTextAlignment(Qt.AlignHCenter)
        self.list_widget.addItem(item)
        self._refs.append(ref)
        self.seed_animation_button.setEnabled(True)

    def _set_progress_if_current(self, generation: int, completed: int, total: int) -> None:
        if generation != self._generation:
            return
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(completed)

    def _show_error_if_current(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self.metadata_label.setText(f"Video error: {message}")

    def _extraction_finished(self, generation: int) -> None:
        if generation != self._generation:
            return
        self.extract_button.setEnabled(self._metadata is not None)
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)
        self._cancel_event = None
        self._worker = None
        if self.list_widget.count() and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        if self._pending_selected_indices is not None:
            pending = self._pending_selected_indices
            self._pending_selected_indices = None
            self.select_indices(pending)
        self._selection_changed()

    def _current_item_changed(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        ref = item.data(Qt.UserRole) if item is not None else None
        if isinstance(ref, FrameRef):
            self.frameActivated.emit(ref)

    def _selection_changed(self) -> None:
        self.selection_label.setText(f"{len(self.selected_refs())} selected")
        self.selectionChanged.emit(self.selected_refs())

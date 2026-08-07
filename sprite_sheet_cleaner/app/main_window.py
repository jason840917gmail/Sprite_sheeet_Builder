from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QToolBar,
)

from sprite_sheet_cleaner.app.core.background_detector import detect_background_color
from sprite_sheet_cleaner.app.core.export_manager import export_individual_tiles, export_metadata, export_sheet
from sprite_sheet_cleaner.app.engines.exact_key import ExactKeyEngine
from sprite_sheet_cleaner.app.engines.smart_solid import SmartSolidEngine
from sprite_sheet_cleaner.app.engines.ai_worker_engine import IsolatedAIWorkerEngine
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet, sheet_capacity
from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, process_crop
from sprite_sheet_cleaner.app.core.retouch import apply_retouch_stroke
from sprite_sheet_cleaner.app.core.video_document import VideoDocument
from sprite_sheet_cleaner.app.core.video_source import (
    FrameRef,
    VideoMetadata,
    VideoSource,
    VideoSourceError,
    read_video_metadata,
    sample_frame_refs,
)
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings
from sprite_sheet_cleaner.app.models.video_settings import VideoSettings
from sprite_sheet_cleaner.app.jobs.qt_job_controller import JobHandle, QtJobController
from sprite_sheet_cleaner.app.services.source_processing_service import SourceProcessingService
from sprite_sheet_cleaner.app.services.source_repository import SourceRepository
from sprite_sheet_cleaner.app.services.project_service import load_model_project, save_model_project
from sprite_sheet_cleaner.app.services.legacy_project_importer import load_legacy_project_into_model
from sprite_sheet_cleaner.app.utils.tool_icons import (
    create_grid_icon,
    create_help_icon,
    create_pointer_icon,
    create_retouch_icon,
    create_select_icon,
)
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage
from sprite_sheet_cleaner.app.widgets.bucket_panel import BucketPanel
from sprite_sheet_cleaner.app.widgets.animation_preview_dialog import AnimationPreviewDialog
from sprite_sheet_cleaner.app.widgets.final_preview import FinalPreview
from sprite_sheet_cleaner.app.widgets.frame_browser import FrameBrowser
from sprite_sheet_cleaner.app.widgets.settings_panel import SettingsPanel
from sprite_sheet_cleaner.app.widgets.source_background_panel import SourceBackgroundPanel
from sprite_sheet_cleaner.app.widgets.source_viewer import SourceViewer
from sprite_sheet_cleaner.app.widgets.model_manager_dialog import ModelManagerDialog, default_runtime_registry
from sprite_sheet_cleaner.app.widgets.help_dialog import HelpDialog
from sprite_sheet_cleaner.app.widgets.retouch_panel import RetouchPanel
from sprite_sheet_cleaner.app.commands.command_stack import CommandStack
from sprite_sheet_cleaner.app.commands.bucket_commands import BucketStateCommand, clone_tiles
from sprite_sheet_cleaner.app.widgets.video_settings_panel import VideoSettingsPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sprite Sheet Cleaner")
        self.resize(1320, 820)

        self.model = ProjectModel()
        self._image_settings = self.model.settings
        self.source_image: Image.Image | None = None
        self.source_repository = SourceRepository()
        self.source_processing_service = SourceProcessingService(
            self.source_repository,
            {"exact_key": ExactKeyEngine(), "smart_solid": SmartSolidEngine()},
        )
        self.runtime_registry = default_runtime_registry()
        self.command_stack = CommandStack()
        self._source_job: JobHandle | None = None
        self._tile_job: JobHandle | None = None
        self._pending_tile_add: dict[str, object] | None = None
        self.job_controller = QtJobController(self)
        self.source_type = "image"
        self.video_source_path: Path | None = None
        self.video_metadata: VideoMetadata | None = None
        self.video_settings = VideoSettings()
        self._video_resize_settings: dict[int, FrameResizeSettings] = {}
        self.video_documents: list[VideoDocument] = []
        self._current_frame_ref = None
        self._video_frame_cache: dict[int, Image.Image] = {}
        self._video_background_detected = False
        self._last_mouse: tuple[int, int] | None = None
        self._last_selection: tuple[int, int, int, int] | None = None
        self._last_zoom = 1.0
        self._video_frame_splitter_initialized = False
        self._bucket_preview_active = False
        self._source_preview_override: Image.Image | None = None
        self._retouch_target = "source"
        self._retouch_bucket_index: int | None = None
        self._retouch_clone_color: tuple[int, int, int] | None = None
        self._retouch_clone_origin: tuple[int, int] | None = None
        self._retouch_clone_anchor: tuple[int, int] | None = None
        self._retouch_clone_snapshot: Image.Image | None = None
        self._retouch_work_image: Image.Image | None = None
        self._retouch_stroke_before = None
        self._retouch_stroke_before_image: Image.Image | None = None
        self._retouch_stroke_changed = False

        self.source_viewer = SourceViewer()
        self.source_background_panel = SourceBackgroundPanel()
        self.video_tabs = QTabWidget()
        self.video_tabs.setDocumentMode(True)
        self.video_tabs.setTabsClosable(True)
        self.video_tabs.setMinimumHeight(150)
        self.frame_browser: FrameBrowser | None = None
        self.settings_panel = SettingsPanel()
        self.video_settings_panel = VideoSettingsPanel()
        self.retouch_panel = RetouchPanel()
        self.bucket_panel = BucketPanel()
        self.final_preview = FinalPreview()
        self._apply_selection_geometry()

        self._build_layout()
        self._create_actions()
        self._connect_signals()
        self.source_viewer.set_retouch_brush_size(self.retouch_panel.brush_size.value())
        self._refresh_all()

    def _build_layout(self) -> None:
        self.source_viewer.setMinimumSize(780, 520)
        self.final_preview.setMinimumHeight(170)
        self.source_background_panel.setMinimumWidth(310)
        self.settings_panel.setMinimumWidth(310)
        self.video_settings_panel.setMinimumWidth(310)
        self.retouch_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumHeight(240)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.source_viewer)
        self.left_splitter.addWidget(self.video_tabs)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 1)
        self.video_tabs.hide()

        self.right_panel_stack = QStackedWidget()
        self.right_panel_stack.addWidget(self.settings_panel)
        self.right_panel_stack.addWidget(self.video_settings_panel)
        self.right_panel_stack.addWidget(self.retouch_panel)
        self.right_panel_stack.setCurrentWidget(self.settings_panel)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.addWidget(self.source_background_panel)
        self.right_splitter.addWidget(self.right_panel_stack)
        self.right_splitter.addWidget(self.bucket_panel)
        self.right_splitter.addWidget(self.final_preview)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 2)
        self.right_splitter.setStretchFactor(2, 2)
        self.right_splitter.setStretchFactor(3, 1)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setStretchFactor(0, 8)
        self.main_splitter.setStretchFactor(1, 2)
        self.setCentralWidget(self.main_splitter)
        QTimer.singleShot(0, self._set_initial_splitter_sizes)

    def _set_initial_splitter_sizes(self) -> None:
        width = max(self.centralWidget().width(), 1)
        height = max(self.centralWidget().height(), 1)
        self.main_splitter.setSizes([round(width * 0.76), round(width * 0.24)])
        self.left_splitter.setSizes([round(height * 0.78), round(height * 0.22)])
        self.right_splitter.setSizes(
            [round(height * 0.20), round(height * 0.28), round(height * 0.32), round(height * 0.20)]
        )

    def _initialize_video_frame_splitter(self) -> None:
        if self._video_frame_splitter_initialized:
            return
        height = max(self.left_splitter.height(), 1)
        handle_space = self.left_splitter.handleWidth()
        available = max(3, height - handle_space)
        source_size = available // 2
        frame_size = max(1, available - source_size)
        self.left_splitter.setSizes([source_size, frame_size])
        self._video_frame_splitter_initialized = True

    def _create_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        view_menu = self.menuBar().addMenu("&View")
        tool_menu = self.menuBar().addMenu("&Tools")
        help_menu = self.menuBar().addMenu("&Help")
        self.model_manager_action = QAction("Optional AI Model Manager...", self)
        tool_menu.addAction(self.model_manager_action)
        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addActions((self.undo_action, self.redo_action))

        self.tool_bar = QToolBar("Tools", self)
        self.tool_bar.setOrientation(Qt.Vertical)
        self.tool_bar.setMovable(False)
        self.tool_bar.setIconSize(QSize(24, 24))
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.LeftToolBarArea, self.tool_bar)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.pointer_action = QAction(create_pointer_icon(), "Pointer", self)
        self.pointer_action.setCheckable(True)
        self.pointer_action.setShortcut("V")
        self.pointer_action.setToolTip("Pointer: drag the image view; WASD pans")
        self.select_action = QAction(create_select_icon(), "Select", self)
        self.select_action.setCheckable(True)
        self.select_action.setChecked(True)
        self.select_action.setToolTip("Select: place the fixed-size tile box; arrow keys nudge 1 px; WASD pans")
        self.grid_action = QAction(create_grid_icon(), "Grid", self)
        self.grid_action.setCheckable(True)
        self.grid_action.setShortcut("G")
        self.grid_action.setToolTip(
            "Grid: left-click a tile; left-drag to select tiles; right-drag the grid; arrow keys nudge 1 px; WASD pans"
        )
        self.retouch_action = QAction(create_retouch_icon(), "Paint", self)
        self.retouch_action.setCheckable(True)
        self.retouch_action.setShortcut("B")
        self.retouch_action.setToolTip(
            "Paint Cleanup: erase pixels, paint a color, or clone color over the source preview or selected bucket tile"
        )
        self.tool_group.addAction(self.pointer_action)
        self.tool_group.addAction(self.select_action)
        self.tool_group.addAction(self.grid_action)
        self.tool_group.addAction(self.retouch_action)
        self.tool_bar.addAction(self.pointer_action)
        self.tool_bar.addAction(self.select_action)
        self.tool_bar.addAction(self.grid_action)
        self.tool_bar.addAction(self.retouch_action)
        self.help_action = QAction(create_help_icon(), "Help", self)
        self.help_action.setShortcut(QKeySequence("F1"))
        self.help_action.setToolTip("Open the indexed in-app help guide.")
        self.help_action.setStatusTip("Open the indexed in-app help guide.")
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.help_action)
        tool_menu.addAction(self.pointer_action)
        tool_menu.addAction(self.select_action)
        tool_menu.addAction(self.grid_action)
        tool_menu.addAction(self.retouch_action)
        help_menu.addAction(self.help_action)

        self.open_action = QAction("&Open Image...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_video_action = QAction("Open &Video...", self)
        self.save_project_action = QAction("&Save Project...", self)
        self.save_project_action.setShortcut(QKeySequence.Save)
        self.load_project_action = QAction("&Load Project...", self)
        self.export_sheet_action = QAction("Export &Sheet...", self)
        self.export_sheet_action.setShortcut("Ctrl+E")
        self.export_tiles_action = QAction("Export Individual &Tiles...", self)
        self.export_tiles_action.setShortcut("Ctrl+Shift+E")
        self.export_metadata_action = QAction("Export Frame &Metadata...", self)
        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)

        for action in (
            self.open_action,
            self.open_video_action,
            self.save_project_action,
            self.load_project_action,
            self.export_sheet_action,
            self.export_tiles_action,
            self.export_metadata_action,
        ):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.reset_zoom_action = QAction("&Reset Zoom", self)
        self.reset_zoom_action.setShortcut("Ctrl+0")
        view_menu.addActions((self.zoom_in_action, self.zoom_out_action, self.reset_zoom_action))

        self.add_selection_action = QAction("Add Selection to Bucket", self)
        self.add_selection_action.setShortcut(QKeySequence(Qt.Key_Space))
        self.delete_tile_action = QAction("Delete Tile", self)
        self.delete_tile_action.setShortcut(QKeySequence.Delete)
        self.clear_selection_action = QAction("Clear Source Selection", self)
        self.clear_selection_action.setShortcut("Esc")
        self.addAction(self.add_selection_action)
        self.addAction(self.delete_tile_action)
        self.addAction(self.clear_selection_action)

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(self._open_image)
        self.open_video_action.triggered.connect(self._open_video)
        self.save_project_action.triggered.connect(self._save_project)
        self.load_project_action.triggered.connect(self._load_project)
        self.export_sheet_action.triggered.connect(self._export_sheet)
        self.export_tiles_action.triggered.connect(self._export_tiles)
        self.export_metadata_action.triggered.connect(self._export_metadata)
        self.exit_action.triggered.connect(self.close)
        self.zoom_in_action.triggered.connect(self.source_viewer.zoom_in)
        self.zoom_out_action.triggered.connect(self.source_viewer.zoom_out)
        self.reset_zoom_action.triggered.connect(self.source_viewer.reset_zoom)
        self.pointer_action.triggered.connect(lambda: self._set_viewer_tool("pointer"))
        self.select_action.triggered.connect(lambda: self._set_viewer_tool("select"))
        self.grid_action.triggered.connect(lambda: self._set_viewer_tool("grid"))
        self.retouch_action.triggered.connect(lambda: self._set_viewer_tool("retouch"))
        self.add_selection_action.triggered.connect(self._add_selection_to_bucket)
        self.delete_tile_action.triggered.connect(self._delete_selected_tile)
        self.clear_selection_action.triggered.connect(self._clear_source_selection)
        self.model_manager_action.triggered.connect(self._show_model_manager)
        self.help_action.triggered.connect(self._show_help)
        self.undo_action.triggered.connect(self._undo_bucket)
        self.redo_action.triggered.connect(self._redo_bucket)

        self.source_viewer.cursorPositionChanged.connect(self._set_mouse_status)
        self.source_viewer.selectionChanged.connect(self._set_selection_status)
        self.source_viewer.zoomChanged.connect(self._set_zoom_status)
        self.source_viewer.toolChanged.connect(self._viewer_tool_changed)
        self.source_viewer.gridCellClicked.connect(self._add_grid_cell_to_bucket)
        self.source_viewer.gridStatusChanged.connect(self._grid_status_changed)
        self.source_viewer.retouchPressed.connect(self._retouch_pressed)
        self.source_viewer.retouchDragged.connect(self._retouch_dragged)
        self.source_viewer.retouchReleased.connect(self._retouch_released)
        self.source_viewer.retouchSampleRequested.connect(self._retouch_sample_requested)
        self.video_tabs.currentChanged.connect(self._video_tab_changed)
        self.video_tabs.tabCloseRequested.connect(self._close_video_tab)
        self.settings_panel.settingsChanged.connect(self._settings_changed)
        self.settings_panel.tileProcessingChanged.connect(self._tile_processing_changed)
        self.settings_panel.addSelectionRequested.connect(self._add_selection_to_bucket)
        self.settings_panel.addAllRequested.connect(self._add_all_grid_cells)
        self.settings_panel.detectBackgroundRequested.connect(self._detect_background_color)
        self.source_background_panel.applyRequested.connect(self._apply_source_background)
        self.source_background_panel.detectRequested.connect(self._detect_background_color)
        self.source_background_panel.activateRequested.connect(self._activate_source_candidate)
        self.source_background_panel.applyToBucketRequested.connect(self._apply_candidate_to_bucket)
        self.source_background_panel.discardRequested.connect(self._discard_source_candidate)
        self.source_background_panel.cancelRequested.connect(self._cancel_source_background)
        self.video_settings_panel.settingsChanged.connect(self._video_settings_changed)
        self.video_settings_panel.detectBackgroundRequested.connect(self._detect_background_color)
        self.video_settings_panel.applyToBucketRequested.connect(self._apply_video_settings_to_bucket)
        self.retouch_panel.modeChanged.connect(self._retouch_mode_changed)
        self.retouch_panel.targetChanged.connect(self._retouch_target_changed)
        self.retouch_panel.brush_size.valueChanged.connect(self.source_viewer.set_retouch_brush_size)
        self.final_preview.animationRequested.connect(self._open_animation_preview)
        self.bucket_panel.deleteRequested.connect(self._delete_tile)
        self.bucket_panel.clearRequested.connect(self._clear_bucket)
        self.bucket_panel.duplicateRequested.connect(self._duplicate_tile)
        self.bucket_panel.moveUpRequested.connect(lambda index: self._move_tile(index, -1))
        self.bucket_panel.moveDownRequested.connect(lambda index: self._move_tile(index, 1))
        self.bucket_panel.renameRequested.connect(self._rename_tile)
        self.bucket_panel.reorderRequested.connect(self._reorder_tiles)
        self.bucket_panel.tileClicked.connect(self._preview_bucket_tile)
        self._refresh_optional_engines()

    def _show_model_manager(self) -> None:
        dialog = ModelManagerDialog(self.runtime_registry, compute="auto", parent=self)
        dialog.runtimeChanged.connect(self._refresh_optional_engines)
        dialog.exec()

    def _show_help(self) -> None:
        try:
            HelpDialog(parent=self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Help unavailable", str(exc))

    def _refresh_optional_engines(self) -> None:
        self._close_optional_engines()
        self.source_background_panel.set_engine_available("rembg", False)
        self.source_background_panel.set_engine_available("ben2", False)
        self.video_settings_panel.set_engine_available("rembg", False)
        self.video_settings_panel.set_engine_available("ben2", False)
        self.settings_panel.set_tile_engine_available("rembg", False)
        engines = {"exact_key": ExactKeyEngine(), "smart_solid": SmartSolidEngine()}
        for manifest in self.runtime_registry.manifests():
            state = self.runtime_registry.state(manifest)
            if not (state.installed and state.environment_ready):
                continue
            environment = self.runtime_registry.environment_manager.environment_path(manifest)
            python_path = self.runtime_registry.environment_manager.python_path(environment)
            provider_id = str(manifest.metadata.get("provider_id", ""))
            if provider_id not in {"rembg", "ben2"}:
                continue
            engine = IsolatedAIWorkerEngine(
                provider_id=provider_id,
                model_id=str(manifest.metadata.get("model_id", provider_id)),
                model_path=state.model_path,
                python_executable=python_path,
                compute="auto",
            )
            engines[provider_id] = engine
            self.source_background_panel.set_engine_available(provider_id, True)
            self.video_settings_panel.set_engine_available(provider_id, True)
            if provider_id == "rembg":
                self.settings_panel.set_tile_engine_available("rembg", True)
        self.source_processing_service.engines = engines

    def _close_optional_engines(self) -> None:
        """Stop managed AI workers before replacing or closing the window."""
        engines = getattr(self.source_processing_service, "engines", {})
        closed: set[int] = set()
        for engine in engines.values():
            marker = id(engine)
            if marker in closed:
                continue
            closed.add(marker)
            close = getattr(engine, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception:
                # A failed cleanup must not prevent the application from closing.
                continue

    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sprite sheet",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)",
        )
        if path:
            self._load_source_image(Path(path), clear_tiles=True)

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Videos (*.mp4 *.mov *.avi *.mkv *.webm);;All files (*.*)",
        )
        if path:
            source_path = Path(path)
            existing_index = next(
                (
                    index
                    for index, document in enumerate(self.video_documents)
                    if document.path.resolve() == source_path.resolve()
                ),
                None,
            )
            if existing_index is not None:
                self.video_tabs.setCurrentIndex(existing_index)
                return
            self._load_source_video(source_path, clear_tiles=not self.video_documents)

    def _active_video_document(self) -> VideoDocument | None:
        index = self.video_tabs.currentIndex()
        if 0 <= index < len(self.video_documents):
            return self.video_documents[index]
        return None

    def _video_app_settings(self, document: VideoDocument) -> AppSettings:
        video = document.settings
        return AppSettings(
            tile_width=video.frame_width,
            tile_height=video.frame_height,
            lock_tile_aspect=video.lock_frame_aspect,
            selection_columns=1,
            selection_rows=1,
            sheet_columns=video.sheet_columns,
            sheet_rows=video.sheet_rows,
            match_sheet_to_grid=False,
            # Video frames are processed through the shared background engine
            # before entering the tile-normalization pipeline.
            remove_background=False,
            tile_background_engine=video.engine,
            background_color=video.background_color,
            tolerance=video.tolerance,
            trim_transparent=video.trim_transparent,
            scale_mode="none",
            padding=0,
            anchor=video.anchor,
        ).validated()

    def _set_image_panel_mode(self) -> None:
        self.right_panel_stack.setCurrentWidget(self.settings_panel)
        self.source_background_panel.setEnabled(True)
        self.select_action.setEnabled(True)
        self.grid_action.setEnabled(True)
        self.retouch_action.setEnabled(True)
        self.retouch_panel.set_target_available("source", True)

    def _set_video_panel_mode(self, document: VideoDocument) -> None:
        self.right_panel_stack.setCurrentWidget(self.video_settings_panel)
        self.source_background_panel.setEnabled(False)
        self.video_settings_panel.set_settings(document.settings)
        self.select_action.setEnabled(False)
        self.grid_action.setEnabled(False)
        self.retouch_action.setEnabled(True)
        self.retouch_panel.set_target_available("source", False)
        self._set_viewer_tool("pointer")

    def _activate_video_document(self, document: VideoDocument, *, show_frame: bool = True) -> None:
        self._bucket_preview_active = False
        self._source_preview_override = None
        self._reset_retouch_state()
        self.frame_browser = document.browser
        self.source_type = "video"
        self.video_source_path = document.path
        self.video_metadata = document.metadata
        self.video_settings = document.settings
        self._video_resize_settings = document.resize_settings
        self._video_frame_cache = document.frame_cache
        self._current_frame_ref = document.current_ref
        self._video_background_detected = document.background_detected
        self.model.source_type = "video"
        self.model.source_image_path = str(document.path)
        self.model.video_metadata = self._video_metadata_dict(document.metadata)
        self.model.settings = self._video_app_settings(document)
        self._set_video_panel_mode(document)
        self._sync_video_resize_project_data()
        if show_frame and document.current_ref is not None:
            self._show_video_frame(document, document.current_ref)

    def _video_metadata_dict(self, metadata: VideoMetadata) -> dict[str, object]:
        return {
            "path": metadata.path,
            "width": metadata.width,
            "height": metadata.height,
            "frame_count": metadata.frame_count,
            "fps": metadata.fps,
            "duration_seconds": metadata.duration_seconds,
        }

    def _connect_video_document(self, document: VideoDocument) -> None:
        browser = document.browser
        browser.extractRequested.connect(lambda document=document: self._extract_video_frames(document))
        browser.addSelectedRequested.connect(lambda document=document: self._add_selected_video_frames(document))
        browser.seedAnimationRequested.connect(
            lambda refs, document=document: self._seed_video_animation(document, refs)
        )
        browser.frameLeftClicked.connect(
            lambda ref, document=document: self._add_video_frame_from_browser(document, ref)
        )
        browser.frameRightClicked.connect(
            lambda ref, document=document: self._remove_video_frame_from_browser(document, ref)
        )
        browser.frameActivated.connect(lambda ref, document=document: self._show_video_frame(document, ref))

    def _video_tab_changed(self, index: int) -> None:
        if not 0 <= index < len(self.video_documents):
            self.frame_browser = None
            return
        document = self.video_documents[index]
        self.video_tabs.show()
        self._activate_video_document(document)
        self._refresh_all()

    def _close_video_tab(self, index: int) -> None:
        if not 0 <= index < len(self.video_documents):
            return
        document = self.video_documents[index]
        document.browser.cancel_extraction()
        self.video_documents.pop(index)
        self.video_tabs.removeTab(index)
        if self.video_documents:
            self._video_tab_changed(self.video_tabs.currentIndex())
            return
        self.frame_browser = None
        self._bucket_preview_active = False
        self.source_type = "image"
        self.video_source_path = None
        self.video_metadata = None
        self.source_image = None
        self._source_preview_override = None
        self._reset_retouch_state()
        self.model.source_type = "image"
        self.model.source_image_path = None
        self.model.video_metadata = None
        self.model.video_settings = None
        self.model.settings = self._image_settings
        self.settings_panel.set_settings(self._image_settings)
        self._set_image_panel_mode()
        self.source_viewer.set_image(QImage())
        self.video_tabs.hide()
        self._refresh_all()

    def _clear_video_documents(self) -> None:
        for document in self.video_documents:
            document.browser.cancel_extraction()
        self.video_tabs.clear()
        self.video_documents.clear()
        self.frame_browser = None
        self.video_tabs.hide()
        self._video_frame_splitter_initialized = False

    def _load_source_image(self, path: Path, *, clear_tiles: bool) -> None:
        try:
            with Image.open(path) as image:
                self.source_image = image.convert("RGBA")
        except Exception as exc:
            QMessageBox.critical(self, "Open image failed", str(exc))
            return

        self._bucket_preview_active = False
        self._source_preview_override = None
        self._reset_retouch_state()
        self._clear_video_documents()
        self.source_type = "image"
        self.video_source_path = None
        self.video_metadata = None
        self.video_settings = VideoSettings()
        self._video_resize_settings = {}
        self._current_frame_ref = None
        self._video_frame_cache = {}
        self._video_background_detected = False
        self.frame_browser = None
        self.video_tabs.hide()
        self.model.settings = self._image_settings
        self.settings_panel.set_settings(self._image_settings)
        self._set_image_panel_mode()
        self.model.source_type = "image"
        self.model.video_metadata = None
        self.model.video_settings = None
        self.model.source_image_path = str(path)
        self.source_repository.open_original(self.source_image, path)
        self.source_background_panel.set_candidate_state(False, "Original source is active")
        if clear_tiles:
            self.model.clear_tiles()
            self.command_stack.clear()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self._sync_sheet_to_grid()
        self._last_selection = None
        self._refresh_all()
        detected_color = self._detect_background_color_for_current_image(show_error_dialog=False)
        if detected_color is None:
            self.statusBar().showMessage(f"Opened {path.name}")
            return

        self.statusBar().showMessage(
            f"Opened {path.name} | Auto-detected background #{detected_color[0]:02X}{detected_color[1]:02X}{detected_color[2]:02X}"
        )

    def _apply_source_background(self) -> None:
        if self.source_type != "image":
            QMessageBox.warning(self, "Apply background", "Source background processing is available for images only.")
            return
        self._restore_source_after_bucket_preview()
        if self.source_image is None:
            QMessageBox.warning(self, "Apply background", "Open a source image first.")
            return
        if self._source_job is not None:
            return
        try:
            settings = self.source_background_panel.settings()
        except Exception as exc:
            QMessageBox.critical(self, "Apply background failed", str(exc))
            return
        self.source_background_panel.set_job_running(True, "Processing source background…")
        self._source_job = self.job_controller.start(
            "source-background",
            lambda progress, cancelled: self.source_processing_service.create_candidate(
                settings,
                progress=progress,
                cancelled=cancelled,
            ),
        )
        self._source_job.signals.progress.connect(self._source_job_progress)
        self._source_job.signals.completed.connect(self._source_job_completed)
        self._source_job.signals.failed.connect(self._source_job_failed)
        self._source_job.signals.cancelled.connect(self._source_job_cancelled)
        self.statusBar().showMessage("Processing source background…")

    def _source_job_progress(self, value: float, message: str) -> None:
        self.statusBar().showMessage(f"{message} ({round(value * 100)}%)")

    def _source_job_completed(self, candidate: object) -> None:
        self._source_job = None
        processed_image = getattr(candidate, "processed_image", None)
        if isinstance(processed_image, Image.Image):
            self._source_preview_override = processed_image.copy()
            self._reset_retouch_state()
            self.source_viewer.set_image(pil_to_qimage(self._source_preview_override))
            self._apply_selection_geometry()
        revision_id = getattr(candidate, "revision_id", "unknown")
        self.source_background_panel.set_job_running(False)
        self.source_background_panel.set_candidate_state(
            True,
            f"Candidate {revision_id[:8]} is ready. Activate it explicitly after review.",
        )
        self.statusBar().showMessage("Background candidate ready; the original source remains active.")

    def _source_job_failed(self, error: object) -> None:
        self._source_job = None
        self.source_background_panel.set_job_running(False)
        self.source_background_panel.set_candidate_state(False, "Original source is active")
        QMessageBox.critical(self, "Apply background failed", str(error))

    def _source_job_cancelled(self) -> None:
        self._source_job = None
        self.source_background_panel.set_job_running(False)
        self.source_background_panel.set_candidate_state(False, "Processing cancelled; original source remains active")
        self.statusBar().showMessage("Background processing cancelled.")

    def _cancel_source_background(self) -> None:
        if self._source_job is not None:
            self._source_job.cancel()

    def _activate_source_candidate(self) -> None:
        try:
            revision = self.source_repository.activate_candidate()
        except Exception as exc:
            QMessageBox.warning(self, "Activate revision", str(exc))
            return
        self.source_image = revision.processed_image.copy()
        self._source_preview_override = None
        self._reset_retouch_state()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self.model.settings.remove_background = False
        self._image_settings = self.model.settings
        self.settings_panel.set_settings(self.model.settings)
        self.source_background_panel.set_candidate_state(False, f"Revision {revision.revision_id[:8]} is active.")
        self.statusBar().showMessage("Activated processed source; existing bucket tiles were not changed.")

    def _discard_source_candidate(self) -> None:
        self.source_repository.discard_candidate()
        self._source_preview_override = None
        self._reset_retouch_state()
        active = self.source_repository.document.active_revision
        state = f"Revision {active.revision_id[:8]} is active." if active is not None else "Original source is active"
        self.source_background_panel.set_candidate_state(False, state)
        if self.source_image is not None:
            self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self.statusBar().showMessage("Discarded background candidate.")

    def _apply_candidate_to_bucket(self) -> None:
        candidate = self.source_repository.document.candidate_revision
        if candidate is None:
            QMessageBox.warning(self, "Apply to bucket", "Create and review a background candidate first.")
            return
        if not self.model.tiles:
            QMessageBox.information(self, "Apply to bucket", "The bucket is empty.")
            return
        before = clone_tiles(self.model.tiles)
        extraction_settings = AppSettings.from_dict(self.model.settings.to_dict())
        extraction_settings.remove_background = False
        try:
            for tile in self.model.tiles:
                rect = clamp_crop_rect(candidate.processed_image, tile.source_rect)
                tile.image_rgba = process_crop(candidate.processed_image, rect, extraction_settings)
                tile.source_rect = rect
                tile.source_size = (rect[2], rect[3])
                tile.final_size = (tile.image_rgba.width, tile.image_rgba.height)
                tile.source_revision_id = candidate.revision_id
        except Exception as exc:
            self.model.tiles = before
            QMessageBox.critical(self, "Apply to bucket failed", str(exc))
            return
        self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage(
            f"Applied candidate revision {candidate.revision_id[:8]} to {len(self.model.tiles)} bucket tile(s)."
        )

    def _load_source_video(self, path: Path, *, clear_tiles: bool) -> None:
        try:
            metadata = read_video_metadata(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open video failed", str(exc))
            return

        template_settings = self.video_documents[0].settings if self.video_documents else VideoSettings()
        document = VideoDocument(
            path=path,
            metadata=metadata,
            browser=FrameBrowser(),
            settings=VideoSettings.from_dict(template_settings.to_dict()),
        )
        document.browser.set_metadata(metadata)
        self._connect_video_document(document)
        if clear_tiles:
            self.model.clear_tiles()
            self.command_stack.clear()

        self.video_documents.append(document)
        tab_index = self.video_tabs.addTab(document.browser, path.name)
        self.video_tabs.setTabToolTip(tab_index, str(path))
        self.video_tabs.show()
        QTimer.singleShot(0, self._initialize_video_frame_splitter)
        self.video_tabs.setCurrentIndex(tab_index)
        self._activate_video_document(document, show_frame=False)

        self._extract_video_frames(document)
        self._refresh_all()
        self.statusBar().showMessage(f"Opened video {path.name}")

    def _extract_video_frames(self, document: VideoDocument | None = None) -> None:
        document = document or self._active_video_document()
        if document is None:
            return
        try:
            sampling = document.browser.sampling_settings()
            document.settings.start_frame = sampling.start_frame
            document.settings.end_frame = sampling.end_frame
            document.settings.sample_every = sampling.sample_every
            document.settings.target_fps = sampling.target_fps
            document.settings.max_frames = sampling.max_frames
            refs = sample_frame_refs(document.metadata, document.settings)
        except Exception as exc:
            QMessageBox.warning(self, "Extract frames", str(exc))
            return

        document.frame_cache.clear()
        if document is self._active_video_document():
            self._activate_video_document(document, show_frame=False)
        document.browser.start_extraction(document.path, refs)
        self.statusBar().showMessage(f"Extracting {len(refs)} candidate frames...")

    def _show_video_frame(self, document: VideoDocument, ref: FrameRef) -> None:
        if document is not self._active_video_document():
            return
        try:
            previous_selection = self.source_viewer.selection_rect()
            image = document.frame_cache.get(ref.index)
            if image is None:
                with VideoSource(document.path) as source:
                    image = source.read_frame(ref.index)
                self._cache_video_frame(document, ref.index, image)
            self.source_image = image
            self._source_preview_override = None
            self._reset_retouch_state()
            document.current_ref = ref
            self._current_frame_ref = ref
            self.source_viewer.set_image(pil_to_qimage(image))
            self.source_viewer.set_selection_rect(previous_selection)
            if not document.background_detected:
                detected_color = self._detect_background_color_for_current_image(show_error_dialog=False)
                if detected_color is not None:
                    document.background_detected = True
                    self._video_background_detected = True
                    self.statusBar().showMessage(
                        f"Frame {ref.index} | Auto-detected background "
                        f"#{detected_color[0]:02X}{detected_color[1]:02X}{detected_color[2]:02X}"
                    )
        except Exception as exc:
            QMessageBox.critical(self, "Load video frame failed", str(exc))

    def _read_video_frame(self, index: int) -> Image.Image:
        document = self._active_video_document()
        if document is None:
            raise VideoSourceError("No video source is loaded.")
        return self._read_video_frame_for_document(document, index)

    def _read_video_frame_for_source(self, source_path: str | None, index: int) -> Image.Image:
        if source_path:
            source = Path(source_path)
            for document in self.video_documents:
                if document.path.resolve() == source.resolve():
                    return self._read_video_frame_for_document(document, index)
            with VideoSource(source) as video:
                return video.read_frame(int(index))
        return self._read_video_frame(index)

    def _read_video_frame_for_document(self, document: VideoDocument, index: int) -> Image.Image:
        image = document.frame_cache.get(int(index))
        if image is not None:
            return image
        with VideoSource(document.path) as source:
            image = source.read_frame(int(index))
        self._cache_video_frame(document, int(index), image)
        return image

    def _cache_video_frame(self, document: VideoDocument, index: int, image: Image.Image) -> None:
        document.frame_cache[int(index)] = image
        while len(document.frame_cache) > 12:
            oldest_index = next(iter(document.frame_cache))
            del document.frame_cache[oldest_index]

    def _save_project(self) -> None:
        if self.source_type == "image" and self.source_image is None:
            QMessageBox.warning(self, "Save project", "Open a source image or video before saving a project.")
            return
        if self.source_type == "video" and self.video_source_path is None:
            QMessageBox.warning(self, "Save project", "Open a source video before saving a project.")
            return
        if not self.model.source_image_path:
            QMessageBox.warning(self, "Save project", "Open a source image or video before saving a project.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save project",
            "",
            "Sprite Sheet Cleaner project (*.sscproj);;Legacy JSON (*.ssc.json *.json)",
        )
        if not path:
            return
        output_path = Path(path)
        try:
            if output_path.suffix.lower() == ".sscproj" and self.source_type == "image":
                output_path = save_model_project(output_path, self.model)
            else:
                project_data = self.model.to_project_data()
                if self.video_documents and self.source_type == "video":
                    project_data["source_type"] = "video_collection" if len(self.video_documents) > 1 else "video"
                    project_data["video_sources"] = [
                        {
                            "path": str(document.path),
                            "metadata": self._video_metadata_dict(document.metadata),
                            "video_settings": {
                                **document.settings.to_dict(),
                                "resize_overrides": {
                                    str(index): settings.to_dict()
                                    for index, settings in sorted(document.resize_settings.items())
                                },
                            },
                            "frame_indices": [ref.index for ref in document.browser.frames()],
                            "selected_frame_indices": [ref.index for ref in document.browser.selected_refs()],
                        }
                        for document in self.video_documents
                    ]
                project_root = output_path.parent.resolve()

                def relative_if_possible(value: object) -> object:
                    if not value:
                        return value
                    try:
                        return str(Path(str(value)).resolve().relative_to(project_root))
                    except ValueError:
                        return value

                project_data["source_image_path"] = relative_if_possible(project_data.get("source_image_path"))
                video_sources = project_data.get("video_sources")
                if isinstance(video_sources, list):
                    for video_data in video_sources:
                        if isinstance(video_data, dict):
                            video_data["path"] = relative_if_possible(video_data.get("path"))
                tiles_data = project_data.get("tiles")
                if isinstance(tiles_data, list):
                    for tile_data in tiles_data:
                        if isinstance(tile_data, dict):
                            tile_data["source_path"] = relative_if_possible(tile_data.get("source_path"))
                output_path.write_text(json.dumps(project_data, indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Save project failed", str(exc))
            return
        self.statusBar().showMessage(f"Saved project {output_path.name}")

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load project",
            "",
            "Sprite Sheet Cleaner project (*.sscproj *.ssc.json *.json);;JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        project_path = Path(path)
        try:
            if project_path.suffix.lower() == ".sscproj":
                loaded_model = ProjectModel()
                load_model_project(project_path, loaded_model)
                source_path_value = loaded_model.source_image_path
                if not source_path_value:
                    raise ValueError("Project does not include a source_image_path.")
                source_path = Path(source_path_value)
                if not source_path.is_absolute():
                    source_path = project_path.parent / source_path
                source_path = source_path.resolve()
                if not source_path.exists():
                    raise FileNotFoundError(f"Source image was not found: {source_path}")
                with Image.open(source_path) as image:
                    self.source_image = image.convert("RGBA")
                self._source_preview_override = None
                self.model = loaded_model
                self.model.source_image_path = str(source_path)
                self._image_settings = self.model.settings
                self._clear_video_documents()
                self.source_type = "image"
                self.source_repository.open_original(self.source_image, source_path)
                self.source_background_panel.set_candidate_state(False, "Original source is active")
                self.settings_panel.set_settings(self.model.settings)
                self._set_image_panel_mode()
                self._apply_selection_geometry()
                self.source_viewer.set_image(pil_to_qimage(self.source_image))
                self._sync_sheet_to_grid()
                self._last_selection = None
                self.command_stack.clear()
                self._refresh_all()
                self.statusBar().showMessage(f"Loaded project {project_path.name}")
                return
            data = json.loads(project_path.read_text(encoding="utf-8"))
            source_type = str(data.get("source_type") or "image")
            video_sources = data.get("video_sources")
            video_entries = video_sources if isinstance(video_sources, list) else []
            if not video_entries and source_type == "video":
                source_path_value = data.get("source_path") or data.get("source_image_path")
                if source_path_value:
                    video_entries = [
                        {
                            "path": source_path_value,
                            "video_settings": data.get("video_settings", {}),
                        }
                    ]

            def resolve_project_path(value: object) -> Path:
                if not value:
                    raise ValueError("Project does not include a source path.")
                candidate = Path(str(value))
                if not candidate.is_absolute():
                    candidate = project_path.parent / candidate
                candidate = candidate.resolve()
                if not candidate.exists():
                    raise FileNotFoundError(f"Source was not found: {candidate}")
                return candidate

            if video_entries:
                documents: list[VideoDocument] = []
                first_image: Image.Image | None = None
                for entry in video_entries:
                    if not isinstance(entry, dict):
                        raise ValueError("Each video source must be an object.")
                    source_path = resolve_project_path(entry.get("path"))
                    metadata = read_video_metadata(source_path)
                    browser = FrameBrowser()
                    browser.set_metadata(metadata)
                    settings_data = entry.get("video_settings", {})
                    if not isinstance(settings_data, dict):
                        settings_data = {}
                    if "frame_width" not in settings_data:
                        legacy_output = data.get("settings", {})
                        if isinstance(legacy_output, dict):
                            settings_data = {
                                **settings_data,
                                "frame_width": legacy_output.get("tile_width", 64),
                                "frame_height": legacy_output.get("tile_height", 64),
                                "sheet_columns": legacy_output.get("sheet_columns", 8),
                                "sheet_rows": legacy_output.get("sheet_rows", 8),
                                "remove_background": legacy_output.get("remove_background", True),
                                "background_color": legacy_output.get("background_color", [255, 0, 255]),
                                "tolerance": legacy_output.get("tolerance", 30),
                                "trim_transparent": legacy_output.get("trim_transparent", False),
                                "anchor": legacy_output.get("anchor", "center"),
                            }
                    settings = VideoSettings.from_dict(settings_data if isinstance(settings_data, dict) else {})
                    browser.set_sampling_settings(settings)
                    browser.set_seed_frame_count(settings.seed_frame_count)
                    document = VideoDocument(
                        path=source_path,
                        metadata=metadata,
                        browser=browser,
                        settings=settings,
                        resize_settings=self._resize_overrides_from_project(settings_data),
                    )
                    self._connect_video_document(document)
                    with VideoSource(source_path) as source:
                        if first_image is None:
                            first_image = source.read_frame(0)
                    documents.append(document)

                if first_image is None:
                    raise ValueError("Project does not contain a readable video source.")

                self._clear_video_documents()
                first_document = documents[0]
                for document in documents[1:]:
                    document.settings.frame_width = first_document.settings.frame_width
                    document.settings.frame_height = first_document.settings.frame_height
                    document.settings.lock_frame_aspect = first_document.settings.lock_frame_aspect
                    document.settings.resize_mode = first_document.settings.resize_mode
                    document.settings.remove_background = first_document.settings.remove_background
                    document.settings.background_color = first_document.settings.background_color
                    document.settings.tolerance = first_document.settings.tolerance
                    document.settings.trim_transparent = first_document.settings.trim_transparent
                    document.settings.anchor = first_document.settings.anchor
                    document.settings.sheet_columns = first_document.settings.sheet_columns
                    document.settings.sheet_rows = first_document.settings.sheet_rows
                normalized_data = dict(data)
                normalized_data["source_type"] = "video"
                normalized_data["source_image_path"] = str(first_document.path)
                normalized_tiles = []
                for tile_data in data.get("tiles", []):
                    if isinstance(tile_data, dict):
                        normalized_tile = dict(tile_data)
                        if normalized_tile.get("source_path"):
                            normalized_tile["source_path"] = str(resolve_project_path(normalized_tile["source_path"]))
                        normalized_tiles.append(normalized_tile)
                normalized_data["tiles"] = normalized_tiles
                self.model.load_project_data(normalized_data, first_image)
                for tile, tile_data in zip(self.model.tiles, data.get("tiles", [])):
                    if isinstance(tile_data, dict):
                        source_rect = tile_data.get("source_rect")
                        if isinstance(source_rect, (list, tuple)) and len(source_rect) == 4:
                            tile.source_rect = tuple(int(value) for value in source_rect)
                            tile.source_size = (tile.source_rect[2], tile.source_rect[3])

                self.video_documents = documents
                for document in documents:
                    tab_index = self.video_tabs.addTab(document.browser, document.path.name)
                    self.video_tabs.setTabToolTip(tab_index, str(document.path))
                self.video_tabs.show()
                QTimer.singleShot(0, self._initialize_video_frame_splitter)
                self.video_tabs.setCurrentIndex(0)
                self._activate_video_document(first_document, show_frame=False)
                self.model.source_type = "video"
                self.model.source_image_path = str(first_document.path)
                self.model.video_metadata = self._video_metadata_dict(first_document.metadata)
                self.model.reprocess_video_tiles(
                    self._read_video_frame,
                    self._read_video_frame_for_source,
                )
                for document, entry in zip(documents, video_entries):
                    if isinstance(entry, dict):
                        selected_indices = entry.get("selected_frame_indices", [])
                        if isinstance(selected_indices, list):
                            document.browser.select_indices(selected_indices)
                    self._extract_video_frames(document)
                self.source_image = first_image
                self._source_preview_override = None
            else:
                source_path_value = data.get("source_path") or data.get("source_image_path")
                source_path = resolve_project_path(source_path_value)
                with Image.open(source_path) as image:
                    self.source_image = image.convert("RGBA")
                self._source_preview_override = None
                self._clear_video_documents()
                self.source_repository.open_original(self.source_image, source_path)
                self.source_background_panel.set_candidate_state(False, "Original source is active")
                self.source_type = "image"
                self.video_source_path = None
                self.video_metadata = None
                self.video_settings = VideoSettings()
                self._video_resize_settings = {}
                self._video_frame_cache = {}
                self._video_background_detected = False
                normalized_data = dict(data)
                normalized_data["source_image_path"] = str(source_path)
                normalized_tiles = []
                for tile_data in data.get("tiles", []):
                    if isinstance(tile_data, dict):
                        normalized_tile = dict(tile_data)
                        if normalized_tile.get("source_path"):
                            normalized_tile["source_path"] = str(resolve_project_path(normalized_tile["source_path"]))
                        normalized_tiles.append(normalized_tile)
                normalized_data["tiles"] = normalized_tiles
                if "source_type" not in data and "source_path" not in data:
                    load_legacy_project_into_model(normalized_data, self.source_image, self.model)
                else:
                    self.model.load_project_data(normalized_data, self.source_image)
                self.model.source_type = "image"
                self.model.source_image_path = str(source_path)
        except Exception as exc:
            QMessageBox.critical(self, "Load project failed", str(exc))
            return

        if self.source_type == "video":
            active_document = self._active_video_document()
            if active_document is not None:
                self._set_video_panel_mode(active_document)
        else:
            self._image_settings = self.model.settings
            self.settings_panel.set_settings(self._image_settings)
            self._set_image_panel_mode()
        self._apply_selection_geometry()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self._sync_sheet_to_grid()
        self._last_selection = None
        self.command_stack.clear()
        self._refresh_all()
        self.statusBar().showMessage(f"Loaded project {project_path.name}")

    def _settings_changed(self, settings: AppSettings) -> None:
        self._restore_source_after_bucket_preview()
        if self.source_type == "video":
            return
        # Tile background processing is controlled by its dedicated signal so
        # geometry/settings changes do not silently switch the selected remover.
        settings.remove_background = self.model.settings.remove_background
        settings.tile_background_engine = self.model.settings.tile_background_engine
        self._image_settings = settings
        self.model.settings = settings
        self._apply_selection_geometry()
        self._sync_sheet_to_grid()
        if self.source_image is not None and self.model.tiles:
            try:
                self.model.reprocess_tiles(self.source_image)
            except Exception as exc:
                QMessageBox.warning(self, "Settings update failed", str(exc))
        self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _video_settings_changed(self, settings: VideoSettings) -> None:
        if self.source_type != "video":
            return
        for document in self.video_documents:
            document.settings.frame_width = settings.frame_width
            document.settings.frame_height = settings.frame_height
            document.settings.lock_frame_aspect = settings.lock_frame_aspect
            document.settings.resize_mode = settings.resize_mode
            document.settings.remove_background = settings.remove_background
            document.settings.engine = settings.engine
            document.settings.compute = settings.compute
            document.settings.background_color = settings.background_color
            document.settings.tolerance = settings.tolerance
            document.settings.transparent_threshold = settings.transparent_threshold
            document.settings.foreground_threshold = settings.foreground_threshold
            document.settings.despill_strength = settings.despill_strength
            document.settings.pixel_art_mode = settings.pixel_art_mode
            document.settings.model_id = settings.model_id
            document.settings.trim_transparent = settings.trim_transparent
            document.settings.anchor = settings.anchor
            document.settings.sheet_columns = settings.sheet_columns
            document.settings.sheet_rows = settings.sheet_rows
            document.settings.seed_frame_count = settings.seed_frame_count
            document.browser.set_seed_frame_count(settings.seed_frame_count)
        document = self._active_video_document()
        if document is None:
            return
        self.model.settings = self._video_app_settings(document)
        self._sync_video_resize_project_data()
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        if self.model.tiles:
            self.statusBar().showMessage("Video settings updated for new frames. Apply them to existing video tiles when ready.")

    def _try_add_image_tiles_with_selected_engine(
        self,
        rects: list[tuple[int, int, int, int]],
        description: str,
        *,
        clear_selection_on_success: bool = False,
    ) -> bool:
        """Handle non-legacy tile removers; return whether the add was handled."""
        if self.source_image is None:
            return False
        try:
            settings = self.settings_panel.settings()
        except Exception as exc:
            QMessageBox.critical(self, "Tile settings failed", str(exc))
            return True
        if not settings.remove_background:
            return False

        if settings.tile_background_engine == "rembg" and len(rects) != 1:
            QMessageBox.warning(
                self,
                "rembg tile limit",
                "rembg/U2Net processes one image tile at a time. Select one tile or choose Exact Key/Smart Solid.",
            )
            return True
        if self._tile_job is not None:
            self.statusBar().showMessage("A tile background job is already running.")
            return True

        if settings.tile_background_engine == "rembg":
            self._start_single_tile_background_job(
                rects[0],
                settings,
                description,
                clear_selection_on_success=clear_selection_on_success,
            )
            return True

        before = clone_tiles(self.model.tiles)
        try:
            processed = [
                (
                    rect,
                    self.source_processing_service.process_tile(self.source_image, rect, settings),
                )
                for rect in rects
            ]
            added_tiles = self.model.add_tiles_from_processed_images(self.source_image, processed)
        except Exception as exc:
            QMessageBox.critical(self, "Add tiles failed", str(exc))
            return True
        self._tag_image_tiles_with_active_revision(added_tiles)
        self._record_bucket_snapshot(before)
        if clear_selection_on_success:
            self.source_viewer.clear_selection()
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        self.statusBar().showMessage(f"Added {len(added_tiles)} tiles from {description}.")
        return True

    def _start_single_tile_background_job(
        self,
        rect: tuple[int, int, int, int],
        settings: AppSettings,
        description: str,
        *,
        clear_selection_on_success: bool,
    ) -> None:
        if self.source_image is None:
            return
        source = self.source_image.copy()
        source_asset = self.source_repository.document.source_asset
        self._pending_tile_add = {
            "rect": tuple(int(value) for value in rect),
            "description": description,
            "clear_selection": clear_selection_on_success,
            "before": clone_tiles(self.model.tiles),
            "source_fingerprint": source_asset.fingerprint if source_asset is not None else None,
            "source_revision_id": self.source_repository.document.active_revision_id,
        }
        self.settings_panel.set_tile_job_running(True)
        self._tile_job = self.job_controller.start(
            "tile-background",
            lambda progress, cancelled: self.source_processing_service.process_tile(
                source,
                rect,
                settings,
                progress=progress,
                cancelled=cancelled,
            ),
        )
        self._tile_job.signals.progress.connect(self._tile_job_progress)
        self._tile_job.signals.completed.connect(self._tile_job_completed)
        self._tile_job.signals.failed.connect(self._tile_job_failed)
        self._tile_job.signals.cancelled.connect(self._tile_job_cancelled)
        self.statusBar().showMessage(f"Processing one tile with rembg/U2Net from {description}…")

    def _tile_job_progress(self, value: float, message: str) -> None:
        self.statusBar().showMessage(f"{message} ({round(value * 100)}%)")

    def _tile_job_completed(self, image: object) -> None:
        pending = self._pending_tile_add
        self._tile_job = None
        self._pending_tile_add = None
        self.settings_panel.set_tile_job_running(False)
        if pending is None or not isinstance(image, Image.Image) or self.source_image is None:
            self._refresh_all(selected_index=self.bucket_panel.current_index())
            return
        source_asset = self.source_repository.document.source_asset
        if (
            source_asset is None
            or source_asset.fingerprint != pending.get("source_fingerprint")
            or self.source_repository.document.active_revision_id != pending.get("source_revision_id")
        ):
            self.statusBar().showMessage("Tile result discarded because the source image changed.")
            self._refresh_all(selected_index=self.bucket_panel.current_index())
            return
        rect = pending["rect"]
        if not isinstance(rect, tuple):
            self._refresh_all(selected_index=self.bucket_panel.current_index())
            return
        try:
            added_tiles = self.model.add_tiles_from_processed_images(self.source_image, [(rect, image)])
        except Exception as exc:
            QMessageBox.critical(self, "Add tile failed", str(exc))
            self._refresh_all(selected_index=self.bucket_panel.current_index())
            return
        self._tag_image_tiles_with_active_revision(added_tiles)
        before = pending.get("before")
        if isinstance(before, list):
            self._record_bucket_snapshot(before)
        if pending.get("clear_selection"):
            self.source_viewer.clear_selection()
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        self.statusBar().showMessage(f"Added {len(added_tiles)} tile from {pending.get('description', 'selection')}.")

    def _tile_job_failed(self, error: object) -> None:
        self._tile_job = None
        self._pending_tile_add = None
        self.settings_panel.set_tile_job_running(False)
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        QMessageBox.critical(self, "Tile background removal failed", str(error))

    def _tile_job_cancelled(self) -> None:
        self._tile_job = None
        self._pending_tile_add = None
        self.settings_panel.set_tile_job_running(False)
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage("Tile background removal cancelled.")

    def _apply_video_settings_to_bucket(self) -> None:
        if self.source_type != "video":
            return
        document = self._active_video_document()
        if document is None:
            return
        before = clone_tiles(self.model.tiles)
        for source_document in self.video_documents:
            resize_settings = FrameResizeSettings(
                source_document.settings.frame_width,
                source_document.settings.frame_height,
                mode=source_document.settings.resize_mode,
            ).validated()
            source_document.resize_settings = {
                tile.source_frame_index: resize_settings
                for tile in self.model.tiles
                if tile.source_type == "video"
                and tile.source_path == str(source_document.path)
                and tile.source_frame_index is not None
            }
            for tile in self.model.tiles:
                if tile.source_type == "video" and tile.source_path == str(source_document.path):
                    tile.resize_size = (resize_settings.target_width, resize_settings.target_height)
                    tile.resize_mode = resize_settings.mode
        self.model.settings = self._video_app_settings(document)
        try:
            self.model.reprocess_video_tiles(
                self._read_video_frame,
                self._read_video_frame_for_source,
                self._process_video_frame_for_tile,
            )
        except Exception as exc:
            self.model.tiles = before
            QMessageBox.critical(self, "Apply video settings failed", str(exc))
            return
        if before:
            self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage("Applied video output settings to the existing video tiles.")

    def _video_document_for_path(self, source_path: str | None) -> VideoDocument | None:
        if not source_path:
            return self._active_video_document()
        candidate = Path(source_path)
        for document in self.video_documents:
            if document.path.resolve() == candidate.resolve():
                return document
        return None

    def _process_video_frame_for_tile(self, frame: Image.Image, tile: object) -> Image.Image:
        document = self._video_document_for_path(getattr(tile, "source_path", None))
        if document is None:
            return frame.convert("RGBA")
        return self.source_processing_service.process_frame(
            frame,
            document.settings.to_source_processing_settings(),
        )

    def _process_video_frames(
        self,
        frames: list[tuple[FrameRef, Image.Image]],
        document: VideoDocument,
    ) -> list[tuple[FrameRef, Image.Image]]:
        """Apply one stable processing recipe to the selected frame sequence."""
        settings = document.settings.to_source_processing_settings()
        return [
            (ref, self.source_processing_service.process_frame(frame, settings))
            for ref, frame in frames
        ]

    def _tile_processing_changed(self, settings: AppSettings) -> None:
        if self.source_type == "video":
            return
        self._image_settings = settings
        self.model.settings = settings
        self._refresh_action_context()
        self.statusBar().showMessage("Tile processing settings updated for new image tiles.")

    def _sync_video_resize_project_data(self) -> None:
        document = self._active_video_document()
        if document is None:
            return
        data = dict(document.settings.to_dict())
        data["resize_overrides"] = {
            str(index): settings.to_dict()
            for index, settings in sorted(document.resize_settings.items())
        }
        self.model.video_settings = data

    def _resize_overrides_from_project(self, value: object) -> dict[int, FrameResizeSettings]:
        if not isinstance(value, dict):
            return {}
        overrides = value.get("resize_overrides")
        if not isinstance(overrides, dict):
            return {}
        parsed: dict[int, FrameResizeSettings] = {}
        for index, settings_data in overrides.items():
            if not isinstance(settings_data, dict):
                continue
            try:
                parsed[int(index)] = FrameResizeSettings.from_dict(settings_data)
            except (TypeError, ValueError):
                continue
        return parsed

    def _add_selection_to_bucket(self) -> None:
        self._restore_source_after_bucket_preview()
        if self.source_type == "video":
            self._add_selected_video_frames()
            return

        if self.source_image is None:
            QMessageBox.warning(self, "Add selection", "Open a source image first.")
            return

        if self.source_viewer.current_tool() == "grid":
            rects = self.source_viewer.selected_grid_rects()
            if not rects:
                QMessageBox.warning(
                    self,
                    "Add selection",
                    "Drag across grid cells first, then add the selection to the bucket.",
                )
                return
            self._add_grid_rects_to_bucket(rects, "grid selection", clear_selection_on_success=True)
            return

        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return

        before = clone_tiles(self.model.tiles)
        rect = self.source_viewer.selection_rect()
        if rect is None:
            QMessageBox.warning(self, "Add selection", "Use the Select tool to place a tile box first.")
            return

        try:
            tile_rects = self.model.selection_grid_rects(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add selection failed", str(exc))
            return

        available_slots = sheet_capacity(self.model.settings) - len(self.model.tiles)
        if len(tile_rects) > available_slots:
            QMessageBox.warning(
                self,
                "Bucket full",
                f"The selection contains {len(tile_rects)} tiles, but the final tilesheet has "
                f"{available_slots} empty slot(s). Increase rows or columns before adding more.",
            )
            return

        if self._try_add_image_tiles_with_selected_engine(tile_rects, "selection"):
            return

        try:
            added_tiles = self.model.add_tiles_from_selection(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add selection failed", str(exc))
            return

        self._tag_image_tiles_with_active_revision(added_tiles)
        self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        if len(added_tiles) == 1:
            self.statusBar().showMessage(f"Added tile {added_tiles[0].name}")
        else:
            self.statusBar().showMessage(f"Added {len(added_tiles)} tiles from selection")

    def _add_selected_video_frames(self, document: VideoDocument | None = None) -> None:
        document = document or self._active_video_document()
        if document is None:
            QMessageBox.warning(self, "Add video frames", "Open a video first.")
            return

        refs = document.browser.selected_refs()
        if not refs:
            QMessageBox.warning(self, "Add video frames", "Select one or more frames first.")
            return

        self._add_video_refs_to_bucket(refs, "selected", document)

    def _seed_video_animation(self, document: VideoDocument, refs: object) -> None:
        if not isinstance(refs, list) or not refs:
            self.statusBar().showMessage("Extract candidate frames before seeding an animation.")
            return
        typed_refs = [ref for ref in refs if isinstance(ref, FrameRef)]
        if not typed_refs:
            return
        document.browser.select_indices([ref.index for ref in typed_refs])
        self._add_video_refs_to_bucket(typed_refs, "animation seed", document)

    def _add_video_frame_from_browser(self, document: VideoDocument, ref: FrameRef | object) -> None:
        if isinstance(ref, FrameRef):
            self._add_video_refs_to_bucket([ref], "clicked", document)

    def _add_video_refs_to_bucket(
        self,
        refs: list[FrameRef],
        description: str,
        document: VideoDocument | None = None,
    ) -> None:
        document = document or self._active_video_document()
        if document is None:
            return

        source_path = str(document.path)
        existing_indices = {
            (tile.source_path, tile.source_frame_index)
            for tile in self.model.tiles
            if tile.source_type == "video" and tile.source_frame_index is not None
        }
        new_refs = [
            ref
            for ref in refs
            if (source_path, ref.index) not in existing_indices
        ]
        if not new_refs:
            self.statusBar().showMessage("The selected frame is already in the bucket." if len(refs) == 1 else "All selected frames are already in the bucket.")
            return

        available_slots = sheet_capacity(self.model.settings) - len(self.model.tiles)
        if len(new_refs) > available_slots:
            QMessageBox.warning(
                self,
                "Bucket full",
                f"This {description} selection contains {len(new_refs)} new frames, but the final tilesheet has "
                f"{available_slots} empty slot(s). Increase rows or columns before adding more.",
            )
            return

        before = clone_tiles(self.model.tiles)
        try:
            self.model.settings = self._video_app_settings(document)
            resize_settings = FrameResizeSettings(
                document.settings.frame_width,
                document.settings.frame_height,
                mode=document.settings.resize_mode,
            ).validated()
            with VideoSource(document.path) as source:
                frames = list(source.read_frames(new_refs))
            if not frames:
                return
            frames = self._process_video_frames(frames, document)
            crop_rect = (0, 0, frames[0][1].width, frames[0][1].height)
            for ref in new_refs:
                document.resize_settings[ref.index] = resize_settings
            added_tiles = self.model.add_video_frames(
                frames,
                crop_rect=crop_rect,
                source_path=source_path,
                resize_settings_by_frame={
                    ref.index: resize_settings for ref in new_refs
                },
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add video frames failed", str(exc))
            return

        self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        self.statusBar().showMessage(f"Added {len(added_tiles)} video frame(s) from {description}.")

    def _remove_video_frame_from_browser(
        self,
        document: VideoDocument,
        ref: FrameRef | object,
    ) -> None:
        if not isinstance(ref, FrameRef):
            return
        source_path = str(document.path)
        matching_indexes = [
            index
            for index, tile in enumerate(self.model.tiles)
            if (
                tile.source_type == "video"
                and tile.source_path == source_path
                and tile.source_frame_index == ref.index
            )
        ]
        if not matching_indexes:
            self.statusBar().showMessage(f"Deselected frame {ref.index}; it was not in the bucket.")
            return

        before = clone_tiles(self.model.tiles)
        for index in reversed(matching_indexes):
            self.model.remove_tile(index)
        self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=min(matching_indexes[0], len(self.model.tiles) - 1))
        self.statusBar().showMessage(f"Removed frame {ref.index} from the bucket.")

    def _add_all_grid_cells(self) -> None:
        rects = self.source_viewer.all_grid_rects()
        if not rects:
            QMessageBox.warning(
                self,
                "Add all",
                self.source_viewer.grid_status_message() or "No valid grid is available.",
            )
            return
        self._add_grid_rects_to_bucket(rects, "grid")

    def _add_grid_rects_to_bucket(
        self,
        rects: list[tuple[int, int, int, int]],
        description: str,
        *,
        clear_selection_on_success: bool = False,
    ) -> None:
        self._restore_source_after_bucket_preview()
        if self.source_image is None:
            QMessageBox.warning(self, "Add grid tiles", "Open a source image first.")
            return

        existing_rects = {tile.source_rect for tile in self.model.tiles}
        new_rects: list[tuple[int, int, int, int]] = []
        seen = set(existing_rects)
        for rect in rects:
            normalized = tuple(int(value) for value in rect)
            if normalized in seen:
                continue
            seen.add(normalized)
            new_rects.append(normalized)

        if not new_rects:
            self.statusBar().showMessage(f"All tiles in this {description} are already in the bucket.")
            return

        capacity = sheet_capacity(self.model.settings)
        available_slots = max(0, capacity - len(self.model.tiles))
        if len(new_rects) > available_slots:
            QMessageBox.warning(
                self,
                "Bucket full",
                f"This {description} requires {len(new_rects)} empty slots, but the final tilesheet has "
                f"{available_slots}. Increase rows or columns before adding.",
            )
            return

        if self._try_add_image_tiles_with_selected_engine(
            new_rects,
            description,
            clear_selection_on_success=clear_selection_on_success,
        ):
            return

        try:
            before = clone_tiles(self.model.tiles)
            added_tiles = self.model.add_tiles_from_rects(self.source_image, new_rects)
        except Exception as exc:
            QMessageBox.critical(self, "Add grid tiles failed", str(exc))
            return

        self._tag_image_tiles_with_active_revision(added_tiles)
        self._record_bucket_snapshot(before)
        if clear_selection_on_success:
            self.source_viewer.clear_selection()
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        self.statusBar().showMessage(f"Added {len(added_tiles)} tiles from {description}.")

    def _add_grid_cell_to_bucket(self, rect: tuple[int, int, int, int]) -> None:
        self._restore_source_after_bucket_preview()
        if self.source_image is None:
            QMessageBox.warning(self, "Add grid tile", "Open a source image first.")
            return

        existing_index = self._tile_index_for_source_rect(rect)
        if existing_index is not None:
            self._refresh_all(selected_index=existing_index)
            self.statusBar().showMessage("Grid cell is already in the bucket.")
            return

        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return

        if self._try_add_image_tiles_with_selected_engine([rect], "grid tile"):
            return

        before = clone_tiles(self.model.tiles)
        try:
            added_tile = self.model.add_tile_from_crop(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add grid tile failed", str(exc))
            return

        self._tag_image_tiles_with_active_revision([added_tile])
        self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        cell = self.source_viewer.grid_cell_for_rect(rect)
        if cell is None:
            self.statusBar().showMessage(f"Added tile {self.model.tiles[-1].name}")
            return
        column, row = cell
        self.statusBar().showMessage(f"Added grid tile row {row + 1}, column {column + 1}")

    def _tag_image_tiles_with_active_revision(self, tiles: list) -> None:
        revision = self.source_repository.document.active_revision
        if revision is None:
            return
        for tile in tiles:
            tile.source_revision_id = revision.revision_id

    def _detect_background_color(self) -> None:
        if self.source_image is None:
            QMessageBox.warning(self, "Detect background", "Open a source image first.")
            return

        color = self._detect_background_color_for_current_image()
        if color is None:
            return
        self.statusBar().showMessage(f"Detected background color #{color[0]:02X}{color[1]:02X}{color[2]:02X}")

    def _detect_background_color_for_current_image(
        self,
        *,
        show_error_dialog: bool = True,
    ) -> tuple[int, int, int] | None:
        self._restore_source_after_bucket_preview()
        if self.source_image is None:
            return None

        try:
            source_image = (
                self.source_repository.original_image()
                if self.source_type == "image"
                else self.source_image
            )
            color = detect_background_color(
                source_image,
                self.source_viewer.selection_rect(),
            )
        except Exception as exc:
            if show_error_dialog:
                QMessageBox.critical(self, "Detect background failed", str(exc))
            return None

        if self.source_type == "video":
            self.video_settings_panel.set_detected_background_color(color)
        else:
            self.settings_panel.set_detected_background_color(color)
        self.source_background_panel.set_background_color(color)
        return color

    def _export_sheet(self) -> None:
        if not self.model.tiles:
            QMessageBox.warning(self, "Export sheet", "Add at least one tile before exporting.")
            return
        capacity = sheet_capacity(self.model.settings)
        if len(self.model.tiles) > capacity:
            QMessageBox.warning(
                self,
                "Export sheet",
                f"The grid capacity is {capacity}, but the bucket has {len(self.model.tiles)} tiles.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export sheet", "", "PNG image (*.png)")
        if not path:
            return
        try:
            output_path = export_sheet(path, self.model.tiles, self.model.settings)
        except Exception as exc:
            QMessageBox.critical(self, "Export sheet failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported sheet {output_path.name}")

    def _open_animation_preview(self) -> None:
        tiles = self.model.tiles
        title = "Animation Preview"
        if self.source_type == "video":
            document = self._active_video_document()
            if document is None:
                return
            selected_indices = {ref.index for ref in document.browser.selected_refs()}
            if not selected_indices:
                has_video_tiles = any(
                    tile.source_type == "video" and tile.source_path == str(document.path)
                    for tile in self.model.tiles
                )
                message = (
                    "The bucket already contains frames from this video. Select the frames for the animation "
                    "in the active video tab; the preview uses only that selection so separate animations "
                    "in the bucket are not mixed."
                    if has_video_tiles
                    else "Select the frames for this animation in the active video tab, then add them to the bucket."
                )
                QMessageBox.information(
                    self,
                    "Animation Preview",
                    message,
                )
                return
            source_path = str(document.path)
            tiles = [
                tile
                for tile in self.model.tiles
                if tile.source_type == "video"
                and tile.source_path == source_path
                and tile.source_frame_index in selected_indices
            ]
            if not tiles:
                QMessageBox.information(
                    self,
                    "Animation Preview",
                    "Add the selected frames to the bucket before previewing this animation.",
                )
                return
            title = f"Animation Preview — {document.path.name}"

        if not tiles:
            return
        dialog = AnimationPreviewDialog(tiles, self)
        dialog.setWindowTitle(title)
        dialog.exec()

    def _export_tiles(self) -> None:
        if not self.model.tiles:
            QMessageBox.warning(self, "Export tiles", "Add at least one tile before exporting.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Export individual tiles")
        if not folder:
            return
        try:
            paths = export_individual_tiles(folder, self.model.tiles)
        except Exception as exc:
            QMessageBox.critical(self, "Export tiles failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {len(paths)} tiles")

    def _export_metadata(self) -> None:
        if not self.model.tiles:
            QMessageBox.warning(self, "Export metadata", "Add at least one tile before exporting metadata.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export frame metadata",
            "",
            "JSON metadata (*.json);;All files (*.*)",
        )
        if not path:
            return
        try:
            video_sources = None
            if len(self.video_documents) > 1:
                video_sources = [
                    {
                        "path": str(document.path),
                        **self._video_metadata_dict(document.metadata),
                    }
                    for document in self.video_documents
                ]
            output_path = export_metadata(
                path,
                self.model.tiles,
                self.model.settings,
                source_path=str(self.video_source_path or self.model.source_image_path or ""),
                video_metadata=self.model.video_metadata,
                animation_fps=self.video_metadata.fps if self.video_metadata else None,
                video_sources=video_sources,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export metadata failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported metadata {output_path.name}")

    def _delete_selected_tile(self) -> None:
        self._delete_tile(self.bucket_panel.current_index())

    def _preview_bucket_tile(self, index: int) -> None:
        if not 0 <= index < len(self.model.tiles):
            return
        tile = self.model.tiles[index]
        if self.source_viewer.current_tool() == "retouch":
            if self.retouch_panel.current_target() != "bucket":
                self.retouch_panel.target.setCurrentIndex(1)
            else:
                self._prepare_retouch_target("bucket")
            return
        if self.source_image is None:
            return
        self._bucket_preview_active = True
        self.source_viewer.set_image(pil_to_qimage(tile.image_rgba))
        self.statusBar().showMessage(f"Previewing bucket tile {index + 1}: {tile.name}")

    def _restore_source_after_bucket_preview(self) -> None:
        if not self._bucket_preview_active:
            return
        self._bucket_preview_active = False
        image = self._source_preview_override or self.source_image
        if image is not None:
            self.source_viewer.set_image(pil_to_qimage(image))
            self._apply_selection_geometry()

    def _prepare_retouch_target(self, target: str) -> None:
        if target == "source" and self.source_type != "image":
            if self.model.tiles:
                bucket_index = self.bucket_panel.current_index()
                if bucket_index < 0:
                    bucket_index = 0
                self.retouch_panel.target.setCurrentIndex(1)
                target = "bucket"
            else:
                self.retouch_panel.set_status("Open an image or add a bucket tile before painting.")
                return

        self._retouch_target = target
        self._reset_retouch_state()
        self._retouch_bucket_index = None
        if target == "bucket":
            index = self.bucket_panel.current_index()
            if not 0 <= index < len(self.model.tiles):
                self.retouch_panel.set_status("Select a bucket tile first, then choose Selected Bucket Tile.")
                return
            self._retouch_bucket_index = index
            self._bucket_preview_active = True
            image = self.model.tiles[index].image_rgba
            self.source_viewer.set_image(pil_to_qimage(image))
            self.retouch_panel.set_status(
                f"Editing bucket tile {index + 1}. Each completed stroke can be undone."
            )
            return

        self._bucket_preview_active = False
        image = self._source_preview_override or self.source_image
        if image is None:
            self.retouch_panel.set_status("Open a source image before painting.")
            return
        self._retouch_work_image = image.copy()
        self.source_viewer.set_image(pil_to_qimage(self._retouch_work_image))
        self._apply_selection_geometry()
        self.retouch_panel.set_status(
            "Editing a review copy. Activate the manual candidate in Source Background when it looks right."
        )

    def _retouch_image(self) -> Image.Image | None:
        if self._retouch_target == "bucket":
            index = self._retouch_bucket_index
            if index is None or not 0 <= index < len(self.model.tiles):
                return None
            return self.model.tiles[index].image_rgba
        if self._retouch_work_image is not None:
            return self._retouch_work_image
        image = self._source_preview_override or self.source_image
        return image

    def _reset_retouch_state(self) -> None:
        self._retouch_clone_color = None
        self._retouch_clone_origin = None
        self._retouch_clone_anchor = None
        self._retouch_clone_snapshot = None
        self._retouch_work_image = None
        self._retouch_stroke_before = None
        self._retouch_stroke_before_image = None
        self._retouch_stroke_changed = False

    def _retouch_mode_changed(self, _mode: str) -> None:
        self._retouch_clone_color = None
        self._retouch_clone_origin = None
        self._retouch_clone_snapshot = None
        self.retouch_panel.set_status("Shift-click in Clone Color mode to sample a color, then click to paint it.")

    def _retouch_target_changed(self, target: str) -> None:
        if self.source_viewer.current_tool() == "retouch":
            self._prepare_retouch_target(target)

    def _retouch_sample_requested(self, point: object) -> None:
        if self.retouch_panel.current_mode() != "clone":
            self.retouch_panel.set_status("Shift-click samples a color only in Clone Color mode.")
            return
        if not isinstance(point, tuple) or len(point) != 2:
            return
        self._sample_retouch_color((int(point[0]), int(point[1])))

    def _sample_retouch_color(self, point: tuple[int, int]) -> bool:
        image = self._retouch_image()
        if image is None or image.width <= 0 or image.height <= 0:
            self.retouch_panel.set_status("Open an image or select a bucket tile first.")
            return False
        x = min(max(int(point[0]), 0), image.width - 1)
        y = min(max(int(point[1]), 0), image.height - 1)
        red, green, blue, _alpha = image.convert("RGBA").getpixel((x, y))
        self._retouch_clone_color = (red, green, blue)
        self.retouch_panel.set_color((red, green, blue))
        self.retouch_panel.set_status(
            f"Sampled #{red:02X}{green:02X}{blue:02X} at ({x}, {y}). Click or drag to paint this exact color."
        )
        return True

    def _retouch_pressed(self, point: object) -> None:
        if not isinstance(point, tuple) or len(point) != 2:
            return
        image = self._retouch_image()
        if image is None:
            self.retouch_panel.set_status("Open an image or select a bucket tile first.")
            return
        mode = self.retouch_panel.current_mode()
        if mode == "clone" and self._retouch_clone_color is None:
            self.retouch_panel.set_status("Shift-click a pixel first to choose the Clone Color.")
            return
        self._retouch_stroke_changed = False
        self._retouch_clone_anchor = (int(point[0]), int(point[1]))
        self._retouch_clone_snapshot = image.copy() if mode == "clone" else None
        self._retouch_stroke_before = clone_tiles(self.model.tiles) if self._retouch_target == "bucket" else None
        self._retouch_stroke_before_image = image.copy() if self._retouch_target == "source" else None
        self._apply_retouch_points([self._retouch_clone_anchor])

    def _retouch_dragged(self, point: object) -> None:
        if not self._retouch_stroke_changed and self._retouch_clone_anchor is None:
            return
        if not isinstance(point, tuple) or len(point) != 2:
            return
        self._apply_retouch_points([(int(point[0]), int(point[1]))])

    def _apply_retouch_points(self, points: list[tuple[int, int]]) -> None:
        image = self._retouch_image()
        if image is None:
            return
        result = apply_retouch_stroke(
            image,
            points,
            mode=self.retouch_panel.current_mode(),
            diameter=self.retouch_panel.brush_diameter(),
            opacity=self.retouch_panel.brush_opacity(),
            color=(
                self._retouch_clone_color
                if self.retouch_panel.current_mode() == "clone" and self._retouch_clone_color is not None
                else self.retouch_panel.color()
            ),
            clone_origin=self._retouch_clone_origin,
            clone_anchor=self._retouch_clone_anchor,
            source_image=self._retouch_clone_snapshot,
        )
        changed = result.tobytes() != image.convert("RGBA").tobytes()
        if not changed:
            return
        self._retouch_stroke_changed = True
        if self._retouch_target == "bucket":
            index = self._retouch_bucket_index
            if index is None or not 0 <= index < len(self.model.tiles):
                return
            self.model.tiles[index].image_rgba = result
        else:
            self._retouch_work_image = result
        self.source_viewer.refresh_image(pil_to_qimage(result))

    def _retouch_released(self) -> None:
        if not self._retouch_stroke_changed:
            self._retouch_stroke_before = None
            self._retouch_clone_anchor = None
            self._retouch_clone_snapshot = None
            self._retouch_stroke_before_image = None
            return
        if self._retouch_target == "bucket":
            before = self._retouch_stroke_before
            index = self._retouch_bucket_index
            if before is not None:
                self._record_bucket_snapshot(before)
            self._refresh_all(selected_index=index)
            self.retouch_panel.set_status("Bucket tile updated. Use Undo to restore the previous pixels.")
        else:
            image = self._retouch_work_image
            if image is not None:
                revision = self.source_repository.create_candidate(
                    image,
                    engine_id="manual_retouch",
                    settings={
                        "mode": self.retouch_panel.current_mode(),
                        "brush_size": self.retouch_panel.brush_size.value(),
                        "opacity": self.retouch_panel.brush_opacity(),
                        "target": "source",
                    },
                    backend="manual",
                )
                self._source_preview_override = revision.processed_image.copy()
                self.source_background_panel.set_candidate_state(
                    True,
                    f"Manual candidate {revision.revision_id[:8]} is ready. Activate it explicitly after review.",
                )
                self.source_viewer.refresh_image(pil_to_qimage(self._source_preview_override))
                self.retouch_panel.set_status("Manual source candidate updated. Activate it when ready.")
        self._retouch_stroke_before = None
        self._retouch_stroke_before_image = None
        self._retouch_clone_anchor = None
        self._retouch_clone_snapshot = None
        self._retouch_stroke_changed = False

    def _clear_source_selection(self) -> None:
        self.source_viewer.clear_selection()
        self.statusBar().showMessage("Cleared source selection")

    def _delete_tile(self, index: int) -> None:
        if index < 0:
            return
        self._record_bucket_change(lambda: self.model.remove_tile(index))
        self._refresh_all(selected_index=min(index, len(self.model.tiles) - 1))

    def _clear_bucket(self) -> None:
        count = len(self.model.tiles)
        if count == 0:
            return
        confirmed = (
            QMessageBox.question(
                self,
                "Clear bucket",
                f"Remove all {count} tile(s) from the bucket?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )
        if not confirmed:
            return
        self._record_bucket_change(self.model.clear_tiles)
        self._refresh_all()
        self.statusBar().showMessage("Cleared bucket")

    def _duplicate_tile(self, index: int) -> None:
        if index < 0:
            return
        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return
        before = clone_tiles(self.model.tiles)
        duplicate = self.model.duplicate_tile(index)
        if duplicate is not None:
            self._record_bucket_snapshot(before)
            self._refresh_all(selected_index=index + 1)

    def _move_tile(self, index: int, offset: int) -> None:
        if index < 0:
            return
        before = clone_tiles(self.model.tiles)
        new_index = self.model.move_tile(index, offset)
        if [tile.tile_id for tile in before] != [tile.tile_id for tile in self.model.tiles]:
            self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=new_index)

    def _reorder_tiles(self, order: object) -> None:
        if not isinstance(order, list):
            return
        if len(order) != len(self.model.tiles):
            return
        try:
            indices = [int(index) for index in order]
        except (TypeError, ValueError):
            return
        if sorted(indices) != list(range(len(self.model.tiles))):
            return
        before = clone_tiles(self.model.tiles)
        self.model.tiles = [self.model.tiles[index] for index in indices]
        if [tile.tile_id for tile in before] != [tile.tile_id for tile in self.model.tiles]:
            self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage("Reordered bucket tiles.")

    def _rename_tile(self, index: int) -> None:
        if index < 0:
            return
        current_name = self.model.tiles[index].name
        name, accepted = QInputDialog.getText(self, "Rename tile", "Name", text=current_name)
        if accepted and name.strip():
            before = clone_tiles(self.model.tiles)
            self.model.rename_tile(index, name)
            self._record_bucket_snapshot(before)
            self._refresh_all(selected_index=index)

    def _record_bucket_change(self, mutation) -> None:
        before = clone_tiles(self.model.tiles)
        mutation()
        self._record_bucket_snapshot(before)

    def _record_bucket_snapshot(self, before) -> None:
        after = clone_tiles(self.model.tiles)
        self.command_stack.execute(BucketStateCommand(self.model, before, after))

    def _undo_bucket(self) -> None:
        if self.command_stack.undo():
            self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _redo_bucket(self) -> None:
        if self.command_stack.redo():
            self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _set_viewer_tool(self, tool: str) -> None:
        if tool != "retouch":
            self._restore_source_after_bucket_preview()
        self.source_viewer.set_tool(tool)
        self.source_viewer.setFocus(Qt.ShortcutFocusReason)
        if tool == "pointer":
            self.pointer_action.setChecked(True)
        elif tool == "grid":
            self.grid_action.setChecked(True)
            self._warn_if_grid_unavailable()
        elif tool == "retouch":
            self.retouch_action.setChecked(True)
            self.right_panel_stack.setCurrentWidget(self.retouch_panel)
            self._prepare_retouch_target(self.retouch_panel.current_target())
        else:
            self.select_action.setChecked(True)
            if self.source_type == "video":
                self.right_panel_stack.setCurrentWidget(self.video_settings_panel)
            else:
                self.right_panel_stack.setCurrentWidget(self.settings_panel)
        if tool != "retouch":
            self.right_panel_stack.setCurrentWidget(
                self.video_settings_panel if self.source_type == "video" else self.settings_panel
            )
        self._refresh_action_context()
        self._update_status()

    def _viewer_tool_changed(self, _tool: str) -> None:
        self._refresh_action_context()
        self._update_status()

    def _grid_status_changed(self, _status: object) -> None:
        self._refresh_action_context()
        self._update_status()

    def _apply_selection_geometry(self) -> None:
        settings = self.model.settings
        self.source_viewer.set_selection_geometry(
            settings.tile_width,
            settings.tile_height,
            settings.selection_columns,
            settings.selection_rows,
        )

    def _sync_sheet_to_grid(self) -> bool:
        settings = self.model.settings
        if not settings.match_sheet_to_grid:
            return False
        dimensions = self.source_viewer.grid_dimensions()
        if dimensions is None:
            return False
        columns, rows = dimensions
        changed = (settings.sheet_columns, settings.sheet_rows) != (columns, rows)
        settings.sheet_columns = columns
        settings.sheet_rows = rows
        self.settings_panel.set_matched_sheet_dimensions(columns, rows)
        return changed

    def _warn_if_grid_unavailable(self) -> None:
        grid_status = self.source_viewer.grid_status_message()
        if self.source_image is not None and grid_status and not grid_status.startswith("Ready"):
            QMessageBox.warning(self, "Grid unavailable", grid_status)

    def _refresh_all(self, selected_index: int | None = None) -> None:
        capacity = sheet_capacity(self.model.settings)
        self.bucket_panel.set_tiles(self.model.tiles, selected_index, capacity)
        self.settings_panel.set_bucket_capacity_state(len(self.model.tiles), capacity)
        self.source_viewer.set_grid_added_rects([tile.source_rect for tile in self.model.tiles])
        sheet = build_sheet(self.model.tiles, self.model.settings, allow_overflow=True)
        self.final_preview.set_preview(sheet, len(self.model.tiles), self.model.settings, self.model.tiles)
        self._refresh_retouch_bucket_preview()
        self._refresh_action_context()
        self._update_status()

    def _refresh_retouch_bucket_preview(self) -> None:
        if self.source_viewer.current_tool() != "retouch" or self._retouch_target != "bucket":
            return
        index = self._retouch_bucket_index
        if index is None or not 0 <= index < len(self.model.tiles):
            return
        self.source_viewer.refresh_image(pil_to_qimage(self.model.tiles[index].image_rgba))

    def _refresh_action_context(self) -> None:
        capacity = sheet_capacity(self.model.settings)
        self.settings_panel.set_action_context(
            self.source_viewer.current_tool(),
            self.source_viewer.grid_is_valid(),
            len(self.model.tiles),
            capacity,
        )

    def _bucket_is_full(self) -> bool:
        return len(self.model.tiles) >= sheet_capacity(self.model.settings)

    def _tile_index_for_source_rect(self, rect: tuple[int, int, int, int]) -> int | None:
        normalized = tuple(int(value) for value in rect)
        for index, tile in enumerate(self.model.tiles):
            if tile.source_rect == normalized:
                return index
        return None

    def _show_bucket_full_warning(self) -> None:
        capacity = sheet_capacity(self.model.settings)
        QMessageBox.warning(
            self,
            "Bucket full",
            f"The final tilesheet holds {capacity} tiles. Increase rows or columns before adding more.",
        )

    def _set_mouse_status(self, x: int, y: int) -> None:
        self._last_mouse = (x, y)
        self._update_status()

    def _set_selection_status(self, rect: tuple[int, int, int, int] | None) -> None:
        self._last_selection = rect
        self._update_status()

    def _set_zoom_status(self, zoom: float) -> None:
        self._last_zoom = zoom
        self._update_status()

    def _update_status(self) -> None:
        mouse = (
            f"Mouse: X {self._last_mouse[0]}, Y {self._last_mouse[1]}"
            if self._last_mouse
            else "Mouse: -"
        )
        selection = (
            "Selection: "
            f"X {self._last_selection[0]}, Y {self._last_selection[1]}, "
            f"W {self._last_selection[2]}, H {self._last_selection[3]}"
            if self._last_selection
            else "Selection: -"
        )
        zoom = f"Zoom: {round(self._last_zoom * 100)}%"
        tool = f"Tool: {self.source_viewer.current_tool().title()}"
        frame = ""
        if self.source_type == "video" and self._current_frame_ref is not None:
            frame = (
                f" | Frame: {self._current_frame_ref.index}"
                f" ({self._current_frame_ref.timestamp_ms} ms)"
            )
        grid_status = self.source_viewer.grid_status_message()
        grid = f" | Grid: {grid_status}" if self.source_viewer.current_tool() == "grid" and grid_status else ""
        if self.source_viewer.current_tool() == "grid":
            hint = " | Left click tile; left-drag select; A add selection; right-drag grid; arrows nudge 1px"
        elif self.source_viewer.current_tool() == "select":
            hint = " | Left click selection; arrows nudge 1px; A add; Esc clear"
        elif self.source_viewer.current_tool() == "retouch":
            hint = " | Drag to paint; Alt-click clone source; choose mode and target in Paint Cleanup"
        else:
            hint = ""
        self.statusBar().showMessage(f"{tool} | {mouse} | {selection} | {zoom}{frame}{grid}{hint}")

    def closeEvent(self, event) -> None:
        if self._source_job is not None:
            self._source_job.cancel()
        if self._tile_job is not None:
            self._tile_job.cancel()
        for document in self.video_documents:
            document.browser.cancel_extraction()
        self._close_optional_engines()
        super().closeEvent(event)

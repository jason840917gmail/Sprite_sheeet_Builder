from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import uuid4

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
    QWidget,
)

from sprite_sheet_cleaner.app.core.background_detector import detect_background_color
from sprite_sheet_cleaner.app.core.export_manager import export_individual_tiles, export_metadata, export_sheet
from sprite_sheet_cleaner.app.engines.exact_key import ExactKeyEngine
from sprite_sheet_cleaner.app.engines.smart_solid import SmartSolidEngine
from sprite_sheet_cleaner.app.engines.ai_worker_engine import IsolatedAIWorkerEngine
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet, sheet_capacity
from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, process_crop
from sprite_sheet_cleaner.app.core.tile_transform import render_tile_transform
from sprite_sheet_cleaner.app.core.retouch import apply_retouch_stroke
from sprite_sheet_cleaner.app.core.video_document import VideoDocument
from sprite_sheet_cleaner.app.core.source_fingerprint import fingerprint_file, fingerprint_image
from sprite_sheet_cleaner.app.core.source_workspace import SourceWorkspace
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
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
from sprite_sheet_cleaner.app.models.video_settings import VideoSettings
from sprite_sheet_cleaner.app.models.source_document import ImageDocument, SourceRecord
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
    create_rotate_icon,
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
from sprite_sheet_cleaner.app.widgets.tile_transform_panel import TileTransformPanel
from sprite_sheet_cleaner.app.commands.command_stack import CommandStack
from sprite_sheet_cleaner.app.commands.bucket_commands import (
    BucketResizeCommand,
    BucketStateCommand,
    clone_settings,
    clone_tiles,
)
from sprite_sheet_cleaner.app.widgets.video_settings_panel import VideoSettingsPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sprite Sheet Cleaner")
        self.resize(1320, 820)

        self.model = ProjectModel(settings=AppSettings(bucket_resize_mode="fit"))
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
        self._source_job_source_id: str | None = None
        self._tile_job: JobHandle | None = None
        self._pending_tile_add: dict[str, object] | None = None
        self.job_controller = QtJobController(self)
        self.source_type = "image"
        self.video_source_path: Path | None = None
        self.video_metadata: VideoMetadata | None = None
        self.video_settings = VideoSettings()
        self._video_resize_settings: dict[int, FrameResizeSettings] = {}
        self.video_documents: list[VideoDocument] = []
        self.image_documents: dict[str, ImageDocument] = {}
        self._source_documents: dict[str, object] = {}
        self._source_tab_ids: list[str] = []
        self._last_active_source_id: str | None = None
        self.source_workspace = SourceWorkspace()
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
        self._transform_tile_index: int | None = None
        self._transform_before_tiles = None
        self._transform_working: TileTransform | None = None
        self._transform_dirty = False

        self.source_viewer = SourceViewer()
        self.source_background_panel = SourceBackgroundPanel()
        self.source_tabs = QTabWidget()
        self.source_tabs.setDocumentMode(True)
        self.source_tabs.setTabsClosable(True)
        self.source_tabs.setMinimumHeight(32)
        # Keep the historical attribute as an alias while the rest of the
        # video workflow is migrated to the unified source strip.
        self.video_tabs = self.source_tabs
        self.video_frame_stack = QStackedWidget()
        self.video_frame_stack.setMinimumHeight(150)
        self.frame_browser: FrameBrowser | None = None
        self.settings_panel = SettingsPanel()
        self.video_settings_panel = VideoSettingsPanel()
        self.retouch_panel = RetouchPanel()
        self.tile_transform_panel = TileTransformPanel()
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
        self.tile_transform_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumHeight(240)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.source_tabs)
        self.left_splitter.addWidget(self.source_viewer)
        self.left_splitter.addWidget(self.video_frame_stack)
        self.left_splitter.setStretchFactor(0, 0)
        self.left_splitter.setStretchFactor(1, 1)
        self.left_splitter.setStretchFactor(2, 0)
        self.source_tabs.hide()
        self.video_frame_stack.hide()

        self.right_panel_stack = QStackedWidget()
        self.right_panel_stack.addWidget(self.settings_panel)
        self.right_panel_stack.addWidget(self.video_settings_panel)
        self.right_panel_stack.addWidget(self.retouch_panel)
        self.right_panel_stack.addWidget(self.tile_transform_panel)
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
        self.left_splitter.setSizes([32, round(height * 0.66), round(height * 0.22)])
        self.right_splitter.setSizes(
            [round(height * 0.20), round(height * 0.28), round(height * 0.32), round(height * 0.20)]
        )

    def _initialize_video_frame_splitter(self) -> None:
        if self._video_frame_splitter_initialized:
            return
        height = max(self.left_splitter.height(), 1)
        handle_space = self.left_splitter.handleWidth()
        available = max(3, height - handle_space)
        tab_size = 32
        frame_size = max(1, round(available * 0.28))
        source_size = max(1, available - tab_size - frame_size)
        self.left_splitter.setSizes([tab_size, source_size, frame_size])
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
        self.rotate_action = QAction(create_rotate_icon(), "Rotate", self)
        self.rotate_action.setCheckable(True)
        self.rotate_action.setShortcut("R")
        self.rotate_action.setToolTip("Rotate the selected bucket tile with on-canvas handles; Shift snaps to 15°")
        self.rotate_action.setEnabled(False)
        self.tool_group.addAction(self.pointer_action)
        self.tool_group.addAction(self.select_action)
        self.tool_group.addAction(self.grid_action)
        self.tool_group.addAction(self.retouch_action)
        self.tool_group.addAction(self.rotate_action)
        self.tool_bar.addAction(self.pointer_action)
        self.tool_bar.addAction(self.select_action)
        self.tool_bar.addAction(self.grid_action)
        self.tool_bar.addAction(self.retouch_action)
        self.tool_bar.addAction(self.rotate_action)
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
        tool_menu.addAction(self.rotate_action)
        help_menu.addAction(self.help_action)

        self.open_action = QAction("&Open Image...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_video_action = QAction("Open &Video...", self)
        self.relink_source_action = QAction("Relink Active Source...", self)
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
            self.relink_source_action,
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
        self.relink_source_action.triggered.connect(self._relink_active_source)
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
        self.rotate_action.triggered.connect(lambda: self._set_viewer_tool("rotate"))
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
        self.source_viewer.tileTransformPreviewChanged.connect(self._tile_transform_preview_changed)
        self.source_viewer.tileTransformCommitRequested.connect(self._apply_tile_transform)
        self.source_viewer.tileTransformCancelRequested.connect(self._cancel_tile_transform)
        self.source_tabs.currentChanged.connect(self._source_tab_changed)
        self.source_tabs.tabCloseRequested.connect(self._close_source_tab)
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
        self.tile_transform_panel.transformChanged.connect(self._tile_transform_preview_changed)
        self.tile_transform_panel.applyRequested.connect(self._apply_tile_transform)
        self.tile_transform_panel.cancelRequested.connect(self._cancel_tile_transform)
        self.tile_transform_panel.fitContentRequested.connect(self._fit_transform_content)
        self.tile_transform_panel.fillCanvasRequested.connect(self._fill_transform_canvas)
        self.tile_transform_panel.fitRotatedRequested.connect(self._fit_rotated_content)
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
            self._load_source_image(Path(path), clear_tiles=False)

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Videos (*.mp4 *.mov *.avi *.mkv *.webm);;All files (*.*)",
        )
        if path:
            source_path = Path(path)
            existing = self.source_workspace.find_by_canonical_path(source_path)
            if existing is not None:
                if existing.source_id in self._source_tab_ids:
                    self.source_tabs.setCurrentIndex(self._source_tab_ids.index(existing.source_id))
                else:
                    self._reopen_source_tab(existing.source_id)
                return
            self._load_source_video(source_path, clear_tiles=False)

    def _relink_active_source(self) -> None:
        source_id = self._active_source_id()
        record = self.source_workspace.records.get(source_id) if source_id else None
        if record is None:
            QMessageBox.information(self, "Relink source", "Select a source tab to relink.")
            return
        if record.source_type == "video":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Relink video source",
                "",
                "Videos (*.mp4 *.mov *.avi *.mkv *.webm);;All files (*.*)",
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Relink image source",
                "",
                "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)",
            )
        if not path:
            return
        replacement = Path(path).resolve()
        existing = self.source_workspace.find_by_canonical_path(replacement)
        if existing is not None and existing.source_id != record.source_id:
            QMessageBox.warning(self, "Relink source", "That file is already open in another source tab.")
            return
        old_path = record.current_path
        record.current_path = str(replacement)
        record.availability = "available"
        try:
            if record.source_type == "image":
                with Image.open(replacement) as image:
                    source_image = image.convert("RGBA")
                repository = SourceRepository()
                repository.open_original(source_image, replacement)
                document = ImageDocument(
                    record,
                    source_image,
                    repository,
                    AppSettings.from_dict(record.settings or self._image_settings.to_dict()),
                )
                self._source_documents[record.source_id] = document
                self.image_documents[record.source_id] = document
                self._activate_image_document(document)
            else:
                metadata = read_video_metadata(replacement)
                kind, digest = fingerprint_file(replacement)
                document = VideoDocument(
                    path=replacement,
                    metadata=metadata,
                    browser=FrameBrowser(),
                    source_id=record.source_id,
                    fingerprint_kind=kind,
                    fingerprint=digest,
                    settings=VideoSettings.from_dict(record.settings or {}),
                )
                document.browser.set_metadata(metadata)
                self._connect_video_document(document)
                self.video_frame_stack.addWidget(document.browser)
                self._source_documents[record.source_id] = document
                self.video_documents.append(document)
                self._activate_video_document(document, show_frame=False)
                self._extract_video_frames(document)
            kind, digest = fingerprint_file(replacement) if record.source_type == "video" else fingerprint_image(source_image)
            record.fingerprint_kind = kind
            record.current_fingerprint = digest
            self.source_tabs.setTabText(self.source_tabs.currentIndex(), replacement.name)
            self.source_tabs.setTabToolTip(self.source_tabs.currentIndex(), str(replacement))
            self.statusBar().showMessage(f"Relinked source to {replacement.name}")
        except Exception as exc:
            record.current_path = old_path
            record.availability = "missing"
            QMessageBox.critical(self, "Relink source failed", str(exc))

    def _active_video_document(self) -> VideoDocument | None:
        source_id = self._active_source_id()
        document = self._source_documents.get(source_id) if source_id else None
        if isinstance(document, VideoDocument):
            return document
        for document in self.video_documents:
            if document.source_id == source_id:
                return document
        return None

    def _active_source_id(self) -> str | None:
        index = self.source_tabs.currentIndex()
        if 0 <= index < len(self._source_tab_ids):
            return self._source_tab_ids[index]
        return None

    def _source_document(self, source_id: str | None) -> object | None:
        return self._source_documents.get(source_id) if source_id else None

    def _add_source_tab(self, record: SourceRecord) -> int:
        placeholder = QWidget(self.source_tabs)
        label = record.display_name + (" (missing)" if record.availability == "missing" else "")
        index = self.source_tabs.addTab(placeholder, label)
        self._source_tab_ids.insert(index, record.source_id)
        self.source_tabs.setTabToolTip(index, record.current_path or record.display_name)
        self.source_tabs.show()
        QTimer.singleShot(0, self._initialize_video_frame_splitter)
        return index

    def _reopen_source_tab(self, source_id: str) -> None:
        record = self.source_workspace.records.get(source_id)
        document = self._source_documents.get(source_id)
        if record is None or document is None:
            return
        record.open = True
        if source_id not in self.source_workspace.open_ids:
            self.source_workspace.activate(source_id)
        index = self._add_source_tab(record)
        self.source_tabs.setCurrentIndex(index)

    def _capture_active_image_document(self, source_id: str | None = None) -> None:
        source_id = source_id or self._last_active_source_id or self._active_source_id()
        document = self._source_documents.get(source_id) if source_id else None
        if not isinstance(document, ImageDocument):
            return
        document.record.view_state = {
            "selection_rect": list(self.source_viewer.selection_rect()) if self.source_viewer.selection_rect() else None,
            "grid_origin": list(self.source_viewer.grid_origin()),
            "tool": self.source_viewer.current_tool(),
            "zoom": self._last_zoom,
        }

    def _sync_shared_image_settings(self, settings: AppSettings) -> None:
        """Keep the image right panel authoritative across every image tab."""
        shared = AppSettings.from_dict(settings.to_dict())
        self._image_settings = shared
        for document in self.image_documents.values():
            document.settings = AppSettings.from_dict(shared.to_dict())
            document.record.settings = document.settings.to_dict()

    def _activate_image_document(self, document: ImageDocument) -> None:
        self._bucket_preview_active = False
        self._source_preview_override = None
        self._reset_retouch_state()
        self.source_type = "image"
        self.source_image = document.repository.active_image()
        self.source_repository = document.repository
        self.source_processing_service.repository = document.repository
        self.video_source_path = None
        self.video_metadata = None
        self.video_settings = VideoSettings()
        self._video_resize_settings = {}
        self._current_frame_ref = None
        self._video_frame_cache = {}
        self._video_background_detected = False
        self.frame_browser = None
        self.model.source_type = "image"
        self.model.source_image_path = str(document.path) if document.path else None
        self.model.source_id = document.source_id
        self.model.source_fingerprint_kind = document.record.fingerprint_kind
        self.model.source_fingerprint = document.record.current_fingerprint or document.record.original_fingerprint
        self.model.video_metadata = None
        self.model.video_settings = None
        self.model.settings = AppSettings.from_dict(self._image_settings.to_dict())
        document.settings = AppSettings.from_dict(self._image_settings.to_dict())
        document.record.settings = document.settings.to_dict()
        self.settings_panel.set_settings(self.model.settings)
        self._set_image_panel_mode()
        self.video_frame_stack.hide()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self._apply_selection_geometry()
        state = document.record.view_state
        selection = state.get("selection_rect")
        if isinstance(selection, list) and len(selection) == 4:
            self.source_viewer.set_selection_rect(tuple(int(value) for value in selection))
        origin = state.get("grid_origin")
        if isinstance(origin, list) and len(origin) == 2:
            current = self.source_viewer.grid_origin()
            self.source_viewer.nudge_grid(int(origin[0]) - current[0], int(origin[1]) - current[1])
        tool = state.get("tool")
        if isinstance(tool, str) and tool in {"pointer", "select", "grid", "retouch", "rotate"}:
            self._set_viewer_tool(tool)
        active = self.source_repository.document.active_revision
        if active is not None:
            self.source_background_panel.set_candidate_state(False, f"Revision {active.revision_id[:8]} is active.")
        else:
            self.source_background_panel.set_candidate_state(False, "Original source is active")
        self._sync_sheet_to_grid()
        self._refresh_all()
        self._last_active_source_id = document.source_id

    def _source_tab_changed(self, index: int) -> None:
        if not 0 <= index < len(self._source_tab_ids):
            return
        self._capture_active_image_document(self._last_active_source_id)
        source_id = self._source_tab_ids[index]
        document = self._source_documents.get(source_id)
        if isinstance(document, ImageDocument):
            self._activate_image_document(document)
        elif isinstance(document, VideoDocument):
            self._activate_video_document(document)
        self._refresh_all()

    def _close_source_tab(self, index: int) -> None:
        if not 0 <= index < len(self._source_tab_ids):
            return
        source_id = self._source_tab_ids[index]
        document = self._source_documents.get(source_id)
        if isinstance(document, VideoDocument):
            document.browser.cancel_extraction()
            if document.browser in [self.video_frame_stack.widget(i) for i in range(self.video_frame_stack.count())]:
                frame_index = next(
                    i for i in range(self.video_frame_stack.count()) if self.video_frame_stack.widget(i) is document.browser
                )
                self.video_frame_stack.removeWidget(document.browser)
                document.browser.deleteLater()
            self.video_documents = [item for item in self.video_documents if item.source_id != source_id]
        elif isinstance(document, ImageDocument):
            self._capture_active_image_document(source_id)
        self.source_workspace.close_tab(source_id)
        self._source_tab_ids.pop(index)
        self.source_tabs.removeTab(index)
        if not self._source_tab_ids:
            self._last_active_source_id = None
            self.frame_browser = None
            self.source_image = None
            self.source_type = "image"
            self.video_source_path = None
            self.video_metadata = None
            self.video_frame_stack.hide()
            self.source_tabs.hide()
            self.source_viewer.set_image(QImage())
            self._refresh_all()
            return
        self.source_tabs.setCurrentIndex(min(index, len(self._source_tab_ids) - 1))


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
        self._capture_active_image_document(self._last_active_source_id)
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
        self.model.source_id = document.source_id
        self.model.source_fingerprint_kind = document.fingerprint_kind
        self.model.source_fingerprint = document.fingerprint
        self.model.video_metadata = self._video_metadata_dict(document.metadata)
        self.model.settings = self._video_app_settings(document)
        self._set_video_panel_mode(document)
        self._sync_video_resize_project_data()
        tab_index = self._source_tab_ids.index(document.source_id) if document.source_id in self._source_tab_ids else -1
        if tab_index >= 0:
            self.source_tabs.setTabText(tab_index, document.path.name)
            self.source_tabs.setTabToolTip(tab_index, str(document.path))
        frame_index = self.video_frame_stack.indexOf(document.browser)
        if frame_index >= 0:
            self.video_frame_stack.setCurrentIndex(frame_index)
        self.video_frame_stack.show()
        if show_frame and document.current_ref is not None:
            self._show_video_frame(document, document.current_ref)
        self._last_active_source_id = document.source_id

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
        self._source_tab_changed(index)

    def _close_video_tab(self, index: int) -> None:
        self._close_source_tab(index)

    def _clear_video_documents(self) -> None:
        for document in list(self.video_documents):
            source_id = document.source_id
            if source_id in self._source_tab_ids:
                self._close_source_tab(self._source_tab_ids.index(source_id))
            else:
                document.browser.cancel_extraction()
        self.video_documents.clear()
        self.frame_browser = None
        self._video_frame_splitter_initialized = False

    def _load_source_image(self, path: Path, *, clear_tiles: bool) -> None:
        try:
            with Image.open(path) as image:
                source_image = image.convert("RGBA")
        except Exception as exc:
            QMessageBox.critical(self, "Open image failed", str(exc))
            return

        existing = self.source_workspace.find_by_canonical_path(path)
        if existing is not None:
            if existing.source_id in self._source_tab_ids:
                self.source_tabs.setCurrentIndex(self._source_tab_ids.index(existing.source_id))
            else:
                self._reopen_source_tab(existing.source_id)
            return

        document = self._register_image_document(path, source_image)

        self._bucket_preview_active = False
        self._source_preview_override = None
        self._reset_retouch_state()
        if clear_tiles:
            self.model.clear_tiles()
            self.command_stack.clear()
        self._activate_image_document(document)
        detected_color = self._detect_background_color_for_current_image(show_error_dialog=False)
        if detected_color is None:
            self.statusBar().showMessage(f"Opened {path.name}")
            return

        self.statusBar().showMessage(
            f"Opened {path.name} | Auto-detected background #{detected_color[0]:02X}{detected_color[1]:02X}{detected_color[2]:02X}"
        )

    def _register_image_document(
        self,
        path: Path,
        source_image: Image.Image,
        *,
        record: SourceRecord | None = None,
        settings: AppSettings | None = None,
    ) -> ImageDocument:
        fingerprint_kind, fingerprint = fingerprint_image(source_image)
        if record is None:
            record = SourceRecord(
                source_type="image",
                original_path=str(path),
                current_path=str(path),
                display_name=path.name,
                fingerprint_kind=fingerprint_kind,
                original_fingerprint=fingerprint,
                current_fingerprint=fingerprint,
                source_size=source_image.size,
            )
        else:
            record.source_type = "image"
            record.current_path = str(path)
            record.original_path = record.original_path or str(path)
            record.display_name = record.display_name or path.name
            record.source_size = record.source_size or source_image.size
            record.fingerprint_kind = record.fingerprint_kind or fingerprint_kind
            record.original_fingerprint = record.original_fingerprint or fingerprint
            record.current_fingerprint = record.current_fingerprint or fingerprint
        repository = SourceRepository()
        repository.open_original(source_image, path)
        document_settings = settings or AppSettings.from_dict(
            self._image_settings.to_dict()
        )
        document = ImageDocument(record, source_image, repository, document_settings)
        self.source_workspace.add(record)
        self._source_documents[record.source_id] = document
        self.image_documents[record.source_id] = document
        tab_index = self._add_source_tab(record)
        self.source_tabs.setCurrentIndex(tab_index)
        return document

    def _clear_all_source_documents(self) -> None:
        if self._source_job is not None:
            self._source_job.cancel()
        for document in self.video_documents:
            document.browser.cancel_extraction()
        for index in range(self.video_frame_stack.count() - 1, -1, -1):
            widget = self.video_frame_stack.widget(index)
            self.video_frame_stack.removeWidget(widget)
            widget.deleteLater()
        self.source_tabs.blockSignals(True)
        self.source_tabs.clear()
        self.source_tabs.blockSignals(False)
        self._source_tab_ids.clear()
        self.video_documents.clear()
        self.image_documents.clear()
        self._source_documents.clear()
        self.source_workspace.remove_all()
        self._last_active_source_id = None
        self.frame_browser = None
        self.video_frame_stack.hide()
        self.source_tabs.hide()
        self._video_frame_splitter_initialized = False

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
        source_id = self._active_source_id()
        repository = self.source_repository
        job_service = SourceProcessingService(repository, dict(self.source_processing_service.engines))
        self._source_job_source_id = source_id
        self._source_job = self.job_controller.start(
            "source-background",
            lambda progress, cancelled: job_service.create_candidate(
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
        source_id = self._source_job_source_id
        self._source_job = None
        self._source_job_source_id = None
        if source_id != self._active_source_id():
            self.source_background_panel.set_job_running(False)
            self.statusBar().showMessage("Background candidate is ready on its source tab.")
            return
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
        self._source_job_source_id = None
        self.source_background_panel.set_job_running(False)
        self.source_background_panel.set_candidate_state(False, "Original source is active")
        QMessageBox.critical(self, "Apply background failed", str(error))

    def _source_job_cancelled(self) -> None:
        self._source_job = None
        self._source_job_source_id = None
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
        self._sync_shared_image_settings(self.model.settings)
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
        existing = self.source_workspace.find_by_canonical_path(path)
        if existing is not None:
            if existing.source_id in self._source_tab_ids:
                self.source_tabs.setCurrentIndex(self._source_tab_ids.index(existing.source_id))
            else:
                self._reopen_source_tab(existing.source_id)
            return
        try:
            metadata = read_video_metadata(path)
            fingerprint_kind, fingerprint = fingerprint_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open video failed", str(exc))
            return

        template_settings = self.video_documents[0].settings if self.video_documents else VideoSettings()
        document = VideoDocument(
            path=path,
            metadata=metadata,
            browser=FrameBrowser(),
            fingerprint_kind=fingerprint_kind,
            fingerprint=fingerprint,
            settings=VideoSettings.from_dict(template_settings.to_dict()),
        )
        document.browser.set_metadata(metadata)
        self._connect_video_document(document)
        if clear_tiles:
            self.model.clear_tiles()
            self.command_stack.clear()

        self._register_video_document(document)
        tab_index = self._source_tab_ids.index(document.source_id)
        QTimer.singleShot(0, self._initialize_video_frame_splitter)
        self.video_tabs.setCurrentIndex(tab_index)
        self._activate_video_document(document, show_frame=False)

        self._extract_video_frames(document)
        self._refresh_all()
        self.statusBar().showMessage(f"Opened video {path.name}")

    def _register_video_document(
        self,
        document: VideoDocument,
        *,
        record: SourceRecord | None = None,
    ) -> None:
        if record is None:
            record = SourceRecord(
                source_id=document.source_id,
                source_type="video",
                original_path=str(document.path),
                current_path=str(document.path),
                display_name=document.path.name,
                fingerprint_kind=document.fingerprint_kind,
                original_fingerprint=document.fingerprint,
                current_fingerprint=document.fingerprint,
            )
        else:
            record.source_id = document.source_id
            record.source_type = "video"
            record.current_path = str(document.path)
            record.original_path = record.original_path or str(document.path)
            record.display_name = record.display_name or document.path.name
            record.fingerprint_kind = record.fingerprint_kind or document.fingerprint_kind
            record.original_fingerprint = record.original_fingerprint or document.fingerprint
            record.current_fingerprint = record.current_fingerprint or document.fingerprint
        self.source_workspace.add(record)
        self._source_documents[document.source_id] = document
        self.video_documents.append(document)
        self.video_frame_stack.addWidget(document.browser)
        self._add_source_tab(record)

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

    def _workspace_project_data(self) -> dict[str, object]:
        self._capture_active_image_document()
        data = self.model.to_project_data()
        sources: list[dict[str, object]] = []
        for source_id, record in self.source_workspace.records.items():
            entry = record.to_dict()
            document = self._source_documents.get(source_id)
            if isinstance(document, VideoDocument):
                entry["video_metadata"] = self._video_metadata_dict(document.metadata)
                entry["video_settings"] = {
                    **document.settings.to_dict(),
                    "resize_overrides": {
                        str(index): settings.to_dict()
                        for index, settings in sorted(document.resize_settings.items())
                    },
                }
                entry["frame_indices"] = [ref.index for ref in document.browser.frames()]
                entry["selected_frame_indices"] = [ref.index for ref in document.browser.selected_refs()]
            sources.append(entry)
        data["schema_version"] = 4
        data["sources"] = sources
        data["active_source_id"] = self._active_source_id()
        data["open_source_ids"] = list(self.source_workspace.open_ids)
        data["source_type"] = self.source_type
        data["source_image_path"] = self.model.source_image_path
        return data

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
            project_data = self._workspace_project_data()
            if output_path.suffix.lower() == ".sscproj":
                output_path = save_model_project(output_path, self.model, project_data=project_data)
            else:
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
                sources = project_data.get("sources")
                if isinstance(sources, list):
                    for source_data in sources:
                        if isinstance(source_data, dict):
                            source_data["original_path"] = relative_if_possible(source_data.get("original_path"))
                            source_data["current_path"] = relative_if_possible(source_data.get("current_path"))
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
                loaded_archive = load_model_project(project_path, loaded_model)
                source_path_value = loaded_model.source_image_path
                if not source_path_value:
                    raise ValueError("Project does not include a source_image_path.")
                source_path = Path(source_path_value)
                if not source_path.is_absolute():
                    source_path = project_path.parent / source_path
                source_path = source_path.resolve()
                if not source_path.exists():
                    self.model = loaded_model
                    self._clear_all_source_documents()
                    sources = loaded_archive.data.get("sources")
                    if isinstance(sources, list) and sources:
                        for entry in sources:
                            if not isinstance(entry, dict):
                                continue
                            record = SourceRecord.from_dict(entry)
                            record.availability = "missing"
                            self.source_workspace.add(record)
                            self._source_documents[record.source_id] = None
                            self._add_source_tab(record)
                    else:
                        record = SourceRecord(
                            source_id=loaded_model.source_id or uuid4().hex,
                            source_type=loaded_model.source_type,
                            original_path=str(source_path),
                            current_path=str(source_path),
                            display_name=source_path.name,
                            fingerprint_kind=loaded_model.source_fingerprint_kind,
                            original_fingerprint=loaded_model.source_fingerprint,
                            current_fingerprint=loaded_model.source_fingerprint,
                            availability="missing",
                        )
                        self.source_workspace.add(record)
                        self._source_documents[record.source_id] = None
                        self._add_source_tab(record)
                    self.source_image = None
                    self.source_type = "image"
                    self.source_tabs.show()
                    self.statusBar().showMessage("Loaded project; source file is missing. Use Relink Active Source…")
                    self.command_stack.clear()
                    self._refresh_all()
                    return
                with Image.open(source_path) as image:
                    self.source_image = image.convert("RGBA")
                self._source_preview_override = None
                self.model = loaded_model
                self.model.source_image_path = str(source_path)
                self._image_settings = self.model.settings
                self._clear_all_source_documents()
                source_entry = None
                sources = loaded_archive.data.get("sources")
                if isinstance(sources, list) and sources:
                    source_entry = next((entry for entry in sources if isinstance(entry, dict) and entry.get("source_id") == loaded_model.source_id), None)
                record = SourceRecord.from_dict(source_entry) if hasattr(SourceRecord, "from_dict") and isinstance(source_entry, dict) else None
                document = self._register_image_document(source_path, self.source_image, record=record, settings=self.model.settings)
                self._activate_image_document(document)
                self._last_selection = None
                self.command_stack.clear()
                self._refresh_all()
                self.statusBar().showMessage(f"Loaded project {project_path.name}")
                return
            data = json.loads(project_path.read_text(encoding="utf-8"))
            source_type = str(data.get("source_type") or "image")
            video_sources = data.get("video_sources")
            video_entries = video_sources if isinstance(video_sources, list) else []
            if not video_entries:
                source_entries = data.get("sources")
                if isinstance(source_entries, list):
                    video_entries = [
                        {
                            **entry,
                            "path": entry.get("current_path") or entry.get("original_path"),
                            "video_settings": entry.get("video_settings") or entry.get("settings", {}),
                        }
                        for entry in source_entries
                        if isinstance(entry, dict) and str(entry.get("source_type") or "") == "video"
                    ]
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
                    fingerprint_kind, fingerprint = fingerprint_file(source_path)
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
                        source_id=str(entry.get("source_id") or uuid4().hex),
                        fingerprint_kind=str(entry.get("fingerprint_kind") or fingerprint_kind),
                        fingerprint=str(entry.get("fingerprint") or fingerprint),
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

                self._clear_all_source_documents()
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

                for document in documents:
                    self._register_video_document(document)
                source_entries = data.get("sources")
                if isinstance(source_entries, list):
                    for entry in source_entries:
                        if not isinstance(entry, dict) or str(entry.get("source_type") or "") != "image":
                            continue
                        source_value = entry.get("current_path") or entry.get("original_path")
                        if not source_value:
                            continue
                        image_path = resolve_project_path(source_value)
                        record = SourceRecord.from_dict(entry)
                        with Image.open(image_path) as image:
                            image_source = image.convert("RGBA")
                        settings_data = record.settings
                        image_settings = (
                            AppSettings.from_dict(settings_data)
                            if isinstance(settings_data, dict) and settings_data
                            else AppSettings.from_dict(self._image_settings.to_dict())
                        )
                        self._register_image_document(
                            image_path,
                            image_source,
                            record=record,
                            settings=image_settings,
                        )
                self.source_tabs.show()
                QTimer.singleShot(0, self._initialize_video_frame_splitter)
                self.source_tabs.setCurrentIndex(0)
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
                    loaded_image = image.convert("RGBA")
                self._source_preview_override = None
                self._clear_all_source_documents()
                document = self._register_image_document(source_path, loaded_image)
                self.source_image = loaded_image
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
                    load_legacy_project_into_model(normalized_data, loaded_image, self.model)
                else:
                    self.model.load_project_data(normalized_data, loaded_image)
                self.model.source_type = "image"
                self.model.source_image_path = str(source_path)
                document.settings = self.model.settings
                self._activate_image_document(document)
        except Exception as exc:
            QMessageBox.critical(self, "Load project failed", str(exc))
            return

        if self.source_type == "video":
            active_document = self._active_video_document()
            if active_document is not None:
                self._set_video_panel_mode(active_document)
        else:
            self._sync_shared_image_settings(self.model.settings)
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
        previous = clone_settings(self.model.settings)
        bucket_size_changed = (
            previous.bucket_tile_width,
            previous.bucket_tile_height,
        ) != (
            settings.bucket_tile_width,
            settings.bucket_tile_height,
        )
        extraction_changed = (
            previous.trim_transparent,
            previous.padding,
            previous.anchor,
        ) != (
            settings.trim_transparent,
            settings.padding,
            settings.anchor,
        )
        self.model.settings = settings
        self._apply_selection_geometry()
        self._sync_sheet_to_grid()
        if bucket_size_changed and self.model.tiles:
            try:
                before_tiles = clone_tiles(self.model.tiles)
                self.model.resize_bucket_tiles(settings)
                command = BucketResizeCommand(
                    self.model,
                    previous,
                    before_tiles,
                    clone_settings(settings),
                    clone_tiles(self.model.tiles),
                )
                self.command_stack.execute(command)
            except Exception as exc:
                self.model.settings = previous
                self.settings_panel.set_settings(previous)
                QMessageBox.warning(self, "Settings update failed", str(exc))
        elif extraction_changed and self.source_image is not None and self.model.tiles:
            try:
                self.model.reprocess_tiles(self.source_image)
            except Exception as exc:
                QMessageBox.warning(self, "Settings update failed", str(exc))
        self._sync_shared_image_settings(self.model.settings)
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
            "source_id": self._active_source_id(),
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
        if pending.get("source_id") != self._active_source_id():
            self.statusBar().showMessage("Tile result discarded because the source tab changed.")
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
        self.model.settings = settings
        self._sync_shared_image_settings(settings)
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
        source_key = (document.source_id, document.fingerprint)
        existing_indices = {
            ((tile.source_id or tile.source_path), tile.source_fingerprint, tile.source_frame_index)
            for tile in self.model.tiles
            if tile.source_type == "video" and tile.source_frame_index is not None
        }
        new_refs = [
            ref
            for ref in refs
            if (source_key[0], source_key[1], ref.index) not in existing_indices
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
                source_id=document.source_id,
                source_fingerprint_kind=document.fingerprint_kind,
                source_fingerprint=document.fingerprint,
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
        if self.source_viewer.current_tool() == "rotate":
            self._begin_tile_transform(index)
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
        self.source_viewer.set_tile_transform(None)
        image = self._source_preview_override or self.source_image
        if image is not None:
            self.source_viewer.set_image(pil_to_qimage(image))
            self._apply_selection_geometry()

    def _begin_tile_transform(self, index: int) -> None:
        if not 0 <= index < len(self.model.tiles):
            self.tile_transform_panel.set_target(None)
            return
        if self._transform_tile_index == index and self._transform_working is not None:
            return
        if self._transform_dirty and not self._resolve_dirty_transform():
            return

        tile = self.model.tiles[index]
        self._transform_tile_index = index
        self._transform_before_tiles = clone_tiles(self.model.tiles)
        self._transform_working = tile.transform.copy()
        self._transform_dirty = False
        self._bucket_preview_active = True
        self.source_viewer.set_image(pil_to_qimage(tile.image_rgba))
        self.source_viewer.set_tile_transform(
            self._transform_working,
            tile.base_image_rgba.getchannel("A").getbbox(),
        )
        self.tile_transform_panel.set_transform(self._transform_working)
        self.tile_transform_panel.set_target(tile.name)
        self.statusBar().showMessage(
            f"Rotating bucket tile {index + 1}: {tile.name}. Drag a handle, press Enter to apply, or Esc to cancel."
        )

    def _resolve_dirty_transform(self) -> bool:
        if not self._transform_dirty:
            return True
        message = QMessageBox(self)
        message.setWindowTitle("Unapplied tile transform")
        message.setText("Apply the current tile transform before switching targets?")
        message.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        message.setDefaultButton(QMessageBox.Save)
        choice = message.exec()
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            self._apply_tile_transform()
        else:
            self._cancel_tile_transform()
        return True

    def _tile_transform_preview_changed(self, transform: object) -> None:
        index = self._transform_tile_index
        if not isinstance(transform, TileTransform) or index is None or not 0 <= index < len(self.model.tiles):
            return
        working = transform.copy().validated()
        tile = self.model.tiles[index]
        try:
            preview = render_tile_transform(tile.base_image_rgba, self.model.settings.bucket_settings(), working)
        except Exception as exc:
            self.tile_transform_panel.set_target(tile.name)
            self.statusBar().showMessage(f"Transform preview failed: {exc}")
            return
        self._transform_working = working
        self._transform_dirty = working != tile.transform
        self.source_viewer.refresh_image(pil_to_qimage(preview))
        self.source_viewer.set_tile_transform(
            working,
            tile.base_image_rgba.getchannel("A").getbbox(),
            preserve_drag=True,
        )
        self.tile_transform_panel.set_transform(working)
        self.tile_transform_panel.set_target(
            tile.name,
            dirty=self._transform_dirty,
            clipped=self._transform_is_clipped(tile, working),
        )

    def _apply_tile_transform(self) -> None:
        index = self._transform_tile_index
        working = self._transform_working
        if index is None or working is None or not 0 <= index < len(self.model.tiles):
            return
        tile = self.model.tiles[index]
        if self._transform_dirty:
            before = self._transform_before_tiles or clone_tiles(self.model.tiles)
            tile.transform = working.copy().validated()
            tile.image_rgba = render_tile_transform(
                tile.base_image_rgba,
                self.model.settings.bucket_settings(),
                tile.transform,
            )
            tile.final_size = tile.image_rgba.size
            self._record_bucket_snapshot(before)
            self._refresh_all(selected_index=index)
        self._transform_before_tiles = clone_tiles(self.model.tiles)
        self._transform_working = self.model.tiles[index].transform.copy()
        self._transform_dirty = False
        self.source_viewer.refresh_image(pil_to_qimage(self.model.tiles[index].image_rgba))
        self.source_viewer.set_tile_transform(
            self._transform_working,
            self.model.tiles[index].base_image_rgba.getchannel("A").getbbox(),
        )
        self.tile_transform_panel.set_transform(self._transform_working)
        self.tile_transform_panel.set_target(self.model.tiles[index].name)
        self.statusBar().showMessage(f"Applied transform to {self.model.tiles[index].name}.")

    def _cancel_tile_transform(self) -> None:
        index = self._transform_tile_index
        if index is None or not 0 <= index < len(self.model.tiles):
            return
        tile = self.model.tiles[index]
        self._transform_working = tile.transform.copy()
        self._transform_dirty = False
        self.source_viewer.refresh_image(pil_to_qimage(tile.image_rgba))
        self.source_viewer.set_tile_transform(
            self._transform_working,
            tile.base_image_rgba.getchannel("A").getbbox(),
        )
        self.tile_transform_panel.set_transform(self._transform_working)
        self.tile_transform_panel.set_target(tile.name)
        self.statusBar().showMessage(f"Cancelled unapplied transform for {tile.name}.")

    def _transformed_content_points(
        self,
        tile,
        transform: TileTransform,
    ) -> list[tuple[float, float]]:
        bbox = tile.base_image_rgba.getchannel("A").getbbox()
        if bbox is None:
            return []
        width, height = tile.base_image_rgba.size
        pivot_x = transform.pivot_x * width
        pivot_y = transform.pivot_y * height
        radians = math.radians(transform.angle_degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        points: list[tuple[float, float]] = []
        for x, y in ((bbox[0], bbox[1]), (bbox[2], bbox[1]), (bbox[2], bbox[3]), (bbox[0], bbox[3])):
            dx = (x - pivot_x) * transform.scale_x
            dy = (y - pivot_y) * transform.scale_y
            points.append((pivot_x + cosine * dx - sine * dy, pivot_y + sine * dx + cosine * dy))
        return points

    def _transform_is_clipped(self, tile, transform: TileTransform) -> bool:
        width, height = tile.base_image_rgba.size
        epsilon = 1e-6
        return any(
            x < -epsilon or y < -epsilon or x > width + epsilon or y > height + epsilon
            for x, y in self._transformed_content_points(tile, transform)
        )

    def _maximum_uniform_transform_scale(self, tile, transform: TileTransform) -> float:
        bbox = tile.base_image_rgba.getchannel("A").getbbox()
        if bbox is None:
            return 1.0
        settings = self.model.settings.bucket_settings()
        width, height = tile.base_image_rgba.size
        pivot_x = transform.pivot_x * width
        pivot_y = transform.pivot_y * height
        radians = math.radians(transform.angle_degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        limits: list[float] = []
        left = float(settings.padding)
        top = float(settings.padding)
        right = float(width - settings.padding)
        bottom = float(height - settings.padding)
        for x, y in ((bbox[0], bbox[1]), (bbox[2], bbox[1]), (bbox[2], bbox[3]), (bbox[0], bbox[3])):
            dx = x - pivot_x
            dy = y - pivot_y
            rotated_x = cosine * dx - sine * dy
            rotated_y = sine * dx + cosine * dy
            if rotated_x > 0:
                limits.append((right - pivot_x) / rotated_x)
            elif rotated_x < 0:
                limits.append((pivot_x - left) / -rotated_x)
            if rotated_y > 0:
                limits.append((bottom - pivot_y) / rotated_y)
            elif rotated_y < 0:
                limits.append((pivot_y - top) / -rotated_y)
        positive = [limit for limit in limits if limit > 0 and math.isfinite(limit)]
        return max(0.01, min(positive, default=1.0))

    def _fit_transform_content(self) -> None:
        self._fit_rotated_content()

    def _fill_transform_canvas(self) -> None:
        index = self._transform_tile_index
        if index is None or not 0 <= index < len(self.model.tiles) or self._transform_working is None:
            return
        tile = self.model.tiles[index]
        bbox = tile.base_image_rgba.getchannel("A").getbbox()
        if bbox is None:
            return
        settings = self.model.settings.bucket_settings()
        inner_width = max(1, settings.tile_width - settings.padding * 2)
        inner_height = max(1, settings.tile_height - settings.padding * 2)
        scale = max(inner_width / max(1, bbox[2] - bbox[0]), inner_height / max(1, bbox[3] - bbox[1]))
        transform = self._transform_working.copy()
        transform.scale_x = scale
        transform.scale_y = scale
        self._tile_transform_preview_changed(transform)

    def _fit_rotated_content(self) -> None:
        index = self._transform_tile_index
        if index is None or not 0 <= index < len(self.model.tiles) or self._transform_working is None:
            return
        transform = self._transform_working.copy()
        scale = self._maximum_uniform_transform_scale(self.model.tiles[index], transform)
        transform.scale_x = scale
        transform.scale_y = scale
        self._tile_transform_preview_changed(transform)

    def _prepare_transform_for_bucket_mutation(self) -> bool:
        if self.source_viewer.current_tool() != "rotate":
            return True
        return self._resolve_dirty_transform()

    def _sync_transform_session_from_model(self, selected_index: int | None = None) -> None:
        if self.source_viewer.current_tool() != "rotate":
            return
        if not self.model.tiles:
            self._transform_tile_index = None
            self._transform_before_tiles = None
            self._transform_working = None
            self._transform_dirty = False
            self.source_viewer.set_tile_transform(None)
            self.source_viewer.set_tool("select")
            self.select_action.setChecked(True)
            self.right_panel_stack.setCurrentWidget(
                self.video_settings_panel if self.source_type == "video" else self.settings_panel
            )
            self._restore_source_after_bucket_preview()
            return
        index = selected_index
        if index is None:
            index = self._transform_tile_index
        if index is None or not 0 <= index < len(self.model.tiles):
            index = min(max(self.bucket_panel.current_index(), 0), len(self.model.tiles) - 1)
        self._transform_tile_index = None
        self._transform_before_tiles = None
        self._transform_working = None
        self._transform_dirty = False
        self._begin_tile_transform(index)

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
            tile = self.model.tiles[index]
            if tile.transform != TileTransform():
                before = clone_tiles(self.model.tiles)
                tile.base_image_rgba = tile.image_rgba.copy()
                tile.transform = TileTransform()
                tile.image_rgba = tile.base_image_rgba.copy()
                tile.final_size = tile.image_rgba.size
                self._record_bucket_snapshot(before)
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
            self.model.tiles[index].base_image_rgba = result.copy()
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
        if not self._prepare_transform_for_bucket_mutation():
            return
        self._record_bucket_change(lambda: self.model.remove_tile(index))
        self._refresh_all(selected_index=min(index, len(self.model.tiles) - 1))

    def _clear_bucket(self) -> None:
        count = len(self.model.tiles)
        if count == 0:
            return
        if not self._prepare_transform_for_bucket_mutation():
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
        if not self._prepare_transform_for_bucket_mutation():
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
        if not self._prepare_transform_for_bucket_mutation():
            return
        before = clone_tiles(self.model.tiles)
        new_index = self.model.move_tile(index, offset)
        if [tile.tile_id for tile in before] != [tile.tile_id for tile in self.model.tiles]:
            self._record_bucket_snapshot(before)
        self._refresh_all(selected_index=new_index)

    def _reorder_tiles(self, order: object) -> None:
        if not self._prepare_transform_for_bucket_mutation():
            return
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
        if not self._prepare_transform_for_bucket_mutation():
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
        if not self._prepare_transform_for_bucket_mutation():
            return
        if self.command_stack.undo():
            if self.source_type == "image":
                self._sync_shared_image_settings(self.model.settings)
                self.settings_panel.set_settings(self.model.settings)
                self._apply_selection_geometry()
            self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _redo_bucket(self) -> None:
        if not self._prepare_transform_for_bucket_mutation():
            return
        if self.command_stack.redo():
            if self.source_type == "image":
                self._sync_shared_image_settings(self.model.settings)
                self.settings_panel.set_settings(self.model.settings)
                self._apply_selection_geometry()
            self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _set_viewer_tool(self, tool: str) -> None:
        current_tool = self.source_viewer.current_tool()
        if tool == "rotate" and not self.model.tiles:
            self.statusBar().showMessage("Add a bucket tile before using Rotate.")
            self.select_action.setChecked(True)
            return
        if current_tool == "rotate" and tool != "rotate":
            if self._transform_dirty and not self._resolve_dirty_transform():
                self.rotate_action.setChecked(True)
                return
            self._transform_tile_index = None
            self._transform_before_tiles = None
            self._transform_working = None
            self._transform_dirty = False
            self.source_viewer.set_tile_transform(None)
            self._restore_source_after_bucket_preview()
        elif tool not in {"retouch", "rotate"}:
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
        elif tool == "rotate":
            self.rotate_action.setChecked(True)
            self.right_panel_stack.setCurrentWidget(self.tile_transform_panel)
            index = self.bucket_panel.current_index()
            if index < 0 and self.model.tiles:
                index = 0
            self._begin_tile_transform(index)
        else:
            self.select_action.setChecked(True)
            if self.source_type == "video":
                self.right_panel_stack.setCurrentWidget(self.video_settings_panel)
            else:
                self.right_panel_stack.setCurrentWidget(self.settings_panel)
        if tool not in {"retouch", "rotate"}:
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
        self._sync_transform_session_from_model(selected_index)

    def _refresh_retouch_bucket_preview(self) -> None:
        if self.source_viewer.current_tool() != "retouch" or self._retouch_target != "bucket":
            return
        index = self._retouch_bucket_index
        if index is None or not 0 <= index < len(self.model.tiles):
            return
        self.source_viewer.refresh_image(pil_to_qimage(self.model.tiles[index].image_rgba))

    def _refresh_action_context(self) -> None:
        capacity = sheet_capacity(self.model.settings)
        self.rotate_action.setEnabled(bool(self.model.tiles))
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

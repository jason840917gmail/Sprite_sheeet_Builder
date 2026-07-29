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
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet, sheet_capacity
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
from sprite_sheet_cleaner.app.utils.tool_icons import create_grid_icon, create_pointer_icon, create_select_icon
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage
from sprite_sheet_cleaner.app.widgets.bucket_panel import BucketPanel
from sprite_sheet_cleaner.app.widgets.animation_preview_dialog import AnimationPreviewDialog
from sprite_sheet_cleaner.app.widgets.final_preview import FinalPreview
from sprite_sheet_cleaner.app.widgets.frame_browser import FrameBrowser
from sprite_sheet_cleaner.app.widgets.settings_panel import SettingsPanel
from sprite_sheet_cleaner.app.widgets.source_viewer import SourceViewer
from sprite_sheet_cleaner.app.widgets.video_settings_panel import VideoSettingsPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sprite Sheet Cleaner")
        self.resize(1320, 820)

        self.model = ProjectModel()
        self._image_settings = self.model.settings
        self.source_image: Image.Image | None = None
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

        self.source_viewer = SourceViewer()
        self.video_tabs = QTabWidget()
        self.video_tabs.setDocumentMode(True)
        self.video_tabs.setTabsClosable(True)
        self.video_tabs.setMinimumHeight(150)
        self.frame_browser: FrameBrowser | None = None
        self.settings_panel = SettingsPanel()
        self.video_settings_panel = VideoSettingsPanel()
        self.bucket_panel = BucketPanel()
        self.final_preview = FinalPreview()
        self._apply_selection_geometry()

        self._build_layout()
        self._create_actions()
        self._connect_signals()
        self._refresh_all()

    def _build_layout(self) -> None:
        self.source_viewer.setMinimumSize(780, 520)
        self.final_preview.setMinimumHeight(170)
        self.settings_panel.setMinimumWidth(310)
        self.video_settings_panel.setMinimumWidth(310)
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
        self.right_panel_stack.setCurrentWidget(self.settings_panel)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.addWidget(self.right_panel_stack)
        self.right_splitter.addWidget(self.bucket_panel)
        self.right_splitter.addWidget(self.final_preview)
        self.right_splitter.setStretchFactor(0, 2)
        self.right_splitter.setStretchFactor(1, 2)
        self.right_splitter.setStretchFactor(2, 1)

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
        # Give the source preview and frame list equal default space. The
        # final preview lives below the bucket in the right panel.
        self.left_splitter.setSizes([round(height * 0.50), round(height * 0.50)])
        self.right_splitter.setSizes([round(height * 0.40), round(height * 0.35), round(height * 0.25)])

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
        view_menu = self.menuBar().addMenu("&View")
        tool_menu = self.menuBar().addMenu("&Tools")

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
        self.tool_group.addAction(self.pointer_action)
        self.tool_group.addAction(self.select_action)
        self.tool_group.addAction(self.grid_action)
        self.tool_bar.addAction(self.pointer_action)
        self.tool_bar.addAction(self.select_action)
        self.tool_bar.addAction(self.grid_action)
        tool_menu.addAction(self.pointer_action)
        tool_menu.addAction(self.select_action)
        tool_menu.addAction(self.grid_action)

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
        self.add_selection_action.triggered.connect(self._add_selection_to_bucket)
        self.delete_tile_action.triggered.connect(self._delete_selected_tile)
        self.clear_selection_action.triggered.connect(self._clear_source_selection)

        self.source_viewer.cursorPositionChanged.connect(self._set_mouse_status)
        self.source_viewer.selectionChanged.connect(self._set_selection_status)
        self.source_viewer.zoomChanged.connect(self._set_zoom_status)
        self.source_viewer.toolChanged.connect(self._viewer_tool_changed)
        self.source_viewer.gridCellClicked.connect(self._add_grid_cell_to_bucket)
        self.source_viewer.gridStatusChanged.connect(self._grid_status_changed)
        self.video_tabs.currentChanged.connect(self._video_tab_changed)
        self.video_tabs.tabCloseRequested.connect(self._close_video_tab)
        self.settings_panel.settingsChanged.connect(self._settings_changed)
        self.settings_panel.addSelectionRequested.connect(self._add_selection_to_bucket)
        self.settings_panel.addAllRequested.connect(self._add_all_grid_cells)
        self.settings_panel.detectBackgroundRequested.connect(self._detect_background_color)
        self.video_settings_panel.settingsChanged.connect(self._video_settings_changed)
        self.video_settings_panel.detectBackgroundRequested.connect(self._detect_background_color)
        self.video_settings_panel.applyToBucketRequested.connect(self._apply_video_settings_to_bucket)
        self.final_preview.animationRequested.connect(self._open_animation_preview)
        self.bucket_panel.deleteRequested.connect(self._delete_tile)
        self.bucket_panel.clearRequested.connect(self._clear_bucket)
        self.bucket_panel.duplicateRequested.connect(self._duplicate_tile)
        self.bucket_panel.moveUpRequested.connect(lambda index: self._move_tile(index, -1))
        self.bucket_panel.moveDownRequested.connect(lambda index: self._move_tile(index, 1))
        self.bucket_panel.renameRequested.connect(self._rename_tile)
        self.bucket_panel.reorderRequested.connect(self._reorder_tiles)
        self.bucket_panel.tileClicked.connect(self._preview_bucket_tile)

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
            remove_background=video.remove_background,
            background_color=video.background_color,
            tolerance=video.tolerance,
            trim_transparent=video.trim_transparent,
            scale_mode="none",
            padding=0,
            anchor=video.anchor,
        ).validated()

    def _set_image_panel_mode(self) -> None:
        self.right_panel_stack.setCurrentWidget(self.settings_panel)
        self.select_action.setEnabled(True)
        self.grid_action.setEnabled(True)

    def _set_video_panel_mode(self, document: VideoDocument) -> None:
        self.right_panel_stack.setCurrentWidget(self.video_settings_panel)
        self.video_settings_panel.set_settings(document.settings)
        self.select_action.setEnabled(False)
        self.grid_action.setEnabled(False)
        self._set_viewer_tool("pointer")

    def _activate_video_document(self, document: VideoDocument, *, show_frame: bool = True) -> None:
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
        self.source_type = "image"
        self.video_source_path = None
        self.video_metadata = None
        self.source_image = None
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
        if clear_tiles:
            self.model.clear_tiles()
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
            "Sprite Sheet Cleaner project (*.ssc.json);;JSON (*.json)",
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix.lower() != ".json":
            output_path = output_path.with_suffix(".ssc.json")
        try:
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
            "Sprite Sheet Cleaner project (*.ssc.json *.json);;JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        project_path = Path(path)
        try:
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
            else:
                source_path_value = data.get("source_path") or data.get("source_image_path")
                source_path = resolve_project_path(source_path_value)
                with Image.open(source_path) as image:
                    self.source_image = image.convert("RGBA")
                self._clear_video_documents()
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
        self._refresh_all()
        self.statusBar().showMessage(f"Loaded project {project_path.name}")

    def _settings_changed(self, settings: AppSettings) -> None:
        if self.source_type == "video":
            return
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
            document.settings.background_color = settings.background_color
            document.settings.tolerance = settings.tolerance
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

    def _apply_video_settings_to_bucket(self) -> None:
        if self.source_type != "video":
            return
        document = self._active_video_document()
        if document is None:
            return
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
            )
        except Exception as exc:
            QMessageBox.critical(self, "Apply video settings failed", str(exc))
            return
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage("Applied video output settings to the existing video tiles.")

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

        try:
            added_tiles = self.model.add_tiles_from_selection(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add selection failed", str(exc))
            return

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

        for index in reversed(matching_indexes):
            self.model.remove_tile(index)
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

        try:
            added_tiles = self.model.add_tiles_from_rects(self.source_image, new_rects)
        except Exception as exc:
            QMessageBox.critical(self, "Add grid tiles failed", str(exc))
            return

        if clear_selection_on_success:
            self.source_viewer.clear_selection()
        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        self.statusBar().showMessage(f"Added {len(added_tiles)} tiles from {description}.")

    def _add_grid_cell_to_bucket(self, rect: tuple[int, int, int, int]) -> None:
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

        try:
            self.model.add_tile_from_crop(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add grid tile failed", str(exc))
            return

        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        cell = self.source_viewer.grid_cell_for_rect(rect)
        if cell is None:
            self.statusBar().showMessage(f"Added tile {self.model.tiles[-1].name}")
            return
        column, row = cell
        self.statusBar().showMessage(f"Added grid tile row {row + 1}, column {column + 1}")

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
        if self.source_image is None:
            return None

        try:
            color = detect_background_color(self.source_image, self.source_viewer.selection_rect())
        except Exception as exc:
            if show_error_dialog:
                QMessageBox.critical(self, "Detect background failed", str(exc))
            return None

        if self.source_type == "video":
            self.video_settings_panel.set_detected_background_color(color)
        else:
            self.settings_panel.set_detected_background_color(color)
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
        self.source_image = tile.image_rgba.copy()
        self._current_frame_ref = None
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self.statusBar().showMessage(f"Previewing bucket tile {index + 1}: {tile.name}")

    def _clear_source_selection(self) -> None:
        self.source_viewer.clear_selection()
        self.statusBar().showMessage("Cleared source selection")

    def _delete_tile(self, index: int) -> None:
        if index < 0:
            return
        self.model.remove_tile(index)
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
        self.model.clear_tiles()
        self._refresh_all()
        self.statusBar().showMessage("Cleared bucket")

    def _duplicate_tile(self, index: int) -> None:
        if index < 0:
            return
        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return
        duplicate = self.model.duplicate_tile(index)
        if duplicate is not None:
            self._refresh_all(selected_index=index + 1)

    def _move_tile(self, index: int, offset: int) -> None:
        if index < 0:
            return
        new_index = self.model.move_tile(index, offset)
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
        self.model.tiles = [self.model.tiles[index] for index in indices]
        self._refresh_all(selected_index=self.bucket_panel.current_index())
        self.statusBar().showMessage("Reordered bucket tiles.")

    def _rename_tile(self, index: int) -> None:
        if index < 0:
            return
        current_name = self.model.tiles[index].name
        name, accepted = QInputDialog.getText(self, "Rename tile", "Name", text=current_name)
        if accepted and name.strip():
            self.model.rename_tile(index, name)
            self._refresh_all(selected_index=index)

    def _set_viewer_tool(self, tool: str) -> None:
        self.source_viewer.set_tool(tool)
        self.source_viewer.setFocus(Qt.ShortcutFocusReason)
        if tool == "pointer":
            self.pointer_action.setChecked(True)
        elif tool == "grid":
            self.grid_action.setChecked(True)
            self._warn_if_grid_unavailable()
        else:
            self.select_action.setChecked(True)
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
        self._refresh_action_context()
        self._update_status()

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
        else:
            hint = ""
        self.statusBar().showMessage(f"{tool} | {mouse} | {selection} | {zoom}{frame}{grid}{hint}")

    def closeEvent(self, event) -> None:
        for document in self.video_documents:
            document.browser.cancel_extraction()
        super().closeEvent(event)

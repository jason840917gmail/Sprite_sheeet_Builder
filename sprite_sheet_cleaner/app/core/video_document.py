from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from PIL import Image

from sprite_sheet_cleaner.app.core.video_source import VideoMetadata, FrameRef
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings
from sprite_sheet_cleaner.app.models.video_settings import VideoSettings
from sprite_sheet_cleaner.app.widgets.frame_browser import FrameBrowser


@dataclass
class VideoDocument:
    path: Path
    metadata: VideoMetadata
    browser: FrameBrowser
    source_id: str = field(default_factory=lambda: uuid4().hex)
    fingerprint_kind: str | None = None
    fingerprint: str | None = None
    settings: VideoSettings = field(default_factory=VideoSettings)
    resize_settings: dict[int, FrameResizeSettings] = field(default_factory=dict)
    frame_cache: dict[int, Image.Image] = field(default_factory=dict)
    current_ref: FrameRef | None = None
    background_detected: bool = False


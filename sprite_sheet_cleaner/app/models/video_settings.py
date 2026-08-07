from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from sprite_sheet_cleaner.app.models.source_processing_settings import (
    BackgroundEngineId,
    ComputePreference,
    SourceProcessingSettings,
)


VideoResizeMode = Literal["fit", "stretch", "fill"]
VideoAnchor = Literal["center", "bottom-center"]

VALID_VIDEO_RESIZE_MODES: tuple[str, ...] = ("fit", "stretch", "fill")
VALID_VIDEO_ANCHORS: tuple[str, ...] = ("center", "bottom-center")


@dataclass(slots=True)
class VideoSettings:
    """Sampling settings used to turn a video into candidate frame references."""

    start_frame: int = 0
    end_frame: int | None = None
    sample_every: int = 1
    target_fps: float | None = None
    max_frames: int = 256
    remove_near_duplicates: bool = False
    duplicate_threshold: float = 0.995
    frame_width: int = 64
    frame_height: int = 64
    lock_frame_aspect: bool = True
    resize_mode: VideoResizeMode = "fit"
    remove_background: bool = True
    engine: BackgroundEngineId = "exact_key"
    background_color: tuple[int, int, int] = (255, 0, 255)
    tolerance: int = 30
    transparent_threshold: int = 24
    foreground_threshold: int = 64
    despill_strength: int = 0
    pixel_art_mode: bool = False
    compute: ComputePreference = "auto"
    model_id: str | None = None
    trim_transparent: bool = False
    anchor: VideoAnchor = "center"
    sheet_columns: int = 8
    sheet_rows: int = 8
    seed_frame_count: int = 10

    def validated(self) -> "VideoSettings":
        if self.start_frame < 0:
            raise ValueError("Start frame cannot be negative.")
        if self.end_frame is not None and self.end_frame < self.start_frame:
            raise ValueError("End frame must be greater than or equal to start frame.")
        if self.sample_every <= 0:
            raise ValueError("Sample every must be positive.")
        if self.target_fps is not None and self.target_fps <= 0:
            raise ValueError("Target FPS must be positive.")
        if self.max_frames <= 0:
            raise ValueError("Maximum frames must be positive.")
        if not 0.0 <= self.duplicate_threshold <= 1.0:
            raise ValueError("Duplicate threshold must be between 0 and 1.")
        if self.frame_width <= 0 or self.frame_height <= 0:
            raise ValueError("Video frame dimensions must be positive.")
        if self.resize_mode not in VALID_VIDEO_RESIZE_MODES:
            raise ValueError(f"Unsupported video resize mode: {self.resize_mode}")
        if self.tolerance < 0 or self.tolerance > 255:
            raise ValueError("Video tolerance must be between 0 and 255.")
        if self.anchor not in VALID_VIDEO_ANCHORS:
            raise ValueError(f"Unsupported video anchor: {self.anchor}")
        if len(self.background_color) != 3:
            raise ValueError("Video background color must be an RGB tuple.")
        if any(channel < 0 or channel > 255 for channel in self.background_color):
            raise ValueError("Video background color channels must be between 0 and 255.")
        if self.sheet_columns <= 0 or self.sheet_rows <= 0:
            raise ValueError("Video sheet dimensions must be positive.")
        if self.seed_frame_count <= 0:
            raise ValueError("Seed animation frame count must be positive.")
        self.to_source_processing_settings().validated()
        return self

    def to_source_processing_settings(self) -> SourceProcessingSettings:
        return SourceProcessingSettings(
            engine=self.engine,
            remove_background=self.remove_background,
            background_color=self.background_color,
            tolerance=self.tolerance,
            transparent_threshold=self.transparent_threshold,
            foreground_threshold=self.foreground_threshold,
            despill_strength=self.despill_strength,
            pixel_art_mode=self.pixel_art_mode,
            compute=self.compute,
            model_id=self.model_id,
        ).validated()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "VideoSettings":
        values = dict(data)
        if values.get("end_frame") is not None:
            values["end_frame"] = int(values["end_frame"])
        if values.get("target_fps") is not None:
            values["target_fps"] = float(values["target_fps"])
        if "background_color" in values:
            color = values["background_color"]
            if not isinstance(color, (list, tuple)) or len(color) != 3:
                raise ValueError("Video background_color must contain three values.")
            values["background_color"] = tuple(int(channel) for channel in color)
        if "frame_width" in values:
            values["frame_width"] = int(values["frame_width"])
        if "frame_height" in values:
            values["frame_height"] = int(values["frame_height"])
        if "tolerance" in values:
            values["tolerance"] = int(values["tolerance"])
        if "sheet_columns" in values:
            values["sheet_columns"] = int(values["sheet_columns"])
        if "sheet_rows" in values:
            values["sheet_rows"] = int(values["sheet_rows"])
        if "seed_frame_count" in values:
            values["seed_frame_count"] = int(values["seed_frame_count"])
        settings = cls(
            start_frame=int(values.get("start_frame", 0)),
            end_frame=values.get("end_frame"),
            sample_every=int(values.get("sample_every", 1)),
            target_fps=values.get("target_fps"),
            max_frames=int(values.get("max_frames", 256)),
            remove_near_duplicates=bool(values.get("remove_near_duplicates", False)),
            duplicate_threshold=float(values.get("duplicate_threshold", 0.995)),
            frame_width=int(values.get("frame_width", 64)),
            frame_height=int(values.get("frame_height", 64)),
            lock_frame_aspect=bool(values.get("lock_frame_aspect", True)),
            resize_mode=str(values.get("resize_mode", "fit")),
            remove_background=bool(values.get("remove_background", True)),
            engine=str(values.get("engine", "exact_key")),
            background_color=values.get("background_color", (255, 0, 255)),
            tolerance=int(values.get("tolerance", 30)),
            transparent_threshold=int(values.get("transparent_threshold", 24)),
            foreground_threshold=int(values.get("foreground_threshold", 64)),
            despill_strength=int(values.get("despill_strength", 0)),
            pixel_art_mode=bool(values.get("pixel_art_mode", False)),
            compute=str(values.get("compute", "auto")),
            model_id=str(values["model_id"]) if values.get("model_id") else None,
            trim_transparent=bool(values.get("trim_transparent", False)),
            anchor=str(values.get("anchor", "center")),
            sheet_columns=int(values.get("sheet_columns", 8)),
            sheet_rows=int(values.get("sheet_rows", 8)),
            seed_frame_count=int(values.get("seed_frame_count", 10)),
        )
        return settings.validated()

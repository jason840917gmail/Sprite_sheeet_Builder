from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from sprite_sheet_cleaner.app.models.sheet_settings import SheetSettings
from sprite_sheet_cleaner.app.models.bucket_settings import (
    BucketResizeMode,
    BucketResampleMode,
    BucketSettings,
    VALID_BUCKET_RESAMPLE_MODES,
    VALID_BUCKET_RESIZE_MODES,
)
from sprite_sheet_cleaner.app.models.source_processing_settings import BackgroundEngineId, SourceProcessingSettings
from sprite_sheet_cleaner.app.models.tile_settings import TileSettings


ScaleMode = Literal["none", "scale_down_only", "scale_to_fit"]
Anchor = Literal["center", "bottom-center"]

VALID_SCALE_MODES: tuple[str, ...] = ("none", "scale_down_only", "scale_to_fit")
VALID_ANCHORS: tuple[str, ...] = ("center", "bottom-center")


@dataclass(slots=True)
class AppSettings:
    tile_width: int = 256
    tile_height: int = 256
    lock_tile_aspect: bool = True
    bucket_tile_width: int | None = None
    bucket_tile_height: int | None = None
    lock_bucket_aspect: bool = True
    bucket_resize_mode: BucketResizeMode | None = None
    bucket_resample_mode: BucketResampleMode = "smooth"
    selection_columns: int = 1
    selection_rows: int = 1
    sheet_columns: int = 8
    sheet_rows: int = 8
    match_sheet_to_grid: bool = False
    remove_background: bool = True
    tile_background_engine: BackgroundEngineId = "exact_key"
    background_color: tuple[int, int, int] = (255, 0, 255)
    tolerance: int = 30
    trim_transparent: bool = False
    scale_mode: ScaleMode = "none"
    padding: int = 0
    anchor: Anchor = "center"
    edge_bleed: int = 1

    def validated(self) -> "AppSettings":
        if self.tile_width <= 0 or self.tile_height <= 0:
            raise ValueError("Source selection dimensions must be positive.")
        if self.scale_mode not in VALID_SCALE_MODES:
            raise ValueError(f"Unsupported scale mode: {self.scale_mode}")
        if self.bucket_tile_width is None:
            self.bucket_tile_width = self.tile_width
        if self.bucket_tile_height is None:
            self.bucket_tile_height = self.tile_height
        if self.bucket_resize_mode is None:
            self.bucket_resize_mode = {
                "none": "none",
                "scale_down_only": "fit_down_only",
                "scale_to_fit": "fit",
            }[self.scale_mode]
        if self.bucket_tile_width <= 0 or self.bucket_tile_height <= 0:
            raise ValueError("Bucket tile dimensions must be positive.")
        if self.bucket_resize_mode not in VALID_BUCKET_RESIZE_MODES:
            raise ValueError(f"Unsupported bucket resize mode: {self.bucket_resize_mode}")
        if self.bucket_resample_mode not in VALID_BUCKET_RESAMPLE_MODES:
            raise ValueError(f"Unsupported bucket resampling mode: {self.bucket_resample_mode}")
        if self.selection_columns <= 0 or self.selection_rows <= 0:
            raise ValueError("Selection grid dimensions must be positive.")
        if self.sheet_columns <= 0 or self.sheet_rows <= 0:
            raise ValueError("Final tilesheet dimensions must be positive.")
        if self.padding < 0:
            raise ValueError("Padding cannot be negative.")
        if self.edge_bleed < 0:
            raise ValueError("Edge bleed cannot be negative.")
        if self.tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")
        if self.tile_background_engine not in {"exact_key", "smart_solid", "rembg", "ben2"}:
            raise ValueError(f"Unsupported tile background engine: {self.tile_background_engine}")
        if self.anchor not in VALID_ANCHORS:
            raise ValueError(f"Unsupported anchor: {self.anchor}")
        if len(self.background_color) != 3:
            raise ValueError("Background color must be an RGB tuple.")
        if any(channel < 0 or channel > 255 for channel in self.background_color):
            raise ValueError("Background color channels must be between 0 and 255.")
        return self

    def to_dict(self) -> dict[str, object]:
        self.validated()
        data = asdict(self)
        data["background_color"] = list(self.background_color)
        return data

    def source_processing_settings(self) -> SourceProcessingSettings:
        return SourceProcessingSettings(
            remove_background=self.remove_background,
            background_color=self.background_color,
            tolerance=self.tolerance,
            edge_bleed=self.edge_bleed,
        ).validated()

    def tile_processing_settings(self) -> SourceProcessingSettings:
        return SourceProcessingSettings(
            engine=self.tile_background_engine,
            remove_background=self.remove_background,
            background_color=self.background_color,
            tolerance=self.tolerance,
            edge_bleed=self.edge_bleed,
        ).validated()

    def tile_settings(self) -> TileSettings:
        return TileSettings(
            tile_width=self.tile_width,
            tile_height=self.tile_height,
            lock_tile_aspect=self.lock_tile_aspect,
            selection_columns=self.selection_columns,
            selection_rows=self.selection_rows,
            trim_transparent=self.trim_transparent,
            scale_mode=self.scale_mode,
            padding=self.padding,
            anchor=self.anchor,
        ).validated()

    def bucket_settings(self) -> BucketSettings:
        self.validated()
        return BucketSettings(
            tile_width=int(self.bucket_tile_width),
            tile_height=int(self.bucket_tile_height),
            lock_aspect=self.lock_bucket_aspect,
            resize_mode=self.bucket_resize_mode,
            resample_mode=self.bucket_resample_mode,
            padding=self.padding,
            anchor=self.anchor,
            edge_bleed=self.edge_bleed,
        ).validated()

    def sheet_settings(self) -> SheetSettings:
        return SheetSettings(
            sheet_columns=self.sheet_columns,
            sheet_rows=self.sheet_rows,
            match_sheet_to_grid=self.match_sheet_to_grid,
        ).validated()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AppSettings":
        values = dict(data)
        legacy_match = values.pop("match_sheet_to_selection", None)
        if "match_sheet_to_grid" not in values and legacy_match is not None:
            values["match_sheet_to_grid"] = bool(legacy_match)
        if "background_color" in values:
            color = values["background_color"]
            if not isinstance(color, (list, tuple)) or len(color) != 3:
                raise ValueError("Project background_color must contain three values.")
            values["background_color"] = tuple(int(channel) for channel in color)
        settings = cls(**values)
        return settings.validated()

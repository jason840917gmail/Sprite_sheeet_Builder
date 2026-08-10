from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BucketResizeMode = Literal["none", "fit_down_only", "fit", "fill", "stretch"]
BucketResampleMode = Literal["nearest", "smooth"]
BucketAnchor = Literal["center", "bottom-center"]

VALID_BUCKET_RESIZE_MODES: tuple[str, ...] = (
    "none",
    "fit_down_only",
    "fit",
    "fill",
    "stretch",
)
VALID_BUCKET_RESAMPLE_MODES: tuple[str, ...] = ("nearest", "smooth")
VALID_BUCKET_ANCHORS: tuple[str, ...] = ("center", "bottom-center")


@dataclass(slots=True)
class BucketSettings:
    tile_width: int = 256
    tile_height: int = 256
    lock_aspect: bool = True
    resize_mode: BucketResizeMode = "none"
    resample_mode: BucketResampleMode = "smooth"
    padding: int = 0
    anchor: BucketAnchor = "center"
    edge_bleed: int = 1

    def validated(self) -> "BucketSettings":
        if self.tile_width <= 0 or self.tile_height <= 0:
            raise ValueError("Bucket tile dimensions must be positive.")
        if self.resize_mode not in VALID_BUCKET_RESIZE_MODES:
            raise ValueError(f"Unsupported bucket resize mode: {self.resize_mode}")
        if self.resample_mode not in VALID_BUCKET_RESAMPLE_MODES:
            raise ValueError(f"Unsupported bucket resampling mode: {self.resample_mode}")
        if self.padding < 0:
            raise ValueError("Bucket padding cannot be negative.")
        if self.anchor not in VALID_BUCKET_ANCHORS:
            raise ValueError(f"Unsupported bucket anchor: {self.anchor}")
        if self.edge_bleed < 0:
            raise ValueError("Bucket edge bleed cannot be negative.")
        return self

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ScaleMode = Literal["none", "scale_down_only", "scale_to_fit"]
Anchor = Literal["center", "bottom-center"]


@dataclass(slots=True)
class TileSettings:
    tile_width: int = 256
    tile_height: int = 256
    lock_tile_aspect: bool = True
    selection_columns: int = 1
    selection_rows: int = 1
    trim_transparent: bool = False
    scale_mode: ScaleMode = "none"
    padding: int = 0
    anchor: Anchor = "center"

    def validated(self) -> "TileSettings":
        if self.tile_width <= 0 or self.tile_height <= 0:
            raise ValueError("Tile dimensions must be positive.")
        if self.selection_columns <= 0 or self.selection_rows <= 0:
            raise ValueError("Selection grid dimensions must be positive.")
        if self.padding < 0:
            raise ValueError("Padding cannot be negative.")
        if self.scale_mode not in {"none", "scale_down_only", "scale_to_fit"}:
            raise ValueError(f"Unsupported scale mode: {self.scale_mode}")
        if self.anchor not in {"center", "bottom-center"}:
            raise ValueError(f"Unsupported anchor: {self.anchor}")
        return self

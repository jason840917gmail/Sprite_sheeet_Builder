from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ScaleMode = Literal["none", "scale_down_only", "scale_to_fit"]
Anchor = Literal["center", "bottom-center"]

VALID_SCALE_MODES: tuple[str, ...] = ("none", "scale_down_only", "scale_to_fit")
VALID_ANCHORS: tuple[str, ...] = ("center", "bottom-center")


@dataclass(slots=True)
class AppSettings:
    tile_width: int = 256
    tile_height: int = 256
    lock_tile_aspect: bool = True
    selection_columns: int = 1
    selection_rows: int = 1
    sheet_columns: int = 8
    sheet_rows: int = 8
    remove_background: bool = True
    background_color: tuple[int, int, int] = (255, 0, 255)
    tolerance: int = 30
    trim_transparent: bool = False
    scale_mode: ScaleMode = "none"
    padding: int = 0
    anchor: Anchor = "center"

    def validated(self) -> "AppSettings":
        if self.tile_width <= 0 or self.tile_height <= 0:
            raise ValueError("Tile dimensions must be positive.")
        if self.selection_columns <= 0 or self.selection_rows <= 0:
            raise ValueError("Selection grid dimensions must be positive.")
        if self.sheet_columns <= 0 or self.sheet_rows <= 0:
            raise ValueError("Final tilesheet dimensions must be positive.")
        if self.padding < 0:
            raise ValueError("Padding cannot be negative.")
        if self.tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")
        if self.scale_mode not in VALID_SCALE_MODES:
            raise ValueError(f"Unsupported scale mode: {self.scale_mode}")
        if self.anchor not in VALID_ANCHORS:
            raise ValueError(f"Unsupported anchor: {self.anchor}")
        if len(self.background_color) != 3:
            raise ValueError("Background color must be an RGB tuple.")
        if any(channel < 0 or channel > 255 for channel in self.background_color):
            raise ValueError("Background color channels must be between 0 and 255.")
        return self

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["background_color"] = list(self.background_color)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AppSettings":
        values = dict(data)
        if "background_color" in values:
            color = values["background_color"]
            if not isinstance(color, (list, tuple)) or len(color) != 3:
                raise ValueError("Project background_color must contain three values.")
            values["background_color"] = tuple(int(channel) for channel in color)
        settings = cls(**values)
        return settings.validated()

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BackgroundEngineId = Literal["exact_key", "smart_solid", "rembg", "ben2"]
ComputePreference = Literal["auto", "cuda", "cpu"]


@dataclass(slots=True)
class SourceProcessingSettings:
    engine: BackgroundEngineId = "exact_key"
    remove_background: bool = True
    background_color: tuple[int, int, int] = (255, 0, 255)
    tolerance: int = 30
    transparent_threshold: int = 24
    foreground_threshold: int = 64
    despill_strength: int = 0
    pixel_art_mode: bool = False
    edge_bleed: int = 1
    compute: ComputePreference = "auto"
    model_id: str | None = None

    def validated(self) -> "SourceProcessingSettings":
        if self.engine not in {"exact_key", "smart_solid", "rembg", "ben2"}:
            raise ValueError(f"Unsupported background engine: {self.engine}")
        if len(self.background_color) != 3:
            raise ValueError("Background color must be an RGB tuple.")
        if any(channel < 0 or channel > 255 for channel in self.background_color):
            raise ValueError("Background color channels must be between 0 and 255.")
        if self.tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")
        if not 0 <= self.transparent_threshold <= 255:
            raise ValueError("Transparent threshold must be between 0 and 255.")
        if not 0 <= self.foreground_threshold <= 255:
            raise ValueError("Foreground threshold must be between 0 and 255.")
        if self.transparent_threshold > self.foreground_threshold:
            raise ValueError("Transparent threshold cannot exceed foreground threshold.")
        if not 0 <= self.despill_strength <= 100:
            raise ValueError("Despill strength must be between 0 and 100.")
        if self.edge_bleed < 0:
            raise ValueError("Edge bleed cannot be negative.")
        if self.compute not in {"auto", "cuda", "cpu"}:
            raise ValueError(f"Unsupported compute preference: {self.compute}")
        return self

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ResizeMode = Literal["fit", "stretch", "fill"]
VALID_RESIZE_MODES: tuple[str, ...] = ("fit", "stretch", "fill")


@dataclass(frozen=True, slots=True)
class FrameResizeSettings:
    target_width: int
    target_height: int
    mode: ResizeMode = "fit"

    def validated(self) -> "FrameResizeSettings":
        if self.target_width <= 0 or self.target_height <= 0:
            raise ValueError("Resize dimensions must be positive.")
        if self.mode not in VALID_RESIZE_MODES:
            raise ValueError(f"Unsupported resize mode: {self.mode}")
        return self

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FrameResizeSettings":
        return cls(
            target_width=int(data.get("target_width", 64)),
            target_height=int(data.get("target_height", 64)),
            mode=str(data.get("mode", "fit")),
        ).validated()


from __future__ import annotations

from dataclasses import dataclass
import math

from sprite_sheet_cleaner.app.models.bucket_settings import VALID_BUCKET_RESAMPLE_MODES


def normalize_angle(angle_degrees: float) -> float:
    angle = (float(angle_degrees) + 180.0) % 360.0 - 180.0
    if angle == -180.0 and float(angle_degrees) > 0:
        return 180.0
    return angle


@dataclass(slots=True)
class TileTransform:
    scale_x: float = 1.0
    scale_y: float = 1.0
    angle_degrees: float = 0.0
    pivot_x: float = 0.5
    pivot_y: float = 0.5
    resample_mode: str | None = None

    def validated(self) -> "TileTransform":
        values = (self.scale_x, self.scale_y, self.angle_degrees, self.pivot_x, self.pivot_y)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Tile transform values must be finite.")
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise ValueError("Tile transform scales must be positive.")
        if not 0.0 <= self.pivot_x <= 1.0 or not 0.0 <= self.pivot_y <= 1.0:
            raise ValueError("Tile transform pivot must stay inside the bucket canvas.")
        if self.resample_mode is not None and self.resample_mode not in VALID_BUCKET_RESAMPLE_MODES:
            raise ValueError(f"Unsupported tile transform resampling mode: {self.resample_mode}")
        self.angle_degrees = normalize_angle(self.angle_degrees)
        return self

    def copy(self) -> "TileTransform":
        return TileTransform(
            scale_x=self.scale_x,
            scale_y=self.scale_y,
            angle_degrees=self.angle_degrees,
            pivot_x=self.pivot_x,
            pivot_y=self.pivot_y,
            resample_mode=self.resample_mode,
        )

    def to_dict(self) -> dict[str, object]:
        self.validated()
        return {
            "version": 1,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "angle_degrees": self.angle_degrees,
            "pivot_x": self.pivot_x,
            "pivot_y": self.pivot_y,
            "resample_mode": self.resample_mode,
        }

    @classmethod
    def from_dict(cls, data: object) -> "TileTransform":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("Tile transform must be an object.")
        if int(data.get("version", 1)) != 1:
            raise ValueError(f"Unsupported tile transform version: {data.get('version')}")
        transform = cls(
            scale_x=float(data.get("scale_x", 1.0)),
            scale_y=float(data.get("scale_y", 1.0)),
            angle_degrees=float(data.get("angle_degrees", 0.0)),
            pivot_x=float(data.get("pivot_x", 0.5)),
            pivot_y=float(data.get("pivot_y", 0.5)),
            resample_mode=(str(data["resample_mode"]) if data.get("resample_mode") is not None else None),
        )
        return transform.validated()

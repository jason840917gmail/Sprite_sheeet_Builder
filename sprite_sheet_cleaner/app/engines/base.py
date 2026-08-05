from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from PIL import Image
import numpy as np


ProgressCallback = Callable[[float, str], None]
CancelCallback = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class EngineDescriptor:
    engine_id: str
    display_name: str
    requires_runtime: bool = False
    model_id: str | None = None


@dataclass(slots=True)
class MatteResult:
    matte: np.ndarray
    engine_id: str
    backend: str = "cpu"
    warnings: list[str] = field(default_factory=list)

    def validated(self, image: Image.Image) -> "MatteResult":
        expected = (image.height, image.width)
        if self.matte.shape != expected:
            raise ValueError(f"Matte dimensions {self.matte.shape} do not match image {expected}.")
        if self.matte.dtype != np.uint8:
            raise ValueError("Matte must use uint8 alpha values.")
        return self


class BackgroundEngine(Protocol):
    descriptor: EngineDescriptor

    def remove(
        self,
        image: Image.Image,
        settings: object,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCallback | None = None,
    ) -> MatteResult:
        ...

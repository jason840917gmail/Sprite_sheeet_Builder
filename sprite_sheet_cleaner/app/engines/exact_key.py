from __future__ import annotations

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.engines.base import BackgroundEngine, EngineDescriptor, MatteResult


class ExactKeyEngine:
    descriptor = EngineDescriptor("exact_key", "Exact Key")

    def remove(
        self,
        image: Image.Image,
        settings: object,
        *,
        progress=None,
        cancelled=None,
    ) -> MatteResult:
        background = tuple(getattr(settings, "background_color", (255, 0, 255)))
        tolerance = int(getattr(settings, "tolerance", 30))
        if tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")
        rgba = np.asarray(image.convert("RGBA"), dtype=np.int32)
        if cancelled is not None and cancelled():
            raise RuntimeError("Background removal cancelled.")
        distance_squared = np.sum((rgba[:, :, :3] - np.asarray(background, dtype=np.int32)) ** 2, axis=2)
        matte = np.where(distance_squared <= tolerance * tolerance, 0, 255).astype(np.uint8)
        if progress is not None:
            progress(1.0, "Exact key complete")
        return MatteResult(matte=matte, engine_id=self.descriptor.engine_id).validated(image)

from __future__ import annotations

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.core.color_math import lab_distance, robust_border_color
from sprite_sheet_cleaner.app.core.matte_ops import border_connected, soft_threshold
from sprite_sheet_cleaner.app.engines.base import EngineDescriptor, MatteResult


class SmartSolidEngine:
    descriptor = EngineDescriptor("smart_solid", "Smart Solid")

    def remove(self, image: Image.Image, settings: object, *, progress=None, cancelled=None) -> MatteResult:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        if cancelled is not None and cancelled():
            raise RuntimeError("Background removal cancelled.")

        configured_color = getattr(settings, "background_color", None)
        if configured_color is None:
            background_color, confidence = robust_border_color(rgba)
        else:
            background_color = tuple(int(channel) for channel in configured_color)
            _, confidence = robust_border_color(rgba)

        distance = lab_distance(rgba[:, :, :3], background_color)
        transparent_threshold = float(getattr(settings, "transparent_threshold", 24))
        foreground_threshold = float(getattr(settings, "foreground_threshold", 64))
        matte = soft_threshold(distance, transparent_threshold, foreground_threshold)

        uncertain = matte < 255
        matte[uncertain & ~border_connected(uncertain)] = 255
        if getattr(settings, "pixel_art_mode", False):
            matte = np.where(matte < 128, 0, 255).astype(np.uint8)
        if progress is not None:
            progress(1.0, f"Smart Solid complete (confidence {confidence:.2f})")
        warnings = [] if confidence >= 0.5 else ["Border background confidence is low."]
        return MatteResult(matte=matte, engine_id=self.descriptor.engine_id, warnings=warnings).validated(image)

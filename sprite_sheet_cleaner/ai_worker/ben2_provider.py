"""BEN2 Base ONNX adapter using the upstream 1024x1024 contract."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.app.engines.base import EngineDescriptor, MatteResult
from sprite_sheet_cleaner.ai_worker.onnx_provider import OnnxSession, create_session


BEN2_INPUT_SIZE = 1024
BEN2_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
BEN2_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


class Ben2Provider:
    descriptor = EngineDescriptor("ben2", "BEN2 Base", requires_runtime=True, model_id="ben2-base-onnx")

    def __init__(
        self,
        model_path: str | Path,
        *,
        preference: str = "auto",
        runtime_module: object | None = None,
        session_factory: Callable[..., object] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.preference = preference
        self.runtime_module = runtime_module
        self.session_factory = session_factory
        self._onnx: OnnxSession | None = None

    def preflight(self) -> Path:
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"BEN2 model is not installed: {self.model_path}. Install it from Tools > Model Manager."
            )
        if self.model_path.stat().st_size <= 0:
            raise RuntimeError(f"BEN2 model is empty and must be repaired: {self.model_path}")
        return self.model_path

    def _ensure_session(self) -> OnnxSession:
        if self._onnx is None:
            self.preflight()
            self._onnx = create_session(
                self.model_path,
                self.preference,
                runtime_module=self.runtime_module,
                session_factory=self.session_factory,
            )
        return self._onnx

    def remove(self, image: Image.Image, settings: object, *, progress=None, cancelled=None) -> MatteResult:
        if cancelled is not None and cancelled():
            raise RuntimeError("Background removal cancelled.")
        onnx = self._ensure_session()
        source = image.convert("RGBA")
        input_image = source.convert("RGB").resize((BEN2_INPUT_SIZE, BEN2_INPUT_SIZE), Image.Resampling.LANCZOS)
        rgb = np.asarray(input_image, dtype=np.float32) / 255.0
        tensor = ((rgb - BEN2_MEAN) / BEN2_STD).transpose(2, 0, 1)[None, ...].astype(np.float32)
        try:
            input_name = str(onnx.session.get_inputs()[0].name)
        except (AttributeError, IndexError):
            input_name = "input"
        outputs = onnx.session.run(None, {input_name: tensor})
        matte = _normalise_output(outputs[0], source.size)
        if progress is not None:
            progress(1.0, f"BEN2 Base complete ({onnx.selection.backend})")
        warnings = list(onnx.selection.warnings)
        return MatteResult(matte, "ben2", backend=onnx.selection.backend, warnings=warnings).validated(source)


def _normalise_output(output: object, size: tuple[int, int]) -> np.ndarray:
    values = np.asarray(output)
    values = np.squeeze(values)
    if values.ndim == 3:
        values = values[0]
    if values.ndim != 2:
        raise ValueError(f"BEN2 returned an invalid matte shape: {values.shape}")
    values = values.astype(np.float32, copy=False)
    finite = np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=0.0)
    if float(np.min(finite)) < 0.0 or float(np.max(finite)) > 1.0:
        finite = 1.0 / (1.0 + np.exp(-np.clip(finite, -30.0, 30.0)))
    else:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
        if hi > lo and hi - lo < 0.5:
            finite = (finite - lo) / (hi - lo)
    mask = np.clip(finite * 255.0, 0, 255).astype(np.uint8)
    if mask.shape[::-1] != size:
        mask = np.asarray(Image.fromarray(mask, mode="L").resize(size, Image.Resampling.LANCZOS), dtype=np.uint8)
    return mask


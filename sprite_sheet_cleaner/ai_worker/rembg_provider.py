"""Offline rembg adapter.

The provider never asks rembg to download a model.  The managed model
directory is checked before the optional package is imported/session-created;
therefore a missing or damaged model is an actionable repair state rather
than an unexpected network request.
"""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.app.engines.base import EngineDescriptor, MatteResult
from sprite_sheet_cleaner.ai_worker.onnx_provider import available_providers


MODEL_FILENAMES = {
    "u2net": "u2net.onnx",
    "u2netp": "u2netp.onnx",
    "isnet-general-use": "isnet-general-use.onnx",
    "birefnet-general-lite": "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
}


class RembgProvider:
    descriptor = EngineDescriptor("rembg", "rembg", requires_runtime=True)

    def __init__(
        self,
        *,
        model_id: str = "u2net",
        model_dir: str | Path | None = None,
        session_factory: Callable[..., object] | None = None,
        remove_function: Callable[..., object] | None = None,
        runtime_module: object | None = None,
        providers: tuple[str, ...] | None = None,
    ) -> None:
        if model_id not in MODEL_FILENAMES:
            raise ValueError(f"Unsupported rembg model: {model_id}")
        self.model_id = model_id
        self.model_dir = Path(model_dir) if model_dir is not None else None
        self._session_factory = session_factory
        self._remove_function = remove_function
        self._runtime_module = runtime_module
        self._providers = providers
        self._session: object | None = None
        self.backend = "cpu"

    @property
    def model_path(self) -> Path:
        if self.model_dir is None:
            raise RuntimeError("rembg model directory is not configured.")
        return self.model_dir / MODEL_FILENAMES[self.model_id]

    def preflight(self) -> Path:
        path = self.model_path
        if not path.is_file():
            raise FileNotFoundError(
                f"rembg model is not installed: {path}. Install it from Tools > Model Manager."
            )
        if path.stat().st_size <= 0:
            raise RuntimeError(f"rembg model is empty and must be repaired: {path}")
        return path

    def _ensure_session(self) -> object:
        if self._session is not None:
            return self._session
        path = self.preflight()
        providers = self._providers
        if providers is None:
            if self._runtime_module is not None:
                providers = available_providers(self._runtime_module)
            elif self._session_factory is not None:
                # Dependency-injected test/provider factories can select their
                # own backend without importing ONNX Runtime in the core env.
                providers = ("CPUExecutionProvider",)
            else:
                providers = available_providers(self._runtime_module)
        if not providers:
            providers = ("CPUExecutionProvider",)
        os.environ["U2NET_HOME"] = str(path.parent)
        factory = self._session_factory
        if factory is None:
            try:
                from rembg import new_session
            except (ImportError, OSError) as exc:
                raise RuntimeError("The optional rembg runtime is not installed.") from exc
            factory = new_session
        try:
            self._session = factory(self.model_id, providers=list(providers))
        except TypeError:
            # Small test doubles and older rembg versions may not accept the
            # providers keyword; the managed environment still controls the
            # ONNX Runtime provider selection.
            self._session = factory(self.model_id)
        session_providers = getattr(self._session, "providers", None)
        if session_providers:
            self.backend = "cuda" if "CUDAExecutionProvider" in session_providers else "cpu"
        elif "CUDAExecutionProvider" in providers:
            self.backend = "cuda"
        return self._session

    def remove(self, image: Image.Image, settings: object, *, progress=None, cancelled=None) -> MatteResult:
        if cancelled is not None and cancelled():
            raise RuntimeError("Background removal cancelled.")
        session = self._ensure_session()
        remover = self._remove_function
        if remover is None:
            try:
                from rembg import remove as remover
            except (ImportError, OSError) as exc:
                raise RuntimeError("The optional rembg runtime is not installed.") from exc
        source = image.convert("RGBA")
        input_buffer = BytesIO()
        source.save(input_buffer, format="PNG")
        result = remover(input_buffer.getvalue(), session=session, only_mask=True)
        matte = _as_matte(result, source.size)
        if progress is not None:
            progress(1.0, f"rembg {self.model_id} complete")
        return MatteResult(matte=matte, engine_id="rembg", backend=self.backend).validated(source)


def _as_matte(value: object, size: tuple[int, int]) -> np.ndarray:
    if isinstance(value, Image.Image):
        array = np.asarray(value.convert("L"), dtype=np.uint8)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        # rembg returns an encoded PNG when the input is bytes (the adapter
        # intentionally sends PNG bytes to keep the worker boundary simple).
        # Decode it before asking NumPy to inspect the mask pixels.
        with Image.open(BytesIO(bytes(value))) as decoded:
            array = np.asarray(decoded.convert("L"), dtype=np.uint8).copy()
    else:
        array = np.asarray(value)
        array = np.squeeze(array)
        if array.ndim == 3:
            array = array[..., 0]
        if array.ndim != 2:
            raise ValueError(
                "rembg returned an invalid matte shape: "
                f"{getattr(array, 'shape', None)} ({type(value).__name__})."
            )
        if np.issubdtype(array.dtype, np.floating):
            if float(np.nanmax(array)) <= 1.0:
                array = array * 255.0
            array = np.nan_to_num(array, nan=0.0, posinf=255.0, neginf=0.0)
        array = np.clip(array, 0, 255).astype(np.uint8)
    if array.shape[::-1] != size:
        array = np.asarray(Image.fromarray(array, mode="L").resize(size, Image.Resampling.LANCZOS), dtype=np.uint8)
    return array

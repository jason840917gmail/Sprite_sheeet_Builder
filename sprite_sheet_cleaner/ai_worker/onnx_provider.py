"""Small ONNX Runtime adapter used only inside optional AI environments."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Callable

import numpy as np

from sprite_sheet_cleaner.ai_worker.capabilities import (
    CPU_PROVIDER,
    BackendSelection,
    select_backend,
)


class OnnxRuntimeUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OnnxSession:
    session: object
    selection: BackendSelection


def load_onnxruntime() -> object:
    try:
        return importlib.import_module("onnxruntime")
    except (ImportError, OSError) as exc:
        raise OnnxRuntimeUnavailable("ONNX Runtime is not installed or its native DLLs could not load.") from exc


def available_providers(module: object | None = None) -> tuple[str, ...]:
    module = module or load_onnxruntime()
    return tuple(str(item) for item in module.get_available_providers())


def _input_spec(session: object) -> tuple[str, tuple[int, ...]]:
    try:
        input_info = session.get_inputs()[0]
        name = str(input_info.name)
        shape = tuple(
            int(value) if isinstance(value, (int, np.integer)) and int(value) > 0 else 1
            for value in input_info.shape
        )
        if len(shape) != 4:
            raise ValueError("ONNX model input must be NCHW.")
        if shape[1] not in {1, 3, 4}:
            shape = (shape[0], 3, shape[2], shape[3])
        return name, shape
    except (AttributeError, IndexError, TypeError, ValueError):
        return "input", (1, 3, 320, 320)


def warmup_session(session: object, *, provider: str | None = None) -> None:
    """Run a tiny real inference to catch CUDA DLL/provider failures early."""

    name, shape = _input_spec(session)
    sample = np.zeros(shape, dtype=np.float32)
    session.run(None, {name: sample})


def create_session(
    model_path: str | Path,
    preference: str = "auto",
    *,
    runtime_module: object | None = None,
    session_factory: Callable[..., object] | None = None,
    warmup: bool = True,
    allow_forced_fallback: bool = False,
) -> OnnxSession:
    """Create a verified session, retrying on CPU in auto mode."""

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"ONNX model is not installed: {path}")
    module = runtime_module or load_onnxruntime()
    providers = available_providers(module)
    factory = session_factory or module.InferenceSession

    def try_provider(provider: str) -> None:
        candidate = factory(str(path), providers=[provider, CPU_PROVIDER] if provider != CPU_PROVIDER else [CPU_PROVIDER])
        if warmup:
            warmup_session(candidate, provider=provider)

    candidate: object | None = None
    cuda_error: Exception | None = None
    if preference in {"auto", "cuda"} and "CUDAExecutionProvider" in providers:
        try:
            candidate = factory(str(path), providers=["CUDAExecutionProvider", CPU_PROVIDER])
            if warmup:
                warmup_session(candidate, provider="CUDAExecutionProvider")
        except Exception as exc:
            cuda_error = exc
    if candidate is not None and cuda_error is None:
        selection = select_backend(preference, providers)
        return OnnxSession(candidate, selection)
    if preference == "cuda" and not allow_forced_fallback:
        if cuda_error is not None:
            raise OnnxRuntimeUnavailable(f"CUDA session warm-up failed: {cuda_error}") from cuda_error
        raise OnnxRuntimeUnavailable("CUDAExecutionProvider is not available.")
    candidate = factory(str(path), providers=[CPU_PROVIDER])
    if warmup:
        warmup_session(candidate, provider=CPU_PROVIDER)
    reason = str(cuda_error) if cuda_error is not None else "CUDAExecutionProvider is not available"
    selection = BackendSelection(
        preference,
        "cpu",
        (CPU_PROVIDER,),
        fallback_reason=f"CUDA unavailable; using CPU ({reason})",
        warnings=(f"CUDA unavailable; using CPU ({reason})",),
    )
    return OnnxSession(candidate, selection)


def looks_like_out_of_memory(error: BaseException) -> bool:
    text = str(error).lower()
    return any(token in text for token in ("out of memory", "cuda_error_out_of_memory", "cudamalloc"))

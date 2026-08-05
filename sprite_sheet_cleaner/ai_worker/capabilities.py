"""Compute capability discovery and conservative backend selection.

The core application does not import CUDA, PyTorch, or ONNX Runtime.  This
module is intentionally dependency-free and can be used by the isolated AI
worker before a provider is loaded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import shutil
import subprocess
from typing import Callable, Iterable


CUDA_PROVIDER = "CUDAExecutionProvider"
CPU_PROVIDER = "CPUExecutionProvider"


class ComputeSelectionError(RuntimeError):
    """Raised when a forced compute preference cannot be honored."""


@dataclass(frozen=True, slots=True)
class NvidiaDevice:
    name: str
    index: int = 0
    total_memory_bytes: int | None = None
    free_memory_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ComputeCapabilities:
    onnxruntime_available: bool
    execution_providers: tuple[str, ...] = ()
    nvidia_devices: tuple[NvidiaDevice, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def cuda_available(self) -> bool:
        return CUDA_PROVIDER in self.execution_providers


@dataclass(frozen=True, slots=True)
class BackendSelection:
    requested: str
    backend: str
    providers: tuple[str, ...]
    fallback_reason: str | None = None
    warnings: tuple[str, ...] = ()


def parse_nvidia_smi_csv(output: str) -> tuple[NvidiaDevice, ...]:
    """Parse the stable CSV output from ``nvidia-smi``.

    The command is optional.  A malformed response is treated as no device
    rather than allowing a diagnostic helper to make inference fail.
    """

    devices: list[NvidiaDevice] = []
    for index, row in enumerate(csv.reader(line for line in output.splitlines() if line.strip())):
        if len(row) < 3:
            continue
        name = row[0].strip()
        try:
            total = int(row[1].strip()) * 1024 * 1024
            free = int(row[2].strip()) * 1024 * 1024
        except ValueError:
            continue
        if name:
            devices.append(NvidiaDevice(name, index, total, free))
    return tuple(devices)


def discover_nvidia_devices(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    executable: str | None = None,
) -> tuple[NvidiaDevice, ...]:
    """Discover NVIDIA memory without treating it as proof CUDA can execute."""

    command = executable or shutil.which("nvidia-smi")
    if not command:
        return ()
    run = runner or subprocess.run
    try:
        result = run(
            [command, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if result.returncode != 0:
        return ()
    return parse_nvidia_smi_csv(result.stdout)


def discover_capabilities(
    *,
    onnxruntime_module: object | None = None,
    nvidia_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> ComputeCapabilities:
    """Collect provider and device information, safely handling missing DLLs."""

    warnings: list[str] = []
    module = onnxruntime_module
    if module is None:
        try:
            import importlib

            module = importlib.import_module("onnxruntime")
        except (ImportError, OSError) as exc:
            warnings.append(f"ONNX Runtime is unavailable: {exc}")
            module = None
    providers: tuple[str, ...] = ()
    if module is not None:
        try:
            providers = tuple(str(item) for item in module.get_available_providers())
        except Exception as exc:  # provider discovery must never crash the UI
            warnings.append(f"Could not query ONNX Runtime providers: {exc}")
    devices = discover_nvidia_devices(runner=nvidia_runner)
    if devices and CUDA_PROVIDER not in providers:
        warnings.append("NVIDIA GPU detected, but ONNX Runtime CUDA is not available.")
    return ComputeCapabilities(module is not None, providers, devices, tuple(warnings))


def select_backend(
    preference: str,
    available_providers: Iterable[str],
    *,
    warmup: Callable[[str], None] | None = None,
    allow_forced_fallback: bool = False,
) -> BackendSelection:
    """Choose a backend and validate CUDA with a real warm-up callback.

    ``auto`` falls back to CPU on provider absence or warm-up failure.  A
    forced CUDA request fails unless the caller explicitly opts into fallback.
    """

    if preference not in {"auto", "cuda", "cpu"}:
        raise ValueError(f"Unsupported compute preference: {preference}")
    providers = tuple(str(item) for item in available_providers)
    if preference == "cpu":
        return BackendSelection(preference, "cpu", (CPU_PROVIDER,))
    cuda_error: str | None = None
    if CUDA_PROVIDER in providers:
        try:
            if warmup is not None:
                warmup(CUDA_PROVIDER)
            return BackendSelection(preference, "cuda", (CUDA_PROVIDER, CPU_PROVIDER))
        except Exception as exc:
            cuda_error = str(exc) or exc.__class__.__name__
    else:
        cuda_error = "CUDAExecutionProvider is not available"
    if preference == "cuda" and not allow_forced_fallback:
        raise ComputeSelectionError(cuda_error)
    reason = f"CUDA unavailable; using CPU ({cuda_error})"
    return BackendSelection(preference, "cpu", (CPU_PROVIDER,), fallback_reason=reason, warnings=(reason,))


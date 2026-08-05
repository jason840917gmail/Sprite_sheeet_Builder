from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from sprite_sheet_cleaner.ai_worker.onnx_provider import create_session, looks_like_out_of_memory


class _Input:
    name = "images"
    shape = [1, 3, 4, 4]


class _Session:
    def __init__(self, providers, fail=False):
        self.providers = providers
        self.fail = fail

    def get_inputs(self):
        return [_Input()]

    def run(self, _outputs, _inputs):
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        return [np.zeros((1, 1, 4, 4), dtype=np.float32)]


class _Runtime:
    def get_available_providers(self):
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]


class ComputeFallbackTests(unittest.TestCase):
    def test_auto_recreates_cpu_session_after_cuda_warmup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.onnx"
            path.write_bytes(b"model")
            calls = []

            def factory(_path, providers):
                calls.append(tuple(providers))
                return _Session(providers, fail=providers[0] == "CUDAExecutionProvider")

            result = create_session(path, runtime_module=_Runtime(), session_factory=factory)
            self.assertEqual(result.selection.backend, "cpu")
            self.assertEqual(calls, [("CUDAExecutionProvider", "CPUExecutionProvider"), ("CPUExecutionProvider",)])

    def test_oom_detector(self) -> None:
        self.assertTrue(looks_like_out_of_memory(RuntimeError("CUDA_ERROR_OUT_OF_MEMORY")))


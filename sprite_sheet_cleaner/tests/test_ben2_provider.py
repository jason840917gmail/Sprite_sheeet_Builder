from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.ai_worker.ben2_provider import Ben2Provider


class _Input:
    name = "input"


class _Session:
    providers = ["CPUExecutionProvider"]

    def get_inputs(self):
        return [_Input()]

    def run(self, _outputs, inputs):
        tensor = inputs["input"]
        self.shape = tensor.shape
        return [np.ones((1, 1, 1024, 1024), dtype=np.float32)]


class _Runtime:
    def get_available_providers(self):
        return ["CPUExecutionProvider"]


class Ben2ProviderTests(unittest.TestCase):
    def test_preprocesses_to_1024_and_restores_source_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "BEN2_Base.onnx"
            model.write_bytes(b"model")
            session = _Session()
            provider = Ben2Provider(
                model,
                runtime_module=_Runtime(),
                session_factory=lambda *_args, **_kwargs: session,
            )
            result = provider.remove(Image.new("RGBA", (7, 5), (200, 50, 30, 255)), object())
            self.assertEqual(session.shape, (1, 3, 1024, 1024))
            self.assertEqual(result.matte.shape, (5, 7))
            self.assertEqual(int(result.matte[0, 0]), 255)


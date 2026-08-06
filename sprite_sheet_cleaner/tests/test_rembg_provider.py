from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.ai_worker.rembg_provider import RembgProvider


class _Session:
    providers = ["CPUExecutionProvider"]


class RembgProviderTests(unittest.TestCase):
    def test_missing_model_fails_before_session_factory(self) -> None:
        called = []
        with tempfile.TemporaryDirectory() as directory:
            provider = RembgProvider(model_dir=directory, session_factory=lambda *args, **kwargs: called.append(1))
            with self.assertRaises(FileNotFoundError):
                provider.remove(Image.new("RGBA", (4, 3)), object())
        self.assertEqual(called, [])

    def test_inference_uses_local_model_and_returns_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "u2net.onnx"
            path.write_bytes(b"model")

            def factory(_model_id, **_kwargs):
                return _Session()

            def remove(_data, *, session, only_mask):
                self.assertIsInstance(session, _Session)
                self.assertTrue(only_mask)
                return Image.new("L", (2, 2), 128)

            provider = RembgProvider(model_dir=directory, session_factory=factory, remove_function=remove)
            result = provider.remove(Image.new("RGBA", (4, 3)), object())
            self.assertEqual(result.matte.shape, (3, 4))
            self.assertEqual(int(result.matte[0, 0]), 128)

    def test_inference_decodes_encoded_png_mask_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "u2net.onnx"
            path.write_bytes(b"model")

            def factory(_model_id, **_kwargs):
                return _Session()

            def remove(_data, *, session, only_mask):
                self.assertIsInstance(session, _Session)
                self.assertTrue(only_mask)
                output = BytesIO()
                Image.new("L", (2, 2), 128).save(output, format="PNG")
                return output.getvalue()

            provider = RembgProvider(model_dir=directory, session_factory=factory, remove_function=remove)
            result = provider.remove(Image.new("RGBA", (4, 3)), object())
            self.assertEqual(result.matte.shape, (3, 4))
            self.assertEqual(int(result.matte[0, 0]), 128)

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.app.engines.ai_worker_engine import IsolatedAIWorkerEngine


class _Client:
    def start(self):
        return None

    def request(self, _message):
        return {"message_type": "result", "backend": "cpu", "warnings": []}

    def close(self):
        return None


class _FailingClient:
    def __init__(self) -> None:
        self.closed = False

    def start(self):
        return None

    def request(self, _message):
        raise RuntimeError("worker failed")

    def close(self):
        self.closed = True


class AIWorkerEngineTests(unittest.TestCase):
    def test_missing_model_is_reported_before_worker_start(self) -> None:
        engine = IsolatedAIWorkerEngine(
            provider_id="ben2",
            model_id="ben2-base-onnx",
            model_path="missing.onnx",
            python_executable="python",
        )
        with self.assertRaises(FileNotFoundError):
            engine.remove(Image.new("RGBA", (2, 2)), object())

    def test_failed_worker_is_discarded_for_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.onnx"
            model.write_bytes(b"model")
            engine = IsolatedAIWorkerEngine(
                provider_id="ben2",
                model_id="ben2-base-onnx",
                model_path=model,
                python_executable="python",
            )
            client = _FailingClient()
            engine._client = client

            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                engine.remove(Image.new("RGBA", (2, 2)), object())

            self.assertTrue(client.closed)
            self.assertIsNone(engine._client)

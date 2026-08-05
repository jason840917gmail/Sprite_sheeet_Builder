from __future__ import annotations

import unittest
from unittest.mock import patch

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


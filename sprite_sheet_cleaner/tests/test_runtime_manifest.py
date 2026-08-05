from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.runtime.manifest import RuntimeManifest


class RuntimeManifestTests(unittest.TestCase):
    def test_manifest_requires_checksum_when_model_url_exists(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeManifest(runtime_id="rembg", display_name="rembg", model_url="https://example.test/model.onnx").validated()

    def test_manifest_round_trip(self) -> None:
        manifest = RuntimeManifest.from_dict(
            {
                "runtime_id": "ben2",
                "display_name": "BEN2",
                "supported_python": ["3.13"],
                "supported_backends": ["cpu", "cuda"],
                "metadata": {"input_size": 1024},
            }
        )

        self.assertEqual(manifest.runtime_id, "ben2")
        self.assertEqual(manifest.metadata["input_size"], 1024)

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib
import tempfile
import unittest

from sprite_sheet_cleaner.app.runtime.registry import RuntimeRegistry


class RuntimeRegistryTests(unittest.TestCase):
    def test_builtin_manifests_validate_and_start_uninstalled(self) -> None:
        directory = Path(__file__).parents[1] / "app" / "runtime" / "manifests"
        registry = RuntimeRegistry.from_directory(directory)
        self.assertEqual({item.runtime_id for item in registry.manifests()}, {"ben2-base-onnx", "rembg-onnx"})

    def test_ben2_runtime_includes_worker_image_dependency(self) -> None:
        directory = Path(__file__).parents[1] / "app" / "runtime" / "manifests"
        manifest = RuntimeRegistry.from_directory(directory).get("ben2-base-onnx")

        self.assertIn("Pillow==12.3.0", manifest.package_requirements)

    def test_download_is_marked_ready_after_verified_install(self) -> None:
        directory = Path(__file__).parents[1] / "app" / "runtime" / "manifests"
        manifest = RuntimeRegistry.from_directory(directory).get("ben2-base-onnx")
        with tempfile.TemporaryDirectory() as temp:
            import sprite_sheet_cleaner.app.runtime.registry as module

            original_model_root = module.model_root
            module.model_root = lambda: Path(temp)  # type: ignore[assignment]
            try:
                payload = b"test model"
                fake = replace(manifest, model_sha256=hashlib.sha256(payload).hexdigest())
                registry = RuntimeRegistry([fake])
                registry.install_model(fake, opener=lambda _request: _Response(payload))
                self.assertTrue(registry.state(fake).installed)
            finally:
                module.model_root = original_model_root  # type: ignore[assignment]


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size: int) -> bytes:
        payload, self.payload = self.payload, b""
        return payload

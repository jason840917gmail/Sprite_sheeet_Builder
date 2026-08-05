from __future__ import annotations

from pathlib import Path
import os
import tempfile

import numpy as np
from PIL import Image

from sprite_sheet_cleaner.app.ai_protocol.client import AIWorkerClient
from sprite_sheet_cleaner.app.engines.base import BackgroundEngine, EngineDescriptor, MatteResult


class IsolatedAIWorkerEngine:
    """BackgroundEngine facade backed by a managed optional Python runtime."""

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        model_path: str | Path,
        python_executable: str | Path,
        source_root: str | Path | None = None,
        compute: str = "auto",
    ) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.model_path = Path(model_path)
        self.python_executable = str(python_executable)
        self.source_root = str(source_root or Path(__file__).resolve().parents[3])
        self.compute = compute
        self.descriptor = EngineDescriptor(provider_id, provider_id, requires_runtime=True, model_id=model_id)
        self._client: AIWorkerClient | None = None

    def _client_for_worker(self) -> AIWorkerClient:
        if self._client is None:
            environment = dict(os.environ)
            current_path = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = os.pathsep.join(item for item in (self.source_root, current_path) if item)
            self._client = AIWorkerClient(
                [self.python_executable, "-m", "sprite_sheet_cleaner.ai_worker.main"],
                environment=environment,
            )
        self._client.start()
        return self._client

    def remove(self, image: Image.Image, settings: object, *, progress=None, cancelled=None) -> MatteResult:
        if cancelled is not None and cancelled():
            raise RuntimeError("Background removal cancelled.")
        if not self.model_path.is_file():
            raise FileNotFoundError(f"AI model is not installed: {self.model_path}")
        source = image.convert("RGBA")
        with tempfile.TemporaryDirectory(prefix="sprite-ai-") as directory:
            directory_path = Path(directory)
            input_path = directory_path / "input.png"
            output_path = directory_path / "matte.png"
            source.save(input_path, format="PNG")
            client = self._client_for_worker()
            try:
                response = client.request(
                    {
                        "protocol_version": 1,
                        "message_type": "infer",
                        "request_id": "background-removal",
                        "provider_id": self.provider_id,
                        "model_id": self.model_id,
                        "model_path": str(self.model_path),
                        "input_path": str(input_path),
                        "output_path": str(output_path),
                        "compute": str(getattr(settings, "compute", self.compute)),
                    }
                )
            except Exception:
                client.close()
                if self._client is client:
                    self._client = None
                raise
            if response.get("message_type") == "error":
                raise RuntimeError(str(response.get("message", "AI worker inference failed.")))
            if response.get("message_type") != "result" or not output_path.is_file():
                raise RuntimeError("AI worker returned no verified matte.")
            matte = np.asarray(Image.open(output_path).convert("L"), dtype=np.uint8)
            backend = str(response.get("backend", "cpu"))
            warnings = [str(item) for item in response.get("warnings", [])]
        if progress is not None:
            progress(1.0, f"{self.provider_id} complete ({backend})")
        return MatteResult(matte, self.provider_id, backend=backend, warnings=warnings).validated(source)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Iterable

from sprite_sheet_cleaner.app.runtime.download_manager import download_verified
from sprite_sheet_cleaner.app.runtime.environment_manager import EnvironmentManager
from sprite_sheet_cleaner.app.runtime.manifest import RuntimeManifest
from sprite_sheet_cleaner.app.runtime.paths import model_root, owned_leaf


MODEL_OWNERSHIP_FILENAME = ".sprite-sheet-cleaner-model.json"


@dataclass(frozen=True, slots=True)
class RuntimeInstallState:
    manifest: RuntimeManifest
    model_path: Path
    installed: bool
    environment_ready: bool
    message: str


class RuntimeRegistry:
    """Catalog and installer for optional runtimes/models outside the repo."""

    def __init__(self, manifests: Iterable[RuntimeManifest] = ()) -> None:
        self._manifests = {manifest.validated().runtime_id: manifest.validated() for manifest in manifests}
        self.environment_manager = EnvironmentManager()

    @classmethod
    def from_directory(cls, directory: str | Path) -> "RuntimeRegistry":
        manifests: list[RuntimeManifest] = []
        for path in sorted(Path(directory).glob("*.json")):
            if path.name == "schema.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            manifests.append(RuntimeManifest.from_dict(data))
        return cls(manifests)

    def manifests(self) -> tuple[RuntimeManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def get(self, runtime_id: str) -> RuntimeManifest:
        try:
            return self._manifests[runtime_id]
        except KeyError as exc:
            raise KeyError(f"Unknown optional runtime: {runtime_id}") from exc

    def model_directory(self, manifest: RuntimeManifest) -> Path:
        return owned_leaf(model_root(), manifest.runtime_id)

    def model_path(self, manifest: RuntimeManifest) -> Path:
        manifest.validated()
        if not manifest.model_filename:
            raise ValueError(f"Runtime {manifest.runtime_id} has no model artifact.")
        return self.model_directory(manifest) / manifest.model_filename

    def state(self, manifest: RuntimeManifest) -> RuntimeInstallState:
        path = self.model_path(manifest)
        environment_ready = self.environment_manager.owns_environment(manifest)
        installed = path.is_file() and self._model_marker_valid(manifest, path)
        if installed and environment_ready:
            message = "Ready"
        elif installed:
            message = "Model ready; runtime environment needs installation"
        else:
            message = "Not installed"
        return RuntimeInstallState(manifest, path, installed, environment_ready, message)

    def install_model(
        self,
        manifest: RuntimeManifest,
        *,
        progress: Callable[[float], None] | None = None,
        opener=None,
    ) -> Path:
        manifest.validated()
        if not manifest.model_url or not manifest.model_sha256:
            raise ValueError("This runtime does not have a verified model download.")
        target = self.model_path(manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        downloaded = download_verified(
            manifest.model_url,
            target,
            manifest.model_sha256,
            progress=progress,
            **({"opener": opener} if opener is not None else {}),
        )
        marker = downloaded.parent / MODEL_OWNERSHIP_FILENAME
        marker.write_text(
            json.dumps(
                {
                    "runtime_id": manifest.runtime_id,
                    "model_filename": manifest.model_filename,
                    "sha256": manifest.model_sha256,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return downloaded

    def install_environment(
        self,
        manifest: RuntimeManifest,
        *,
        compute: str = "auto",
        python_executable: str | None = None,
        runner=None,
    ) -> Path:
        target = self.environment_manager.create_environment(manifest, python_executable=python_executable)
        requirements = list(manifest.package_requirements)
        if compute == "cuda":
            cuda_requirement = manifest.metadata.get("cuda_package")
            if cuda_requirement:
                requirements = [item for item in requirements if not item.lower().startswith("onnxruntime")]
                requirements.append(str(cuda_requirement))
        if requirements:
            try:
                self.environment_manager.install_packages(target, requirements, runner=runner)
            except Exception:
                marker = target / ".sprite-sheet-cleaner-managed.json"
                if marker.exists():
                    marker.unlink()
                raise
        return target

    def _model_marker_valid(self, manifest: RuntimeManifest, path: Path) -> bool:
        marker = path.parent / MODEL_OWNERSHIP_FILENAME
        if not marker.is_file():
            return False
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (
            data.get("runtime_id") == manifest.runtime_id
            and data.get("model_filename") == manifest.model_filename
            and str(data.get("sha256", "")).lower() == str(manifest.model_sha256).lower()
        )

    def uninstall_model(self, manifest: RuntimeManifest) -> None:
        """Remove only a verified managed model leaf."""

        target = self.model_directory(manifest)
        path = self.model_path(manifest)
        if not target.is_dir() or not self._model_marker_valid(manifest, path):
            raise RuntimeError("Refusing to remove an unmarked or incomplete model directory.")
        for child in target.iterdir():
            if child.is_symlink():
                raise RuntimeError("Refusing to remove a model directory containing a link.")
            if child.name not in {manifest.model_filename, MODEL_OWNERSHIP_FILENAME}:
                raise RuntimeError("Refusing to remove a model directory containing unknown files.")
        for child in target.iterdir():
            child.unlink()
        target.rmdir()

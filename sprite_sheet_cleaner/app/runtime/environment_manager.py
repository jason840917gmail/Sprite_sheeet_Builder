from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

from sprite_sheet_cleaner.app.runtime.manifest import RuntimeManifest
from sprite_sheet_cleaner.app.runtime.paths import owned_leaf, runtime_root


OWNERSHIP_FILENAME = ".sprite-sheet-cleaner-managed.json"


class EnvironmentManager:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()

    def environment_path(self, manifest: RuntimeManifest) -> Path:
        manifest.validated()
        return owned_leaf(self.root, manifest.runtime_id)

    def create_environment(self, manifest: RuntimeManifest, python_executable: str | None = None) -> Path:
        manifest.validated()
        if not manifest.supports_current_python() and python_executable is None:
            raise RuntimeError("The current Python interpreter is not supported by this runtime.")
        target = self.environment_path(manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        interpreter = python_executable or sys.executable
        subprocess.run([interpreter, "-m", "venv", str(target)], check=True)
        marker = target / OWNERSHIP_FILENAME
        marker.write_text(json.dumps({"runtime_id": manifest.runtime_id}, indent=2), encoding="utf-8")
        return target

    def owns_environment(self, manifest: RuntimeManifest) -> bool:
        target = self.environment_path(manifest)
        marker = target / OWNERSHIP_FILENAME
        if not marker.is_file() or not self.python_path(target).is_file():
            return False
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return data.get("runtime_id") == manifest.runtime_id

    def python_path(self, environment: Path) -> Path:
        candidate = environment / ("Scripts" if sys.platform.startswith("win") else "bin") / "python"
        if sys.platform.startswith("win"):
            candidate = candidate.with_suffix(".exe")
        return candidate

    def install_packages(
        self,
        environment: Path,
        requirements: list[str],
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        if not requirements:
            return
        if not requirements or any(not isinstance(item, str) or not item.strip() for item in requirements):
            raise ValueError("Runtime package requirements must be non-empty strings.")
        command = [str(self.python_path(environment)), "-m", "pip", "install", "--disable-pip-version-check", "--no-input"]
        command.extend(requirements)
        (runner or subprocess.run)(command, check=True)

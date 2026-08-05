from __future__ import annotations

from dataclasses import dataclass, field
import sys


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    runtime_id: str
    display_name: str
    package_requirements: tuple[str, ...] = ()
    model_url: str | None = None
    model_filename: str | None = None
    model_sha256: str | None = None
    supported_python: tuple[str, ...] = ()
    supported_backends: tuple[str, ...] = ("cpu",)
    license_name: str = "Unknown"
    download_size_bytes: int = 0
    installed_size_bytes: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    def validated(self) -> "RuntimeManifest":
        if not self.runtime_id or any(character in self.runtime_id for character in "\\/:"):
            raise ValueError("Runtime identifier must be a simple name.")
        if self.model_url and (not self.model_filename or not self.model_sha256):
            raise ValueError("A model URL requires a filename and SHA-256 checksum.")
        if self.model_sha256 and len(self.model_sha256) != 64:
            raise ValueError("Model checksum must be a SHA-256 hex digest.")
        if self.download_size_bytes < 0 or self.installed_size_bytes < 0:
            raise ValueError("Runtime sizes cannot be negative.")
        return self

    def supports_current_python(self) -> bool:
        if not self.supported_python:
            return True
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        return version in self.supported_python

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RuntimeManifest":
        manifest = cls(
            runtime_id=str(data.get("runtime_id") or ""),
            display_name=str(data.get("display_name") or ""),
            package_requirements=tuple(str(value) for value in data.get("package_requirements", [])),
            model_url=str(data["model_url"]) if data.get("model_url") else None,
            model_filename=str(data["model_filename"]) if data.get("model_filename") else None,
            model_sha256=str(data["model_sha256"]) if data.get("model_sha256") else None,
            supported_python=tuple(str(value) for value in data.get("supported_python", [])),
            supported_backends=tuple(str(value) for value in data.get("supported_backends", ["cpu"])),
            license_name=str(data.get("license_name") or "Unknown"),
            download_size_bytes=int(data.get("download_size_bytes", 0)),
            installed_size_bytes=int(data.get("installed_size_bytes", 0)),
            metadata=dict(data.get("metadata", {})),
        )
        return manifest.validated()

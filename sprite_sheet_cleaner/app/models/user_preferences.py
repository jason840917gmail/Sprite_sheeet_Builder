from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UserPreferences:
    compute: str = "auto"
    preview_quality: str = "balanced"
    cache_limit_mb: int = 4096
    diagnostics_enabled: bool = True

    def validated(self) -> "UserPreferences":
        if self.compute not in {"auto", "cuda", "cpu"}:
            raise ValueError(f"Unsupported compute preference: {self.compute}")
        if self.preview_quality not in {"draft", "balanced", "quality"}:
            raise ValueError(f"Unsupported preview quality: {self.preview_quality}")
        if self.cache_limit_mb <= 0:
            raise ValueError("Cache limit must be positive.")
        return self

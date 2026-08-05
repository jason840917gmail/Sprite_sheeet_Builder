from __future__ import annotations

from typing import Protocol


class WorkerProvider(Protocol):
    provider_id: str

    def capabilities(self) -> dict[str, object]:
        ...

    def infer(self, input_path: str, output_path: str, options: dict[str, object]) -> dict[str, object]:
        ...

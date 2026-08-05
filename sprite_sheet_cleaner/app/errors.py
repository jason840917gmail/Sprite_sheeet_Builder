from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    SOURCE = "source"
    RUNTIME = "runtime"
    NETWORK = "network"
    CHECKSUM = "checksum"
    WORKER = "worker"
    CUDA = "cuda"
    OUT_OF_MEMORY = "out_of_memory"
    CANCELLED = "cancelled"
    CACHE = "cache"
    PROJECT = "project"
    DISK = "disk"
    EXPORT = "export"


@dataclass
class AppError(Exception):
    category: ErrorCategory
    message: str
    action: str | None = None
    details: str | None = None

    def __str__(self) -> str:
        return self.message if not self.action else f"{self.message} {self.action}"


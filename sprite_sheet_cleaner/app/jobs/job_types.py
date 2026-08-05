from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Callable, TypeVar


ResultT = TypeVar("ResultT")


@dataclass(slots=True)
class CancellationToken:
    _event: threading.Event

    @classmethod
    def create(cls) -> "CancellationToken":
        return cls(threading.Event())

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


JobOperation = Callable[[Callable[[float, str], None], Callable[[], bool]], ResultT]

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from sprite_sheet_cleaner.app.jobs.job_types import CancellationToken, JobOperation


ResultT = TypeVar("ResultT")


class JobSignals(QObject, Generic[ResultT]):
    progress = Signal(float, str)
    completed = Signal(object)
    failed = Signal(object)
    cancelled = Signal()


@dataclass(slots=True)
class JobHandle(Generic[ResultT]):
    name: str
    token: CancellationToken
    signals: JobSignals[ResultT]

    def cancel(self) -> None:
        self.token.cancel()


class _JobRunnable(QRunnable):
    def __init__(self, operation: JobOperation, handle: JobHandle) -> None:
        super().__init__()
        self.operation = operation
        self.handle = handle

    def run(self) -> None:
        try:
            result = self.operation(self.handle.signals.progress.emit, self.handle.token.is_cancelled)
            if self.handle.token.is_cancelled():
                self.handle.signals.cancelled.emit()
            else:
                self.handle.signals.completed.emit(result)
        except Exception as exc:
            if self.handle.token.is_cancelled():
                self.handle.signals.cancelled.emit()
            else:
                self.handle.signals.failed.emit(exc)


class QtJobController:
    def __init__(self, parent: QObject | None = None) -> None:
        self._pool = QThreadPool(parent)

    def start(self, name: str, operation: JobOperation[ResultT]) -> JobHandle[ResultT]:
        token = CancellationToken.create()
        handle: JobHandle[ResultT] = JobHandle(name, token, JobSignals())
        self._pool.start(_JobRunnable(operation, handle))
        return handle

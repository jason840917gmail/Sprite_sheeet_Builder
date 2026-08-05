from __future__ import annotations

from typing import Protocol


class Command(Protocol):
    def redo(self) -> None:
        ...

    def undo(self) -> None:
        ...


class CommandStack:
    def __init__(self, limit: int = 100) -> None:
        if limit <= 0:
            raise ValueError("Command history limit must be positive.")
        self.limit = limit
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    def execute(self, command: Command) -> None:
        command.redo()
        self._undo.append(command)
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.redo()
        self._undo.append(command)
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

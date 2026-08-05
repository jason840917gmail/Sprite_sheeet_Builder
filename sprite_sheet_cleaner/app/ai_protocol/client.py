from __future__ import annotations

import subprocess
from typing import Any

from sprite_sheet_cleaner.app.ai_protocol.messages import decode_message, encode_message


class AIWorkerClient:
    def __init__(self, command: list[str]) -> None:
        if not command:
            raise ValueError("AI worker command cannot be empty.")
        self.command = list(command)
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("AI worker is not running.")
        self.process.stdin.write(encode_message(message))
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        if not response:
            raise RuntimeError("AI worker exited without a response.")
        return decode_message(response)

    def close(self, timeout: float = 2.0) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

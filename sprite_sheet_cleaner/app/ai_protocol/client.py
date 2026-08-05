from __future__ import annotations

import subprocess
import os
from typing import Any

from sprite_sheet_cleaner.app.ai_protocol.messages import decode_message, encode_message


class AIWorkerClient:
    def __init__(self, command: list[str], *, environment: dict[str, str] | None = None) -> None:
        if not command:
            raise ValueError("AI worker command cannot be empty.")
        self.command = list(command)
        self.environment = dict(environment) if environment is not None else None
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self.process is not None:
            if self.process.poll() is None:
                return
            self._close_streams(self.process)
            self.process = None
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.environment,
        )

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("AI worker is not running.")
        self.process.stdin.write(encode_message(message))
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        if not response:
            details = ""
            process = self.process
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None and process.stderr is not None:
                details = process.stderr.read().decode("utf-8", errors="replace").strip()
            suffix = f": {details[-2000:]}" if details else "."
            raise RuntimeError(f"AI worker exited without a response{suffix}")
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
        self._close_streams(process)

    @staticmethod
    def _close_streams(process: subprocess.Popen[bytes]) -> None:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

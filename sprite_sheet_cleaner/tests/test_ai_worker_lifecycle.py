from __future__ import annotations

import sys
import unittest

from sprite_sheet_cleaner.app.ai_protocol.client import AIWorkerClient


class AIWorkerLifecycleTests(unittest.TestCase):
    def test_placeholder_worker_responds_and_shuts_down(self) -> None:
        command = [sys.executable, "-m", "sprite_sheet_cleaner.ai_worker.main"]
        client = AIWorkerClient(command)
        try:
            client.start()
            capabilities = client.request({"protocol_version": 1, "message_type": "hello", "request_id": "one"})
            self.assertEqual(capabilities["message_type"], "capabilities")
            shutdown = client.request({"protocol_version": 1, "message_type": "shutdown", "request_id": "two"})
            self.assertEqual(shutdown["message_type"], "shutdown_ack")
        finally:
            client.close()

    def test_dead_worker_is_replaced_on_next_start(self) -> None:
        client = AIWorkerClient([sys.executable, "-c", "pass"])
        try:
            client.start()
            first = client.process
            self.assertIsNotNone(first)
            first.wait(timeout=5)

            client.start()

            self.assertIsNot(client.process, first)
        finally:
            client.close()

    def test_worker_startup_error_includes_stderr(self) -> None:
        client = AIWorkerClient(
            [sys.executable, "-c", "import sys; sys.stderr.write('missing optional dependency')"]
        )
        try:
            client.start()
            with self.assertRaisesRegex(RuntimeError, "missing optional dependency"):
                client.request({"protocol_version": 1, "message_type": "hello", "request_id": "stderr"})
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()

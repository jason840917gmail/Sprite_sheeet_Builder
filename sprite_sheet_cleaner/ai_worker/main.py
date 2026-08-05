from __future__ import annotations

import sys

from sprite_sheet_cleaner.app.ai_protocol.messages import decode_message, encode_message


def run() -> int:
    for line in sys.stdin.buffer:
        try:
            message = decode_message(line)
            message_type = message["message_type"]
            if message_type == "hello":
                response = {
                    "protocol_version": 1,
                    "message_type": "capabilities",
                    "request_id": message.get("request_id"),
                    "provider_id": "placeholder",
                    "backends": ["cpu"],
                }
            elif message_type == "shutdown":
                response = {
                    "protocol_version": 1,
                    "message_type": "shutdown_ack",
                    "request_id": message.get("request_id"),
                }
                sys.stdout.buffer.write(encode_message(response))
                sys.stdout.buffer.flush()
                return 0
            else:
                response = {
                    "protocol_version": 1,
                    "message_type": "error",
                    "request_id": message.get("request_id"),
                    "error_code": "provider_not_installed",
                    "message": "No AI provider is installed in this worker.",
                }
        except Exception as exc:
            response = {
                "protocol_version": 1,
                "message_type": "error",
                "error_code": "invalid_message",
                "message": str(exc),
            }
        sys.stdout.buffer.write(encode_message(response))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

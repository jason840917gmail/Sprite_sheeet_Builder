from __future__ import annotations

import json
import math
from typing import Any


PROTOCOL_VERSION = 1


def encode_message(message: dict[str, Any]) -> bytes:
    validate_message(message)
    return (json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def decode_message(line: bytes | str) -> dict[str, Any]:
    try:
        message = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("AI worker message is not valid JSON.") from exc
    if not isinstance(message, dict):
        raise ValueError("AI worker message must be an object.")
    validate_message(message)
    return message


def validate_message(message: dict[str, Any]) -> None:
    if int(message.get("protocol_version", 0)) != PROTOCOL_VERSION:
        raise ValueError("Unsupported AI worker protocol version.")
    if not isinstance(message.get("message_type"), str) or not message["message_type"]:
        raise ValueError("AI worker message_type is required.")
    request_id = message.get("request_id")
    if request_id is not None and (not isinstance(request_id, str) or not request_id):
        raise ValueError("AI worker request_id must be a non-empty string.")
    if _contains_non_finite(message):
        raise ValueError("AI worker message contains a non-finite number.")


def _contains_non_finite(value: object) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_non_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_non_finite(item) for item in value)
    return False

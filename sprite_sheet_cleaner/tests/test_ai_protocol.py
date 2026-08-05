from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.ai_protocol.messages import decode_message, encode_message


class AIProtocolTests(unittest.TestCase):
    def test_message_round_trip(self) -> None:
        message = {"protocol_version": 1, "message_type": "hello", "request_id": "one"}

        self.assertEqual(decode_message(encode_message(message)), message)

    def test_rejects_wrong_version_and_nan(self) -> None:
        with self.assertRaises(ValueError):
            encode_message({"protocol_version": 2, "message_type": "hello"})
        with self.assertRaises(ValueError):
            encode_message({"protocol_version": 1, "message_type": "hello", "value": float("nan")})

    def test_rejects_non_object_message(self) -> None:
        with self.assertRaises(ValueError):
            decode_message(b"[]\n")


if __name__ == "__main__":
    unittest.main()

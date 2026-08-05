from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.jobs.job_types import CancellationToken


class JobTypeTests(unittest.TestCase):
    def test_cancellation_token_is_reversible_only_by_creation(self) -> None:
        token = CancellationToken.create()

        self.assertFalse(token.is_cancelled())
        token.cancel()
        self.assertTrue(token.is_cancelled())


if __name__ == "__main__":
    unittest.main()

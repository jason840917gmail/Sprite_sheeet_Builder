from __future__ import annotations

import random
import unittest

from sprite_sheet_cleaner.app.core.animation_sampler import (
    pick_animation_refs,
    recommended_animation_frame_count,
)
from sprite_sheet_cleaner.app.core.video_source import FrameRef


class AnimationSamplerTests(unittest.TestCase):
    def test_recommended_count_stays_compact_and_scales_with_source_length(self) -> None:
        self.assertEqual(recommended_animation_frame_count(4), 4)
        self.assertEqual(recommended_animation_frame_count(60), 8)
        self.assertEqual(recommended_animation_frame_count(120), 10)
        self.assertEqual(recommended_animation_frame_count(240), 12)
        self.assertEqual(recommended_animation_frame_count(2400), 12)

    def test_pick_is_randomized_within_ordered_timeline_segments(self) -> None:
        refs = [FrameRef(index, index * 10) for index in range(120)]

        picked = pick_animation_refs(refs, 120, rng=random.Random(7))

        self.assertEqual(len(picked), 10)
        self.assertEqual(picked, sorted(picked, key=lambda ref: ref.index))
        self.assertGreaterEqual(picked[0].index, 0)
        self.assertLess(picked[-1].index, 120)
        self.assertEqual(len({ref.index // 12 for ref in picked}), 10)

    def test_short_candidate_lists_return_every_candidate_once(self) -> None:
        refs = [FrameRef(8, 80), FrameRef(2, 20), FrameRef(5, 50)]

        picked = pick_animation_refs(refs, 120, rng=random.Random(3))

        self.assertEqual([ref.index for ref in picked], [2, 5, 8])

    def test_user_target_count_overrides_default_seed_size(self) -> None:
        refs = [FrameRef(index, index * 10) for index in range(120)]

        picked = pick_animation_refs(refs, 120, target_count=6, rng=random.Random(4))

        self.assertEqual(len(picked), 6)


if __name__ == "__main__":
    unittest.main()

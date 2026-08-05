from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.core.video_source import VideoMetadata, frame_ref, sample_frame_refs
from sprite_sheet_cleaner.app.models.video_settings import VideoSettings


class VideoSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = VideoMetadata(
            path="demo.mp4",
            width=640,
            height=360,
            frame_count=120,
            fps=30.0,
            duration_seconds=4.0,
        )

    def test_frame_ref_contains_timestamp(self) -> None:
        ref = frame_ref(self.metadata, 15)
        self.assertEqual((ref.index, ref.timestamp_ms), (15, 500))

    def test_sampling_uses_frame_range_and_step(self) -> None:
        refs = sample_frame_refs(
            self.metadata,
            VideoSettings(start_frame=10, end_frame=20, sample_every=3, max_frames=256),
        )

        self.assertEqual([ref.index for ref in refs], [10, 13, 16, 19])
        self.assertEqual([ref.timestamp_ms for ref in refs], [333, 433, 533, 633])

    def test_target_fps_increases_sampling_step(self) -> None:
        refs = sample_frame_refs(
            self.metadata,
            VideoSettings(start_frame=0, end_frame=60, target_fps=10.0, max_frames=256),
        )

        self.assertEqual([ref.index for ref in refs[:4]], [0, 3, 6, 9])

    def test_max_frames_keeps_first_and_last_candidates(self) -> None:
        refs = sample_frame_refs(
            self.metadata,
            VideoSettings(start_frame=0, end_frame=99, sample_every=1, max_frames=4),
        )

        self.assertEqual([ref.index for ref in refs], [0, 33, 66, 99])

    def test_video_output_settings_round_trip_separately_from_sampling(self) -> None:
        settings = VideoSettings(
            start_frame=4,
            sample_every=2,
            frame_width=64,
            frame_height=96,
            resize_mode="fit",
            remove_background=True,
            background_color=(10, 20, 30),
            sheet_columns=6,
            sheet_rows=4,
        )

        restored = VideoSettings.from_dict(settings.to_dict())

        self.assertEqual(restored.start_frame, 4)
        self.assertEqual((restored.frame_width, restored.frame_height), (64, 96))
        self.assertEqual(restored.background_color, (10, 20, 30))
        self.assertEqual((restored.sheet_columns, restored.sheet_rows), (6, 4))


if __name__ == "__main__":
    unittest.main()

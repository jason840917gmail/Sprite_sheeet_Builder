from __future__ import annotations

import math
import random
from collections.abc import Sequence

from sprite_sheet_cleaner.app.core.video_source import FrameRef


def recommended_animation_frame_count(total_frames: int) -> int:
    """Return a compact starting count for a hand-tuned animation.

    The rule aims for roughly one candidate per twelve source frames, then
    keeps the starting animation between eight and twelve frames whenever the
    source is long enough.
    """
    total_frames = max(0, int(total_frames))
    if total_frames == 0:
        return 0
    return min(total_frames, max(8, min(12, round(total_frames / 12))))


def pick_animation_refs(
    refs: Sequence[FrameRef],
    total_frames: int,
    *,
    target_count: int | None = None,
    rng: random.Random | None = None,
) -> list[FrameRef]:
    """Pick one random candidate from each chronological segment.

    Segmenting before choosing prevents a purely random pick from clustering
    near one part of the video. The returned refs are always source ordered.
    """
    ordered = sorted(refs, key=lambda ref: ref.index)
    target = (
        recommended_animation_frame_count(total_frames)
        if target_count is None
        else max(1, int(target_count))
    )
    target = min(target, max(1, int(total_frames)))
    if len(ordered) <= target:
        return ordered

    chooser = rng or random.Random()
    picked: list[FrameRef] = []
    for segment in range(target):
        start = math.floor(segment * len(ordered) / target)
        end = math.floor((segment + 1) * len(ordered) / target) - 1
        picked.append(ordered[chooser.randint(start, max(start, end))])
    return sorted(picked, key=lambda ref: ref.index)

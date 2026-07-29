from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image

from sprite_sheet_cleaner.app.models.video_settings import VideoSettings


class VideoSourceError(RuntimeError):
    """Raised when a video cannot be opened or decoded."""


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    path: str
    width: int
    height: int
    frame_count: int
    fps: float
    duration_seconds: float

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


@dataclass(frozen=True, slots=True)
class FrameRef:
    index: int
    timestamp_ms: int


def _cv2():
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - depends on the runtime environment
        raise VideoSourceError(
            "Video support requires OpenCV. Install the project requirements and try again."
        ) from exc
    return cv2


def read_video_metadata(path: str | Path) -> VideoMetadata:
    cv2 = _cv2()
    video_path = Path(path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise VideoSourceError(f"Could not open video: {video_path}")

    try:
        width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        frame_count = max(0, int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        capture.release()

    if width <= 0 or height <= 0:
        raise VideoSourceError(f"Video has invalid dimensions: {video_path}")
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    return VideoMetadata(str(video_path), width, height, frame_count, fps, duration)


def frame_ref(metadata: VideoMetadata, index: int) -> FrameRef:
    index = int(index)
    if not 0 <= index < metadata.frame_count:
        raise ValueError(f"Frame index {index} is outside the video.")
    timestamp_ms = round(index * 1000 / metadata.fps) if metadata.fps > 0 else 0
    return FrameRef(index=index, timestamp_ms=timestamp_ms)


def _bound_indices(indices: list[int], maximum: int) -> list[int]:
    if len(indices) <= maximum:
        return indices
    if maximum == 1:
        return [indices[0]]

    selected: list[int] = []
    for position in range(maximum):
        source_position = round(position * (len(indices) - 1) / (maximum - 1))
        index = indices[source_position]
        if not selected or selected[-1] != index:
            selected.append(index)
    return selected


def sample_frame_refs(metadata: VideoMetadata, settings: VideoSettings) -> list[FrameRef]:
    settings.validated()
    if metadata.frame_count <= 0:
        return []

    start = min(settings.start_frame, metadata.frame_count - 1)
    end = metadata.frame_count - 1 if settings.end_frame is None else min(settings.end_frame, metadata.frame_count - 1)
    if end < start:
        return []

    step = settings.sample_every
    if settings.target_fps is not None and metadata.fps > 0:
        step = max(step, round(metadata.fps / settings.target_fps))
    indices = list(range(start, end + 1, max(1, step)))
    return [frame_ref(metadata, index) for index in _bound_indices(indices, settings.max_frames)]


class VideoSource:
    """Small OpenCV-backed frame source.

    A source owns one capture handle and is intentionally not shared between UI
    and worker threads. Workers should create their own instance.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._capture = None
        self._metadata = read_video_metadata(self.path)

    @property
    def metadata(self) -> VideoMetadata:
        return self._metadata

    def _open_capture(self):
        if self._capture is None:
            cv2 = _cv2()
            self._capture = cv2.VideoCapture(str(self.path))
            if not self._capture.isOpened():
                self.close()
                raise VideoSourceError(f"Could not open video: {self.path}")
        return self._capture

    @staticmethod
    def _to_pil(frame) -> Image.Image:
        cv2 = _cv2()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb, "RGB").convert("RGBA")

    def read_frame(self, index: int) -> Image.Image:
        ref = frame_ref(self.metadata, index)
        capture = self._open_capture()
        cv2 = _cv2()
        capture.set(cv2.CAP_PROP_POS_FRAMES, ref.index)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise VideoSourceError(f"Could not decode frame {ref.index} from {self.path.name}")
        return self._to_pil(frame)

    def read_frames(
        self,
        refs: list[FrameRef],
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[tuple[FrameRef, Image.Image]]:
        if not refs:
            return
        ordered_refs = sorted(refs, key=lambda ref: ref.index)
        capture = self._open_capture()
        cv2 = _cv2()
        capture.set(cv2.CAP_PROP_POS_FRAMES, ordered_refs[0].index)
        wanted = {ref.index: ref for ref in ordered_refs}
        current_index = ordered_refs[0].index
        last_index = ordered_refs[-1].index

        while current_index <= last_index:
            if cancel_event is not None and cancel_event.is_set():
                return
            ok, frame = capture.read()
            if not ok or frame is None:
                raise VideoSourceError(f"Could not decode frame {current_index} from {self.path.name}")
            ref = wanted.get(current_index)
            if ref is not None:
                yield ref, self._to_pil(frame)
            current_index += 1

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


from __future__ import annotations

from collections import deque

import numpy as np


def border_connected(mask: np.ndarray) -> np.ndarray:
    """Return the part of a boolean mask connected to any image border."""
    candidate = np.asarray(mask, dtype=bool)
    if candidate.ndim != 2:
        raise ValueError("Mask must be two-dimensional.")
    try:
        import cv2  # type: ignore
    except ImportError:
        cv2 = None

    if cv2 is not None:
        labels_count, labels = cv2.connectedComponents(candidate.astype(np.uint8), connectivity=8)
        connected_labels: set[int] = set()
        connected_labels.update(int(value) for value in labels[0, :] if value)
        connected_labels.update(int(value) for value in labels[-1, :] if value)
        connected_labels.update(int(value) for value in labels[:, 0] if value)
        connected_labels.update(int(value) for value in labels[:, -1] if value)
        if not connected_labels:
            return np.zeros_like(candidate)
        return np.isin(labels, list(connected_labels))

    height, width = candidate.shape
    visited = np.zeros_like(candidate)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        if candidate[0, x]:
            queue.append((0, x))
        if candidate[height - 1, x]:
            queue.append((height - 1, x))
    for y in range(height):
        if candidate[y, 0]:
            queue.append((y, 0))
        if candidate[y, width - 1]:
            queue.append((y, width - 1))

    while queue:
        y, x = queue.popleft()
        if not (0 <= y < height and 0 <= x < width) or visited[y, x] or not candidate[y, x]:
            continue
        visited[y, x] = True
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    queue.append((y + dy, x + dx))
    return visited


def soft_threshold(distance: np.ndarray, transparent: float, foreground: float) -> np.ndarray:
    if transparent < 0 or foreground <= transparent:
        raise ValueError("Foreground threshold must exceed transparent threshold.")
    return np.clip((distance - transparent) * 255.0 / (foreground - transparent), 0, 255).astype(np.uint8)

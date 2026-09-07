"""Streaming event snapshots and overlays on the input video."""

from collections import deque
from pathlib import Path

import cv2
import numpy as np


POSITIVE_COLOR = (0, 0, 255)  # Red in OpenCV BGR order.
NEGATIVE_COLOR = (255, 0, 0)  # Blue in OpenCV BGR order.


def _draw_events(frame, x, y, p, alpha=1.0):
    """Draw positive events in red and negative events in blue."""

    if len(p) == 0:
        return frame
    for event_mask, color in (
        (p < 0, NEGATIVE_COLOR),
        (p > 0, POSITIVE_COLOR),
    ):
        event_x = x[event_mask]
        event_y = y[event_mask]
        if len(event_x) == 0:
            continue
        if alpha == 1.0:
            frame[event_y, event_x] = color
            continue
        original = frame[event_y, event_x].astype(np.float32)
        blended = original * (1.0 - alpha) + np.asarray(color) * alpha
        frame[event_y, event_x] = np.rint(blended).astype(np.uint8)
    return frame


class StreamingEventVisualizer:
    """Write the overlay and snapshot during the simulator's video pass."""

    def __init__(
        self,
        video_info,
        overlay_path,
        snapshot_path,
        accumulation_time,
        snapshot_start_time,
        snapshot_duration,
        overlay_playback_fps,
        overlay_event_alpha,
    ):
        if accumulation_time <= 0:
            raise ValueError("Accumulation time must be greater than zero")
        if snapshot_start_time < 0:
            raise ValueError("Snapshot start time cannot be negative")
        if snapshot_duration <= 0:
            raise ValueError("Snapshot duration must be greater than zero")
        if overlay_playback_fps <= 0:
            raise ValueError("Overlay playback FPS must be greater than zero")
        if not 0 < overlay_event_alpha <= 1:
            raise ValueError("Overlay event alpha must be in the range (0, 1]")

        self.overlay_path = Path(overlay_path)
        self.snapshot_path = Path(snapshot_path)
        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.accumulation_time = float(accumulation_time)
        self.snapshot_start_time = float(snapshot_start_time)
        self.snapshot_end_time = float(snapshot_start_time + snapshot_duration)
        self.overlay_event_alpha = float(overlay_event_alpha)
        self._recent_batches = deque()
        self.processed_frames = 0
        self.snapshot_event_count = 0
        self._closed = False

        width = int(video_info["width"])
        height = int(video_info["height"])
        self._snapshot = np.full((height, width, 3), 127, dtype=np.uint8)
        self._writer = cv2.VideoWriter(
            str(self.overlay_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            float(overlay_playback_fps),
            (width, height),
        )
        if not self._writer.isOpened():
            raise RuntimeError(f"Cannot create overlay video: {self.overlay_path}")

    def add_frame(self, frame, timestamp, events):
        if self._closed:
            raise RuntimeError("Cannot write to a closed overlay video")

        event_count = len(events["t"])
        if event_count > 0:
            self._recent_batches.append(events)

            snapshot_start = np.searchsorted(
                events["t"], self.snapshot_start_time, side="left"
            )
            snapshot_end = np.searchsorted(
                events["t"], self.snapshot_end_time, side="left"
            )
            if snapshot_end > snapshot_start:
                _draw_events(
                    self._snapshot,
                    events["x"][snapshot_start:snapshot_end],
                    events["y"][snapshot_start:snapshot_end],
                    events["p"][snapshot_start:snapshot_end],
                )
                self.snapshot_event_count += snapshot_end - snapshot_start

        window_start = max(0.0, float(timestamp) - self.accumulation_time)
        while (
            self._recent_batches
            and self._recent_batches[0]["t"][-1] < window_start
        ):
            self._recent_batches.popleft()

        for batch in self._recent_batches:
            start = np.searchsorted(batch["t"], window_start, side="left")
            end = np.searchsorted(batch["t"], timestamp, side="right")
            if end > start:
                _draw_events(
                    frame,
                    batch["x"][start:end],
                    batch["y"][start:end],
                    batch["p"][start:end],
                    self.overlay_event_alpha,
                )

        self._writer.write(frame)
        self.processed_frames += 1

    def finalize(self):
        if self._closed:
            return
        self._writer.release()
        self._closed = True
        if self.processed_frames == 0:
            raise RuntimeError("No video frames were available for visualization")
        if not cv2.imwrite(str(self.snapshot_path), self._snapshot):
            raise RuntimeError(f"Cannot create event snapshot: {self.snapshot_path}")
        if not self.overlay_path.is_file() or self.overlay_path.stat().st_size == 0:
            raise RuntimeError(f"Overlay video was not created: {self.overlay_path}")

    def abort(self):
        if self._closed:
            return
        self._writer.release()
        self._closed = True

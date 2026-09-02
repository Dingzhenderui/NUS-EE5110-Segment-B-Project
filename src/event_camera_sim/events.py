"""Event generation from consecutive video frames."""

import cv2
import numpy as np


EVENT_DTYPES = {
    "x": np.int32,
    "y": np.int32,
    "t": np.float64,
    "p": np.int8,
}


def empty_events():
    """Return an empty event batch with explicit field types."""

    return {name: np.empty(0, dtype=dtype) for name, dtype in EVENT_DTYPES.items()}


def frame_to_log_intensity(frame, epsilon=1e-3):
    """Convert one BGR frame to normalized float32 log intensity."""

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    intensity = gray.astype(np.float32) / 255.0
    return np.log(intensity + epsilon)


class EventSimulator:
    """Generate ideal, noise-free threshold-crossing events."""

    def __init__(
        self,
        threshold_pos,
        threshold_neg,
        epsilon=1e-3,
        timestamp_resolution=1e-6,
    ):
        if threshold_pos <= 0 or threshold_neg <= 0:
            raise ValueError("Event thresholds must be greater than zero")
        if timestamp_resolution <= 0:
            raise ValueError("Timestamp resolution must be greater than zero")

        self.threshold_pos = float(threshold_pos)
        self.threshold_neg = float(threshold_neg)
        self._threshold_pos32 = np.float32(threshold_pos)
        self._threshold_neg32 = np.float32(threshold_neg)
        self.epsilon = float(epsilon)
        self.timestamp_resolution = float(timestamp_resolution)
        self.reference_log = None
        self.previous_log = None
        self.previous_timestamp = None

    def process_frame(self, frame, timestamp):
        """Return one time-ordered event batch with x, y, t, and p arrays."""

        current_timestamp = float(timestamp)
        current_log = frame_to_log_intensity(frame, self.epsilon)
        if self.reference_log is None:
            self.reference_log = current_log.copy()
            self.previous_log = current_log.copy()
            self.previous_timestamp = current_timestamp
            return empty_events()

        if current_log.shape != self.previous_log.shape:
            raise ValueError("All input video frames must have the same resolution")
        if current_timestamp <= self.previous_timestamp:
            raise ValueError("Frame timestamps must be strictly increasing")
        previous_timestamp = float(self.previous_timestamp)

        delta_from_reference = current_log - self.reference_log
        tolerance = np.float32(1e-6)
        positive_counts = np.floor(
            np.maximum(delta_from_reference, np.float32(0.0))
            / self._threshold_pos32
            + tolerance
        ).astype(np.int32)
        negative_counts = np.floor(
            np.maximum(-delta_from_reference, np.float32(0.0))
            / self._threshold_neg32
            + tolerance
        ).astype(np.int32)

        batches = []
        positive = self._generate_crossings(
            current_log,
            positive_counts,
            self.threshold_pos,
            polarity=1,
            current_timestamp=current_timestamp,
        )
        if len(positive["t"]) > 0:
            batches.append(positive)

        negative = self._generate_crossings(
            current_log,
            negative_counts,
            self.threshold_neg,
            polarity=-1,
            current_timestamp=current_timestamp,
        )
        if len(negative["t"]) > 0:
            batches.append(negative)

        # Preserve the original float64 multiplication and float32 assignment
        # semantics, but update only a small row block at a time. This keeps the
        # original event counts without allocating a full-resolution temporary.
        rows = self.reference_log.shape[0]
        for start in range(0, rows, 128):
            end = min(start + 128, rows)
            self.reference_log[start:end] += (
                positive_counts[start:end] * self.threshold_pos
            )
            self.reference_log[start:end] -= (
                negative_counts[start:end] * self.threshold_neg
            )

        self.previous_log = current_log
        self.previous_timestamp = current_timestamp

        if not batches:
            return empty_events()

        if len(batches) == 1:
            events = batches[0]
        else:
            events = {
                name: np.concatenate([batch[name] for batch in batches])
                for name in EVENT_DTYPES
            }

        order = np.argsort(events["t"], kind="stable")
        events = {name: values[order] for name, values in events.items()}

        # Sort using the continuous interpolation time first, then quantize.
        # This keeps the original event ordering while providing a declared
        # sensor timestamp resolution.
        resolution = self.timestamp_resolution
        lower_tick = np.ceil(previous_timestamp / resolution - 1e-12)
        upper_tick = np.floor(current_timestamp / resolution + 1e-12)
        event_ticks = np.rint(events["t"] / resolution)
        np.clip(event_ticks, lower_tick, upper_tick, out=event_ticks)
        events["t"] = event_ticks * resolution
        return events

    def _generate_crossings(
        self,
        current_log,
        counts,
        threshold,
        polarity,
        current_timestamp,
    ):
        """Vectorize all threshold crossings for one polarity."""

        active_y, active_x = np.nonzero(counts)
        if len(active_x) == 0:
            return empty_events()

        repetitions = counts[active_y, active_x].astype(np.int64, copy=False)
        event_count = int(repetitions.sum(dtype=np.int64))
        if event_count == 0:
            return empty_events()

        x = np.repeat(active_x.astype(np.int32, copy=False), repetitions)
        y = np.repeat(active_y.astype(np.int32, copy=False), repetitions)

        # Build [1, 2, ..., count] for every active pixel without rescanning
        # the full image once per threshold level.
        levels = np.ones(event_count, dtype=np.int32)
        if len(repetitions) > 1:
            starts = np.cumsum(repetitions[:-1], dtype=np.int64)
            levels[starts] = 1 - repetitions[:-1]
        np.cumsum(levels, dtype=np.int32, out=levels)

        # The former implementation emitted one row-major image scan for each
        # threshold level. Restore that same pre-sort order so events sharing an
        # identical timestamp remain byte-for-byte compatible.
        level_order = np.argsort(levels, kind="stable")
        levels = levels[level_order]
        x = x[level_order]
        y = y[level_order]

        # Match the former scalar expression ``level * threshold``: compute
        # each unique level in float64, then cast once to float32 for addition
        # to the float32 reference image.
        level_offsets = (
            np.arange(int(levels[-1]) + 1, dtype=np.float64)
            * float(polarity)
            * float(threshold)
        ).astype(np.float32)
        offsets = level_offsets[levels]

        numerator = self.reference_log[y, x]
        numerator += offsets
        previous = self.previous_log[y, x]
        numerator -= previous

        change = current_log[y, x]
        change -= previous
        fraction = np.ones(event_count, dtype=np.float64)
        np.divide(
            numerator,
            change,
            out=fraction,
            where=np.abs(change) > np.float32(1e-12),
        )
        np.clip(fraction, 0.0, 1.0, out=fraction)

        previous_timestamp = float(self.previous_timestamp)
        event_time = previous_timestamp + fraction * (
            current_timestamp - previous_timestamp
        )
        return {
            "x": x,
            "y": y,
            "t": event_time.astype(np.float64, copy=False),
            "p": np.full(event_count, polarity, dtype=np.int8),
        }

    def reset(self):
        self.reference_log = None
        self.previous_log = None
        self.previous_timestamp = None

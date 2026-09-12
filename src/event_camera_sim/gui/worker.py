"""Background worker thread for running the simulation pipeline without blocking Qt GUI."""

from pathlib import Path
from time import perf_counter
from PySide6.QtCore import QThread, Signal

from ..pipeline import run as run_pipeline


class SimulationWorker(QThread):
    """QThread running the Event Camera Simulation pipeline."""

    started_sig = Signal()
    progress_sig = Signal(int, int, int, float, int, int, int)
    # preview: (orig_bgr, event_bgr, overlay_bgr, timestamp, frame_idx)
    preview_sig = Signal(object, object, object, float, int)
    finished_sig = Signal(dict)
    error_sig = Signal(str)
    cancelled_sig = Signal()
    log_sig = Signal(str)

    def __init__(self, video_path, params=None, max_frames=None, parent=None):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.params = params or {}
        self.max_frames = max_frames
        self._is_cancelled = False
        self._last_preview_time = 0.0
        self._preview_interval = 0.033  # ~30 FPS preview throttle to keep UI ultra responsive

    def cancel(self):
        """Request cooperative cancellation."""
        self._is_cancelled = True

    def _check_cancellation(self):
        return self._is_cancelled

    def _on_progress(
        self,
        processed_frames,
        total_frames,
        total_events,
        current_fps,
        pos_events,
        neg_events,
        h5_bytes,
    ):
        self.progress_sig.emit(
            int(processed_frames),
            int(total_frames),
            int(total_events),
            float(current_fps),
            int(pos_events),
            int(neg_events),
            int(h5_bytes),
        )

    def _on_preview(self, orig_frame, event_canvas, overlay_frame, timestamp, frame_idx):
        now = perf_counter()
        # Always emit every 5 frames or if preview interval has elapsed
        if (now - self._last_preview_time >= self._preview_interval) or (frame_idx % 5 == 0):
            self._last_preview_time = now
            # Pass copies or arrays to main thread
            self.preview_sig.emit(
                orig_frame.copy() if orig_frame is not None else None,
                event_canvas.copy() if event_canvas is not None else None,
                overlay_frame.copy() if overlay_frame is not None else None,
                float(timestamp),
                int(frame_idx),
            )

    def run(self):
        self.started_sig.emit()
        self.log_sig.emit(f"Starting simulation on: {self.video_path.name}")
        try:
            result = run_pipeline(
                video_path=self.video_path,
                params=self.params,
                max_frames=self.max_frames,
                progress_callback=self._on_progress,
                preview_callback=self._on_preview,
                cancellation_check=self._check_cancellation,
            )
            if self._is_cancelled:
                self.cancelled_sig.emit()
                self.log_sig.emit("Simulation was stopped by user.")
            else:
                self.finished_sig.emit(result)
                self.log_sig.emit(
                    f"Simulation completed! Generated {result['event_count']:,} events in "
                    f"{result['timings']['total_seconds']:.2f} s."
                )
        except KeyboardInterrupt:
            self.cancelled_sig.emit()
            self.log_sig.emit("Simulation cancelled by user.")
        except Exception as exc:
            self.error_sig.emit(str(exc))
            self.log_sig.emit(f"[ERROR] {exc}")

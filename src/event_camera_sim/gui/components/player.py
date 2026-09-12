"""Visual display and interactive video/event player component."""

from pathlib import Path
import cv2
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QComboBox,
    QStackedWidget,
    QButtonGroup,
    QFrame,
    QSizePolicy,
)


def bgr_to_qpixmap(bgr_array, target_size=None):
    """Convert a BGR numpy array to QPixmap efficiently."""
    if bgr_array is None or bgr_array.size == 0:
        return QPixmap()
    height, width, channel = bgr_array.shape
    bytes_per_line = 3 * width
    # cv2 BGR to RGB
    rgb = cv2.cvtColor(bgr_array, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
    pix = QPixmap.fromImage(qimg)
    if target_size and not pix.isNull():
        return pix.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pix


class ImageCanvas(QWidget):
    """Clean, high-performance canvas displaying an image with preserved aspect ratio."""

    def __init__(self, title="", placeholder_text="等待载入画面...", parent=None):
        super().__init__(parent)
        self.title = title
        self.placeholder_text = placeholder_text
        self._pixmap = QPixmap()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 200)

    def set_image(self, bgr_array):
        """Update display with a new BGR image array."""
        if bgr_array is None:
            self._pixmap = QPixmap()
        else:
            self._pixmap = bgr_to_qpixmap(bgr_array)
        self.update()

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def clear(self):
        self._pixmap = QPixmap()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Draw dark canvas background
        painter.fillRect(rect, QColor("#14151E"))

        if not self._pixmap.isNull():
            # Scale pixmap preserving aspect ratio
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # Draw placeholder message
            painter.setPen(QColor("#6B728D"))
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholder_text)

        # Draw title badge in upper-left corner
        if self.title:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 22, 34, 200))
            title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(title_font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.title) + 16
            th = fm.height() + 8
            painter.drawRoundedRect(10, 10, tw, th, 4, 4)

            painter.setPen(QColor("#A5B4FC"))
            painter.drawText(18, 10 + fm.ascent() + 4, self.title)


class VideoPlayerWidget(QWidget):
    """Central display widget featuring Multi-view and Side-by-Side playback."""

    frame_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Video playback state
        self._cap_orig = None
        self._cap_event = None
        self._cap_overlay = None
        self._total_frames = 0
        self._current_frame_idx = 0
        self._is_playing = False
        self._playback_fps = 30.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_play_tick)

        # Cached frames during simulation
        self._last_orig_frame = None
        self._last_event_frame = None
        self._last_overlay_frame = None
        self._snapshot_img = None

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Top view selector bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(4, 0, 4, 0)

        view_title = QLabel("视觉呈现窗口 (Visual Presentation)")
        view_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        top_bar.addWidget(view_title)

        top_bar.addStretch()

        # View mode buttons
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        self.btn_side_by_side = QPushButton("⊞ 并排对比模式 (Side-by-Side)")
        self.btn_side_by_side.setCheckable(True)
        self.btn_side_by_side.setChecked(True)
        self.btn_group.addButton(self.btn_side_by_side, 0)
        top_bar.addWidget(self.btn_side_by_side)

        self.btn_event_only = QPushButton("🔴🔵 纯事件流 (Event-Only)")
        self.btn_event_only.setCheckable(True)
        self.btn_group.addButton(self.btn_event_only, 1)
        top_bar.addWidget(self.btn_event_only)

        self.btn_overlay = QPushButton("🎬 事件叠加 (Overlay)")
        self.btn_overlay.setCheckable(True)
        self.btn_group.addButton(self.btn_overlay, 2)
        top_bar.addWidget(self.btn_overlay)

        self.btn_snapshot = QPushButton("🖼️ 时间窗快照 (Snapshot)")
        self.btn_snapshot.setCheckable(True)
        self.btn_group.addButton(self.btn_snapshot, 3)
        top_bar.addWidget(self.btn_snapshot)

        self.btn_group.idClicked.connect(self._on_view_mode_changed)
        main_layout.addLayout(top_bar)

        # Stacked display container
        self.display_stack = QStackedWidget()
        self.display_stack.setStyleSheet(
            "QStackedWidget { background-color: #161824; border: 1px solid #2B2F44; border-radius: 10px; }"
        )

        # Page 0: Side by side view
        self.page_side_by_side = QWidget()
        sbs_layout = QHBoxLayout(self.page_side_by_side)
        sbs_layout.setContentsMargins(6, 6, 6, 6)
        sbs_layout.setSpacing(6)
        self.sbs_orig_canvas = ImageCanvas(title="原始高速视频 (Input Video)", placeholder_text="等待载入原始输入视频...")
        self.sbs_event_canvas = ImageCanvas(title="模拟事件流 (Event Stream)", placeholder_text="等待开始仿真生成事件...")
        sbs_layout.addWidget(self.sbs_orig_canvas, 1)
        sbs_layout.addWidget(self.sbs_event_canvas, 1)
        self.display_stack.addWidget(self.page_side_by_side)

        # Page 1: Event-Only single view
        self.single_event_canvas = ImageCanvas(title="事件流相机独立视图 (Event-Only)", placeholder_text="等待模拟...")
        self.display_stack.addWidget(self.single_event_canvas)

        # Page 2: Overlay single view
        self.single_overlay_canvas = ImageCanvas(title="事件与输入视频叠加视图 (Overlay)", placeholder_text="等待模拟...")
        self.display_stack.addWidget(self.single_overlay_canvas)

        # Page 3: Snapshot view
        self.snapshot_canvas = ImageCanvas(title="时间窗口静态积分快照 (Integrated Snapshot)", placeholder_text="模拟完成后生成快照...")
        self.display_stack.addWidget(self.snapshot_canvas)

        main_layout.addWidget(self.display_stack, 1)

        # Bottom player control bar
        self.player_bar = QFrame()
        self.player_bar.setStyleSheet(
            "QFrame { background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 8px; padding: 4px; }"
        )
        bar_layout = QHBoxLayout(self.player_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.setSpacing(10)

        self.btn_play = QPushButton("▶ 播放 (Play)")
        self.btn_play.setFixedWidth(90)
        self.btn_play.clicked.connect(self.toggle_play)
        bar_layout.addWidget(self.btn_play)

        self.btn_prev_frame = QPushButton("⏮")
        self.btn_prev_frame.setToolTip("上一帧 (Previous Frame)")
        self.btn_prev_frame.setFixedWidth(36)
        self.btn_prev_frame.clicked.connect(lambda: self.step_frame(-1))
        bar_layout.addWidget(self.btn_prev_frame)

        self.btn_next_frame = QPushButton("⏭")
        self.btn_next_frame.setToolTip("下一帧 (Next Frame)")
        self.btn_next_frame.setFixedWidth(36)
        self.btn_next_frame.clicked.connect(lambda: self.step_frame(1))
        bar_layout.addWidget(self.btn_next_frame)

        # Timeline slider
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.sliderMoved.connect(self._on_slider_moved)
        bar_layout.addWidget(self.timeline_slider, 1)

        # Frame index / time label
        self.lbl_frame_info = QLabel("帧: 0 / 0  (0.000 s)")
        self.lbl_frame_info.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #CDD6F4;")
        bar_layout.addWidget(self.lbl_frame_info)

        # Speed selector
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1.0x (30fps)", "2.0x"])
        self.combo_speed.setCurrentIndex(2)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        bar_layout.addWidget(self.combo_speed)

        main_layout.addWidget(self.player_bar)

    def _on_view_mode_changed(self, view_id):
        self.display_stack.setCurrentIndex(view_id)
        self._refresh_current_view()

    def update_live_preview(self, orig_frame, event_canvas, overlay_frame, timestamp, frame_idx):
        """Update displays during live simulation."""
        self._last_orig_frame = orig_frame
        self._last_event_frame = event_canvas
        self._last_overlay_frame = overlay_frame

        # Update canvases
        self.sbs_orig_canvas.set_image(orig_frame)
        self.sbs_event_canvas.set_image(overlay_frame if overlay_frame is not None else event_canvas)
        self.single_event_canvas.set_image(event_canvas)
        self.single_overlay_canvas.set_image(overlay_frame)

        self.lbl_frame_info.setText(f"帧: {frame_idx}  ({timestamp:.4f} s)")

    def load_completed_results(self, orig_video_path, event_only_path, overlay_path, snapshot_path):
        """Load finished videos and snapshot for playback."""
        self._release_caps()

        if orig_video_path and Path(orig_video_path).is_file():
            self._cap_orig = cv2.VideoCapture(str(orig_video_path))
        if event_only_path and Path(event_only_path).is_file():
            self._cap_event = cv2.VideoCapture(str(event_only_path))
        if overlay_path and Path(overlay_path).is_file():
            self._cap_overlay = cv2.VideoCapture(str(overlay_path))

        # Snapshot image
        if snapshot_path and Path(snapshot_path).is_file():
            self._snapshot_img = cv2.imread(str(snapshot_path))
            self.snapshot_canvas.set_image(self._snapshot_img)

        # Determine total frames
        total = 0
        for cap in (self._cap_overlay, self._cap_event, self._cap_orig):
            if cap and cap.isOpened():
                total = max(total, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self._total_frames = total

        self.timeline_slider.setRange(0, max(0, self._total_frames - 1))
        self.seek_frame(0)

    def seek_frame(self, frame_idx):
        """Seek to a specific frame across opened videos."""
        if self._total_frames <= 0:
            return
        frame_idx = max(0, min(frame_idx, self._total_frames - 1))
        self._current_frame_idx = frame_idx

        orig_bgr = None
        event_bgr = None
        overlay_bgr = None

        if self._cap_orig and self._cap_orig.isOpened():
            self._cap_orig.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, orig_bgr = self._cap_orig.read()

        if self._cap_event and self._cap_event.isOpened():
            self._cap_event.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, event_bgr = self._cap_event.read()

        if self._cap_overlay and self._cap_overlay.isOpened():
            self._cap_overlay.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, overlay_bgr = self._cap_overlay.read()

        self._last_orig_frame = orig_bgr
        self._last_event_frame = event_bgr
        self._last_overlay_frame = overlay_bgr

        self._refresh_current_view()
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(frame_idx)
        self.timeline_slider.blockSignals(False)

        fps = 30.0
        time_sec = frame_idx / fps
        self.lbl_frame_info.setText(f"帧: {frame_idx + 1:04d} / {self._total_frames:04d}  ({time_sec:.3f} s)")
        self.frame_changed.emit(frame_idx)

    def _refresh_current_view(self):
        curr_view = self.display_stack.currentIndex()
        if curr_view == 0:
            self.sbs_orig_canvas.set_image(self._last_orig_frame)
            self.sbs_event_canvas.set_image(self._last_overlay_frame or self._last_event_frame)
        elif curr_view == 1:
            self.single_event_canvas.set_image(self._last_event_frame)
        elif curr_view == 2:
            self.single_overlay_canvas.set_image(self._last_overlay_frame)
        elif curr_view == 3:
            if self._snapshot_img is not None:
                self.snapshot_canvas.set_image(self._snapshot_img)

    def step_frame(self, step):
        self.pause()
        self.seek_frame(self._current_frame_idx + step)

    def _on_slider_moved(self, value):
        self.pause()
        self.seek_frame(value)

    def toggle_play(self):
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self._total_frames <= 0:
            return
        self._is_playing = True
        self.btn_play.setText("⏸ 暂停 (Pause)")
        interval = int(1000 / (self._playback_fps * self._get_speed_multiplier()))
        self._timer.start(max(10, interval))

    def pause(self):
        self._is_playing = False
        self.btn_play.setText("▶ 播放 (Play)")
        self._timer.stop()

    def _get_speed_multiplier(self):
        idx = self.combo_speed.currentIndex()
        if idx == 0:
            return 0.25
        elif idx == 1:
            return 0.5
        elif idx == 2:
            return 1.0
        elif idx == 3:
            return 2.0
        return 1.0

    def _on_speed_changed(self):
        if self._is_playing:
            self.play()

    def _on_play_tick(self):
        next_frame = self._current_frame_idx + 1
        if next_frame >= self._total_frames:
            next_frame = 0  # Loop back
        self.seek_frame(next_frame)

    def _release_caps(self):
        self.pause()
        for cap in (self._cap_orig, self._cap_event, self._cap_overlay):
            if cap and cap.isOpened():
                cap.release()
        self._cap_orig = None
        self._cap_event = None
        self._cap_overlay = None

    def closeEvent(self, event):
        self._release_caps()
        super().closeEvent(event)

"""Streamlined, robust English GUI application for EE5110 Event Camera Simulator."""

import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap

def _get_icon_path():
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "assets" / "icon.png",
        Path(sys.executable).parent / "assets" / "icon.png",
        Path(sys.executable).parent / "_internal" / "assets" / "icon.png",
        Path.cwd() / "assets" / "icon.png",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..video import VideoReader
from .theme import MODERN_DARK_STYLESHEET
from .worker import SimulationWorker


def format_bytes(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def cv_frame_to_qpixmap(bgr_img):
    """Convert OpenCV BGR image to a safely copied QPixmap."""
    if bgr_img is None or bgr_img.size == 0:
        return QPixmap()
    h, w, ch = bgr_img.shape
    rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg).copy()


class ImageCanvas(QWidget):
    """Clean, high-performance canvas displaying video frames with preserved aspect ratio."""

    def __init__(self, placeholder="No video or image loaded", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self._pixmap = QPixmap()
        self.setMinimumSize(480, 320)
        self.setStyleSheet("background-color: #12131C; border-radius: 8px;")

    def set_frame(self, bgr_img):
        self._pixmap = cv_frame_to_qpixmap(bgr_img)
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

        # Canvas background
        painter.fillRect(rect, QColor("#12131C"))

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor("#6B728D"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholder)


class MainWindow(QMainWindow):
    """Main GUI window for the Event Camera Simulator."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EE5110 Event Camera Simulator - NUS CA")
        self.resize(1260, 800)
        self.setMinimumSize(960, 640)

        icon_path = _get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(str(icon_path)))

        self._worker = None
        self._current_video_path = None
        self._last_result = None

        # Playback engine
        self._current_cap = None
        self._current_cap_type = None  # 'overlay' or 'event_only'
        self._total_playback_frames = 0
        self._current_frame_idx = 0
        self._is_playing = False
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._on_play_step)

        self._setup_ui()
        self._populate_sample_videos()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Header banner - single clean line with logo
        header = QFrame()
        header.setStyleSheet(
            "background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 6px; padding: 4px 12px;"
        )
        h_box = QHBoxLayout(header)
        h_box.setContentsMargins(4, 2, 4, 2)

        icon_path = _get_icon_path()
        if icon_path:
            lbl_logo = QLabel()
            pix = QPixmap(str(icon_path)).scaled(
                26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pix)
            h_box.addWidget(lbl_logo)
            h_box.addSpacing(6)

        lbl_title = QLabel("Event Camera Simulator")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        h_box.addWidget(lbl_title)
        h_box.addStretch()
        main_layout.addWidget(header)

        # Main splitter (Left: Controls, Right: Player & Stats)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        # LEFT SIDEBAR
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setMinimumWidth(380)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        sidebar = QWidget()
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(2, 2, 14, 2)
        side_layout.setSpacing(10)

        # 1. Video Input Group
        grp_video = QGroupBox("1. Video Input")
        gv_layout = QVBoxLayout(grp_video)
        gv_layout.setSpacing(6)

        h_samples = QHBoxLayout()
        h_samples.addWidget(QLabel("Sample:"))
        self.combo_samples = QComboBox()
        self.combo_samples.currentIndexChanged.connect(self._on_sample_selected)
        h_samples.addWidget(self.combo_samples, 1)
        gv_layout.addLayout(h_samples)

        h_file = QHBoxLayout()
        self.txt_video_path = QLineEdit()
        self.txt_video_path.setPlaceholderText("Select video file...")
        self.txt_video_path.textChanged.connect(self._on_video_path_changed)
        h_file.addWidget(self.txt_video_path, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_video)
        h_file.addWidget(self.btn_browse)
        gv_layout.addLayout(h_file)

        self.lbl_video_info = QLabel("Resolution: -- | FPS: -- | Frames: --")
        self.lbl_video_info.setStyleSheet(
            "background-color: #12131D; border: 1px solid #2B2F44; border-radius: 5px; padding: 6px; font-size: 11px; color: #A5B4FC;"
        )
        gv_layout.addWidget(self.lbl_video_info)

        # Frame limit for quick demo
        h_limit = QHBoxLayout()
        self.chk_limit = QCheckBox("Limit Frames (Fast Demo):")
        self.chk_limit.setChecked(True)
        self.chk_limit.setToolTip("Limits the number of processed frames for fast 1-second presentation demos.")
        self.chk_limit.toggled.connect(lambda c: self.spin_max_frames.setEnabled(c))
        h_limit.addWidget(self.chk_limit)

        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(10, 50000)
        self.spin_max_frames.setValue(150)
        self.spin_max_frames.setSuffix(" frames")
        h_limit.addWidget(self.spin_max_frames)
        gv_layout.addLayout(h_limit)

        side_layout.addWidget(grp_video)

        # 2. Parameters Group
        grp_param = QGroupBox("2. Parameters")
        gp_layout = QVBoxLayout(grp_param)
        gp_layout.setSpacing(8)

        # Pos threshold
        self.slider_pos, self.spin_pos = self._create_param_row(
            gp_layout, "Positive Threshold (C_pos):", 0.05, 1.00, 0.40, 0.05
        )
        # Neg threshold
        self.slider_neg, self.spin_neg = self._create_param_row(
            gp_layout, "Negative Threshold (C_neg):", 0.05, 1.00, 0.40, 0.05
        )
        # Accumulation window (ms)
        self.slider_acc, self.spin_acc = self._create_param_row(
            gp_layout, "Accumulation Time (ms):", 0.5, 20.0, 2.0, 0.5, suffix=" ms"
        )
        # Event alpha
        self.slider_alpha, self.spin_alpha = self._create_param_row(
            gp_layout, "Overlay Alpha:", 0.10, 1.00, 0.45, 0.05
        )

        side_layout.addWidget(grp_param)

        # 3. Actions & Status Group
        grp_action = QGroupBox("3. Simulation")
        ga_layout = QVBoxLayout(grp_action)
        ga_layout.setSpacing(6)

        h_act = QHBoxLayout()
        self.btn_start = QPushButton("▶  Start Simulation")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setProperty("class", "PrimaryButton")
        self.btn_start.clicked.connect(self._start_simulation)
        h_act.addWidget(self.btn_start, 2)

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setProperty("class", "DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_simulation)
        h_act.addWidget(self.btn_stop, 1)
        ga_layout.addLayout(h_act)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        ga_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Status: Ready")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #10B981; font-weight: bold;")
        ga_layout.addWidget(self.lbl_status)

        self.btn_open_folder = QPushButton("📁 Open Output Folder")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.setToolTip("Open the timestamped output directory for this simulation in Windows Explorer.")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        ga_layout.addWidget(self.btn_open_folder)

        side_layout.addWidget(grp_action)
        side_layout.addStretch()

        sidebar_scroll.setWidget(sidebar)
        splitter.addWidget(sidebar_scroll)

        # RIGHT DISPLAY AREA
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        # View Mode Selector Bar
        top_view_bar = QHBoxLayout()
        top_view_bar.addWidget(QLabel("Display Mode:"))

        self.btn_view_overlay = QPushButton("🎬 Event Overlay")
        self.btn_view_overlay.setCheckable(True)
        self.btn_view_overlay.setChecked(True)
        self.btn_view_overlay.clicked.connect(lambda: self._switch_view_mode("overlay"))
        top_view_bar.addWidget(self.btn_view_overlay)

        self.btn_view_event = QPushButton("🔴🔵 Event-Only")
        self.btn_view_event.setCheckable(True)
        self.btn_view_event.clicked.connect(lambda: self._switch_view_mode("event_only"))
        top_view_bar.addWidget(self.btn_view_event)

        top_view_bar.addStretch()
        right_layout.addLayout(top_view_bar)

        # Display Canvas
        self.canvas = ImageCanvas(placeholder="Select video and click 'Start Simulation'")
        right_layout.addWidget(self.canvas, 1)

        # Playback Controls Bar
        play_bar = QFrame()
        play_bar.setStyleSheet(
            "background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 6px; padding: 4px 8px;"
        )
        pb_layout = QHBoxLayout(play_bar)
        pb_layout.setContentsMargins(6, 4, 6, 4)
        pb_layout.setSpacing(8)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setFixedWidth(80)
        self.btn_play.clicked.connect(self._toggle_playback)
        pb_layout.addWidget(self.btn_play)

        self.slider_timeline = QSlider(Qt.Orientation.Horizontal)
        self.slider_timeline.setRange(0, 0)
        self.slider_timeline.sliderMoved.connect(self._on_timeline_seek)
        pb_layout.addWidget(self.slider_timeline, 1)

        self.lbl_frame_counter = QLabel("Frame: 0 / 0")
        self.lbl_frame_counter.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #CDD6F4;")
        pb_layout.addWidget(self.lbl_frame_counter)

        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.5x", "1.0x (30fps)", "2.0x"])
        self.combo_speed.setCurrentIndex(1)
        pb_layout.addWidget(self.combo_speed)

        right_layout.addWidget(play_bar)

        # Statistics Summary Bar
        stats_bar = QFrame()
        stats_bar.setStyleSheet(
            "background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 6px; padding: 6px 12px;"
        )
        st_layout = QHBoxLayout(stats_bar)
        st_layout.setContentsMargins(8, 6, 8, 6)

        self.lbl_stat_events = QLabel("Total Events: 0")
        self.lbl_stat_events.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 13px;")
        st_layout.addWidget(self.lbl_stat_events)

        st_layout.addStretch()

        self.lbl_stat_polarity = QLabel("Polarity: ON: 0 (0%) | OFF: 0 (0%)")
        self.lbl_stat_polarity.setStyleSheet("font-size: 12px; color: #CDD6F4;")
        st_layout.addWidget(self.lbl_stat_polarity)

        st_layout.addStretch()

        self.lbl_stat_time = QLabel("Time: 0.00 s (0.0 FPS)")
        self.lbl_stat_time.setStyleSheet("font-size: 12px; color: #A5B4FC;")
        st_layout.addWidget(self.lbl_stat_time)

        right_layout.addWidget(stats_bar)

        right_panel.setMinimumWidth(500)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 800])

        main_layout.addWidget(splitter, 1)

    def _create_param_row(self, layout, label_text, min_val, max_val, default_val, step, suffix=""):
        v_box = QVBoxLayout()
        v_box.setSpacing(2)

        h_box = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 12px; color: #CDD6F4;")
        h_box.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 0.1 else 1)
        spin.setValue(default_val)
        if suffix:
            spin.setSuffix(suffix)
        spin.setFixedWidth(130)
        h_box.addWidget(spin)
        v_box.addLayout(h_box)

        slider = QSlider(Qt.Orientation.Horizontal)
        scale = 100
        slider.setRange(int(min_val * scale), int(max_val * scale))
        slider.setSingleStep(int(step * scale))
        slider.setValue(int(default_val * scale))
        v_box.addWidget(slider)

        def sync_from_slider(v):
            spin.blockSignals(True)
            spin.setValue(v / scale)
            spin.blockSignals(False)

        def sync_from_spin(v):
            slider.blockSignals(True)
            slider.setValue(int(v * scale))
            slider.blockSignals(False)

        slider.valueChanged.connect(sync_from_slider)
        spin.valueChanged.connect(sync_from_spin)

        layout.addLayout(v_box)
        return slider, spin

    def _populate_sample_videos(self):
        self.combo_samples.clear()
        input_dir = config.INPUT_DIR
        if input_dir.is_dir():
            videos = sorted(
                p for p in input_dir.iterdir()
                if p.is_file() and p.suffix.lower() in config.SUPPORTED_VIDEO_EXTENSIONS
            )
            for v in videos:
                self.combo_samples.addItem(v.name, userData=str(v))
        if self.combo_samples.count() > 0:
            self.combo_samples.setCurrentIndex(0)
            self._on_sample_selected(0)

    def _on_sample_selected(self, index):
        if index >= 0:
            p = self.combo_samples.itemData(index)
            if p:
                self.txt_video_path.setText(p)

    def _browse_video(self):
        filters = "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*.*)"
        start_dir = str(config.INPUT_DIR) if config.INPUT_DIR.is_dir() else ""
        selected, _ = QFileDialog.getOpenFileName(self, "Select Input Video", start_dir, filters)
        if selected:
            self.txt_video_path.setText(selected)

    def _on_video_path_changed(self, text):
        p = Path(text.strip())
        if p.is_file():
            self._current_video_path = p
            try:
                reader = VideoReader(p)
                info = reader.get_info()
                reader.release()
                size_str = format_bytes(p.stat().st_size)
                self.lbl_video_info.setText(
                    f"Resolution: {info['width']}x{info['height']} | "
                    f"FPS: {info['fps']:.1f} | "
                    f"Frames: {info['frame_count']} | Size: {size_str}"
                )
            except Exception as e:
                self.lbl_video_info.setText(f"Error reading video: {e}")
        else:
            self._current_video_path = None
            self.lbl_video_info.setText("Resolution: -- | FPS: -- | Frames: --")

    def _start_simulation(self):
        if not self._current_video_path or not self._current_video_path.is_file():
            QMessageBox.warning(self, "Warning", "Please select a valid input video file first.")
            return

        self._release_playback()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Status: Running simulation...")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #3B82F6; font-weight: bold;")

        max_frames = self.spin_max_frames.value() if self.chk_limit.isChecked() else None
        params = {
            "contrast_threshold_pos": self.spin_pos.value(),
            "contrast_threshold_neg": self.spin_neg.value(),
            "accumulation_time": self.spin_acc.value() / 1000.0,
            "overlay_event_alpha": self.spin_alpha.value(),
        }

        self._worker = SimulationWorker(
            video_path=self._current_video_path,
            params=params,
            max_frames=max_frames,
        )
        self._worker.preview_sig.connect(self._on_live_preview)
        self._worker.progress_sig.connect(self._on_progress_update)
        self._worker.finished_sig.connect(self._on_simulation_finished)
        self._worker.cancelled_sig.connect(self._on_simulation_stopped)
        self._worker.error_sig.connect(self._on_simulation_error)
        self._worker.start()

    def _stop_simulation(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.lbl_status.setText("Status: Stopping...")

    def _on_live_preview(self, orig_frame, event_canvas, overlay_frame, timestamp, frame_idx):
        # Update canvas live with overlay or event frame
        frame_to_show = overlay_frame if overlay_frame is not None else event_canvas
        if frame_to_show is not None:
            self.canvas.set_frame(frame_to_show)

    def _on_progress_update(self, processed, total, events, fps, pos_events, neg_events, h5_bytes):
        pct = int(processed / total * 100) if total > 0 else 0
        self.progress_bar.setValue(min(100, pct))
        self.lbl_status.setText(f"Status: Processing frame {processed}/{total} ({pct}%)")

        self.lbl_stat_events.setText(f"Total Events: {events:,}")
        tot_pol = pos_events + neg_events
        pos_p = (pos_events / tot_pol * 100) if tot_pol > 0 else 0
        neg_p = (neg_events / tot_pol * 100) if tot_pol > 0 else 0
        self.lbl_stat_polarity.setText(
            f"Polarity: <font color='#EF4444'>ON: {pos_events:,} ({pos_p:.1f}%)</font> | "
            f"<font color='#3B82F6'>OFF: {neg_events:,} ({neg_p:.1f}%)</font>"
        )
        self.lbl_stat_time.setText(f"Speed: {fps:.1f} FPS | HDF5: {format_bytes(h5_bytes)}")

    def _on_simulation_finished(self, result):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Status: Completed successfully!")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #10B981; font-weight: bold;")

        self._last_result = result
        self.btn_open_folder.setEnabled(True)

        # Update final stats
        tot_time = result["timings"].get("total_seconds", 0.0)
        ev_rate = (result["event_count"] / tot_time / 1e6) if tot_time > 0 else 0.0
        self.lbl_stat_time.setText(f"Total Time: {tot_time:.2f} s ({ev_rate:.2f} M events/s)")

        # Load video into player
        self._load_playback_video("overlay")

    def _on_simulation_stopped(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Status: Stopped by user.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #F59E0B; font-weight: bold;")

    def _on_simulation_error(self, err_msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Status: Simulation failed.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #EF4444; font-weight: bold;")
        QMessageBox.critical(self, "Simulation Error", f"An error occurred during simulation:\n{err_msg}")

    def _release_playback(self):
        """Stop playback and explicitly release any open video file handles."""
        self._stop_playback()
        if self._current_cap is not None:
            self._current_cap.release()
            self._current_cap = None

    # View & Playback Methods
    def _switch_view_mode(self, mode):
        self._release_playback()
        self.btn_view_overlay.setChecked(mode == "overlay")
        self.btn_view_event.setChecked(mode == "event_only")

        if not self._last_result:
            return

        self.btn_play.setEnabled(True)
        self.slider_timeline.setEnabled(True)
        self._load_playback_video(mode)

    def _load_playback_video(self, video_type):
        if not self._last_result:
            return
        self._release_playback()

        video_path = self._last_result["output_paths"].get(video_type)
        if not video_path or not Path(video_path).is_file():
            return

        self._current_cap = cv2.VideoCapture(str(video_path))
        self._current_cap_type = video_type
        if self._current_cap.isOpened():
            self._total_playback_frames = int(self._current_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.slider_timeline.setRange(0, max(0, self._total_playback_frames - 1))
            self._seek_playback_frame(0)

    def _seek_playback_frame(self, frame_idx):
        if not self._current_cap or not self._current_cap.isOpened():
            return
        frame_idx = max(0, min(frame_idx, self._total_playback_frames - 1))
        self._current_frame_idx = frame_idx
        self._current_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self._current_cap.read()
        if ret and frame is not None:
            self.canvas.set_frame(frame)

        self.slider_timeline.blockSignals(True)
        self.slider_timeline.setValue(frame_idx)
        self.slider_timeline.blockSignals(False)
        self.lbl_frame_counter.setText(f"Frame: {frame_idx + 1} / {self._total_playback_frames}")

    def _toggle_playback(self):
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if not self._current_cap or self._total_playback_frames <= 0:
            return
        self._is_playing = True
        self.btn_play.setText("⏸ Pause")

        speed_idx = self.combo_speed.currentIndex()
        mult = 0.5 if speed_idx == 0 else (2.0 if speed_idx == 2 else 1.0)
        interval = max(10, int(1000 / (30.0 * mult)))
        self._play_timer.start(interval)

    def _stop_playback(self):
        self._is_playing = False
        self.btn_play.setText("▶ Play")
        self._play_timer.stop()

    def _on_play_step(self):
        next_frame = self._current_frame_idx + 1
        if next_frame >= self._total_playback_frames:
            next_frame = 0  # Loop
        self._seek_playback_frame(next_frame)

    def _on_timeline_seek(self, value):
        self._stop_playback()
        self._seek_playback_frame(value)

    def _open_output_folder(self):
        if not self._last_result or "output_directory" not in self._last_result:
            return
        out_dir = Path(self._last_result["output_directory"])
        if out_dir.is_dir():
            if os.name == "nt":
                os.startfile(str(out_dir))

    def closeEvent(self, event):
        self._stop_playback()
        if self._current_cap:
            self._current_cap.release()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(1000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EE5110 Event Camera Simulator")
    app.setStyleSheet(MODERN_DARK_STYLESHEET)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

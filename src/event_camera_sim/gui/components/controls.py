"""Sidebar control panel for video selection, parameter adjustments, and presets."""

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSlider,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QFrame,
)

from ... import config
from ...video import VideoReader


def format_bytes(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


class ParameterControls(QWidget):
    """Parameter adjustment controls and input video selector."""

    simulation_requested = Signal(dict)
    stop_requested = Signal()
    video_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_video_path = None
        self._video_info = None
        self._setup_ui()
        self._populate_input_videos()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Video input card
        video_group = QGroupBox("视频输入源 (Input Video)")
        v_layout = QVBoxLayout(video_group)
        v_layout.setSpacing(8)

        # Preset selector combo
        h_combo = QHBoxLayout()
        h_combo.addWidget(QLabel("内置素材:"))
        self.combo_presets = QComboBox()
        self.combo_presets.currentIndexChanged.connect(self._on_preset_video_changed)
        h_combo.addWidget(self.combo_presets, 1)
        v_layout.addLayout(h_combo)

        # Browse file row
        h_file = QHBoxLayout()
        self.txt_video_path = QLineEdit()
        self.txt_video_path.setPlaceholderText("选择或输入视频文件路径...")
        self.txt_video_path.textChanged.connect(self._on_path_edited)
        h_file.addWidget(self.txt_video_path, 1)

        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._browse_file)
        h_file.addWidget(self.btn_browse)
        v_layout.addLayout(h_file)

        # Video info pill card
        self.info_card = QFrame()
        self.info_card.setObjectName("InfoCard")
        self.info_card.setStyleSheet(
            "#InfoCard { background-color: #12131D; border: 1px solid #2B2F44; border-radius: 6px; padding: 6px; }"
        )
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(6, 6, 6, 6)

        self.lbl_info_res = QLabel("分辨率: -- x -- | 原生 FPS: --")
        self.lbl_info_res.setStyleSheet("font-size: 11px; color: #A5B4FC; font-weight: bold;")
        self.lbl_info_frames = QLabel("帧数: -- | 物理时长: -- | 大小: --")
        self.lbl_info_frames.setStyleSheet("font-size: 11px; color: #9DA2B8;")
        info_layout.addWidget(self.lbl_info_res)
        info_layout.addWidget(self.lbl_info_frames)
        v_layout.addWidget(self.info_card)

        # Frame limit row (PPT demo optimization)
        limit_box = QHBoxLayout()
        self.chk_limit_frames = QCheckBox("限制帧数 (演示推荐)")
        self.chk_limit_frames.setChecked(True)
        self.chk_limit_frames.setToolTip("限制处理的最大帧数，适合现场 PPT 答辩快速演示秒级出结果！")
        self.chk_limit_frames.toggled.connect(self._on_limit_toggled)
        limit_box.addWidget(self.chk_limit_frames)

        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(10, 50000)
        self.spin_max_frames.setValue(150)
        self.spin_max_frames.setSuffix(" 帧")
        limit_box.addWidget(self.spin_max_frames, 1)
        v_layout.addLayout(limit_box)

        # Quick chips for frame limits
        chip_layout = QHBoxLayout()
        for count in (100, 150, 300, 500):
            btn = QPushButton(f"{count}帧")
            btn.setProperty("class", "SecondaryButton")
            btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn.clicked.connect(lambda _, c=count: self._set_frame_limit(c))
            chip_layout.addWidget(btn)
        btn_all = QPushButton("全部")
        btn_all.setProperty("class", "SecondaryButton")
        btn_all.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_all.clicked.connect(lambda: self.chk_limit_frames.setChecked(False))
        chip_layout.addWidget(btn_all)
        v_layout.addLayout(chip_layout)

        layout.addWidget(video_group)

        # 2. Parameters card
        param_group = QGroupBox("模拟参数配置 (Simulation Parameters)")
        p_layout = QVBoxLayout(param_group)
        p_layout.setSpacing(10)

        # Preset parameter combo
        h_param_preset = QHBoxLayout()
        h_param_preset.addWidget(QLabel("参数预设:"))
        self.combo_param_presets = QComboBox()
        self.combo_param_presets.addItems([
            "默认平衡 (Pos 0.4 / Neg 0.4 / Acc 2ms)",
            "高灵敏度 (Pos 0.1 / Neg 0.1 / Acc 2ms)",
            "低噪点 (Pos 0.8 / Neg 0.8 / Acc 2ms)",
            "非对称极性 (Pos 0.1 / Neg 0.4 / Acc 2ms)",
        ])
        self.combo_param_presets.currentIndexChanged.connect(self._on_param_preset_changed)
        h_param_preset.addWidget(self.combo_param_presets, 1)
        p_layout.addLayout(h_param_preset)

        # Positive threshold C_pos
        self.slider_pos, self.spin_pos = self._create_slider_spin_row(
            p_layout,
            label="正对比度阈值 (C_pos):",
            min_val=0.05,
            max_val=1.00,
            default_val=0.40,
            step=0.05,
            decimals=2,
            tooltip="亮度相对参考值上升触发 ON 事件的对数增量阈值",
        )

        # Negative threshold C_neg
        self.slider_neg, self.spin_neg = self._create_slider_spin_row(
            p_layout,
            label="负对比度阈值 (C_neg):",
            min_val=0.05,
            max_val=1.00,
            default_val=0.40,
            step=0.05,
            decimals=2,
            tooltip="亮度相对参考值下降触发 OFF 事件的对数减量阈值",
        )

        # Accumulation time T_acc (ms)
        self.slider_acc, self.spin_acc = self._create_slider_spin_row(
            p_layout,
            label="累积时间窗口 (T_acc):",
            min_val=0.5,
            max_val=20.0,
            default_val=2.0,
            step=0.5,
            decimals=1,
            suffix=" ms",
            tooltip="每个叠加帧中聚合显示的事件物理时间窗口（毫秒）",
        )

        # Alpha
        self.slider_alpha, self.spin_alpha = self._create_slider_spin_row(
            p_layout,
            label="事件叠加透明度 (Alpha):",
            min_val=0.10,
            max_val=1.00,
            default_val=0.45,
            step=0.05,
            decimals=2,
            tooltip="叠加视频中事件点的透明度 (0.1~1.0)",
        )

        # Advanced options group (foldable)
        self.adv_group = QGroupBox("高级配置 (Advanced Settings)")
        self.adv_group.setCheckable(True)
        self.adv_group.setChecked(False)
        adv_layout = QVBoxLayout(self.adv_group)
        adv_layout.setSpacing(6)

        # Epsilon
        h_eps = QHBoxLayout()
        h_eps.addWidget(QLabel("Epsilon (避免log0):"))
        self.spin_eps = QDoubleSpinBox()
        self.spin_eps.setRange(1e-5, 1e-1)
        self.spin_eps.setDecimals(5)
        self.spin_eps.setValue(0.001)
        h_eps.addWidget(self.spin_eps)
        adv_layout.addLayout(h_eps)

        # Timestamp resolution
        h_ts = QHBoxLayout()
        h_ts.addWidget(QLabel("时间戳分辨率 (s):"))
        self.spin_ts = QDoubleSpinBox()
        self.spin_ts.setRange(1e-7, 1e-3)
        self.spin_ts.setDecimals(7)
        self.spin_ts.setValue(1e-6)
        h_ts.addWidget(self.spin_ts)
        adv_layout.addLayout(h_ts)

        # Snapshot start & duration
        h_snap = QHBoxLayout()
        h_snap.addWidget(QLabel("快照起始/时长(s):"))
        self.spin_snap_start = QDoubleSpinBox()
        self.spin_snap_start.setRange(0.0, 100.0)
        self.spin_snap_start.setValue(0.3)
        self.spin_snap_start.setDecimals(3)
        h_snap.addWidget(self.spin_snap_start)

        self.spin_snap_dur = QDoubleSpinBox()
        self.spin_snap_dur.setRange(0.001, 1.0)
        self.spin_snap_dur.setValue(0.005)
        self.spin_snap_dur.setDecimals(4)
        h_snap.addWidget(self.spin_snap_dur)
        adv_layout.addLayout(h_snap)

        p_layout.addWidget(self.adv_group)
        layout.addWidget(param_group)

        # 3. Execution action buttons
        act_box = QVBoxLayout()
        act_box.setSpacing(8)

        self.btn_start = QPushButton("▶ 开始模拟 (Start Simulation)")
        self.btn_start.setProperty("class", "PrimaryButton")
        self.btn_start.clicked.connect(self._on_start_clicked)
        act_box.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 终止/停止 (Stop)")
        self.btn_stop.setProperty("class", "DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        act_box.addWidget(self.btn_stop)

        layout.addLayout(act_box)
        layout.addStretch()

    def _create_slider_spin_row(
        self,
        parent_layout,
        label,
        min_val,
        max_val,
        default_val,
        step=0.05,
        decimals=2,
        suffix="",
        tooltip="",
    ):
        v_box = QVBoxLayout()
        v_box.setSpacing(2)

        h_header = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #CDD6F4; font-weight: 500;")
        if tooltip:
            lbl.setToolTip(tooltip)
        h_header.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setValue(default_val)
        if suffix:
            spin.setSuffix(suffix)
        spin.setFixedWidth(85)
        if tooltip:
            spin.setToolTip(tooltip)
        h_header.addWidget(spin)
        v_box.addLayout(h_header)

        slider = QSlider(Qt.Orientation.Horizontal)
        # Convert float to int scale (x 1000)
        scale = 1000
        slider.setRange(int(min_val * scale), int(max_val * scale))
        slider.setSingleStep(int(step * scale))
        slider.setValue(int(default_val * scale))
        v_box.addWidget(slider)

        # Two-way sync
        def on_slider(val):
            spin.blockSignals(True)
            spin.setValue(val / scale)
            spin.blockSignals(False)

        def on_spin(val):
            slider.blockSignals(True)
            slider.setValue(int(val * scale))
            slider.blockSignals(False)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)

        parent_layout.addLayout(v_box)
        return slider, spin

    def _populate_input_videos(self):
        input_dir = config.INPUT_DIR
        self.combo_presets.clear()
        if input_dir.is_dir():
            videos = sorted(
                path for path in input_dir.iterdir()
                if path.is_file() and path.suffix.lower() in config.SUPPORTED_VIDEO_EXTENSIONS
            )
            for v in videos:
                self.combo_presets.addItem(v.name, userData=str(v))
        if self.combo_presets.count() > 0:
            self.combo_presets.setCurrentIndex(0)
            self._on_preset_video_changed(0)

    def _on_preset_video_changed(self, index):
        if index >= 0:
            path_str = self.combo_presets.itemData(index)
            if path_str:
                self.txt_video_path.setText(path_str)

    def _browse_file(self):
        filters = "视频文件 (*.mp4 *.avi *.mov *.mkv *.webm);;所有文件 (*.*)"
        start_dir = str(config.INPUT_DIR) if config.INPUT_DIR.is_dir() else ""
        selected, _ = QFileDialog.getOpenFileName(self, "选择输入视频文件", start_dir, filters)
        if selected:
            self.txt_video_path.setText(selected)

    def _on_path_edited(self, text):
        p = Path(text.strip())
        if p.is_file():
            self._current_video_path = p
            self._load_video_info(p)
            self.video_selected.emit(str(p))
        else:
            self._current_video_path = None
            self.lbl_info_res.setText("分辨率: 未知 | 原生 FPS: --")
            self.lbl_info_frames.setText("文件不存在或未选择")

    def _load_video_info(self, path):
        try:
            reader = VideoReader(path)
            info = reader.get_info()
            reader.release()
            self._video_info = info
            size_str = format_bytes(path.stat().st_size)

            fps_warning = " (⚠️低于120FPS)" if info['fps'] < config.LOW_FPS_WARNING else ""
            self.lbl_info_res.setText(f"分辨率: {info['width']} x {info['height']} | 原生 FPS: {info['fps']:.1f}{fps_warning}")
            self.lbl_info_frames.setText(
                f"帧数: {info['frame_count']} 帧 | 物理时长: {info['duration']:.3f} s | 大小: {size_str}"
            )
        except Exception as exc:
            self.lbl_info_res.setText("无法读取视频元数据")
            self.lbl_info_frames.setText(str(exc))

    def _on_limit_toggled(self, checked):
        self.spin_max_frames.setEnabled(checked)

    def _set_frame_limit(self, count):
        self.chk_limit_frames.setChecked(True)
        self.spin_max_frames.setValue(count)

    def _on_param_preset_changed(self, index):
        if index == 0:  # Default
            self.spin_pos.setValue(0.40)
            self.spin_neg.setValue(0.40)
            self.spin_acc.setValue(2.0)
        elif index == 1:  # High Sensitivity
            self.spin_pos.setValue(0.10)
            self.spin_neg.setValue(0.10)
            self.spin_acc.setValue(2.0)
        elif index == 2:  # Low Noise
            self.spin_pos.setValue(0.80)
            self.spin_neg.setValue(0.80)
            self.spin_acc.setValue(2.0)
        elif index == 3:  # Asymmetric
            self.spin_pos.setValue(0.10)
            self.spin_neg.setValue(0.40)
            self.spin_acc.setValue(2.0)

    def get_simulation_payload(self):
        if not self._current_video_path or not self._current_video_path.is_file():
            return None

        max_frames = self.spin_max_frames.value() if self.chk_limit_frames.isChecked() else None

        params = {
            "contrast_threshold_pos": self.spin_pos.value(),
            "contrast_threshold_neg": self.spin_neg.value(),
            "accumulation_time": self.spin_acc.value() / 1000.0,  # convert ms to seconds
            "overlay_event_alpha": self.spin_alpha.value(),
            "epsilon": self.spin_eps.value(),
            "timestamp_resolution": self.spin_ts.value(),
            "snapshot_start_time": self.spin_snap_start.value(),
            "snapshot_duration": self.spin_snap_dur.value(),
        }

        return {
            "video_path": str(self._current_video_path),
            "params": params,
            "max_frames": max_frames,
        }

    def _on_start_clicked(self):
        payload = self.get_simulation_payload()
        if payload:
            self.simulation_requested.emit(payload)

    def set_running_state(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.txt_video_path.setEnabled(not running)
        self.btn_browse.setEnabled(not running)
        self.combo_presets.setEnabled(not running)

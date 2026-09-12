"""Real-time metrics dashboard, status pill, and execution logs."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QTextEdit,
    QPushButton,
)

from .controls import format_bytes


class RatioBar(QWidget):
    """Visual dual-color proportional bar showing ON (Red) vs OFF (Blue) events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pos_ratio = 0.5
        self.setFixedHeight(8)

    def set_counts(self, pos_count, neg_count):
        total = pos_count + neg_count
        if total > 0:
            self.pos_ratio = pos_count / total
        else:
            self.pos_ratio = 0.5
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#242738"))
        painter.drawRoundedRect(rect, 4, 4)

        if self.pos_ratio <= 0 and self.pos_ratio >= 1:
            return

        w = rect.width()
        pos_w = int(w * self.pos_ratio)
        neg_w = w - pos_w

        # Draw Positive (Red)
        if pos_w > 0:
            painter.setBrush(QColor("#EF4444"))
            painter.drawRoundedRect(0, 0, pos_w, rect.height(), 4, 4)

        # Draw Negative (Blue)
        if neg_w > 0:
            painter.setBrush(QColor("#3B82F6"))
            painter.drawRoundedRect(pos_w, 0, neg_w, rect.height(), 4, 4)


class StatCard(QFrame):
    """Reusable modern stat card."""

    def __init__(self, title, initial_value="--", subtext="", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            "#StatCard { background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 8px; padding: 6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #85899D; text-transform: uppercase;")
        layout.addWidget(self.lbl_title)

        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(self.lbl_value)

        self.lbl_subtext = QLabel(subtext)
        self.lbl_subtext.setStyleSheet("font-size: 11px; color: #9DA2B8;")
        layout.addWidget(self.lbl_subtext)

    def set_data(self, value, subtext=None):
        self.lbl_value.setText(str(value))
        if subtext is not None:
            self.lbl_subtext.setText(str(subtext))


class DashboardWidget(QWidget):
    """Comprehensive real-time dashboard and log viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Status row & Progress bar
        status_box = QHBoxLayout()
        self.lbl_status_pill = QLabel("就绪 (Ready)")
        self.lbl_status_pill.setStyleSheet(
            "background-color: #242738; color: #10B981; font-weight: bold; padding: 4px 12px; border-radius: 12px; font-size: 12px;"
        )
        status_box.addWidget(self.lbl_status_pill)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_box.addWidget(self.progress_bar, 1)

        self.lbl_speed = QLabel("0.0 FPS")
        self.lbl_speed.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #A5B4FC; font-size: 12px;")
        status_box.addWidget(self.lbl_speed)

        layout.addLayout(status_box)

        # Metric cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)

        # Card 1: Total Events
        self.card_events = StatCard("总事件数 (Total Events)", "0", "帧数: 0 / 0")
        cards_layout.addWidget(self.card_events)

        # Card 2: Polarity Distribution
        self.card_polarity = QFrame()
        self.card_polarity.setObjectName("StatCard")
        self.card_polarity.setStyleSheet(
            "#StatCard { background-color: #1A1C28; border: 1px solid #2B2F44; border-radius: 8px; padding: 6px; }"
        )
        pol_layout = QVBoxLayout(self.card_polarity)
        pol_layout.setContentsMargins(10, 8, 10, 8)
        pol_layout.setSpacing(3)

        pol_title = QLabel("极性比例 (ON/OFF Polarity)")
        pol_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #85899D; text-transform: uppercase;")
        pol_layout.addWidget(pol_title)

        self.lbl_pos_neg = QLabel("ON: 0 (0%) | OFF: 0 (0%)")
        self.lbl_pos_neg.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        pol_layout.addWidget(self.lbl_pos_neg)

        self.ratio_bar = RatioBar()
        pol_layout.addWidget(self.ratio_bar)
        cards_layout.addWidget(self.card_polarity)

        # Card 3: Storage Size
        self.card_storage = StatCard("存储占用 (Storage)", "0 B", "HDF5分块压缩")
        cards_layout.addWidget(self.card_storage)

        # Card 4: Processing Time
        self.card_time = StatCard("处理耗时 (Time)", "0.00 s", "事件速率: 0 M/s")
        cards_layout.addWidget(self.card_time)

        layout.addLayout(cards_layout)

        # Collapsible log viewer
        log_header = QHBoxLayout()
        lbl_log = QLabel("运行日志 (Console Log)")
        lbl_log.setStyleSheet("font-size: 11px; font-weight: bold; color: #85899D;")
        log_header.addWidget(lbl_log)
        log_header.addStretch()

        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.setProperty("class", "SecondaryButton")
        self.btn_clear_log.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self.btn_clear_log.clicked.connect(self.clear_log)
        log_header.addWidget(self.btn_clear_log)
        layout.addLayout(log_header)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(80)
        layout.addWidget(self.txt_log)

    def set_status(self, text, color="#10B981", bg="#242738"):
        self.lbl_status_pill.setText(text)
        self.lbl_status_pill.setStyleSheet(
            f"background-color: {bg}; color: {color}; font-weight: bold; padding: 4px 12px; border-radius: 12px; font-size: 12px;"
        )

    def update_progress(self, processed, total, events, fps, pos_events, neg_events, h5_bytes):
        pct = int(processed / total * 100) if total > 0 else 0
        self.progress_bar.setValue(min(100, pct))
        self.lbl_speed.setText(f"{fps:.1f} FPS")

        # Update cards
        self.card_events.set_data(f"{events:,}", f"帧数: {processed} / {total} ({pct}%)")

        tot_pol = pos_events + neg_events
        pos_pct = (pos_events / tot_pol * 100) if tot_pol > 0 else 0
        neg_pct = (neg_events / tot_pol * 100) if tot_pol > 0 else 0
        self.lbl_pos_neg.setText(f"<font color='#EF4444'>ON: {pos_events:,} ({pos_pct:.1f}%)</font>  |  <font color='#3B82F6'>OFF: {neg_events:,} ({neg_pct:.1f}%)</font>")
        self.ratio_bar.set_counts(pos_events, neg_events)

        self.card_storage.set_data(format_bytes(h5_bytes), "LZF分块流式压缩")

    def update_final_result(self, result):
        events = result["event_count"]
        processed = result["processed_frames"]
        timings = result["timings"]
        tot_time = timings.get("total_seconds", 0.0)
        m_rate = (events / tot_time / 1e6) if tot_time > 0 else 0.0

        self.card_events.set_data(f"{events:,}", f"共完成 {processed} 帧")
        self.card_time.set_data(f"{tot_time:.2f} s", f"吞吐: {m_rate:.2f} M events/s")
        self.set_status("已完成 (Completed)", color="#10B981", bg="#064E3B")

    def append_log(self, text):
        self.txt_log.append(text)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def clear_log(self):
        self.txt_log.clear()

    def reset(self):
        self.progress_bar.setValue(0)
        self.lbl_speed.setText("0.0 FPS")
        self.card_events.set_data("0", "帧数: 0 / 0")
        self.lbl_pos_neg.setText("ON: 0 (0%) | OFF: 0 (0%)")
        self.ratio_bar.set_counts(0, 0)
        self.card_storage.set_data("0 B", "LZF分块压缩")
        self.card_time.set_data("0.00 s", "事件速率: 0 M/s")
        self.set_status("正在仿真 (Simulating...)", color="#3B82F6", bg="#1E3A8A")

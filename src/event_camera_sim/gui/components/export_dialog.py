"""Data export toolbar and dialog manager."""

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QMenu,
)


class ExportToolbar(QWidget):
    """Toolbar providing one-click data export and folder opening."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_paths = {}
        self._last_result = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Open directory button
        self.btn_open_folder = QPushButton("📁 打开输出目录 (Open Folder)")
        self.btn_open_folder.setProperty("class", "SecondaryButton")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        layout.addWidget(self.btn_open_folder)

        # Export dropdown button
        self.btn_export_menu = QPushButton("💾 导出数据文件 (Export...) ▾")
        self.btn_export_menu.setProperty("class", "SecondaryButton")
        self.btn_export_menu.setEnabled(False)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1A1C28; border: 1px solid #33374E; color: #F1F2F8; padding: 4px; }"
            "QMenu::item { padding: 6px 20px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: #4F46E5; color: #FFFFFF; }"
        )

        act_h5 = menu.addAction("导出 HDF5 完整事件流 (.h5)")
        act_h5.triggered.connect(lambda: self._export_file("h5", "HDF5文件 (*.h5)"))

        act_csv = menu.addAction("导出 CSV 样例事件列表 (.csv)")
        act_csv.triggered.connect(lambda: self._export_file("csv", "CSV文件 (*.csv)"))

        act_png = menu.addAction("导出静态事件积分快照 (.png)")
        act_png.triggered.connect(lambda: self._export_file("snapshot", "PNG图片 (*.png)"))

        act_overlay = menu.addAction("导出事件叠加演示视频 (.mp4)")
        act_overlay.triggered.connect(lambda: self._export_file("overlay", "MP4视频 (*.mp4)"))

        act_event_only = menu.addAction("导出纯事件相机视频 (.mp4)")
        act_event_only.triggered.connect(lambda: self._export_file("event_only", "MP4视频 (*.mp4)"))

        act_meta = menu.addAction("导出实验元数据报告 (.json)")
        act_meta.triggered.connect(lambda: self._export_file("metadata", "JSON文件 (*.json)"))

        self.btn_export_menu.setMenu(menu)
        layout.addWidget(self.btn_export_menu)

        # Copy summary button
        self.btn_copy_summary = QPushButton("📋 复制 PPT 答辩摘要 (Copy Summary)")
        self.btn_copy_summary.setProperty("class", "SecondaryButton")
        self.btn_copy_summary.setEnabled(False)
        self.btn_copy_summary.clicked.connect(self._copy_summary_to_clipboard)
        layout.addWidget(self.btn_copy_summary)

    def set_result(self, result):
        self._last_result = result
        if result and "output_paths" in result:
            self._output_paths = {k: Path(v) for k, v in result["output_paths"].items()}
            self.btn_open_folder.setEnabled(True)
            self.btn_export_menu.setEnabled(True)
            self.btn_copy_summary.setEnabled(True)

    def _open_output_folder(self):
        if not self._output_paths or "directory" not in self._output_paths:
            return
        target_dir = self._output_paths["directory"]
        if target_dir.is_dir():
            if os.name == "nt":
                os.startfile(str(target_dir))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir)))

    def _export_file(self, key, filter_str):
        if key not in self._output_paths:
            return
        source_path = self._output_paths[key]
        if not source_path.is_file():
            QMessageBox.warning(self, "导出提示", f"源文件不存在: {source_path.name}")
            return

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出 {source_path.name}",
            source_path.name,
            filter_str,
        )
        if dest_path:
            try:
                shutil.copy2(str(source_path), dest_path)
                QMessageBox.information(self, "导出成功", f"文件已保存至:\n{dest_path}")
            except Exception as exc:
                QMessageBox.critical(self, "导出失败", f"无法写入文件:\n{exc}")

    def _copy_summary_to_clipboard(self):
        if not self._last_result:
            return
        res = self._last_result
        meta = res.get("metadata", {})
        vid = meta.get("video", {})
        params = meta.get("parameters", {})
        timings = res.get("timings", {})
        tot_time = timings.get("total_seconds", 0.0)

        events = res.get("event_count", 0)
        pos = res.get("pos_events", 0)
        neg = res.get("neg_events", 0)
        tot_pol = pos + neg
        pos_pct = (pos / tot_pol * 100) if tot_pol > 0 else 0
        neg_pct = (neg / tot_pol * 100) if tot_pol > 0 else 0

        summary = (
            f"【EE5110 事件相机模拟器实验数据摘要】\n"
            f"• 输入视频: {meta.get('input_video', '未知')}\n"
            f"• 原始分辨率与帧率: {vid.get('width', '-')}x{vid.get('height', '-')}, {vid.get('fps', 0):.1f} FPS\n"
            f"• 处理帧数: {res.get('processed_frames', 0)} 帧 (物理时长 {vid.get('duration', 0):.3f}s)\n"
            f"• 参数配置: C_pos = {params.get('contrast_threshold_pos', 0.4)}, C_neg = {params.get('contrast_threshold_neg', 0.4)}, "
            f"T_acc = {params.get('accumulation_time', 0.002)*1000:.1f}ms\n"
            f"• 事件总数: {events:,} 个\n"
            f"• 极性分布: ON = {pos:,} ({pos_pct:.1f}%), OFF = {neg:,} ({neg_pct:.1f}%)\n"
            f"• 仿真耗时: {tot_time:.2f} 秒 (事件速率: {(events/tot_time/1e6) if tot_time>0 else 0:.2f} M events/s)\n"
            f"• 输出目录: {res.get('output_directory', '')}"
        )

        QGuiApplication.clipboard().setText(summary)
        QMessageBox.information(self, "摘要复制成功", "已成功将实验统计摘要复制到系统剪贴板！\n可以直接粘贴 (Ctrl+V) 到 PPT 或报告中。")

"""Modern, polished dark theme and styling for EE5110 Event Camera Simulator GUI."""

# Color palette definitions
DARK_BG_MAIN = "#12131C"
DARK_BG_CARD = "#1A1C28"
DARK_BG_INPUT = "#242738"
DARK_BG_HOVER = "#2D3146"
BORDER_COLOR = "#33374E"
BORDER_FOCUS = "#4F46E5"

TEXT_PRIMARY = "#F1F2F8"
TEXT_SECONDARY = "#9DA2B8"
TEXT_MUTED = "#6B728D"

COLOR_ON = "#EF4444"     # Red for Positive polarity (+1)
COLOR_OFF = "#3B82F6"    # Blue for Negative polarity (-1)
COLOR_SUCCESS = "#10B981" # Green
COLOR_WARNING = "#F59E0B" # Amber
COLOR_ACCENT = "#6366F1"  # Indigo Accent

MODERN_DARK_STYLESHEET = """
QMainWindow {
    background-color: #12131C;
    color: #F1F2F8;
    font-family: "Segoe UI", "Microsoft YaHei", -apple-system, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F1F2F8;
    font-family: "Segoe UI", "Microsoft YaHei", -apple-system, sans-serif;
}

/* Splitter */
QSplitter::handle {
    background-color: #2B2F44;
}
QSplitter::handle:horizontal {
    width: 6px;
    background-color: #2B2F44;
    border-radius: 3px;
}
QSplitter::handle:horizontal:hover {
    background-color: #6366F1;
}

/* Scroll Area & Bars */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #12131C;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #33374E;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #4F46E5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #12131C;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #33374E;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #4F46E5;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Card Panels */
QFrame.CardPanel {
    background-color: #1A1C28;
    border: 1px solid #2B2F44;
    border-radius: 10px;
}

QGroupBox {
    background-color: #1A1C28;
    border: 1px solid #2B2F44;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 16px;
    padding-bottom: 12px;
    padding-left: 12px;
    padding-right: 12px;
    font-weight: 600;
    color: #F1F2F8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 2px;
    padding: 2px 8px;
    background-color: #242738;
    border-radius: 5px;
    color: #A5B4FC;
    font-size: 12px;
    font-weight: bold;
}

/* Push Buttons */
QPushButton {
    background-color: #242738;
    border: 1px solid #33374E;
    border-radius: 6px;
    color: #F1F2F8;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #2E334A;
    border-color: #4F46E5;
}
QPushButton:pressed {
    background-color: #1D2030;
}
QPushButton:disabled {
    background-color: #161722;
    border-color: #232534;
    color: #55596D;
}

/* Primary Action Button */
QPushButton#btn_start,
QPushButton[class="PrimaryButton"] {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #6366F1);
    border: 1px solid #6366F1;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 6px;
}
QPushButton#btn_start:hover,
QPushButton[class="PrimaryButton"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338CA, stop:1 #4F46E5);
    border-color: #818CF8;
}
QPushButton#btn_start:pressed,
QPushButton[class="PrimaryButton"]:pressed {
    background-color: #3730A3;
}
QPushButton#btn_start:disabled,
QPushButton[class="PrimaryButton"]:disabled {
    background-color: #1A1C28;
    border-color: #2B2F44;
    color: #55596D;
}

/* Stop Button */
QPushButton#btn_stop,
QPushButton[class="DangerButton"] {
    background-color: #DC2626;
    border: 1px solid #EF4444;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 6px;
}
QPushButton#btn_stop:hover,
QPushButton[class="DangerButton"]:hover {
    background-color: #B91C1C;
}
QPushButton#btn_stop:disabled,
QPushButton[class="DangerButton"]:disabled {
    background-color: #1A1C28;
    border-color: #2B2F44;
    color: #55596D;
}

/* Secondary Action Button */
QPushButton.SecondaryButton {
    background-color: #1E293B;
    border: 1px solid #334155;
    color: #94A3B8;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 6px;
}
QPushButton.SecondaryButton:hover {
    background-color: #334155;
    color: #F8FAFC;
}

/* Inputs & Combos */
QLineEdit {
    background-color: #242738;
    border: 1px solid #33374E;
    border-radius: 6px;
    color: #F1F2F8;
    padding: 6px 10px;
    selection-background-color: #4F46E5;
}
QLineEdit:focus {
    border: 1px solid #6366F1;
    background-color: #262A3E;
}

QComboBox {
    background-color: #242738;
    border: 1px solid #33374E;
    border-radius: 6px;
    color: #F1F2F8;
    padding: 6px 12px;
    min-height: 18px;
}
QComboBox:hover {
    border-color: #4F46E5;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #1A1C28;
    border: 1px solid #33374E;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
    color: #F1F2F8;
    outline: none;
    padding: 4px;
}

QSpinBox, QDoubleSpinBox {
    background-color: #242738;
    border: 1px solid #33374E;
    border-radius: 6px;
    color: #F1F2F8;
    padding-left: 6px;
    padding-right: 46px; /* Crucial: reserves space so inner QLineEdit never overlaps up/down buttons */
    padding-top: 4px;
    padding-bottom: 4px;
    min-height: 20px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #6366F1;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #242738;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #6366F1);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #F1F2F8;
    border: 2px solid #6366F1;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #FFFFFF;
    border-color: #818CF8;
    transform: scale(1.1);
}

/* Progress Bar */
QProgressBar {
    background-color: #242738;
    border: 1px solid #33374E;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 11px;
    height: 18px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:0.5 #3B82F6, stop:1 #10B981);
    border-radius: 5px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #2B2F44;
    background-color: #161823;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #1A1C28;
    border: 1px solid #2B2F44;
    border-bottom: none;
    color: #9DA2B8;
    padding: 8px 16px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #161823;
    color: #A5B4FC;
    border-bottom: 2px solid #6366F1;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #242738;
    color: #F1F2F8;
}

/* Text Edit / Console */
QTextEdit, QPlainTextEdit {
    background-color: #0F1017;
    border: 1px solid #2B2F44;
    border-radius: 6px;
    color: #C6C8D1;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}

/* Labels */
QLabel {
    color: #F1F2F8;
}

QLabel.TitleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel.SubtitleLabel {
    font-size: 12px;
    color: #9DA2B8;
}

QLabel.SectionHeader {
    font-size: 13px;
    font-weight: bold;
    color: #A5B4FC;
    margin-bottom: 4px;
}

QLabel.StatValue {
    font-size: 20px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel.StatLabel {
    font-size: 11px;
    font-weight: 500;
    color: #85899D;
    text-transform: uppercase;
}

/* CheckBox */
QCheckBox {
    color: #F1F2F8;
    spacing: 8px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #33374E;
    border-radius: 4px;
    background-color: #242738;
}
QCheckBox::indicator:checked {
    background-color: #4F46E5;
    border-color: #6366F1;
    image: none;
}
QCheckBox::indicator:hover {
    border-color: #6366F1;
}

/* Tooltips */
QToolTip {
    background-color: #1E2030;
    border: 1px solid #3E435E;
    color: #F1F2F8;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}
"""

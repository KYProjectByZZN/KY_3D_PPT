"""Steel-blue desktop theme adapted from the project's DCE reference UI."""

APP_QSS = """
QMainWindow, QWidget#rootWidget {
    background: #eef1f5;
    color: #1f2937;
}
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}
QFrame#topBar {
    background: #ffffff;
    border-bottom: 1px solid #dbe1e8;
}
QLabel#brandBadge {
    background: #2563eb;
    color: #ffffff;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 800;
    padding: 7px 9px;
}
QLabel#brandTitle {
    color: #111827;
    font-size: 17px;
    font-weight: 700;
}
QLabel#brandSubtitle, QLabel#mutedLabel {
    color: #64748b;
    font-size: 11px;
}
QFrame#leftPanel, QFrame#rightPanel, QFrame#previewPanel {
    background: #eef1f5;
    border: none;
}
QFrame#rightPanel {
    border-left: 1px solid #d5dce5;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #dce2ea;
    border-radius: 12px;
    margin-top: 16px;
    padding: 18px 14px 13px 14px;
    color: #374151;
    font-size: 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 7px;
    color: #64748b;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: #ffffff;
    border: 1px solid #d7dee8;
    border-radius: 8px;
    color: #111827;
    padding: 7px 10px;
    selection-background-color: #dbeafe;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 2px solid #3b82f6;
    padding: 6px 9px;
}
QLineEdit[readOnly="true"] {
    background: #f8fafc;
    color: #64748b;
}
QPushButton {
    background: #ffffff;
    color: #374151;
    border: 1px solid #cfd7e2;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f8fafc;
    border-color: #94a3b8;
    color: #111827;
}
QPushButton:pressed {
    background: #eef2f7;
}
QPushButton:disabled {
    background: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}
QPushButton#primaryButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    padding: 8px 18px;
    font-weight: 700;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton#successButton {
    background: #0f9f6e;
    color: #ffffff;
    border: none;
    padding: 9px 20px;
    font-weight: 700;
}
QPushButton#successButton:hover {
    background: #0b815a;
}
QTabWidget::pane {
    border: 1px solid #dce2ea;
    border-radius: 11px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #64748b;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 11px 18px;
    font-weight: 600;
}
QTabBar::tab:hover {
    color: #334155;
    background: #f8fafc;
}
QTabBar::tab:selected {
    color: #2563eb;
    border-bottom: 3px solid #2563eb;
}
QTableWidget, QListWidget, QTreeWidget {
    background: #ffffff;
    border: 1px solid #dce2ea;
    border-radius: 9px;
    alternate-background-color: #f8fafc;
    gridline-color: #edf1f5;
    selection-background-color: #e8f1ff;
    selection-color: #1d4ed8;
    outline: none;
}
QTableWidget::item, QListWidget::item {
    padding: 7px 9px;
}
QTreeWidget#moduleTree::item {
    min-height: 28px;
    padding: 4px 7px;
    border-bottom: 1px solid #eef2f6;
}
QTreeWidget#moduleTree::item:selected {
    background: #e8f1ff;
    color: #1d4ed8;
}
QListWidget#moduleList::item, QListWidget#structureList::item {
    margin: 3px 5px;
    border: 1px solid #e3e8ef;
    border-radius: 8px;
    background: #ffffff;
    padding: 10px;
}
QListWidget#moduleList::item:selected, QListWidget#structureList::item:selected {
    background: #eff6ff;
    border-color: #93c5fd;
}
QHeaderView::section {
    background: #f4f6f9;
    color: #475569;
    border: none;
    border-bottom: 1px solid #dce2ea;
    border-right: 1px solid #e8edf3;
    padding: 8px 9px;
    font-size: 11px;
    font-weight: 700;
}
QSplitter::handle {
    background: #d3dae3;
    width: 4px;
    margin: 0 2px;
}
QSplitter::handle:hover {
    background: #3b82f6;
}
QStatusBar {
    background: #ffffff;
    color: #64748b;
    border-top: 1px solid #dce2ea;
    padding: 3px 10px;
}
QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#metricValue {
    color: #1d4ed8;
    font-size: 18px;
    font-weight: 800;
}
QLabel#metricName {
    color: #64748b;
    font-size: 11px;
}
QLabel#previewTitle {
    color: #111827;
    font-size: 15px;
    font-weight: 800;
}
QLabel#previewPageLabel {
    background: #ffffff;
    color: #334155;
    border: 1px solid #dce2ea;
    border-radius: 8px;
    padding: 8px 10px;
    font-weight: 700;
}
QLabel#slideCanvas {
    background: #dfe5ec;
    color: #64748b;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px;
}
QLabel#slideLoadingOverlay {
    background: rgba(15, 23, 42, 150);
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 24px;
    font-size: 14px;
    font-weight: 800;
}
QLabel#previewStatus {
    color: #64748b;
    font-size: 11px;
    padding: 2px 3px;
}
QProgressBar {
    border: none;
    background: #e2e8f0;
    border-radius: 3px;
    height: 6px;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 3px;
}
"""

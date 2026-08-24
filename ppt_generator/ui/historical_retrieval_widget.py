"""PySide6 adapter for explainable historical-solution retrieval."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..auto_solution_application import AutoSolutionApplication
from ..solution_generation import HistoricalMatch


class HistoricalRetrievalWidget(QWidget):
    def __init__(self, application: AutoSolutionApplication, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.requirement_id = ""
        self.matches: list[HistoricalMatch] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("历史技术方案检索")
        title.setObjectName("brandTitle")
        layout.addWidget(title)
        note = QLabel(
            "只读取历史方案的结构化摘要，不把整份 PPT 交给生成器。相似度由产品、尺寸、检测项、节拍、上下料和特殊要求共同计算。"
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        controls = QHBoxLayout()
        self.current_label = QLabel("当前需求：未选择")
        controls.addWidget(self.current_label)
        controls.addStretch()
        self.search_button = QPushButton("按当前需求检索")
        self.search_button.setEnabled(False)
        self.search_button.clicked.connect(self.search)
        controls.addWidget(self.search_button)
        layout.addLayout(controls)

        self.history_table = QTableWidget(0, 7)
        self.history_table.setObjectName("autoHistoryMatches")
        self.history_table.setHorizontalHeaderLabels(
            ["项目", "来源", "产品/尺寸", "检测项", "节拍", "相似度与命中理由", "已知问题"]
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.history_table.horizontalHeader()
        for column in (0, 2, 3, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        for column in (1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table, 1)
        self.result_note = QLabel("选择一条已保存需求后开始检索。")
        self.result_note.setObjectName("mutedLabel")
        layout.addWidget(self.result_note)

    def set_requirement_id(self, requirement_id: str) -> None:
        self.requirement_id = requirement_id
        self.search_button.setEnabled(bool(requirement_id))
        if not requirement_id:
            self.current_label.setText("当前需求：未选择")
            self.history_table.setRowCount(0)
            return
        try:
            record = self.application.get_requirement(requirement_id)
        except KeyError:
            self.current_label.setText("当前需求：记录不存在")
            self.search_button.setEnabled(False)
            return
        self.current_label.setText(
            f"当前需求：{record.requirement_no}｜{record.project_name or record.product_name or '未命名'}"
        )
        self.search()

    def search(self) -> None:
        if not self.requirement_id:
            return
        self.matches = self.application.retrieve_history(self.requirement_id)
        self.history_table.setRowCount(len(self.matches))
        for row, match in enumerate(self.matches):
            record = match.record
            values = (
                record.project_name,
                "演示数据" if record.source_kind == "demo" else "用户历史",
                " / ".join(value for value in (record.product_type, record.product_size) if value),
                "、".join(record.inspection_items),
                record.cycle_time,
                f"{match.score}%｜" + "；".join(match.reasons),
                "；".join(record.known_issues),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, record.id)
                self.history_table.setItem(row, column, item)
        if self.matches:
            demo_count = sum(value.record.source_kind == "demo" for value in self.matches)
            self.result_note.setText(
                f"找到 {len(self.matches)} 条结构化候选，其中 {demo_count} 条为明确标注的演示数据。"
            )
        else:
            self.result_note.setText("没有符合条件的历史摘要；候选方案将不显示历史参考区。")


__all__ = ["HistoricalRetrievalWidget"]

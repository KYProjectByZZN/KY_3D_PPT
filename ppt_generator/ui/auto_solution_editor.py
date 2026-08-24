"""Shell coordinating the isolated auto-solution v2 workspaces."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..auto_solution_application import AutoSolutionApplication
from .candidate_solution_widget import CandidateSolutionWidget
from .historical_retrieval_widget import HistoricalRetrievalWidget
from .requirement_management_widget import RequirementManagementWidget


STAGES = (
    "1  客户需求管理",
    "2  历史方案检索",
    "3  候选技术方案",
    "4  工程规则审核（后续）",
    "5  局部纠正（后续）",
    "6  输出准备（后续）",
)


class AutoSolutionEditor(QWidget):
    """Presentation coordinator; cross-page communication uses requirement IDs."""

    def __init__(
        self,
        parent=None,
        application: AutoSolutionApplication | None = None,
    ) -> None:
        super().__init__(parent)
        self.application = application or AutoSolutionApplication()
        self._build_ui()
        self._connect_workspaces()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("可靠技术方案自动生成 v2")
        title.setObjectName("brandTitle")
        subtitle = QLabel("原始需求 → 分类配置 → 历史检索 → 工艺/工位 → DrawingSpecification → Prompt")
        subtitle.setObjectName("mutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        boundary = QLabel("独立模块｜候选结果需人工确认｜尚未接入正式PPT与图像API")
        boundary.setObjectName("mutedLabel")
        boundary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        boundary.setWordWrap(True)
        header.addWidget(boundary)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.stage_list = QListWidget()
        self.stage_list.setObjectName("autoSolutionStages")
        self.stage_list.addItems(STAGES)
        self.stage_list.setFixedWidth(225)
        self.stage_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        splitter.addWidget(self.stage_list)

        self.stage_stack = QStackedWidget()
        self.stage_stack.setObjectName("autoSolutionStack")
        self.requirement_widget = RequirementManagementWidget(self.application)
        self.retrieval_widget = HistoricalRetrievalWidget(self.application)
        self.candidate_widget = CandidateSolutionWidget(self.application)
        self.stage_stack.addWidget(self.requirement_widget)
        self.stage_stack.addWidget(self.retrieval_widget)
        self.stage_stack.addWidget(self.candidate_widget)
        self.stage_stack.addWidget(
            self._placeholder(
                "工程规则审核",
                "v2 本轮不伪实现节拍、干涉、视觉工艺或机械安全计算。候选方案确认后，下一轮在这里接入确定性规则和工程师复核。",
            )
        )
        self.stage_stack.addWidget(
            self._placeholder(
                "局部纠正与版本",
                "保留阶段入口。后续只纠正被审核标记的问题，并尊重人工锁定，不重生成整套方案。",
            )
        )
        self.stage_stack.addWidget(self._build_output_placeholder())
        splitter.addWidget(self.stage_stack)
        splitter.setSizes([225, 1200])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.stage_list.currentRowChanged.connect(self.stage_stack.setCurrentIndex)
        self.stage_list.setCurrentRow(0)

        # Small compatibility aliases for existing smoke automation.
        self.requirement_table = self.requirement_widget.requirement_table
        self.station_table = self.candidate_widget.station_table

    def _connect_workspaces(self) -> None:
        self.requirement_widget.requirement_selected.connect(
            self.retrieval_widget.set_requirement_id
        )
        self.requirement_widget.requirement_selected.connect(
            self.candidate_widget.set_requirement_id
        )
        self.requirement_widget.candidate_generation_requested.connect(
            self._generate_candidate
        )

    def _generate_candidate(self, requirement_id: str) -> None:
        self.candidate_widget.generate_for_requirement(requirement_id)
        self.stage_list.setCurrentRow(2)

    @staticmethod
    def _placeholder(title: str, description: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(title)
        heading.setObjectName("brandTitle")
        layout.addWidget(heading)
        note = QLabel(description)
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _build_output_placeholder(self) -> QWidget:
        page = self._placeholder(
            "输出准备与正式合并边界",
            "当前只保存需求和候选方案 JSON。工程规则、方案图片、人工审核和固定模板全部完成前，不允许写入正式 PPT。",
        )
        self.merge_button = QPushButton("合并到正式项目 / PPT（尚未开放）")
        self.merge_button.setObjectName("primaryButton")
        self.merge_button.setEnabled(False)
        page.layout().insertWidget(2, self.merge_button)
        return page

    def add_station(self) -> None:
        self.candidate_widget.add_station()


__all__ = ["AutoSolutionEditor"]

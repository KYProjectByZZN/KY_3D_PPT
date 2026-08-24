"""PySide6 adapter for candidate process, stations and drawing specification."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..auto_solution_application import AutoSolutionApplication
from ..solution_generation import CandidateSolution, CandidateStation, DrawingSpecification


class CandidateSolutionWidget(QWidget):
    def __init__(self, application: AutoSolutionApplication, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.requirement_id = ""
        self.current_candidate: CandidateSolution | None = None
        self._guard = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("候选技术方案")
        title.setObjectName("brandTitle")
        layout.addWidget(title)
        note = QLabel(
            "固定三部分：历史参考、结构化工艺/工位、DrawingSpecification + Prompt。当前结果是待工程师确认的候选，不是机械设计真值。"
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        controls = QHBoxLayout()
        self.requirement_label = QLabel("当前需求：未选择")
        controls.addWidget(self.requirement_label)
        controls.addWidget(QLabel("候选版本"))
        self.candidate_combo = QComboBox()
        self.candidate_combo.setMinimumWidth(150)
        self.candidate_combo.currentIndexChanged.connect(self._candidate_changed)
        controls.addWidget(self.candidate_combo)
        self.generate_button = QPushButton("生成 / 重新生成")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.generate)
        controls.addWidget(self.generate_button)
        save_button = QPushButton("保存人工修改")
        save_button.clicked.connect(self.save_edits)
        controls.addWidget(save_button)
        confirm_button = QPushButton("确认候选方案")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self.confirm_candidate)
        controls.addWidget(confirm_button)
        self.image_button = QPushButton("生成方案图（待配置图像API）")
        self.image_button.setEnabled(False)
        self.image_button.setToolTip("DrawingSpecification 与 Prompt 已生成；图像 Provider 尚未配置。")
        controls.addWidget(self.image_button)
        controls.addStretch()
        layout.addLayout(controls)

        sections = QSplitter(Qt.Orientation.Vertical)
        self.history_group = self._build_history_section()
        sections.addWidget(self.history_group)
        sections.addWidget(self._build_process_section())
        sections.addWidget(self._build_drawing_section())
        sections.setSizes([180, 300, 360])
        layout.addWidget(sections, 1)
        self.status_label = QLabel("请先保存需求并生成候选方案。")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def _build_history_section(self) -> QGroupBox:
        group = QGroupBox("1. 历史参考（无匹配时自动隐藏）")
        layout = QVBoxLayout(group)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["项目", "相似度", "命中理由", "来源", "已知问题"]
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)
        return group

    def _build_process_section(self) -> QGroupBox:
        group = QGroupBox("2. 结构化工艺与工位")
        layout = QVBoxLayout(group)
        self.process_edit = QPlainTextEdit()
        self.process_edit.setPlaceholderText("每行一个工艺步骤")
        self.process_edit.setMaximumHeight(100)
        layout.addWidget(self.process_edit)
        row = QHBoxLayout()
        add_button = QPushButton("增加工位")
        add_button.clicked.connect(self.add_station)
        delete_button = QPushButton("删除工位")
        delete_button.clicked.connect(self.delete_station)
        row.addWidget(add_button)
        row.addWidget(delete_button)
        row.addStretch()
        layout.addLayout(row)
        self.station_table = QTableWidget(0, 5)
        self.station_table.setObjectName("autoCandidateStations")
        self.station_table.setHorizontalHeaderLabels(
            ["工位ID", "工位名称", "说明", "参考模块", "参考项目"]
        )
        self.station_table.verticalHeader().setVisible(False)
        self.station_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.station_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.station_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.station_table)
        return group

    def _build_drawing_section(self) -> QGroupBox:
        group = QGroupBox("3. DrawingSpecification 与二维方案图 Prompt")
        layout = QVBoxLayout(group)
        tabs = QTabWidget()
        self.drawing_json_edit = QPlainTextEdit()
        self.drawing_json_edit.setPlaceholderText("候选方案生成后显示结构化 DrawingSpecification JSON")
        tabs.addTab(self.drawing_json_edit, "DrawingSpecification JSON（可人工修改）")
        prompt_page = QWidget()
        prompt_layout = QVBoxLayout(prompt_page)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setReadOnly(True)
        prompt_layout.addWidget(self.prompt_edit)
        copy_button = QPushButton("复制 Prompt")
        copy_button.clicked.connect(self.copy_prompt)
        prompt_layout.addWidget(copy_button)
        tabs.addTab(prompt_page, "最终图像 Prompt")
        layout.addWidget(tabs)
        return group

    def set_requirement_id(self, requirement_id: str) -> None:
        self.requirement_id = requirement_id
        self.generate_button.setEnabled(bool(requirement_id))
        if not requirement_id:
            self.requirement_label.setText("当前需求：未选择")
            self._clear_candidate()
            return
        try:
            record = self.application.get_requirement(requirement_id)
        except KeyError:
            self.requirement_label.setText("当前需求：记录不存在")
            self.generate_button.setEnabled(False)
            self._clear_candidate()
            return
        self.requirement_label.setText(
            f"当前需求：{record.requirement_no}｜{record.project_name or record.product_name or '未命名'}"
        )
        self._refresh_candidate_combo()

    def generate_for_requirement(self, requirement_id: str) -> None:
        self.set_requirement_id(requirement_id)
        self.generate()

    def generate(self) -> None:
        if not self.requirement_id:
            return
        try:
            candidate = self.application.generate_candidate(self.requirement_id)
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return
        self.current_candidate = candidate
        self._refresh_candidate_combo(select_id=candidate.id)
        self.status_label.setText(
            f"已生成候选方案 V{candidate.version}；历史引用、工艺和绘图规格均可见，等待人工确认。"
        )

    def _refresh_candidate_combo(self, select_id: str = "") -> None:
        candidates = self.application.list_candidates(self.requirement_id)
        self._guard = True
        try:
            self.candidate_combo.clear()
            selected_index = -1
            for index, candidate in enumerate(candidates):
                self.candidate_combo.addItem(
                    f"V{candidate.version}｜{'已确认' if candidate.status == 'confirmed' else '草稿'}",
                    candidate.id,
                )
                if candidate.id == select_id:
                    selected_index = index
            if candidates:
                self.candidate_combo.setCurrentIndex(
                    selected_index if selected_index >= 0 else len(candidates) - 1
                )
        finally:
            self._guard = False
        if candidates:
            selected = self.candidate_combo.currentData()
            if selected:
                self._load_candidate(self.application.get_candidate(str(selected)))
        else:
            self._clear_candidate()

    def _candidate_changed(self) -> None:
        if self._guard:
            return
        candidate_id = str(self.candidate_combo.currentData() or "")
        if candidate_id:
            try:
                self._load_candidate(self.application.get_candidate(candidate_id))
            except KeyError as exc:
                self._show_error(str(exc))

    def _load_candidate(self, candidate: CandidateSolution) -> None:
        self.current_candidate = candidate
        self.process_edit.setPlainText("\n".join(candidate.process_flow))
        self.station_table.setRowCount(len(candidate.stations))
        for row, station in enumerate(candidate.stations):
            values = (
                station.station_id,
                station.name,
                station.description,
                station.reference_module,
                station.reference_project,
            )
            for column, value in enumerate(values):
                self.station_table.setItem(row, column, QTableWidgetItem(value))
        references = candidate.historical_references
        self.history_group.setVisible(bool(references))
        self.history_table.setRowCount(len(references))
        for row, reference in enumerate(references):
            values = (
                str(reference.get("projectName") or ""),
                f"{int(reference.get('score') or 0)}%",
                "；".join(reference.get("reasons") or []),
                "演示数据" if reference.get("sourceKind") == "demo" else "用户历史",
                "；".join(reference.get("knownIssues") or []),
            )
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(value))
        self.drawing_json_edit.setPlainText(
            json.dumps(candidate.drawing_specification.to_dict(), ensure_ascii=False, indent=2)
        )
        self.prompt_edit.setPlainText(candidate.drawing_prompt)
        self.status_label.setText(
            f"候选方案 V{candidate.version}｜状态：{'已确认' if candidate.status == 'confirmed' else '草稿'}"
        )

    def _clear_candidate(self) -> None:
        self.current_candidate = None
        self.candidate_combo.clear()
        self.process_edit.clear()
        self.station_table.setRowCount(0)
        self.history_table.setRowCount(0)
        self.history_group.setVisible(False)
        self.drawing_json_edit.clear()
        self.prompt_edit.clear()

    def add_station(self) -> None:
        used = {
            self.station_table.item(row, 0).text()
            for row in range(self.station_table.rowCount())
            if self.station_table.item(row, 0)
        }
        index = 1
        while f"S{index:02d}" in used:
            index += 1
        row = self.station_table.rowCount()
        self.station_table.insertRow(row)
        for column, value in enumerate((f"S{index:02d}", "新工位", "", "", "")):
            self.station_table.setItem(row, column, QTableWidgetItem(value))
        self.station_table.selectRow(row)

    def delete_station(self) -> None:
        row = self.station_table.currentRow()
        if row >= 0:
            self.station_table.removeRow(row)

    def _collect_stations(self) -> list[CandidateStation]:
        stations: list[CandidateStation] = []
        for row in range(self.station_table.rowCount()):
            values = [
                self.station_table.item(row, column).text().strip()
                if self.station_table.item(row, column)
                else ""
                for column in range(5)
            ]
            if not values[0] or not values[1]:
                raise ValueError("工位 ID 和名称不能为空")
            stations.append(CandidateStation(*values))
        return stations

    def save_edits(self) -> CandidateSolution | None:
        if self.current_candidate is None:
            return None
        try:
            raw = json.loads(self.drawing_json_edit.toPlainText())
            if not isinstance(raw, dict):
                raise ValueError("DrawingSpecification 根节点必须是 JSON 对象")
            specification = DrawingSpecification.from_dict(raw)
            process = [
                value.strip()
                for value in self.process_edit.toPlainText().splitlines()
                if value.strip()
            ]
            saved = self.application.save_candidate_edits(
                self.current_candidate.id,
                process,
                self._collect_stations(),
                specification,
            )
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return None
        self._load_candidate(saved)
        self.status_label.setText(f"候选方案 V{saved.version} 的人工修改已保存，Prompt 已重新构建。")
        return saved

    def confirm_candidate(self) -> None:
        if self.current_candidate is None:
            return
        saved = self.save_edits()
        if saved is None:
            return
        try:
            confirmed = self.application.confirm_candidate(saved.id)
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return
        self._refresh_candidate_combo(select_id=confirmed.id)
        self.status_label.setText(f"候选方案 V{confirmed.version} 已人工确认；尚未合并到正式 PPT。")

    def copy_prompt(self) -> None:
        QGuiApplication.clipboard().setText(self.prompt_edit.toPlainText())
        self.status_label.setText("Prompt 已复制到剪贴板。")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "候选技术方案", message)


__all__ = ["CandidateSolutionWidget"]

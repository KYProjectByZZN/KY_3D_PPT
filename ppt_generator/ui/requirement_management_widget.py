"""PySide6 adapter for requirement CRUD and confirmation-first parsing."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..auto_solution_application import AutoSolutionApplication
from ..requirement_management import (
    InspectionRequirement,
    LOADING_MODES,
    PRODUCT_STATE_FIELDS,
    RequirementRecord,
    RequirementSuggestion,
    UNLOADING_MODES,
)


STATUS_OPTIONS = (("草稿", "draft"), ("已确认", "confirmed"), ("已归档", "archived"))
TRI_STATE_OPTIONS = (("未知", "unknown"), ("是", "yes"), ("否", "no"))


class RequirementManagementWidget(QWidget):
    requirement_selected = Signal(str)
    candidate_generation_requested = Signal(str)

    def __init__(self, application: AutoSolutionApplication, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.current_record: RequirementRecord | None = None
        self.suggestions: list[RequirementSuggestion] = []
        self._suggestion_checks: list[QCheckBox] = []
        self._guard = False
        self._build_ui()
        self.refresh_records()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QLabel("客户需求记录与结构化配置")
        header.setObjectName("brandTitle")
        layout.addWidget(header)
        note = QLabel(
            f"原始需求永久保留。当前解析器：{self.application.parser_name}；解析结果先作为建议显示，人工确认后才写入空字段。"
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_record_list())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([520, 900])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def _build_record_list(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 6, 0)
        controls = QHBoxLayout()
        new_button = QPushButton("新建")
        new_button.clicked.connect(self.new_record)
        copy_button = QPushButton("复制")
        copy_button.clicked.connect(self.copy_record)
        self.show_archived_check = QCheckBox("显示归档")
        self.show_archived_check.toggled.connect(self.refresh_records)
        controls.addWidget(new_button)
        controls.addWidget(copy_button)
        controls.addStretch()
        controls.addWidget(self.show_archived_check)
        layout.addLayout(controls)

        self.record_table = QTableWidget(0, 9)
        self.record_table.setObjectName("autoRequirementRecords")
        self.record_table.setHorizontalHeaderLabels(
            ["编号", "客户", "项目", "产品", "节拍", "创建人", "更新时间", "状态", "方案数"]
        )
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(True)
        self.record_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.record_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.record_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.record_table.horizontalHeader()
        for column in range(9):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.record_table.itemSelectionChanged.connect(self._load_selected_row)
        layout.addWidget(self.record_table, 1)
        self.requirement_table = self.record_table
        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 0, 0)
        action_row = QHBoxLayout()
        self.save_button = QPushButton("保存需求")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_record)
        parse_button = QPushButton("解析需求并给出建议")
        parse_button.clicked.connect(self.parse_requirement)
        generate_button = QPushButton("生成候选方案")
        generate_button.clicked.connect(self.request_candidate_generation)
        history_button = QPushButton("版本历史")
        history_button.clicked.connect(self.show_version_history)
        archive_button = QPushButton("归档")
        archive_button.clicked.connect(self.archive_record)
        delete_button = QPushButton("删除草稿")
        delete_button.clicked.connect(self.delete_record)
        for button in (
            self.save_button,
            parse_button,
            generate_button,
            history_button,
            archive_button,
            delete_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.detail_tabs = QTabWidget()
        self.detail_tabs.addTab(self._build_basic_tab(), "原始需求与基本配置")
        self.detail_tabs.addTab(self._build_inspection_tab(), "检测项与产品状态")
        self.detail_tabs.addTab(self._build_suggestion_tab(), "解析建议")
        layout.addWidget(self.detail_tabs, 1)
        self.detail_status = QLabel()
        self.detail_status.setObjectName("mutedLabel")
        layout.addWidget(self.detail_status)
        return panel

    def _build_basic_tab(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)

        identity_group = QGroupBox("记录与产品基本信息")
        identity_layout = QGridLayout(identity_group)
        self.requirement_no_label = QLabel("-")
        self.version_label = QLabel("V1")
        self.created_by_label = QLabel("-")
        self.meta_edits = {
            "customerName": QLineEdit(),
            "projectName": QLineEdit(),
            "productName": QLineEdit(),
        }
        self.basic_edits = {
            "productType": QLineEdit(),
            "model": QLineEdit(),
            "size": QLineEdit(),
            "material": QLineEdit(),
        }
        self.status_combo = QComboBox()
        for label, value in STATUS_OPTIONS:
            self.status_combo.addItem(label, value)
        fields: list[tuple[str, QWidget]] = [
            ("需求编号", self.requirement_no_label),
            ("版本", self.version_label),
            ("客户名称", self.meta_edits["customerName"]),
            ("项目名称", self.meta_edits["projectName"]),
            ("产品名称", self.meta_edits["productName"]),
            ("产品类型", self.basic_edits["productType"]),
            ("产品型号", self.basic_edits["model"]),
            ("产品尺寸", self.basic_edits["size"]),
            ("产品材料", self.basic_edits["material"]),
            ("创建人", self.created_by_label),
            ("状态", self.status_combo),
        ]
        for index, (label, widget) in enumerate(fields):
            row, side = divmod(index, 2)
            column = side * 2
            identity_layout.addWidget(QLabel(label), row, column)
            identity_layout.addWidget(widget, row, column + 1)
        identity_layout.setColumnStretch(1, 1)
        identity_layout.setColumnStretch(3, 1)
        layout.addWidget(identity_group)

        original_group = QGroupBox("客户原始描述（解析过程永不覆盖）")
        original_layout = QVBoxLayout(original_group)
        self.original_edit = QPlainTextEdit()
        self.original_edit.setPlaceholderText("粘贴销售或工程师记录的客户原始需求……")
        self.original_edit.setMinimumHeight(120)
        original_layout.addWidget(self.original_edit)
        layout.addWidget(original_group)

        capacity_group = QGroupBox("产能与节拍")
        capacity_layout = QFormLayout(capacity_group)
        self.capacity_edits = {
            "targetCycle": QLineEdit(),
            "batchQuantity": QLineEdit(),
            "dailyCapacity": QLineEdit(),
        }
        self.continuous_combo = self._tri_state_combo()
        capacity_layout.addRow("目标节拍", self.capacity_edits["targetCycle"])
        capacity_layout.addRow("每批数量", self.capacity_edits["batchQuantity"])
        capacity_layout.addRow("日产能", self.capacity_edits["dailyCapacity"])
        capacity_layout.addRow("连续生产", self.continuous_combo)
        layout.addWidget(capacity_group)

        transfer_group = QGroupBox("上下料")
        transfer_layout = QGridLayout(transfer_group)
        self.loading_combo = self._editable_combo(LOADING_MODES)
        self.unloading_combo = self._editable_combo(UNLOADING_MODES)
        self.loading_note_edit = QLineEdit()
        self.unloading_note_edit = QLineEdit()
        transfer_layout.addWidget(QLabel("上料方式"), 0, 0)
        transfer_layout.addWidget(self.loading_combo, 0, 1)
        transfer_layout.addWidget(QLabel("上料说明"), 0, 2)
        transfer_layout.addWidget(self.loading_note_edit, 0, 3)
        transfer_layout.addWidget(QLabel("下料方式"), 1, 0)
        transfer_layout.addWidget(self.unloading_combo, 1, 1)
        transfer_layout.addWidget(QLabel("下料说明"), 1, 2)
        transfer_layout.addWidget(self.unloading_note_edit, 1, 3)
        transfer_layout.setColumnStretch(3, 1)
        layout.addWidget(transfer_group)

        special_group = QGroupBox("特殊要求")
        special_layout = QVBoxLayout(special_group)
        self.special_edit = QPlainTextEdit()
        self.special_edit.setMaximumHeight(90)
        special_layout.addWidget(self.special_edit)
        layout.addWidget(special_group)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    def _build_inspection_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        inspection_group = QGroupBox("检测项目（支持多项）")
        inspection_layout = QVBoxLayout(inspection_group)
        button_row = QHBoxLayout()
        add_button = QPushButton("增加检测项")
        add_button.clicked.connect(self.add_inspection_row)
        remove_button = QPushButton("删除检测项")
        remove_button.clicked.connect(self.remove_inspection_row)
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        inspection_layout.addLayout(button_row)
        self.inspection_table = QTableWidget(0, 4)
        self.inspection_table.setObjectName("autoInspectionItems")
        self.inspection_table.setHorizontalHeaderLabels(["检测项", "精度", "范围", "备注"])
        self.inspection_table.verticalHeader().setVisible(False)
        self.inspection_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        inspection_layout.addWidget(self.inspection_table)
        layout.addWidget(inspection_group, 1)

        states_group = QGroupBox("产品状态：是 / 否 / 未知")
        states_layout = QGridLayout(states_group)
        self.product_state_combos: dict[str, QComboBox] = {}
        for index, (key, label) in enumerate(PRODUCT_STATE_FIELDS):
            row, column_group = divmod(index, 3)
            combo = self._tri_state_combo()
            self.product_state_combos[key] = combo
            column = column_group * 2
            states_layout.addWidget(QLabel(label), row, column)
            states_layout.addWidget(combo, row, column + 1)
        for column in (1, 3, 5):
            states_layout.setColumnStretch(column, 1)
        layout.addWidget(states_group)
        return page

    def _build_suggestion_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("这里只显示解析建议。已有人工值会显示为当前值，并且“应用”操作不会覆盖它。")
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.suggestion_table = QTableWidget(0, 6)
        self.suggestion_table.setHorizontalHeaderLabels(
            ["应用", "字段路径", "当前值", "建议值", "依据", "置信度/来源"]
        )
        self.suggestion_table.verticalHeader().setVisible(False)
        self.suggestion_table.setAlternatingRowColors(True)
        self.suggestion_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.suggestion_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.suggestion_table, 1)
        apply_button = QPushButton("应用勾选建议到空字段")
        apply_button.clicked.connect(self.apply_selected_suggestions)
        layout.addWidget(apply_button)
        return page

    @staticmethod
    def _editable_combo(options: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(options)
        return combo

    @staticmethod
    def _tri_state_combo() -> QComboBox:
        combo = QComboBox()
        for label, value in TRI_STATE_OPTIONS:
            combo.addItem(label, value)
        return combo

    def refresh_records(self, _checked: bool = False, select_id: str = "") -> None:
        summaries = self.application.list_requirement_summaries(
            include_archived=self.show_archived_check.isChecked()
        )
        self._guard = True
        try:
            self.record_table.setRowCount(len(summaries))
            selected_row = -1
            status_labels = dict((value, label) for label, value in STATUS_OPTIONS)
            for row, summary in enumerate(summaries):
                values = (
                    summary.requirement_no,
                    summary.customer_name,
                    summary.project_name,
                    summary.product_name,
                    summary.target_cycle,
                    summary.created_by,
                    summary.updated_time.replace("T", " ")[:19],
                    status_labels.get(summary.status, summary.status),
                    str(summary.solution_count),
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, summary.id)
                    self.record_table.setItem(row, column, item)
                if summary.id == select_id:
                    selected_row = row
            if selected_row >= 0:
                self.record_table.selectRow(selected_row)
        finally:
            self._guard = False
        if selected_row >= 0:
            self._load_record(select_id)
        elif self.current_record is None:
            self.new_record()

    def new_record(self) -> None:
        self.record_table.clearSelection()
        self.current_record = self.application.new_requirement()
        self._load_form(self.current_record)
        self.requirement_selected.emit("")

    def _load_selected_row(self) -> None:
        if self._guard:
            return
        items = self.record_table.selectedItems()
        if not items:
            return
        requirement_id = str(items[0].data(Qt.ItemDataRole.UserRole) or "")
        if requirement_id:
            self._load_record(requirement_id)

    def _load_record(self, requirement_id: str) -> None:
        try:
            self.current_record = self.application.get_requirement(requirement_id)
        except (KeyError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._load_form(self.current_record)
        self.requirement_selected.emit(requirement_id)

    def _load_form(self, record: RequirementRecord, clear_suggestions: bool = True) -> None:
        self._guard = True
        try:
            structured = record.structured_requirement
            self.requirement_no_label.setText(record.requirement_no)
            self.version_label.setText(f"V{record.version}")
            self.created_by_label.setText(record.created_by or self.application.actor)
            self.meta_edits["customerName"].setText(record.customer_name)
            self.meta_edits["projectName"].setText(record.project_name)
            self.meta_edits["productName"].setText(record.product_name)
            self.basic_edits["productType"].setText(structured.basic_info.product_type)
            self.basic_edits["model"].setText(structured.basic_info.model)
            self.basic_edits["size"].setText(structured.basic_info.size)
            self.basic_edits["material"].setText(structured.basic_info.material)
            self.original_edit.setPlainText(record.original_requirement)
            self.capacity_edits["targetCycle"].setText(structured.capacity_and_cycle.target_cycle)
            self.capacity_edits["batchQuantity"].setText(structured.capacity_and_cycle.batch_quantity)
            self.capacity_edits["dailyCapacity"].setText(structured.capacity_and_cycle.daily_capacity)
            self._set_combo_data(self.continuous_combo, structured.capacity_and_cycle.continuous_production)
            self.loading_combo.setCurrentText(structured.loading.mode)
            self.loading_note_edit.setText(structured.loading.note)
            self.unloading_combo.setCurrentText(structured.unloading.mode)
            self.unloading_note_edit.setText(structured.unloading.note)
            self.special_edit.setPlainText(structured.special_requirements)
            self._set_combo_data(self.status_combo, record.status)
            self.inspection_table.setRowCount(len(structured.inspection_items))
            for row, inspection in enumerate(structured.inspection_items):
                for column, value in enumerate(
                    (inspection.name, inspection.accuracy, inspection.range, inspection.note)
                ):
                    self.inspection_table.setItem(row, column, QTableWidgetItem(value))
            for key, combo in self.product_state_combos.items():
                self._set_combo_data(combo, structured.product_states.get(key, "unknown"))
        finally:
            self._guard = False
        if clear_suggestions:
            self.suggestions = []
            self._render_suggestions()
        self.detail_status.setText(
            f"{record.requirement_no} · V{record.version} · 数据文件：{self.application.storage_path}"
        )

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _collect_form(self) -> RequirementRecord:
        record = self.current_record.clone() if self.current_record else self.application.new_requirement()
        structured = record.structured_requirement
        record.customer_name = self.meta_edits["customerName"].text().strip()
        record.project_name = self.meta_edits["projectName"].text().strip()
        record.product_name = self.meta_edits["productName"].text().strip()
        record.original_requirement = self.original_edit.toPlainText()
        record.status = str(self.status_combo.currentData() or "draft")
        structured.basic_info.product_type = self.basic_edits["productType"].text().strip()
        structured.basic_info.model = self.basic_edits["model"].text().strip()
        structured.basic_info.size = self.basic_edits["size"].text().strip()
        structured.basic_info.material = self.basic_edits["material"].text().strip()
        structured.capacity_and_cycle.target_cycle = self.capacity_edits["targetCycle"].text().strip()
        structured.capacity_and_cycle.batch_quantity = self.capacity_edits["batchQuantity"].text().strip()
        structured.capacity_and_cycle.daily_capacity = self.capacity_edits["dailyCapacity"].text().strip()
        structured.capacity_and_cycle.continuous_production = str(self.continuous_combo.currentData() or "unknown")
        structured.loading.mode = self.loading_combo.currentText().strip() or "未知"
        structured.loading.note = self.loading_note_edit.text().strip()
        structured.unloading.mode = self.unloading_combo.currentText().strip() or "未知"
        structured.unloading.note = self.unloading_note_edit.text().strip()
        structured.special_requirements = self.special_edit.toPlainText().strip()
        inspections: list[InspectionRequirement] = []
        for row in range(self.inspection_table.rowCount()):
            values = [
                self.inspection_table.item(row, column).text().strip()
                if self.inspection_table.item(row, column)
                else ""
                for column in range(4)
            ]
            if values[0]:
                inspections.append(InspectionRequirement(*values))
        structured.inspection_items = inspections
        structured.product_states = {
            key: str(combo.currentData() or "unknown")
            for key, combo in self.product_state_combos.items()
        }
        record.validate()
        return record

    def save_record(self) -> RequirementRecord | None:
        try:
            saved = self.application.save_requirement(self._collect_form())
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return None
        self.current_record = saved
        self.refresh_records(select_id=saved.id)
        self.detail_status.setText(f"已保存 {saved.requirement_no} V{saved.version}")
        return saved

    def copy_record(self) -> None:
        saved = self.save_record()
        if saved is None:
            return
        try:
            copied = self.application.copy_requirement(saved.id)
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return
        self.current_record = copied
        self.refresh_records(select_id=copied.id)

    def archive_record(self) -> None:
        saved = self.save_record()
        if saved is None:
            return
        try:
            archived = self.application.archive_requirement(saved.id)
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return
        self.show_archived_check.setChecked(True)
        self.current_record = archived
        self.refresh_records(select_id=archived.id)

    def delete_record(self) -> None:
        if self.current_record is None:
            return
        if not self.application.requirement_exists(self.current_record.id):
            self.new_record()
            return
        answer = QMessageBox.question(
            self,
            "删除草稿",
            f"确认删除 {self.current_record.requirement_no}？此操作只允许无候选方案的草稿。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.application.delete_requirement(self.current_record.id)
        except (KeyError, ValueError, OSError) as exc:
            self._show_error(str(exc))
            return
        self.current_record = None
        self.refresh_records()

    def parse_requirement(self) -> None:
        try:
            self.current_record = self._collect_form()
            self.suggestions = self.application.parse_requirement(self.current_record)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._render_suggestions()
        self.detail_tabs.setCurrentIndex(2)
        self.detail_status.setText(f"解析完成：{len(self.suggestions)} 条建议；尚未写入正式字段")

    def _render_suggestions(self) -> None:
        self._suggestion_checks = []
        self.suggestion_table.setRowCount(len(self.suggestions))
        for row, suggestion in enumerate(self.suggestions):
            check = QCheckBox()
            check.setChecked(True)
            self._suggestion_checks.append(check)
            self.suggestion_table.setCellWidget(row, 0, check)
            current = self._display_json_value(suggestion.current_value)
            proposed = self._display_json_value(suggestion.proposed_value)
            values = (
                suggestion.field_path,
                current,
                proposed,
                suggestion.evidence,
                f"{suggestion.confidence}% / {suggestion.provider}",
            )
            for column, value in enumerate(values, 1):
                self.suggestion_table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _display_json_value(value: Any) -> str:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value or "")

    def apply_selected_suggestions(self) -> None:
        if self.current_record is None:
            return
        selected = [
            suggestion
            for suggestion, check in zip(self.suggestions, self._suggestion_checks)
            if check.isChecked()
        ]
        try:
            applied = self.application.apply_suggestions(self.current_record, selected)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._load_form(self.current_record, clear_suggestions=False)
        self.detail_status.setText(
            f"已应用 {len(applied)} 个空字段；原始需求和已有人工值未修改。请检查后保存。"
        )

    def request_candidate_generation(self) -> None:
        saved = self.save_record()
        if saved is not None:
            self.candidate_generation_requested.emit(saved.id)

    def add_inspection_row(self) -> None:
        row = self.inspection_table.rowCount()
        self.inspection_table.insertRow(row)
        for column in range(4):
            self.inspection_table.setItem(row, column, QTableWidgetItem(""))
        self.inspection_table.setCurrentCell(row, 0)

    def remove_inspection_row(self) -> None:
        row = self.inspection_table.currentRow()
        if row >= 0:
            self.inspection_table.removeRow(row)

    def show_version_history(self) -> None:
        if self.current_record is None:
            return
        snapshots = self.application.requirement_history(self.current_record.id)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"版本历史｜{self.current_record.requirement_no}")
        dialog.resize(980, 420)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(snapshots), 5)
        table.setHorizontalHeaderLabels(["版本", "动作", "时间", "操作人", "主要变化"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, snapshot in enumerate(snapshots):
            values = (
                f"V{snapshot.version}",
                snapshot.action,
                snapshot.changed_time.replace("T", " "),
                snapshot.changed_by,
                self._snapshot_summary(snapshot.before, snapshot.after),
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for column in range(4):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    @staticmethod
    def _snapshot_summary(before: dict[str, Any], after: dict[str, Any]) -> str:
        labels = {
            "customerName": "客户",
            "projectName": "项目",
            "productName": "产品",
            "originalRequirement": "原始需求",
            "structuredRequirement": "结构化配置",
            "status": "状态",
        }
        changed = [labels[key] for key in labels if before.get(key) != after.get(key)]
        return "、".join(changed) or "元数据更新"

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "自动方案", message)


__all__ = ["RequirementManagementWidget"]

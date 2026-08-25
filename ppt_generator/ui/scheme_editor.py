"""Structured equipment workflow and physical-module editor."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..project import AssetRecord, DeviceModule, FlowNode, PptProject
from ..scheme_service import (
    SchemeError,
    add_device_module,
    add_flow_node,
    device_module_by_id,
    flow_node_by_id,
    initialize_equipment_scheme,
    materialize_equipment_scheme,
    move_device_module,
    move_flow_node,
    referenced_flow_nodes,
    remove_device_module,
    remove_flow_node,
)
from ..template_renderer import TemplateManifest


FLOW_TYPES = ["上料", "搬运", "定位", "检测", "翻转", "分拣", "下料", "其他"]
FLOW_OUTPUTS = ["下一步", "OK", "NG", "返工"]
DEVICE_TYPES = ["上料", "搬运", "定位", "翻转", "视觉检测", "分拣", "下料", "控制", "安全", "其他"]


class SchemeEditor(QWidget):
    changed = Signal()
    materialized = Signal()
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: PptProject | None = None
        self.manifest: TemplateManifest | None = None
        self._guard = False
        self._build_ui()

    def _button(self, text: str, slot, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setObjectName("primaryButton")
        button.clicked.connect(slot)
        return button

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        header = QHBoxLayout()
        hint = QLabel(
            "先确认流程节点和实体设备模块，再同步到检测流程、设备总览和设备模块PPT页面。"
        )
        hint.setObjectName("mutedLabel")
        header.addWidget(hint, 1)
        header.addWidget(
            self._button("同步方案到PPT模块", self.materialize, primary=True)
        )
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(), "整机方案")
        self.tabs.addTab(self._build_flow_tab(), "流程设计")
        self.tabs.addTab(self._build_device_tab(), "设备功能模块")
        layout.addWidget(self.tabs, 1)

    def _build_overview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("设备总览页内容")
        form = QFormLayout(group)
        image_row = QHBoxLayout()
        self.overview_image_edit = QLineEdit()
        self.overview_image_edit.setReadOnly(True)
        self.overview_image_edit.setPlaceholderText("选择工程师确认的整机设备方案图")
        image_row.addWidget(self.overview_image_edit, 1)
        image_row.addWidget(self._button("导入/替换图片", self.choose_overview_image))
        form.addRow("整机方案图", image_row)
        self.overview_image_source_label = QLabel("未配置")
        form.addRow("图片来源", self.overview_image_source_label)
        self.overview_description_edit = QPlainTextEdit()
        self.overview_description_edit.setPlaceholderText(
            "说明设备由哪些机构组成，以及各模块如何协同完成检测。"
        )
        self.overview_description_edit.setMaximumBlockCount(20)
        self.overview_description_edit.textChanged.connect(self._save_overview)
        form.addRow("整机说明", self.overview_description_edit)
        self.overview_structure_output = QPlainTextEdit()
        self.overview_structure_output.setReadOnly(True)
        self.overview_structure_output.setMaximumHeight(120)
        form.addRow("整机结构", self.overview_structure_output)
        self.overview_prompt_output = QPlainTextEdit()
        self.overview_prompt_output.setReadOnly(True)
        self.overview_prompt_output.setMaximumHeight(120)
        form.addRow("整机提示词", self.overview_prompt_output)
        layout.addWidget(group)
        note = QLabel(
            "从无CAD页一键同步时整机和模块确认图都必须齐全；在本页可继续导入图片、自定义信息和页面版式。"
        )
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")
        layout.addWidget(note)
        layout.addStretch()
        return tab

    def _build_flow_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        buttons = QHBoxLayout()
        buttons.addWidget(self._button("增加节点", self.add_flow))
        buttons.addWidget(self._button("删除节点", self.delete_flow))
        buttons.addWidget(self._button("上移", lambda: self.move_flow(-1)))
        buttons.addWidget(self._button("下移", lambda: self.move_flow(1)))
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.flow_table = QTableWidget(0, 5)
        self.flow_table.setHorizontalHeaderLabels(
            ["步骤", "节点名称", "类型", "工位", "关联设备模块"]
        )
        self.flow_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.flow_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.flow_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.flow_table.verticalHeader().setVisible(False)
        self.flow_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.flow_table.itemSelectionChanged.connect(self._show_flow)
        splitter.addWidget(self.flow_table)

        group = QGroupBox("流程节点属性")
        form = QFormLayout(group)
        self.flow_name_edit = QLineEdit()
        self.flow_name_edit.setMaxLength(16)
        self.flow_name_edit.editingFinished.connect(self._save_flow)
        form.addRow("节点名称", self.flow_name_edit)
        self.flow_type_combo = QComboBox()
        self.flow_type_combo.addItems(FLOW_TYPES)
        self.flow_type_combo.currentTextChanged.connect(self._save_flow)
        form.addRow("节点类型", self.flow_type_combo)
        self.flow_station_edit = QLineEdit()
        self.flow_station_edit.editingFinished.connect(self._save_flow)
        form.addRow("对应工位", self.flow_station_edit)
        self.flow_action_edit = QPlainTextEdit()
        self.flow_action_edit.setMaximumBlockCount(8)
        self.flow_action_edit.textChanged.connect(self._save_flow)
        form.addRow("动作说明", self.flow_action_edit)
        self.flow_cycle_edit = QLineEdit()
        self.flow_cycle_edit.setPlaceholderText("例如：1.2 s")
        self.flow_cycle_edit.editingFinished.connect(self._save_flow)
        form.addRow("节点节拍", self.flow_cycle_edit)
        self.flow_output_combo = QComboBox()
        self.flow_output_combo.addItems(FLOW_OUTPUTS)
        self.flow_output_combo.currentTextChanged.connect(self._save_flow)
        form.addRow("输出方向", self.flow_output_combo)
        self.flow_module_combo = QComboBox()
        self.flow_module_combo.currentIndexChanged.connect(self._save_flow)
        form.addRow("关联模块", self.flow_module_combo)
        splitter.addWidget(group)
        splitter.setSizes([520, 330])
        layout.addWidget(splitter, 1)
        return tab

    def _build_device_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        buttons = QHBoxLayout()
        buttons.addWidget(self._button("增加模块及绑定", self.add_device))
        buttons.addWidget(self._button("删除设备模块", self.delete_device))
        buttons.addWidget(self._button("上移", lambda: self.move_device(-1)))
        buttons.addWidget(self._button("下移", lambda: self.move_device(1)))
        buttons.addStretch()
        layout.addLayout(buttons)
        binding_hint = QLabel(
            "每个模块独立拥有：结构、提示词、方案图和PPT页面绑定；增删与排序按同一模块ID整体联动。"
        )
        binding_hint.setWordWrap(True)
        binding_hint.setObjectName("mutedLabel")
        layout.addWidget(binding_hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.device_table = QTableWidget(0, 8)
        self.device_table.setHorizontalHeaderLabels(
            ["序号", "设备模块", "类型", "结构", "提示词", "图片", "PPT绑定", "关联流程"]
        )
        self.device_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.device_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.device_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.device_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.device_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.device_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        for column in (4, 5, 6):
            self.device_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.device_table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )
        self.device_table.itemSelectionChanged.connect(self._show_device)
        splitter.addWidget(self.device_table)

        group = QGroupBox("设备功能模块属性（可自定义编辑）")
        form = QFormLayout(group)
        self.device_name_edit = QLineEdit()
        self.device_name_edit.editingFinished.connect(self._save_device)
        form.addRow("模块名称", self.device_name_edit)
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItems(DEVICE_TYPES)
        self.device_type_combo.currentTextChanged.connect(self._save_device)
        form.addRow("模块类型", self.device_type_combo)
        self.device_station_edit = QLineEdit()
        self.device_station_edit.editingFinished.connect(self._save_device)
        form.addRow("对应工位", self.device_station_edit)
        self.device_function_edit = QPlainTextEdit()
        self.device_function_edit.setMaximumBlockCount(10)
        self.device_function_edit.textChanged.connect(self._save_device)
        form.addRow("模块功能", self.device_function_edit)
        self.device_action_edit = QPlainTextEdit()
        self.device_action_edit.setMaximumBlockCount(10)
        self.device_action_edit.textChanged.connect(self._save_device)
        form.addRow("动作过程", self.device_action_edit)
        self.device_structure_output = QPlainTextEdit()
        self.device_structure_output.setReadOnly(True)
        self.device_structure_output.setMaximumHeight(115)
        form.addRow("绑定结构", self.device_structure_output)
        self.device_prompt_output = QPlainTextEdit()
        self.device_prompt_output.setReadOnly(True)
        self.device_prompt_output.setMaximumHeight(115)
        form.addRow("绑定提示词", self.device_prompt_output)
        image_row = QHBoxLayout()
        self.device_image_edit = QLineEdit()
        self.device_image_edit.setReadOnly(True)
        image_row.addWidget(self.device_image_edit, 1)
        image_row.addWidget(self._button("导入/替换图片", self.choose_device_image))
        form.addRow("模块方案图", image_row)
        self.device_image_source_label = QLabel("未配置")
        form.addRow("图片来源", self.device_image_source_label)
        self.device_note_edit = QLineEdit()
        self.device_note_edit.editingFinished.connect(self._save_device)
        form.addRow("特别说明", self.device_note_edit)
        self.device_template_combo = QComboBox()
        self.device_template_combo.currentIndexChanged.connect(self._save_device)
        form.addRow("PPT页面版式", self.device_template_combo)
        self.device_enabled_check = QCheckBox("参与设备模块页面生成")
        self.device_enabled_check.stateChanged.connect(self._save_device)
        form.addRow("启用", self.device_enabled_check)
        splitter.addWidget(group)
        splitter.setSizes([650, 430])
        layout.addWidget(splitter, 1)
        return tab

    def set_state(self, project: PptProject, manifest: TemplateManifest) -> None:
        self.project = project
        self.manifest = manifest
        initialize_equipment_scheme(project)
        self._guard = True
        try:
            self.overview_image_edit.setText(project.equipment_scheme.overview_image)
            self.overview_image_source_label.setText(
                self._image_source_text(
                    project.equipment_scheme.overview_image,
                    project.equipment_scheme.overview_image_provenance,
                )
            )
            self.overview_description_edit.setPlainText(
                project.equipment_scheme.overview_description
            )
            self.overview_structure_output.setPlainText(
                json.dumps(
                    project.equipment_scheme.overview_structure,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            self.overview_prompt_output.setPlainText(
                project.equipment_scheme.overview_prompt
            )
        finally:
            self._guard = False
        self.refresh_flow_table()
        self.refresh_device_table()

    def _selected_id(self, table: QTableWidget) -> str:
        row = table.currentRow()
        item = table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _selected_flow(self) -> FlowNode | None:
        if not self.project:
            return None
        node_id = self._selected_id(self.flow_table)
        return flow_node_by_id(self.project, node_id) if node_id else None

    def _selected_device(self) -> DeviceModule | None:
        if not self.project:
            return None
        module_id = self._selected_id(self.device_table)
        return device_module_by_id(self.project, module_id) if module_id else None

    def refresh_flow_table(self, selected_id: str = "") -> None:
        if not self.project:
            return
        selected_id = selected_id or self._selected_id(self.flow_table)
        modules = {
            item.id: item.name
            for item in self.project.equipment_scheme.equipment_modules
        }
        nodes = self.project.equipment_scheme.flow_nodes
        self._guard = True
        try:
            self.flow_table.setRowCount(len(nodes))
            selected_row = -1
            for row, node in enumerate(nodes):
                values = [
                    str(row + 1),
                    node.name,
                    node.node_type,
                    node.station,
                    modules.get(node.equipment_module_id, "未关联"),
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, node.id)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.flow_table.setItem(row, column, item)
                if node.id == selected_id:
                    selected_row = row
            if selected_row < 0 and nodes:
                selected_row = 0
            if selected_row >= 0:
                self.flow_table.selectRow(selected_row)
        finally:
            self._guard = False
        self._show_flow()

    def refresh_device_table(self, selected_id: str = "") -> None:
        if not self.project:
            return
        selected_id = selected_id or self._selected_id(self.device_table)
        modules = self.project.equipment_scheme.equipment_modules
        self._guard = True
        try:
            self.device_table.setRowCount(len(modules))
            selected_row = -1
            for row, module in enumerate(modules):
                values = self._device_table_values(row, module)
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, module.id)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.device_table.setItem(row, column, item)
                if module.id == selected_id:
                    selected_row = row
            if selected_row < 0 and modules:
                selected_row = 0
            if selected_row >= 0:
                self.device_table.selectRow(selected_row)
        finally:
            self._guard = False
        self._show_device()
        self._refresh_flow_module_combo()

    def _device_table_values(
        self,
        row: int,
        module: DeviceModule,
    ) -> list[str]:
        assert self.project is not None
        links = "、".join(
            node.name for node in referenced_flow_nodes(self.project, module.id)
        )
        structure_status = "已绑定" if module.structure_definition else "待定义"
        prompt_status = "已生成" if module.image_prompt.strip() else "待生成"
        if module.image_path:
            image_status = (
                "人工确认"
                if module.image_provenance.get("source") == "manual-import"
                else "AI已采用"
                if module.image_provenance
                else "已选择"
            )
        else:
            image_status = "待添加"
        ppt_status = "已绑定" if module.page_template_key else "默认绑定"
        if not module.enabled:
            ppt_status = "未启用"
        return [
            str(row + 1),
            module.name,
            module.module_type,
            structure_status,
            prompt_status,
            image_status,
            ppt_status,
            links or "未关联",
        ]

    @staticmethod
    def _image_source_text(path: str, provenance: dict) -> str:
        if not path:
            return "未配置"
        source = str(provenance.get("source") or "")
        if source == "manual-import":
            return "人工导入并确认"
        provider = str(provenance.get("provider") or "")
        if provenance:
            return f"AI人工采用 · {provider}" if provider else "AI人工采用"
        return "旧项目图片（来源未记录）"

    def _refresh_flow_module_combo(self, requested_id: str = "") -> None:
        if not self.project:
            return
        node = self._selected_flow()
        requested_id = requested_id or (node.equipment_module_id if node else "")
        was_guard = self._guard
        self._guard = True
        try:
            self.flow_module_combo.clear()
            self.flow_module_combo.addItem("不关联", "")
            for module in self.project.equipment_scheme.equipment_modules:
                self.flow_module_combo.addItem(module.name, module.id)
            index = self.flow_module_combo.findData(requested_id)
            self.flow_module_combo.setCurrentIndex(max(0, index))
        finally:
            self._guard = was_guard

    def _show_flow(self) -> None:
        if self._guard:
            return
        node = self._selected_flow()
        self._guard = True
        try:
            enabled = node is not None
            for widget in (
                self.flow_name_edit,
                self.flow_type_combo,
                self.flow_station_edit,
                self.flow_action_edit,
                self.flow_cycle_edit,
                self.flow_output_combo,
                self.flow_module_combo,
            ):
                widget.setEnabled(enabled)
            if not node:
                return
            self.flow_name_edit.setText(node.name)
            self.flow_type_combo.setCurrentText(node.node_type)
            self.flow_station_edit.setText(node.station)
            self.flow_action_edit.setPlainText(node.action)
            self.flow_cycle_edit.setText(node.cycle_time)
            self.flow_output_combo.setCurrentText(node.output)
        finally:
            self._guard = False
        self._refresh_flow_module_combo(node.equipment_module_id if node else "")

    def _show_device(self) -> None:
        if self._guard:
            return
        module = self._selected_device()
        self._guard = True
        try:
            enabled = module is not None
            for widget in (
                self.device_name_edit,
                self.device_type_combo,
                self.device_station_edit,
                self.device_function_edit,
                self.device_action_edit,
                self.device_structure_output,
                self.device_prompt_output,
                self.device_image_edit,
                self.device_image_source_label,
                self.device_note_edit,
                self.device_template_combo,
                self.device_enabled_check,
            ):
                widget.setEnabled(enabled)
            self.device_template_combo.clear()
            if not module:
                return
            self.device_name_edit.setText(module.name)
            self.device_type_combo.setCurrentText(module.module_type)
            self.device_station_edit.setText(module.station)
            self.device_function_edit.setPlainText(module.function)
            self.device_action_edit.setPlainText(module.action)
            self.device_structure_output.setPlainText(
                json.dumps(
                    module.structure_definition,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            self.device_prompt_output.setPlainText(module.image_prompt)
            self.device_image_edit.setText(module.image_path)
            self.device_image_source_label.setText(
                self._image_source_text(module.image_path, module.image_provenance)
            )
            self.device_note_edit.setText(module.note)
            ppt_module = next(
                (
                    item
                    for item in self.project.modules
                    if item.template_module_key == "equipment_module"
                    and not item.generated_by_binding_id
                ),
                None,
            ) if self.project else None
            if ppt_module:
                for template in ppt_module.page_templates:
                    if template.source_slide in {6, 7, 8, 9}:
                        self.device_template_combo.addItem(
                            f"{template.name} · 模板第{template.source_slide}页",
                            template.key,
                        )
            index = self.device_template_combo.findData(module.page_template_key)
            if index < 0:
                index = next(
                    (
                        item_index
                        for item_index in range(self.device_template_combo.count())
                        if "模板第7页" in self.device_template_combo.itemText(item_index)
                    ),
                    0,
                )
            self.device_template_combo.setCurrentIndex(index)
            self.device_enabled_check.setChecked(module.enabled)
        finally:
            self._guard = False

    def _save_overview(self) -> None:
        if self._guard or not self.project:
            return
        self.project.equipment_scheme.overview_description = (
            self.overview_description_edit.toPlainText().strip()
        )
        self.changed.emit()

    def _save_flow(self, *_args) -> None:
        if self._guard:
            return
        node = self._selected_flow()
        if not node:
            return
        node.name = self.flow_name_edit.text().strip()
        node.node_type = self.flow_type_combo.currentText()
        node.station = self.flow_station_edit.text().strip()
        node.action = self.flow_action_edit.toPlainText().strip()
        node.cycle_time = self.flow_cycle_edit.text().strip()
        node.output = self.flow_output_combo.currentText()
        node.equipment_module_id = str(self.flow_module_combo.currentData() or "")
        row = self.flow_table.currentRow()
        linked = (
            device_module_by_id(self.project, node.equipment_module_id).name
            if self.project and node.equipment_module_id
            else "未关联"
        )
        for column, value in enumerate(
            [str(row + 1), node.name, node.node_type, node.station, linked]
        ):
            item = self.flow_table.item(row, column) if row >= 0 else None
            if item:
                item.setText(value)
        if self.project:
            for device_row, device in enumerate(
                self.project.equipment_scheme.equipment_modules
            ):
                item = self.device_table.item(device_row, 7)
                if item:
                    links = "、".join(
                        linked_node.name
                        for linked_node in referenced_flow_nodes(
                            self.project, device.id
                        )
                    )
                    item.setText(links or "未关联")
        self.changed.emit()

    def _save_device(self, *_args) -> None:
        if self._guard:
            return
        module = self._selected_device()
        if not module:
            return
        module.name = self.device_name_edit.text().strip()
        module.module_type = self.device_type_combo.currentText()
        module.station = self.device_station_edit.text().strip()
        module.function = self.device_function_edit.toPlainText().strip()
        module.action = self.device_action_edit.toPlainText().strip()
        module.note = self.device_note_edit.text().strip()
        module.page_template_key = str(self.device_template_combo.currentData() or "")
        module.enabled = self.device_enabled_check.isChecked()
        row = self.device_table.currentRow()
        if row >= 0 and self.project:
            for column, value in enumerate(
                self._device_table_values(row, module)
            ):
                item = self.device_table.item(row, column)
                if item:
                    item.setText(value)
        if self.project:
            module_names = {
                item.id: item.name
                for item in self.project.equipment_scheme.equipment_modules
            }
            for flow_row, node in enumerate(
                self.project.equipment_scheme.flow_nodes
            ):
                item = self.flow_table.item(flow_row, 4)
                if item:
                    item.setText(
                        module_names.get(node.equipment_module_id, "未关联")
                    )
        self._refresh_flow_module_combo()
        self.changed.emit()

    def add_flow(self) -> None:
        if not self.project:
            return
        node = add_flow_node(self.project)
        self.refresh_flow_table(node.id)
        self.changed.emit()

    def delete_flow(self) -> None:
        if not self.project:
            return
        node = self._selected_flow()
        if not node:
            return
        answer = QMessageBox.question(
            self, "删除流程节点", f"确定删除流程节点“{node.name}”？"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        remove_flow_node(self.project, node.id)
        self.refresh_flow_table()
        self.refresh_device_table()
        self.changed.emit()

    def move_flow(self, offset: int) -> None:
        if not self.project:
            return
        node = self._selected_flow()
        if node and move_flow_node(self.project, node.id, offset):
            self.refresh_flow_table(node.id)
            self.changed.emit()

    def add_device(self) -> None:
        if not self.project:
            return
        module = add_device_module(self.project)
        self.refresh_device_table(module.id)
        self.refresh_flow_table()
        self.changed.emit()

    def delete_device(self) -> None:
        if not self.project:
            return
        module = self._selected_device()
        if not module:
            return
        references = referenced_flow_nodes(self.project, module.id)
        text = f"确定删除设备模块“{module.name}”？"
        if references:
            names = "、".join(node.name for node in references)
            text += f"\n\n以下流程会同时解除关联：{names}"
        answer = QMessageBox.question(self, "删除设备模块", text)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_device_module(
                self.project, module.id, clear_links=bool(references)
            )
        except SchemeError as exc:
            QMessageBox.warning(self, "删除设备模块失败", str(exc))
            return
        self.refresh_device_table()
        self.refresh_flow_table()
        self.changed.emit()

    def move_device(self, offset: int) -> None:
        if not self.project:
            return
        module = self._selected_device()
        if module and move_device_module(self.project, module.id, offset):
            self.refresh_device_table(module.id)
            self.changed.emit()

    def _remember_asset(self, path: str) -> None:
        if not self.project:
            return
        resolved = str(Path(path).expanduser().resolve())
        if not any(Path(item.path) == Path(resolved) for item in self.project.assets):
            self.project.assets.append(AssetRecord(path=resolved, category="设备图"))

    def choose_overview_image(self) -> None:
        if not self.project:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择整机设备方案图", str(Path.cwd()), "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        resolved = str(Path(path).resolve())
        self.project.equipment_scheme.overview_image = resolved
        self.project.equipment_scheme.overview_image_provenance = {
            "source": "manual-import",
            "projectId": self.project.project_id,
            "projectName": self.project.project_name,
            "targetId": "overview",
            "targetKind": "overview",
            "humanConfirmed": True,
        }
        self.overview_image_edit.setText(resolved)
        self.overview_image_source_label.setText("人工导入并确认")
        self._remember_asset(resolved)
        self.changed.emit()

    def choose_device_image(self) -> None:
        if not self.project:
            return
        module = self._selected_device()
        if not module:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择设备模块方案图", str(Path.cwd()), "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        module.image_path = str(Path(path).resolve())
        module.image_provenance = {
            "source": "manual-import",
            "projectId": self.project.project_id,
            "projectName": self.project.project_name,
            "targetId": module.source_scene_node_id or module.id,
            "targetKind": "module",
            "humanConfirmed": True,
        }
        self.device_image_edit.setText(module.image_path)
        self.device_image_source_label.setText("人工导入并确认")
        self._remember_asset(module.image_path)
        self.refresh_device_table(module.id)
        self.changed.emit()

    def materialize(self) -> None:
        if not self.project or not self.manifest:
            return
        self._save_overview()
        self._save_flow()
        self._save_device()
        try:
            result = materialize_equipment_scheme(self.project, self.manifest)
        except Exception as exc:
            QMessageBox.warning(self, "设备方案同步失败", str(exc))
            return
        self.materialized.emit()
        message = (
            f"设备方案已同步：流程 {result.flow_pages} 页，"
            f"设备模块 {result.equipment_pages} 页"
        )
        self.message.emit(message)
        QMessageBox.information(self, "设备方案已同步", message)

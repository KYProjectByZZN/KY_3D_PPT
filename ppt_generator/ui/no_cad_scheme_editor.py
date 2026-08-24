"""PySide6 editor for no-CAD equipment logic schemes."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..no_cad_scheme import (
    CATEGORY_NAMES,
    MODULE_BY_TYPE,
    EquipmentScene,
    NoCadSchemeResult,
    NoCadSchemeService,
    SceneNode,
    VisualGenerationTarget,
    normalize_module_structure,
)
from ..openai_image import ImageProvider
from .module_visual_overview import ModuleVisualOverviewDialog
from .openai_image_dialog import DEFAULT_AI_OUTPUT_ROOT, OpenAIImageDialog


class NoCadSchemeEditor(QWidget):
    """Independent visual editor; the EquipmentScene is its only state owner."""

    scheme_committed = Signal(object)
    workspace_changed = Signal(object)

    def __init__(
        self,
        service: NoCadSchemeService | None = None,
        image_provider: ImageProvider | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or NoCadSchemeService()
        self.image_provider = image_provider
        self._openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.project_id = ""
        self.candidate_batch_records: list[dict[str, Any]] = []
        self.scene: EquipmentScene = self.service.create_demo_scene()
        self.current_result: NoCadSchemeResult | None = None
        self._ui_guard = False
        self._setup_ui()
        self.refresh()

    def set_project_context(
        self,
        project_id: str,
        scene_data: Mapping[str, Any] | None = None,
        batch_records: list[Mapping[str, Any]] | None = None,
    ) -> None:
        """Replace the editor workspace with data owned by one PPT project."""

        self.project_id = str(project_id or "")
        self.candidate_batch_records = [
            deepcopy(dict(value)) for value in (batch_records or [])
        ]
        self.scene = (
            EquipmentScene.from_dict(scene_data)
            if scene_data
            else self.service.create_demo_scene()
        )
        self.refresh()

    def workspace_snapshot(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "scene": self.scene.to_dict(),
            "aiImageBatches": deepcopy(self.candidate_batch_records),
        }

    def _emit_workspace_changed(self, *, candidate_history_changed: bool = False) -> None:
        payload = self.workspace_snapshot()
        payload["candidateHistoryChanged"] = candidate_history_changed
        self.workspace_changed.emit(payload)

    def _receive_ai_batch_records(self, records: object) -> None:
        if not isinstance(records, list):
            return
        normalized = [
            deepcopy(dict(value)) for value in records if isinstance(value, Mapping)
        ]
        if len(normalized) != len(records) or normalized == self.candidate_batch_records:
            return
        self.candidate_batch_records = normalized
        self._emit_workspace_changed(candidate_history_changed=True)

    def _button(
        self,
        text: str,
        slot,
        *,
        primary: bool = False,
    ) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setObjectName("primaryButton")
        button.clicked.connect(slot)
        return button

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("labHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        title_box = QVBoxLayout()
        title = QLabel("无CAD设备逻辑方案")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #20242A;")
        self.scope_label = QLabel(
            "逻辑正确优先：标准模块 + 单条产品主线；当前输出是售前结构示意，不是制造图。"
        )
        self.scope_label.setStyleSheet("color: #9E1B20; font-weight: 600;")
        title_box.addWidget(title)
        title_box.addWidget(self.scope_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        self.visual_overview_button = QPushButton("模块效果总览")
        self.visual_overview_button.clicked.connect(self.show_visual_overview)
        header_layout.addWidget(self.visual_overview_button)
        self.ai_generate_button = QPushButton("使用 Codex Pro 生成效果图")
        self.ai_generate_button.setEnabled(False)
        self.ai_generate_button.clicked.connect(self.generate_ai_effect)
        header_layout.addWidget(self.ai_generate_button)
        self.commit_button = QPushButton("同步结构到正式设备方案")
        self.commit_button.setEnabled(False)
        self.commit_button.clicked.connect(self.commit_scheme)
        header_layout.addWidget(self.commit_button)
        root.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._button("加载演示方案", self.load_demo))
        toolbar.addWidget(self._button("新建最小方案", self.new_minimum_scene))
        toolbar.addWidget(self._button("自动排布（保留锁定）", self.auto_layout))
        toolbar.addStretch()
        self.export_svg_button = self._button("导出结构SVG", self.export_svg)
        self.export_scene_button = self._button("导出Scene JSON", self.export_scene)
        toolbar.addWidget(self.export_svg_button)
        toolbar.addWidget(self.export_scene_button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.workspace_splitter = splitter
        splitter.addWidget(self._build_library_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([380, 760, 470])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _build_library_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(310)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        catalog_title = QLabel("标准设备模块库")
        catalog_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(catalog_title)
        catalog_note = QLabel("选择模块后可添加到主线，或替换当前选中模块。")
        catalog_note.setWordWrap(True)
        catalog_note.setStyleSheet("color: #68717A;")
        layout.addWidget(catalog_note)
        self.catalog_list = QListWidget()
        self.catalog_list.setObjectName("noCadModuleCatalog")
        for definition in self.service.module_catalog:
            item = QListWidgetItem(
                f"[{CATEGORY_NAMES[definition.category]}] {definition.name}\n{definition.description}"
            )
            item.setData(Qt.ItemDataRole.UserRole, definition.module_type)
            item.setToolTip("内部部件：" + "、".join(definition.integrated_components))
            self.catalog_list.addItem(item)
        self.catalog_list.setCurrentRow(0)
        layout.addWidget(self.catalog_list, 2)
        catalog_buttons = QHBoxLayout()
        catalog_buttons.addWidget(self._button("添加到主线", self.add_selected_module, primary=True))
        catalog_buttons.addWidget(self._button("替换当前模块", self.replace_selected_module))
        layout.addLayout(catalog_buttons)

        flow_title = QLabel("设备产品主线（可拖动排序）")
        flow_title.setStyleSheet("font-size: 16px; font-weight: 700; margin-top: 6px;")
        layout.addWidget(flow_title)
        self.flow_list = QListWidget()
        self.flow_list.setObjectName("noCadFlowList")
        self.flow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.flow_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.flow_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.flow_list.setDragEnabled(True)
        self.flow_list.setAcceptDrops(True)
        self.flow_list.setDropIndicatorShown(True)
        self.flow_list.currentItemChanged.connect(self._selected_node_changed)
        self.flow_list.model().rowsMoved.connect(self._flow_rows_moved)
        layout.addWidget(self.flow_list, 3)
        flow_buttons = QHBoxLayout()
        flow_buttons.addWidget(self._button("上移", lambda: self.move_selected(-1)))
        flow_buttons.addWidget(self._button("下移", lambda: self.move_selected(1)))
        flow_buttons.addWidget(self._button("删除", self.remove_selected_module))
        layout.addLayout(flow_buttons)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QLabel("无CAD逻辑结构图")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        self.preview_widget = QSvgWidget()
        self.preview_widget.setObjectName("noCadSchemePreview")
        self.preview_widget.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(self.preview_widget, 1)
        note = QLabel("模块顺序和产品流向为审核重点；外观、比例和机械细节仅作概念表达。")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(
            "background: #FFF1F1; color: #9E1B20; padding: 7px; font-weight: 600;"
        )
        layout.addWidget(note)
        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        scene_title = QLabel("方案与当前模块")
        scene_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(scene_title)
        form = QFormLayout()
        self.project_name_edit = QLineEdit()
        self.product_name_edit = QLineEdit()
        self.node_name_edit = QLineEdit()
        self.station_id_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.reference_image_edit = QLineEdit()
        self.locked_check = QCheckBox("锁定位置与结构")
        form.addRow("方案名称", self.project_name_edit)
        form.addRow("产品名称", self.product_name_edit)
        form.addRow("模块名称", self.node_name_edit)
        form.addRow("工位编号", self.station_id_edit)
        form.addRow("功能说明", self.description_edit)
        reference_row = QHBoxLayout()
        reference_row.addWidget(self.reference_image_edit, 1)
        reference_row.addWidget(self._button("选择", self.choose_reference_image))
        form.addRow("模块参考图", reference_row)
        form.addRow("确认状态", self.locked_check)
        layout.addLayout(form)
        self.apply_properties_button = self._button(
            "应用属性并重新检查",
            self.apply_properties,
            primary=True,
        )
        layout.addWidget(self.apply_properties_button)

        self.detail_tabs = QTabWidget()
        self.issue_table = QTableWidget(0, 3)
        self.issue_table.setHorizontalHeaderLabels(["级别", "代码", "检查结果"])
        self.issue_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.issue_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.issue_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.issue_table.verticalHeader().setVisible(False)
        self.issue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scene_json_output = QPlainTextEdit()
        self.scene_json_output.setReadOnly(True)
        self.generation_brief_output = QPlainTextEdit()
        self.generation_brief_output.setReadOnly(True)
        self.detail_tabs.addTab(self.issue_table, "逻辑检查")
        self.detail_tabs.addTab(self.scene_json_output, "Scene JSON")
        self.detail_tabs.addTab(self.generation_brief_output, "整机生成约束")
        self.detail_tabs.addTab(self._build_target_editor(), "结构 / 提示词绑定")
        layout.addWidget(self.detail_tabs, 1)
        return panel

    def _build_target_editor(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        form = QFormLayout()
        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        form.addRow("结构编辑目标", self.target_combo)
        self.target_image_label = QLabel("尚未采用图片")
        self.target_image_label.setWordWrap(True)
        form.addRow("目标图片", self.target_image_label)
        layout.addLayout(form)

        structure_label = QLabel("人工定义结构 JSON")
        structure_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(structure_label)
        self.target_structure_editor = QPlainTextEdit()
        self.target_structure_editor.setPlaceholderText(
            "整机可填写附加结构；模块包含部件、机构关系、运动关系和禁止元素。"
        )
        layout.addWidget(self.target_structure_editor, 2)

        requirements_label = QLabel("人工补充提示要求")
        requirements_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(requirements_label)
        self.target_prompt_requirements_edit = QPlainTextEdit()
        self.target_prompt_requirements_edit.setMaximumHeight(86)
        layout.addWidget(self.target_prompt_requirements_edit)
        self.apply_target_button = self._button(
            "应用结构并重建提示词",
            self.apply_target_definition,
            primary=True,
        )
        layout.addWidget(self.apply_target_button)

        final_label = QLabel("当前目标最终提示词（只读）")
        final_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(final_label)
        self.target_prompt_output = QPlainTextEdit()
        self.target_prompt_output.setReadOnly(True)
        layout.addWidget(self.target_prompt_output, 2)
        return panel

    def load_demo(self) -> None:
        self.scene = self.service.create_demo_scene()
        self.refresh()

    def new_minimum_scene(self) -> None:
        self.scene = self.service.create_minimum_scene()
        self.refresh()

    def auto_layout(self) -> None:
        selected_id = self._selected_node_id()
        self.service.auto_layout(self.scene)
        self.refresh(select_id=selected_id)

    def add_selected_module(self) -> None:
        module_type = self._selected_catalog_type()
        if not module_type:
            return
        current_row = self.flow_list.currentRow()
        index = current_row + 1 if current_row >= 0 else len(self.scene.nodes)
        node = self.service.add_module(self.scene, module_type, index=index)
        self.service.auto_layout(self.scene)
        self.refresh(select_id=node.node_id)

    def replace_selected_module(self) -> None:
        node_id = self._selected_node_id()
        module_type = self._selected_catalog_type()
        if not node_id or not module_type:
            self._set_status("请先在主线和模块库中分别选择一项", error=True)
            return
        try:
            self.service.replace_module(self.scene, node_id, module_type)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self.refresh(select_id=node_id)

    def remove_selected_module(self) -> None:
        node_id = self._selected_node_id()
        if not node_id:
            return
        row = self.flow_list.currentRow()
        try:
            self.service.remove_module(self.scene, node_id)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self.service.auto_layout(self.scene)
        next_id = ""
        if self.scene.nodes:
            next_id = self.scene.nodes[min(row, len(self.scene.nodes) - 1)].node_id
        self.refresh(select_id=next_id)

    def move_selected(self, offset: int) -> None:
        node_id = self._selected_node_id()
        if not node_id:
            return
        try:
            self.service.move_module(self.scene, node_id, offset)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self.service.auto_layout(self.scene)
        self.refresh(select_id=node_id)

    def apply_properties(self) -> None:
        self.scene.project_name = self.project_name_edit.text().strip()
        self.scene.product_name = self.product_name_edit.text().strip()
        node = self._selected_node()
        if node is not None:
            node.name = self.node_name_edit.text().strip()
            node.station_id = self.station_id_edit.text().strip()
            node.description = self.description_edit.text().strip()
            node.reference_image = self.reference_image_edit.text().strip()
            node.locked = self.locked_check.isChecked()
        self.service.rebuild_connections(self.scene)
        self.refresh(select_id=node.node_id if node else "")

    def choose_reference_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模块参考图",
            self.reference_image_edit.text(),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)",
        )
        if path:
            self.reference_image_edit.setText(path)

    def refresh(self, select_id: str = "", target_id: str = "") -> None:
        previous_id = select_id or self._selected_node_id()
        previous_target_id = target_id or self._current_target_id()
        self.current_result = self.service.evaluate(self.scene)
        invalidated_targets = self.service.invalidate_stale_images(
            self.scene,
            self.current_result,
        )
        if invalidated_targets:
            self.current_result = self.service.evaluate(self.scene)
        self._ui_guard = True
        try:
            self.project_name_edit.setText(self.scene.project_name)
            self.product_name_edit.setText(self.scene.product_name)
            self.flow_list.clear()
            select_row = 0
            for row, node in enumerate(self.scene.nodes):
                definition = MODULE_BY_TYPE.get(node.module_type)
                category = CATEGORY_NAMES.get(definition.category, "未知") if definition else "未知"
                lock_text = " 🔒" if node.locked else ""
                item = QListWidgetItem(
                    f"{row + 1:02d}  {node.station_id or '未编号'} · {node.name}{lock_text}\n{category}｜{node.description}"
                )
                item.setData(Qt.ItemDataRole.UserRole, node.node_id)
                if node.locked:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                if node.node_id == previous_id:
                    select_row = row
                self.flow_list.addItem(item)
            if self.flow_list.count():
                self.flow_list.setCurrentRow(select_row)
            self.preview_widget.load(
                QByteArray(self.current_result.svg.encode("utf-8"))
            )
            self._refresh_issues()
            self.scene_json_output.setPlainText(
                json.dumps(
                    {
                        "scene": self.scene.to_dict(),
                        "result": self.current_result.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            self.generation_brief_output.setPlainText(
                self.current_result.generation_brief
            )
            self._refresh_target_combo(previous_target_id)
        finally:
            self._ui_guard = False
        self._load_selected_node_properties()
        self._target_changed()
        blocking = sum(
            value.level == "blocking" for value in self.current_result.issues
        )
        warnings = sum(
            value.level == "warning" for value in self.current_result.issues
        )
        self.ai_generate_button.setEnabled(not bool(blocking))
        self.commit_button.setEnabled(not bool(blocking))
        if blocking:
            self.ai_generate_button.setText("AI效果图生成（逻辑未通过）")
            self._set_status(
                f"逻辑未通过：{blocking}项阻断、{warnings}项待确认｜Scene {self.current_result.scene_hash[:12]}",
                error=True,
            )
        else:
            self.ai_generate_button.setText("打开 Codex Pro AI效果图生成")
            accepted = sum(
                bool(value.image_path)
                for value in self.current_result.visual_targets
            )
            self._set_status(
                f"逻辑通过：0项阻断、{warnings}项待确认｜"
                f"视觉目标 {len(self.current_result.visual_targets)} 个，已采用 {accepted} 个｜"
                f"Scene {self.current_result.scene_hash[:12]}"
                + (
                    f"｜结构变化，已清除 {len(invalidated_targets)} 张过期采用图"
                    if invalidated_targets
                    else ""
                ),
                error=False,
            )
        self._emit_workspace_changed()

    def _current_target_id(self) -> str:
        if not hasattr(self, "target_combo"):
            return ""
        return str(self.target_combo.currentData() or "")

    def _current_target(self):
        if self.current_result is None:
            return None
        target_id = self._current_target_id()
        if not target_id:
            return None
        try:
            return self.current_result.visual_target(target_id)
        except ValueError:
            return None

    def _refresh_target_combo(self, requested_id: str = "") -> None:
        assert self.current_result is not None
        self.target_combo.clear()
        for target in self.current_result.visual_targets:
            status = "已采用" if target.image_path else "待生成"
            self.target_combo.addItem(f"{target.title} · {status}", target.target_id)
        requested_id = requested_id or "overview"
        index = self.target_combo.findData(requested_id)
        self.target_combo.setCurrentIndex(max(0, index))

    def _target_changed(self, *_args) -> None:
        if self._ui_guard or self.current_result is None:
            return
        target = self._current_target()
        if target is None:
            self.target_structure_editor.clear()
            self.target_prompt_requirements_edit.clear()
            self.target_prompt_output.clear()
            self.target_image_label.setText("尚未选择生成目标")
            return
        if target.target_kind == "overview":
            structure = self.scene.overview_structure
            requirements = self.scene.overview_prompt_requirements
            editable = True
        else:
            node = next(
                value for value in self.scene.nodes if value.node_id == target.target_id
            )
            structure = node.structure
            requirements = node.prompt_requirements
            editable = not node.locked
        self.target_structure_editor.setEnabled(editable)
        self.target_prompt_requirements_edit.setEnabled(editable)
        self.apply_target_button.setEnabled(editable)
        self.target_structure_editor.setPlainText(
            json.dumps(structure, ensure_ascii=False, indent=2)
        )
        self.target_prompt_requirements_edit.setPlainText(requirements)
        self.target_prompt_output.setPlainText(target.prompt)
        self.target_image_label.setText(
            target.image_path or "尚未采用图片"
        )
        if self.current_result.can_generate_ai:
            self.ai_generate_button.setText("打开 Codex Pro AI效果图生成")

    def apply_target_definition(self) -> None:
        target = self._current_target()
        if target is None:
            return
        try:
            raw = json.loads(self.target_structure_editor.toPlainText() or "{}")
            if not isinstance(raw, dict):
                raise ValueError("人工定义结构必须是 JSON 对象")
            requirements = self.target_prompt_requirements_edit.toPlainText().strip()
            changed = False
            if target.target_kind == "overview":
                changed = (
                    raw != self.scene.overview_structure
                    or requirements != self.scene.overview_prompt_requirements
                )
                self.scene.overview_structure = raw
                self.scene.overview_prompt_requirements = requirements
                if changed:
                    self.scene.overview_image = ""
                    self.scene.overview_image_provenance = {}
            else:
                node = next(
                    value for value in self.scene.nodes if value.node_id == target.target_id
                )
                normalized = normalize_module_structure(raw, node.module_type)
                changed = (
                    normalized != node.structure
                    or requirements != node.prompt_requirements
                )
                node.structure = normalized
                node.prompt_requirements = requirements
                if changed:
                    node.image_path = ""
                    node.image_provenance = {}
        except (json.JSONDecodeError, ValueError) as exc:
            self._set_status(f"结构定义未应用：{exc}", error=True)
            return
        self.refresh(
            select_id=self._selected_node_id(),
            target_id=target.target_id,
        )
        self._set_status(
            "结构与提示词绑定已更新；原采用图已失效，请按新目标重新生成。"
            if changed
            else "结构与提示词没有变化。",
            error=False,
        )

    def commit_scheme(self) -> None:
        if self.current_result is None or not self.current_result.can_generate_ai:
            self._set_status("当前设备方案未通过逻辑门禁，不能同步。", error=True)
            return
        self.scheme_committed.emit(self.scene.to_dict())
        self._set_status(
            "整机及各模块结构、提示词和已采用图片已提交到正式设备方案；尚未自动生成 PPT。",
            error=False,
        )

    def _refresh_issues(self) -> None:
        assert self.current_result is not None
        labels = {"blocking": "阻断", "warning": "警告", "info": "提示"}
        colors = {
            "blocking": QColor("#FFE5E5"),
            "warning": QColor("#FFF4D6"),
            "info": QColor("#EAF2F7"),
        }
        self.issue_table.setRowCount(len(self.current_result.issues))
        for row, issue in enumerate(self.current_result.issues):
            values = (labels[issue.level], issue.code, issue.message)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setBackground(colors[issue.level])
                self.issue_table.setItem(row, column, item)
        self.issue_table.resizeRowsToContents()

    def _selected_node_changed(self, _current, _previous) -> None:
        if not self._ui_guard:
            self._load_selected_node_properties()
            node_id = self._selected_node_id()
            index = self.target_combo.findData(node_id)
            if index >= 0:
                self.target_combo.setCurrentIndex(index)

    def _load_selected_node_properties(self) -> None:
        node = self._selected_node()
        enabled = node is not None
        for widget in (
            self.locked_check,
            self.apply_properties_button,
        ):
            widget.setEnabled(enabled)
        details_enabled = enabled and not bool(node and node.locked)
        for widget in (
            self.node_name_edit,
            self.station_id_edit,
            self.description_edit,
            self.reference_image_edit,
        ):
            widget.setEnabled(details_enabled)
        if node is None:
            self.node_name_edit.clear()
            self.station_id_edit.clear()
            self.description_edit.clear()
            self.reference_image_edit.clear()
            self.locked_check.setChecked(False)
            return
        self.node_name_edit.setText(node.name)
        self.station_id_edit.setText(node.station_id)
        self.description_edit.setText(node.description)
        self.reference_image_edit.setText(node.reference_image)
        self.locked_check.setChecked(node.locked)

    def _flow_rows_moved(self, *_args) -> None:
        if self._ui_guard:
            return
        node_ids = [
            self.flow_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.flow_list.count())
        ]
        selected_id = self._selected_node_id()
        try:
            self.service.reorder_modules(self.scene, node_ids)
        except ValueError as exc:
            self.refresh(select_id=selected_id)
            self._set_status(str(exc), error=True)
            return
        self.service.auto_layout(self.scene)
        self.refresh(select_id=selected_id)

    def _selected_catalog_type(self) -> str:
        item = self.catalog_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else ""

    def _selected_node_id(self) -> str:
        item = self.flow_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else ""

    def _selected_node(self) -> SceneNode | None:
        node_id = self._selected_node_id()
        return next((value for value in self.scene.nodes if value.node_id == node_id), None)

    def _set_status(self, text: str, *, error: bool) -> None:
        if error:
            self.status_label.setStyleSheet(
                "color: #9E1B20; background: #FFF1F1; padding: 7px;"
            )
        else:
            self.status_label.setStyleSheet(
                "color: #276738; background: #EDF8F0; padding: 7px;"
            )
        self.status_label.setText(text)

    def export_svg(self) -> None:
        if self.current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出无CAD逻辑结构图",
            "无CAD设备逻辑方案.svg",
            "SVG 文件 (*.svg)",
        )
        if path:
            Path(path).write_text(self.current_result.svg, encoding="utf-8")
            self._set_status(f"已导出SVG：{path}", error=False)

    def show_visual_overview(self) -> None:
        if self.current_result is None:
            self.refresh()
        assert self.current_result is not None
        dialog = ModuleVisualOverviewDialog(
            self.current_result.visual_targets,
            project_name=self.scene.project_name,
            product_name=self.scene.product_name,
            parent=self,
        )
        dialog.exec()

    def generate_ai_effect(self) -> None:
        if self.current_result is None or not self.current_result.can_generate_ai:
            self._set_status("当前设备方案未通过逻辑门禁。", error=True)
            return
        target = self._current_target()
        dialog = OpenAIImageDialog(
            scene_snapshot=self.scene.to_dict(),
            result=self.current_result,
            target=target,
            provider=self.image_provider,
            api_key=self._openai_api_key,
            output_root=DEFAULT_AI_OUTPUT_ROOT / (self.project_id or "_unbound"),
            project_id=self.project_id,
            batch_history=self.candidate_batch_records,
            parent=self,
        )
        dialog.batch_records_changed.connect(self._receive_ai_batch_records)
        dialog.exec()
        self._openai_api_key = dialog.api_key()
        history_reader = getattr(dialog, "project_batch_records", None)
        if callable(history_reader):
            records = history_reader()
            self._receive_ai_batch_records(records)
        selections = list(getattr(dialog, "accepted_selections", []))
        if not selections and dialog.accepted_selection is not None:
            selections = [dialog.accepted_selection]
        if selections:
            bindings: list[tuple[VisualGenerationTarget, str, dict]] = []
            for selection in selections:
                target_id = str(selection.get("targetId") or "")
                try:
                    accepted_target = self.current_result.visual_target(target_id)
                except ValueError:
                    self._set_status(
                        f"采用结果目标不存在：{target_id}",
                        error=True,
                    )
                    return
                if selection.get("targetHash") != accepted_target.target_hash:
                    self._set_status(
                        f"“{accepted_target.title}”采用结果与当前目标哈希不一致，未回写。",
                        error=True,
                    )
                    return
                image_path = str(selection.get("imagePath") or "")
                if not Path(image_path).is_file():
                    self._set_status(
                        f"“{accepted_target.title}”采用结果图片不存在，未回写。",
                        error=True,
                    )
                    return
                bindings.append((accepted_target, image_path, selection))
            for accepted_target, image_path, selection in bindings:
                self.service.bind_accepted_image(
                    self.scene,
                    accepted_target.target_id,
                    image_path,
                    selection,
                )
            last_target = bindings[-1][0]
            self.refresh(
                select_id=self._selected_node_id(),
                target_id=last_target.target_id,
            )
            names = "、".join(value[0].title for value in bindings)
            self._set_status(
                f"已回写 {len(bindings)} 个效果图目标：{names}。完成后可同步正式设备方案。",
                error=False,
            )
            return
        if dialog.batch is not None:
            batch_target = dialog.target
            self._set_status(
                f"{dialog.batch.provider} 已生成 {len(dialog.batch.candidates)} 张候选图｜"
                f"目标 {batch_target.title if batch_target else '未选择'}｜请人工采用后再关闭窗口",
                error=False,
            )

    def export_scene(self) -> None:
        if self.current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出无CAD设备Scene",
            "无CAD设备逻辑方案.scene.json",
            "JSON 文件 (*.json)",
        )
        if path:
            Path(path).write_text(
                json.dumps(
                    {
                        "scene": self.scene.to_dict(),
                        "result": self.current_result.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            self._set_status(f"已导出Scene：{path}", error=False)


__all__ = ["NoCadSchemeEditor"]

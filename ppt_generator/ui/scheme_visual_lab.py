"""Standalone PySide6 workspace for the deterministic scheme-visual lab."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..scheme_visual_lab import (
    SchemeVisualLabResult,
    SchemeVisualLabService,
    demo_drawing_specification,
)
from ..solution_generation import DrawingSpecification


PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
<rect width="1600" height="900" fill="#F4F5F6"/>
<text x="800" y="420" text-anchor="middle" font-family="Microsoft YaHei" font-size="34" fill="#434A51">等待生成结构示意图</text>
<text x="800" y="475" text-anchor="middle" font-family="Microsoft YaHei" font-size="22" fill="#7A838C">先校验 DrawingSpecification，再生成稳定布局</text>
</svg>"""


class SchemeVisualLabWidget(QWidget):
    """Review lab that has no dependency on formal candidate repositories."""

    def __init__(
        self,
        service: SchemeVisualLabService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or SchemeVisualLabService()
        self.current_result: SchemeVisualLabResult | None = None
        self._setup_ui()
        self.load_demo()

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
        title = QLabel("方案图实验室")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #20242A;")
        self.isolation_label = QLabel(
            "独立实验，不读取/修改正式候选方案，不写 PPT；当前只验证稳定结构与提示词配方。"
        )
        self.isolation_label.setStyleSheet("color: #9E1B20; font-weight: 600;")
        title_box.addWidget(title)
        title_box.addWidget(self.isolation_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        self.ai_generate_button = QPushButton("生成 AI 候选图（未配置）")
        self.ai_generate_button.setEnabled(False)
        self.ai_generate_button.setToolTip("本次核验不接入图片 Provider")
        header_layout.addWidget(self.ai_generate_button)
        root.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.workspace_splitter = splitter
        splitter.addWidget(self._build_spec_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_output_panel())
        splitter.setSizes([350, 700, 430])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("等待生成")
        self.status_label.setObjectName("labStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _build_spec_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(270)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        label = QLabel("DrawingSpecification JSON")
        label.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(label)
        note = QLabel("可直接修改。视觉部件和治具只有明确填写后才会进入结构图。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #68717A;")
        layout.addWidget(note)
        self.spec_editor = QPlainTextEdit()
        self.spec_editor.setObjectName("drawingSpecificationEditor")
        self.spec_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.spec_editor.setPlaceholderText("粘贴 DrawingSpecification JSON")
        layout.addWidget(self.spec_editor, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self._button("加载演示", self.load_demo))
        self.generate_button = self._button(
            "校验并生成",
            self.generate,
            primary=True,
        )
        buttons.addWidget(self.generate_button)
        layout.addLayout(buttons)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        title = QLabel("SVG 结构示意")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        heading.addWidget(title)
        heading.addStretch()
        self.export_svg_button = self._button("导出 SVG", self.export_svg)
        self.export_svg_button.setEnabled(False)
        heading.addWidget(self.export_svg_button)
        layout.addLayout(heading)
        self.preview_widget = QSvgWidget()
        self.preview_widget.setObjectName("schemeSvgPreview")
        self.preview_widget.renderer().setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.preview_widget.load(QByteArray(PLACEHOLDER_SVG.encode("utf-8")))
        layout.addWidget(self.preview_widget, 1)
        warning = QLabel("结构示意图 / 非 CAD 施工图 / 人工确认后方可进入正式方案")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning.setStyleSheet(
            "background: #FFF1F1; color: #9E1B20; padding: 7px; font-weight: 600;"
        )
        layout.addWidget(warning)
        return panel

    def _build_output_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        title = QLabel("可核验中间产物")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        heading.addWidget(title)
        heading.addStretch()
        self.export_recipe_button = self._button(
            "导出 Recipe",
            self.export_recipe,
        )
        self.export_recipe_button.setEnabled(False)
        heading.addWidget(self.export_recipe_button)
        layout.addLayout(heading)

        self.output_tabs = QTabWidget()
        self.layout_output = self._readonly_editor()
        self.recipe_output = self._readonly_editor()
        self.prompt_output = self._readonly_editor()
        self.checklist_table = QTableWidget(0, 2)
        self.checklist_table.setHorizontalHeaderLabels(["状态", "核验项"])
        self.checklist_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.checklist_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.checklist_table.verticalHeader().setVisible(False)
        self.checklist_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.output_tabs.addTab(self.layout_output, "LayoutPlan")
        self.output_tabs.addTab(self.recipe_output, "PromptRecipe")
        self.output_tabs.addTab(self.prompt_output, "最终提示词")
        self.output_tabs.addTab(self.checklist_table, "核验清单")
        layout.addWidget(self.output_tabs, 1)
        return panel

    @staticmethod
    def _readonly_editor() -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        return editor

    def load_demo(self) -> None:
        specification = demo_drawing_specification()
        self.spec_editor.setPlainText(
            json.dumps(specification.to_dict(), ensure_ascii=False, indent=2)
        )
        self.generate()

    def generate(self) -> None:
        try:
            raw = json.loads(self.spec_editor.toPlainText())
            if not isinstance(raw, dict):
                raise ValueError("DrawingSpecification 顶层必须是 JSON 对象")
            specification = DrawingSpecification.from_dict(raw)
            result = self.service.run(specification)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self.current_result = result
        self.preview_widget.load(QByteArray(result.svg.encode("utf-8")))
        self.layout_output.setPlainText(
            json.dumps(result.layout_plan.to_dict(), ensure_ascii=False, indent=2)
        )
        self.recipe_output.setPlainText(
            json.dumps(result.prompt_recipe.to_dict(), ensure_ascii=False, indent=2)
        )
        self.prompt_output.setPlainText(
            "【正向提示词】\n"
            + result.prompt_recipe.positive_prompt
            + "\n\n【负向提示词】\n"
            + result.prompt_recipe.negative_prompt
        )
        checklist = result.prompt_recipe.evaluation_checklist
        self.checklist_table.setRowCount(len(checklist))
        for row, item in enumerate(checklist):
            status = QTableWidgetItem("待人工核验")
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.checklist_table.setItem(row, 0, status)
            self.checklist_table.setItem(row, 1, QTableWidgetItem(item))
        self.checklist_table.resizeRowsToContents()
        self.export_svg_button.setEnabled(True)
        self.export_recipe_button.setEnabled(True)
        self.status_label.setStyleSheet(
            "color: #276738; background: #EDF8F0; padding: 7px;"
        )
        self.status_label.setText(
            "生成成功：相同 JSON 将得到相同结果｜"
            f"规格 {result.layout_plan.source_spec_hash[:12]}｜"
            f"布局 {result.layout_plan.layout_hash[:12]}｜"
            f"Recipe {result.prompt_recipe.recipe_hash[:12]}"
        )

    def _show_error(self, message: str) -> None:
        self.current_result = None
        self.preview_widget.load(QByteArray(PLACEHOLDER_SVG.encode("utf-8")))
        self.layout_output.clear()
        self.recipe_output.clear()
        self.prompt_output.clear()
        self.checklist_table.setRowCount(0)
        self.export_svg_button.setEnabled(False)
        self.export_recipe_button.setEnabled(False)
        self.status_label.setStyleSheet(
            "color: #9E1B20; background: #FFF1F1; padding: 7px;"
        )
        self.status_label.setText("输入校验失败：" + message)

    def export_svg(self) -> None:
        if self.current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 SVG 结构示意图",
            "方案图实验室_结构示意图.svg",
            "SVG 文件 (*.svg)",
        )
        if not path:
            return
        Path(path).write_text(self.current_result.svg, encoding="utf-8")
        self.status_label.setText(f"已导出 SVG：{path}")

    def export_recipe(self) -> None:
        if self.current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 PromptRecipe",
            "方案图实验室_PromptRecipe.json",
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        Path(path).write_text(
            json.dumps(
                self.current_result.prompt_recipe.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.status_label.setText(f"已导出 PromptRecipe：{path}")


__all__ = ["SchemeVisualLabWidget"]

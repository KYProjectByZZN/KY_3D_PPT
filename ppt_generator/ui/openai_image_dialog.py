"""Image generation dialog for a frozen no-CAD equipment scene."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QByteArray, QRectF, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..app_paths import project_ai_candidates_root
from ..codex_image import CodexImageProvider
from ..no_cad_scheme import (
    EquipmentScene,
    NoCadSchemeResult,
    VisualGenerationTarget,
)
from ..openai_image import (
    DEFAULT_OPENAI_IMAGE_MODEL,
    ImageProvider,
    OPENAI_IMAGE_QUALITIES,
    OPENAI_IMAGE_SIZES,
    OpenAIImageBatch,
    OpenAIImageError,
    OpenAIImageProvider,
    prepare_openai_image_request,
)
from .module_visual_overview import ImagePreviewDialog


DEFAULT_AI_OUTPUT_ROOT = project_ai_candidates_root("_unbound")


class OpenAIConnectionWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, provider: ImageProvider, api_key: str, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.api_key = api_key

    def run(self) -> None:
        try:
            self.succeeded.emit(self.provider.test_connection(self.api_key))
        except Exception as exc:
            self.failed.emit(str(exc))


class CodexLoginWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, provider: ImageProvider, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider

    def run(self) -> None:
        try:
            login = getattr(self.provider, "login", None)
            if not callable(login):
                raise OpenAIImageError("当前图片 Provider 不支持 ChatGPT 登录。")
            self.succeeded.emit(str(login()))
        except Exception as exc:
            self.failed.emit(str(exc))


class OpenAIImageWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, provider: ImageProvider, request, api_key: str, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.request = request
        self.api_key = api_key

    def run(self) -> None:
        try:
            self.succeeded.emit(self.provider.generate(self.request, self.api_key))
        except Exception as exc:
            self.failed.emit(str(exc))


class OpenAIImageDialog(QDialog):
    """Configure one Codex/API request and review its traceable candidates."""

    batch_records_changed = Signal(object)

    def __init__(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        result: NoCadSchemeResult,
        target: VisualGenerationTarget | None = None,
        provider: ImageProvider | None = None,
        api_key: str = "",
        output_root: str | Path = DEFAULT_AI_OUTPUT_ROOT,
        project_id: str = "",
        batch_history: list[Mapping[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scene_snapshot = dict(scene_snapshot)
        self.result = result
        self.target = target or (
            result.visual_target("overview") if result.visual_targets else None
        )
        self.providers: list[ImageProvider] = (
            [provider]
            if provider is not None
            else [CodexImageProvider(), OpenAIImageProvider()]
        )
        self.provider = self.providers[0]
        self.output_root = Path(output_root)
        self.project_id = project_id
        self.batch_records = [
            deepcopy(dict(value)) for value in (batch_history or [])
        ]
        self.generated_batch_records: list[dict[str, Any]] = []
        self.batch: OpenAIImageBatch | None = None
        self.accepted_selection: dict[str, Any] | None = None
        self.accepted_selections: list[dict[str, Any]] = []
        self._worker: QThread | None = None
        self._history_guard = False
        self.setWindowTitle("AI 设备方案效果图")
        self.setMinimumSize(1080, 720)
        self.resize(1280, 820)
        self._setup_ui(api_key or os.environ.get("OPENAI_API_KEY", ""))

    def _setup_ui(self, api_key: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("AI 设备方案效果图")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #20242A;")
        root.addWidget(title)
        note = QLabel(
            "结构和工艺关系仍以 EquipmentScene 为准。AI 只生成候选外观图，结果必须人工核验后才能采用。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9E1B20; font-weight: 600;")
        root.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_settings_panel(api_key))
        splitter.addWidget(self._build_review_panel())
        splitter.setSizes([390, 820])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("等待配置。API Key 仅保留在当前软件会话中，不写入工程文件。")
        self.status_label.setWordWrap(True)
        self._set_status(self.status_label.text(), error=False)
        root.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        self._provider_changed()
        self._target_changed(reset_candidates=False)

    def _build_settings_panel(self, api_key: str) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(350)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        heading = QLabel("连接与生成参数")
        heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(heading)
        form = QFormLayout()
        self.target_combo = QComboBox()
        for visual_target in self.result.visual_targets:
            self.target_combo.addItem(
                self._target_combo_text(visual_target),
                visual_target.target_id,
            )
        initial_target_id = self.target.target_id if self.target else "overview"
        initial_index = self.target_combo.findData(initial_target_id)
        self.target_combo.setCurrentIndex(max(0, initial_index))
        form.addRow("本次生成目标", self.target_combo)
        self.provider_combo = QComboBox()
        for candidate in self.providers:
            self.provider_combo.addItem(
                str(getattr(candidate, "display_name", "图片 Provider"))
            )
        self.provider_combo.setEnabled(len(self.providers) > 1)
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        form.addRow("调用方式", self.provider_combo)
        self.api_key_edit = QLineEdit(api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-... 或项目 API Key")
        form.addRow("API Key", self.api_key_edit)
        self.api_key_label = form.labelForField(self.api_key_edit)
        self.model_label = QLabel(DEFAULT_OPENAI_IMAGE_MODEL)
        self.model_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("运行模型", self.model_label)
        self.size_combo = QComboBox()
        self.size_combo.addItems(OPENAI_IMAGE_SIZES)
        form.addRow("图片尺寸", self.size_combo)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(OPENAI_IMAGE_QUALITIES)
        self.quality_combo.setCurrentText("medium")
        form.addRow("生成质量", self.quality_combo)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 4)
        self.count_spin.setValue(1)
        form.addRow("候选数量", self.count_spin)
        layout.addLayout(form)

        self.credentials_note = QLabel(
            '需要在 <a href="https://platform.openai.com/api-keys">OpenAI API 平台</a>创建密钥并具备图片模型权限。生成会消耗 API 额度。'
        )
        self.credentials_note.setOpenExternalLinks(True)
        self.credentials_note.setWordWrap(True)
        self.credentials_note.setStyleSheet("color: #68717A;")
        layout.addWidget(self.credentials_note)

        action_row = QHBoxLayout()
        self.login_button = QPushButton("登录 Codex")
        self.login_button.clicked.connect(self.login_codex)
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        self.generate_button = QPushButton("生成候选图")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.login_button)
        action_row.addWidget(self.test_button)
        action_row.addWidget(self.generate_button)
        layout.addLayout(action_row)

        target_title = self.target.title if self.target else "整机设备总览"
        target_hash = self.target.target_hash if self.target else self.result.scene_hash
        self.scene_label = QLabel(
            f"当前目标：{target_title}｜Hash {target_hash[:16]}"
        )
        self.scene_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.scene_label.setStyleSheet("color: #68717A;")
        layout.addWidget(self.scene_label)
        prompt_label = QLabel("提交给 AI 的结构约束")
        prompt_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(prompt_label)
        self.brief_output = QPlainTextEdit(
            self.target.prompt if self.target else self.result.generation_brief
        )
        self.brief_output.setReadOnly(True)
        layout.addWidget(self.brief_output, 1)
        return panel

    def _build_review_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("labPanel")
        panel.setMinimumWidth(560)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        self.review_title = QLabel("候选图人工核验")
        self.review_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        heading.addWidget(self.review_title)
        heading.addStretch()
        heading.addWidget(QLabel("历史批次"))
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(210)
        self.history_combo.currentIndexChanged.connect(self._history_changed)
        heading.addWidget(self.history_combo)
        self.candidate_combo = QComboBox()
        self.candidate_combo.setEnabled(False)
        self.candidate_combo.currentIndexChanged.connect(self._show_candidate)
        heading.addWidget(self.candidate_combo)
        layout.addLayout(heading)

        self.preview_label = QLabel("尚未生成候选图")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(560, 400)
        self.preview_label.setStyleSheet(
            "background: #F1F3F5; border: 1px solid #C7CCD1; color: #68717A;"
        )
        layout.addWidget(self.preview_label, 1)

        checklist = QLabel(
            "核验重点：模块数量和顺序、产品流向、检测工位、剔除机构、上下料接口；发现多画、漏画或顺序错误时不要采用。"
        )
        checklist.setWordWrap(True)
        checklist.setStyleSheet("background: #FFF4D6; color: #6E5417; padding: 8px;")
        layout.addWidget(checklist)

        action_row = QHBoxLayout()
        self.view_accepted_button = QPushButton("查看已采用图")
        self.view_accepted_button.setEnabled(False)
        self.view_accepted_button.clicked.connect(self.view_accepted_image)
        self.accept_button = QPushButton("采用当前候选")
        self.accept_button.setEnabled(False)
        self.accept_button.clicked.connect(self.accept_current)
        self.open_folder_button = QPushButton("打开结果目录")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_output_folder)
        action_row.addWidget(self.view_accepted_button)
        action_row.addWidget(self.accept_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.metadata_output = QPlainTextEdit()
        self.metadata_output.setReadOnly(True)
        self.metadata_output.setMaximumHeight(150)
        layout.addWidget(self.metadata_output)
        return panel

    def _accepted_for_target(self, target_id: str) -> dict[str, Any] | None:
        return next(
            (
                value
                for value in reversed(self.accepted_selections)
                if str(value.get("targetId") or "") == target_id
            ),
            None,
        )

    def _target_combo_text(self, target: VisualGenerationTarget) -> str:
        if self._accepted_for_target(target.target_id) is not None:
            status = "本次已采用"
        elif target.image_path:
            status = "已采用"
        else:
            status = "待生成"
        return f"{target.title} · {status}"

    @staticmethod
    def _record_batch_id(record: Mapping[str, Any]) -> str:
        batch = record.get("batch") or {}
        return str(batch.get("batchId") or "") if isinstance(batch, Mapping) else ""

    def project_batch_records(self) -> list[dict[str, Any]]:
        return deepcopy(self.batch_records)

    def _matching_batch_records(self) -> list[dict[str, Any]]:
        if self.target is None:
            return []
        matches: list[dict[str, Any]] = []
        for record in self.batch_records:
            if self.project_id and str(record.get("projectId") or "") not in {
                "",
                self.project_id,
            }:
                continue
            target = record.get("generationTarget") or {}
            if not isinstance(target, Mapping):
                continue
            if str(target.get("targetId") or "") != self.target.target_id:
                continue
            if str(target.get("targetHash") or "") != self.target.target_hash:
                continue
            matches.append(record)
        return matches

    def _refresh_history_combo(self, selected_batch_id: str = "") -> None:
        self._history_guard = True
        try:
            self.history_combo.clear()
            self.history_combo.addItem("当前已采用图", None)
            selected_index = 0
            for record in reversed(self._matching_batch_records()):
                batch = record.get("batch") or {}
                if not isinstance(batch, Mapping):
                    continue
                candidates = batch.get("candidates") or []
                created_at = str(batch.get("createdAt") or "")
                provider = str(batch.get("provider") or "AI")
                batch_id = str(batch.get("batchId") or "")
                accepted = " · 已采用" if record.get("acceptedCandidateId") else ""
                label = (
                    f"{created_at[:19] or batch_id} · {provider} · "
                    f"{len(candidates) if isinstance(candidates, list) else 0}张{accepted}"
                )
                self.history_combo.addItem(label, record)
                if batch_id == selected_batch_id:
                    selected_index = self.history_combo.count() - 1
            self.history_combo.setCurrentIndex(selected_index)
        finally:
            self._history_guard = False

    def _history_changed(self, *_args) -> None:
        if self._history_guard:
            return
        record = self.history_combo.currentData()
        if not isinstance(record, Mapping):
            self._clear_candidates()
            self._show_current_target_image()
            return
        batch_raw = record.get("batch") or {}
        try:
            batch = OpenAIImageBatch.from_dict(batch_raw)
        except (TypeError, ValueError) as exc:
            self._set_status(f"历史候选批次无法读取：{exc}", error=True)
            return
        if self.target is None or batch.scene_hash != self.target.target_hash:
            self._set_status("历史批次与当前目标结构不一致，不能载入。", error=True)
            return
        self._show_batch(batch, history=True)

    def _target_changed(
        self,
        *_args,
        reset_candidates: bool = True,
    ) -> None:
        target_id = str(self.target_combo.currentData() or "")
        try:
            self.target = self.result.visual_target(target_id)
        except ValueError:
            self.target = None
        if reset_candidates:
            self._clear_candidates()
        if self.target is None:
            self.scene_label.setText("尚未选择生成目标")
            self.brief_output.clear()
            self.review_title.setText("候选图人工核验")
            self.generate_button.setEnabled(False)
            self.view_accepted_button.setEnabled(False)
            return
        self.scene_label.setText(
            f"当前目标：{self.target.title}｜Hash {self.target.target_hash[:16]}"
        )
        self.brief_output.setPlainText(self.target.prompt)
        self.review_title.setText(f"效果图预览｜{self.target.title}")
        self.generate_button.setText(f"生成：{self.target.title}")
        self.generate_button.setEnabled(True)
        self._refresh_history_combo()
        self._show_current_target_image()
        if reset_candidates:
            self._set_status(
                f"已选择“{self.target.title}”；本次只生成这个目标。",
                error=False,
            )

    def _clear_candidates(self) -> None:
        self.batch = None
        self.candidate_combo.clear()
        self.candidate_combo.setEnabled(False)
        self.accept_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.metadata_output.clear()
        self.preview_label.setPixmap(QPixmap())

    def _current_bound_image_path(self) -> str:
        if self.target is None:
            return ""
        accepted = self._accepted_for_target(self.target.target_id)
        if accepted is not None:
            return str(accepted.get("imagePath") or "")
        return self.target.image_path

    def _show_current_target_image(self) -> None:
        path = self._current_bound_image_path()
        self.view_accepted_button.setEnabled(False)
        if not path:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(
                "当前目标尚未采用效果图\n请在左侧生成候选图并人工采用"
            )
            return
        loaded = self._show_image_path(
            Path(path),
            f"已采用效果图无法加载：{path}",
        )
        self.view_accepted_button.setEnabled(loaded)

    def view_accepted_image(self) -> None:
        if self.target is None:
            return
        path = self._current_bound_image_path()
        if not path or not Path(path).is_file():
            self._set_status("当前目标没有可查看的已采用效果图。", error=True)
            return
        try:
            dialog = ImagePreviewDialog(
                replace(self.target, image_path=path),
                self,
            )
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        dialog.exec()

    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    def active_provider(self) -> ImageProvider:
        index = self.provider_combo.currentIndex()
        if not 0 <= index < len(self.providers):
            index = 0
        self.provider = self.providers[index]
        return self.provider

    def _provider_changed(self, *_args) -> None:
        provider = self.active_provider()
        requires_api_key = bool(getattr(provider, "requires_api_key", True))
        supports_login = bool(getattr(provider, "supports_login", False))
        self.api_key_edit.setVisible(requires_api_key)
        if self.api_key_label is not None:
            self.api_key_label.setVisible(requires_api_key)
        self.login_button.setVisible(supports_login)
        self.test_button.setText("检查登录" if supports_login else "测试连接")
        if supports_login:
            agent_model = str(getattr(provider, "agent_model", "Codex"))
            self.model_label.setText(f"{agent_model} + ImageGen")
            self.credentials_note.setText(
                '使用本机 Codex 的 <a href="https://learn.chatgpt.com/docs/auth">ChatGPT 登录</a>和会员套餐额度；不需要填写 API Key。'
            )
            self._set_status(
                "默认使用 Codex Pro。请先检查登录；未登录时点击“登录 Codex”。",
                error=False,
            )
        else:
            self.model_label.setText(DEFAULT_OPENAI_IMAGE_MODEL)
            self.credentials_note.setText(
                '备用模式：需要在 <a href="https://platform.openai.com/api-keys">OpenAI API 平台</a>创建密钥并单独充值 API 额度。'
            )
            self._set_status(
                "当前为 OpenAI API 单独计费模式，API Key 仅保留在本次软件会话。",
                error=False,
            )

    def login_codex(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        provider = self.active_provider()
        if not bool(getattr(provider, "supports_login", False)):
            self._set_status("当前图片 Provider 不支持 ChatGPT 登录。", error=True)
            return
        worker = CodexLoginWorker(provider, self)
        worker.succeeded.connect(self._connection_succeeded)
        worker.failed.connect(self._request_failed)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        self._set_busy(True, "正在打开 ChatGPT 登录，请在浏览器完成授权……")
        worker.start()

    def test_connection(self) -> None:
        if not self._ready_for_request():
            return
        worker = OpenAIConnectionWorker(
            self.active_provider(), self._provider_credential(), self
        )
        worker.succeeded.connect(self._connection_succeeded)
        worker.failed.connect(self._request_failed)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        self._set_busy(True, "正在检查 AI 连接……")
        worker.start()

    def generate(self) -> None:
        if not self._ready_for_request():
            return
        try:
            control_path = self._render_control_image()
            scene = EquipmentScene.from_dict(self.scene_snapshot)
            request = prepare_openai_image_request(
                scene,
                self.result,
                control_image_path=control_path,
                output_root=self.output_root,
                size=self.size_combo.currentText(),
                quality=self.quality_combo.currentText(),
                candidate_count=self.count_spin.value(),
                target_id=self.target.target_id if self.target else "",
            )
        except (OSError, ValueError, OpenAIImageError) as exc:
            self._set_status(str(exc), error=True)
            return
        worker = OpenAIImageWorker(
            self.active_provider(), request, self._provider_credential(), self
        )
        worker.succeeded.connect(self._generation_succeeded)
        worker.failed.connect(self._request_failed)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        self._set_busy(True, "正在调用 AI 生成候选图，请稍候……")
        worker.start()

    def _ready_for_request(self) -> bool:
        if self._worker is not None and self._worker.isRunning():
            return False
        provider = self.active_provider()
        if bool(getattr(provider, "requires_api_key", True)) and not self.api_key():
            self._set_status("请先输入 OpenAI API Key。", error=True)
            return False
        if not self.result.can_generate_ai:
            self._set_status("当前设备方案未通过逻辑门禁。", error=True)
            return False
        if self.target is None:
            self._set_status("请先在AI效果图窗口选择整机或一个设备模块。", error=True)
            return False
        return True

    def _provider_credential(self) -> str:
        provider = self.active_provider()
        return self.api_key() if bool(getattr(provider, "requires_api_key", True)) else ""

    def _render_control_image(self) -> Path:
        control_dir = self.output_root / "_controls"
        control_dir.mkdir(parents=True, exist_ok=True)
        target_hash = self.target.target_hash if self.target else self.result.scene_hash
        control_svg = self.target.control_svg if self.target else self.result.svg
        path = control_dir / f"{target_hash}.png"
        renderer = QSvgRenderer(QByteArray(control_svg.encode("utf-8")))
        if not renderer.isValid():
            raise OpenAIImageError("当前结构 SVG 无法转换为 AI 输入图。")
        width, height = map(int, self.size_combo.currentText().split("x", 1))
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        source_size = renderer.defaultSize()
        if source_size.width() <= 0 or source_size.height() <= 0:
            raise OpenAIImageError("当前结构 SVG 尺寸无效。")
        scale = min(width / source_size.width(), height / source_size.height())
        target_width = source_size.width() * scale
        target_height = source_size.height() * scale
        target = QRectF(
            (width - target_width) / 2,
            (height - target_height) / 2,
            target_width,
            target_height,
        )
        painter = QPainter(image)
        try:
            renderer.render(painter, target)
        finally:
            painter.end()
        if not image.save(str(path), "PNG"):
            raise OpenAIImageError(f"无法保存 AI 结构控制图：{path}")
        return path

    def _connection_succeeded(self, model_id: str) -> None:
        provider = self.active_provider()
        if bool(getattr(provider, "supports_login", False)):
            self._set_status(model_id, error=False)
        else:
            self._set_status(
                f"OpenAI API 连接正常，已识别模型：{model_id}", error=False
            )

    def _generation_succeeded(self, batch: OpenAIImageBatch) -> None:
        expected_hash = self.target.target_hash if self.target else self.result.scene_hash
        if batch.scene_hash != expected_hash:
            self._request_failed("Provider 返回的批次目标哈希不匹配，候选图已拒绝。")
            return
        target_payload = self._current_target_payload(batch.scene_hash)
        record = {
            "schemaVersion": "project-ai-image-batch/v1",
            "projectId": self.project_id,
            "generationTarget": target_payload,
            "batch": batch.to_dict(),
        }
        self.batch_records = [
            value
            for value in self.batch_records
            if self._record_batch_id(value) != batch.batch_id
        ]
        self.batch_records.append(record)
        self.generated_batch_records.append(record)
        self.batch_records_changed.emit(self.project_batch_records())
        self._refresh_history_combo(selected_batch_id=batch.batch_id)
        self._show_batch(batch, history=False)
        self._set_status(
            f"{batch.provider} 已生成 {len(batch.candidates)} 张候选图；"
            "批次已登记到当前项目，请按工程逻辑逐项人工核验。",
            error=False,
        )

    def _show_batch(self, batch: OpenAIImageBatch, *, history: bool) -> None:
        self.batch = batch
        self.accepted_selection = None
        self.candidate_combo.clear()
        for index, candidate in enumerate(batch.candidates, start=1):
            suffix = "" if candidate.image_path.is_file() else " · 文件缺失"
            self.candidate_combo.addItem(
                f"候选 {index}{suffix}",
                str(candidate.image_path),
            )
        self.candidate_combo.setEnabled(bool(batch.candidates))
        self.accept_button.setEnabled(
            bool(batch.candidates and batch.candidates[0].image_path.is_file())
        )
        self.open_folder_button.setEnabled(batch.output_dir.is_dir())
        self.metadata_output.setPlainText(
            json.dumps(batch.to_dict(), ensure_ascii=False, indent=2)
        )
        self._show_candidate(0)
        if history:
            self._set_status(
                f"已载入当前项目历史批次 {batch.batch_id}；采用前仍需人工核验。",
                error=False,
            )

    def _current_target_payload(self, fallback_hash: str) -> dict[str, str]:
        if self.target is not None:
            return {
                "targetId": self.target.target_id,
                "targetKind": self.target.target_kind,
                "targetHash": self.target.target_hash,
                "title": self.target.title,
            }
        return {
            "targetId": "overview",
            "targetKind": "overview",
            "targetHash": fallback_hash,
            "title": "整机设备总览",
        }

    def _request_failed(self, message: str) -> None:
        self._set_status(message or "OpenAI 请求失败。", error=True)

    def _worker_finished(self) -> None:
        self._set_busy(False)
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.target_combo.setEnabled(not busy)
        self.history_combo.setEnabled(not busy)
        self.provider_combo.setEnabled(not busy and len(self.providers) > 1)
        self.api_key_edit.setEnabled(not busy)
        self.size_combo.setEnabled(not busy)
        self.quality_combo.setEnabled(not busy)
        self.count_spin.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        self.test_button.setEnabled(not busy)
        self.generate_button.setEnabled(not busy)
        if message:
            self._set_status(message, error=False)

    def _show_candidate(self, index: int) -> None:
        if self.batch is None or not 0 <= index < len(self.batch.candidates):
            self.accept_button.setEnabled(False)
            return
        path = self.batch.candidates[index].image_path
        loaded = self._show_image_path(path, f"候选图无法加载：{path}")
        self.accept_button.setEnabled(loaded)

    def _show_image_path(self, path: Path, error_text: str) -> bool:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview_label.setText(error_text)
            self.preview_label.setPixmap(QPixmap())
            return False
        self.preview_label.setText("")
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return True

    def accept_current(self) -> None:
        if self.batch is None:
            return
        index = self.candidate_combo.currentIndex()
        if not 0 <= index < len(self.batch.candidates):
            return
        candidate = self.batch.candidates[index]
        if not candidate.image_path.is_file():
            self._set_status("当前候选图文件已缺失，不能采用。", error=True)
            return
        target_payload = self._current_target_payload(self.batch.scene_hash)
        accepted_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "schemaVersion": "accepted-ai-image/v2",
            "sceneHash": self.result.scene_hash,
            "generationTarget": target_payload,
            "batchId": self.batch.batch_id,
            "provider": self.batch.provider,
            "model": self.batch.model,
            "candidate": candidate.to_dict(),
            "acceptedAt": accepted_at,
            "reviewStatus": "human-accepted",
        }
        path = self.batch.output_dir / "accepted.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        self.accepted_selection = {
            **target_payload,
            "sceneHash": self.result.scene_hash,
            "batchId": self.batch.batch_id,
            "provider": self.batch.provider,
            "model": self.batch.model,
            "candidateId": candidate.candidate_id,
            "imagePath": str(candidate.image_path),
            "sha256": candidate.sha256,
            "manifestPath": str(self.batch.manifest_path),
            "acceptedAt": accepted_at,
            "reviewStatus": "human-accepted",
        }
        self.accepted_selections = [
            value
            for value in self.accepted_selections
            if value.get("targetId") != target_payload["targetId"]
        ]
        self.accepted_selections.append(dict(self.accepted_selection))
        for record in self.batch_records:
            if self._record_batch_id(record) == self.batch.batch_id:
                record["acceptedCandidateId"] = candidate.candidate_id
                record["acceptedAt"] = accepted_at
                break
        self.batch_records_changed.emit(self.project_batch_records())
        self._refresh_history_combo(selected_batch_id=self.batch.batch_id)
        target_index = self.target_combo.findData(target_payload["targetId"])
        if target_index >= 0 and self.target is not None:
            self.target_combo.setItemText(
                target_index,
                self._target_combo_text(self.target),
            )
        self.view_accepted_button.setEnabled(True)
        self._set_status(
            f"已采用“{target_payload['title']}”候选图并记录来源；"
            f"可继续选择其他模块，关闭后统一回写 {len(self.accepted_selections)} 个目标。",
            error=False,
        )

    def open_output_folder(self) -> None:
        if self.batch is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.batch.output_dir)))

    def _set_status(self, text: str, *, error: bool) -> None:
        if not hasattr(self, "status_label"):
            return
        self.status_label.setStyleSheet(
            (
                "color: #9E1B20; background: #FFF1F1; padding: 7px;"
                if error
                else "color: #276738; background: #EDF8F0; padding: 7px;"
            )
        )
        self.status_label.setText(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.batch is not None:
            self._show_candidate(self.candidate_combo.currentIndex())
        else:
            self._show_current_target_image()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._set_status("AI 请求仍在运行，请等待完成后再关闭。", error=True)
            event.ignore()
            return
        super().closeEvent(event)


__all__ = [
    "CodexLoginWorker",
    "DEFAULT_AI_OUTPUT_ROOT",
    "OpenAIConnectionWorker",
    "OpenAIImageDialog",
    "OpenAIImageWorker",
]

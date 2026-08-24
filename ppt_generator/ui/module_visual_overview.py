"""Large read-only gallery for reviewing overview and module renderings."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..no_cad_scheme import VisualGenerationTarget


THUMBNAIL_SIZE = QSize(720, 440)


def _read_pixmap(path: str, maximum_size: QSize | None = None) -> QPixmap:
    """Read an oriented image, optionally decoding only a display-sized copy."""
    image_path = Path(path)
    if not image_path.is_file():
        return QPixmap()
    reader = QImageReader(str(image_path))
    reader.setAutoTransform(True)
    if maximum_size is not None:
        source_size = reader.size()
        if source_size.isValid():
            source_size.scale(
                maximum_size,
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            reader.setScaledSize(source_size)
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class ClickableImageLabel(QLabel):
    """Image label that exposes one explicit left-click signal."""

    clicked = Signal()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ModuleVisualCard(QFrame):
    """One industrial section card in the visual overview."""

    open_requested = Signal(str)

    def __init__(
        self,
        target: VisualGenerationTarget,
        ordinal: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.target = target
        self.target_id = target.target_id
        self._thumbnail = _read_pixmap(target.image_path, THUMBNAIL_SIZE)
        self.has_image = not self._thumbnail.isNull()
        self.setObjectName("moduleVisualCard")
        self.setProperty("targetId", target.target_id)
        self.setMinimumSize(330, 330)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(8)

        section_name = "整机总览" if target.target_kind == "overview" else "设备模块"
        self.header_label = QLabel(
            f"{ordinal:02d}  {section_name}｜{target.title}"
        )
        self.header_label.setObjectName("moduleVisualCardHeader")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        self.image_label = ClickableImageLabel()
        self.image_label.setObjectName("moduleVisualCardImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(225)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.image_label.setEnabled(self.has_image)
        self.image_label.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self.has_image
            else Qt.CursorShape.ArrowCursor
        )
        self.image_label.clicked.connect(
            lambda: self.open_requested.emit(self.target_id)
        )
        layout.addWidget(self.image_label, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(10, 0, 10, 0)
        self.status_label = QLabel()
        self.status_label.setObjectName("moduleVisualCardStatus")
        footer.addWidget(self.status_label, 1)
        self.open_button = QPushButton("查看大图")
        self.open_button.setEnabled(self.has_image)
        self.open_button.clicked.connect(
            lambda: self.open_requested.emit(self.target_id)
        )
        footer.addWidget(self.open_button)
        layout.addLayout(footer)

        self._update_content()

    def _update_content(self) -> None:
        if self.has_image:
            self.status_label.setText("已采用 · 点击图片查看原图")
            self.status_label.setProperty("state", "accepted")
            self._render_thumbnail()
            return
        if self.target.image_path:
            self.image_label.setText("图片文件不可用\n请重新采用该模块效果图")
            self.status_label.setText("图片不可用")
            self.status_label.setProperty("state", "missing")
        else:
            self.image_label.setText("尚未采用效果图\n请先生成并人工采用")
            self.status_label.setText("待生成 / 待采用")
            self.status_label.setProperty("state", "pending")

    def _render_thumbnail(self) -> None:
        if self._thumbnail.isNull():
            return
        available = self.image_label.size() - QSize(18, 18)
        if available.width() <= 0 or available.height() <= 0:
            return
        self.image_label.setPixmap(
            self._thumbnail.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._render_thumbnail()


class ImagePreviewDialog(QDialog):
    """On-demand original-resolution viewer with basic zoom controls."""

    def __init__(
        self,
        target: VisualGenerationTarget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.target = target
        self._source = _read_pixmap(target.image_path)
        if self._source.isNull():
            raise ValueError(f"图片无法读取：{target.image_path}")
        self._fit_to_window = True
        self._zoom = 1.0
        self.setWindowTitle(f"效果图大图｜{target.title}")
        self.setMinimumSize(900, 620)
        self.resize(1400, 880)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(9)
        heading = QHBoxLayout()
        title = QLabel(target.title)
        title.setObjectName("imagePreviewTitle")
        heading.addWidget(title)
        heading.addStretch()
        fit_button = QPushButton("适应窗口")
        fit_button.clicked.connect(self.fit_to_window)
        heading.addWidget(fit_button)
        actual_button = QPushButton("100%")
        actual_button.clicked.connect(self.actual_size)
        heading.addWidget(actual_button)
        zoom_out_button = QPushButton("－")
        zoom_out_button.clicked.connect(lambda: self.change_zoom(0.8))
        heading.addWidget(zoom_out_button)
        zoom_in_button = QPushButton("＋")
        zoom_in_button.clicked.connect(lambda: self.change_zoom(1.25))
        heading.addWidget(zoom_in_button)
        root.addLayout(heading)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel()
        self.image_label.setObjectName("imagePreviewCanvas")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        root.addWidget(self.scroll_area, 1)

        path_label = QLabel(target.image_path)
        path_label.setObjectName("imagePreviewPath")
        path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(path_label)
        self._render_image()

    def fit_to_window(self) -> None:
        self._fit_to_window = True
        self._render_image()

    def actual_size(self) -> None:
        self._fit_to_window = False
        self._zoom = 1.0
        self._render_image()

    def change_zoom(self, factor: float) -> None:
        if self._fit_to_window:
            viewport = self.scroll_area.viewport().size() - QSize(24, 24)
            fitted = self._source.size()
            fitted.scale(viewport, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = max(0.1, fitted.width() / self._source.width())
        self._fit_to_window = False
        self._zoom = min(4.0, max(0.1, self._zoom * factor))
        self._render_image()

    def _render_image(self) -> None:
        if self._fit_to_window:
            target_size = self.scroll_area.viewport().size() - QSize(24, 24)
            target_size.setWidth(max(1, target_size.width()))
            target_size.setHeight(max(1, target_size.height()))
        else:
            target_size = QSize(
                max(1, int(self._source.width() * self._zoom)),
                max(1, int(self._source.height() * self._zoom)),
            )
        pixmap = self._source.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit_to_window:
            self._render_image()


class ModuleVisualOverviewDialog(QDialog):
    """Large adaptive mosaic for all scene-owned visual targets."""

    def __init__(
        self,
        targets: Iterable[VisualGenerationTarget],
        *,
        project_name: str = "",
        product_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.targets = tuple(targets)
        self.project_name = project_name
        self.product_name = product_name
        self.cards: list[ModuleVisualCard] = []
        self._column_count = 0
        self.setObjectName("moduleVisualOverviewDialog")
        self.setWindowTitle("设备方案 · 模块效果总览")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(680, 560)
        self.resize(1560, 920)
        self._setup_ui()
        self.set_targets(self.targets)

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog#moduleVisualOverviewDialog { background: #EEF2F6; }
            QFrame#moduleVisualOverviewHeader {
                background: #FFFFFF; border: 1px solid #D7E0EA; border-radius: 8px;
            }
            QLabel#moduleVisualOverviewTitle {
                color: #12365A; font-size: 24px; font-weight: 800;
            }
            QLabel#moduleVisualOverviewSubtitle { color: #607286; font-size: 13px; }
            QFrame#moduleVisualCard {
                background: #FFFFFF; border: 1px solid #AFC0D2; border-radius: 6px;
            }
            QLabel#moduleVisualCardHeader {
                background: #123D69; color: #FFFFFF; border: none;
                border-top-left-radius: 5px; border-top-right-radius: 5px;
                padding: 9px 12px; font-size: 14px; font-weight: 800;
            }
            QLabel#moduleVisualCardImage {
                background: #F7F9FB; color: #7A8794; border: none;
                padding: 8px; font-size: 14px; font-weight: 600;
            }
            QLabel#moduleVisualCardImage:hover { background: #EDF4FA; }
            QLabel#moduleVisualCardStatus[state="accepted"] { color: #147A4A; font-weight: 700; }
            QLabel#moduleVisualCardStatus[state="pending"] { color: #8A6414; font-weight: 700; }
            QLabel#moduleVisualCardStatus[state="missing"] { color: #A52A2A; font-weight: 700; }
            QLabel#imagePreviewTitle { color: #12365A; font-size: 19px; font-weight: 800; }
            QLabel#imagePreviewCanvas { background: #202832; }
            QLabel#imagePreviewPath { color: #66788A; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("moduleVisualOverviewHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        title_box = QVBoxLayout()
        title = QLabel("设备方案模块效果总览")
        title.setObjectName("moduleVisualOverviewTitle")
        title_box.addWidget(title)
        project_text = self.project_name or "未命名方案"
        product_text = self.product_name or "产品待确认"
        subtitle = QLabel(
            f"{project_text}｜{product_text}｜整机与各模块独立绑定，点击已采用图片查看大图"
        )
        subtitle.setObjectName("moduleVisualOverviewSubtitle")
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box, 1)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("moduleVisualOverviewSubtitle")
        header_layout.addWidget(self.summary_label)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        header_layout.addWidget(close_button)
        root.addWidget(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.viewport().installEventFilter(self)
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setContentsMargins(2, 2, 2, 2)
        self.gallery_layout.setHorizontalSpacing(10)
        self.gallery_layout.setVerticalSpacing(10)
        self.gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.scroll_area.setWidget(self.gallery_widget)
        root.addWidget(self.scroll_area, 1)

    def set_targets(
        self,
        targets: Iterable[VisualGenerationTarget],
    ) -> None:
        self.targets = tuple(targets)
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = []
        for ordinal, target in enumerate(self.targets, start=1):
            card = ModuleVisualCard(target, ordinal, self.gallery_widget)
            card.open_requested.connect(self.open_target)
            self.cards.append(card)
        accepted = sum(card.has_image for card in self.cards)
        self.summary_label.setText(
            f"目标 {len(self.cards)} 个｜已采用 {accepted} 个｜待完成 {len(self.cards) - accepted} 个"
        )
        self._column_count = 0
        self._relayout_cards()

    def _desired_columns(self) -> int:
        width = self.scroll_area.viewport().width()
        if width >= 1250:
            return 3
        if width >= 760:
            return 2
        return 1

    def _relayout_cards(self) -> None:
        columns = self._desired_columns()
        if columns == self._column_count and self.gallery_layout.count() == len(self.cards):
            return
        while self.gallery_layout.count():
            self.gallery_layout.takeAt(0)
        for column in range(3):
            self.gallery_layout.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.cards):
            self.gallery_layout.addWidget(card, index // columns, index % columns)
        self._column_count = columns

    def open_target(self, target_id: str) -> None:
        target = next(
            (value for value in self.targets if value.target_id == target_id),
            None,
        )
        if target is None or not target.image_path:
            return
        try:
            dialog = ImagePreviewDialog(target, self)
        except ValueError as exc:
            QMessageBox.warning(self, "无法查看大图", str(exc))
            return
        dialog.exec()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout_cards()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._relayout_cards()
        return super().eventFilter(watched, event)


__all__ = [
    "ImagePreviewDialog",
    "ModuleVisualCard",
    "ModuleVisualOverviewDialog",
]

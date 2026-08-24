"""Read-only current-slide preview widgets."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SlideCanvas(QLabel):
    """A label that keeps a source image fitted without losing aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_source = QPixmap()
        self._navigation_source = QPixmap()
        self._source = QPixmap()
        self.setObjectName("slideCanvas")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.loading_overlay = QLabel(self)
        self.loading_overlay.setObjectName("slideLoadingOverlay")
        self.loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_overlay.setWordWrap(True)
        self.loading_overlay.hide()
        self.set_message("请在“方案模块”中选择一个具体页面")

    def set_message(self, message: str) -> None:
        self._base_source = QPixmap()
        self._navigation_source = QPixmap()
        self._source = QPixmap()
        self.clear()
        self.setText(message)
        self.hide_loading()

    def set_image_data(self, data: bytes) -> bool:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data, "PNG"):
            return False
        self._base_source = pixmap.copy()
        self._navigation_source = QPixmap()
        self._source = pixmap.copy()
        self.setText("")
        self._fit_image()
        return True

    def _clean_navigation_source(self) -> QPixmap:
        """Remove the source image's old navigation and fixed shadow once."""
        slide_width_inches = 13.333333
        slide_height_inches = 7.5
        pixmap = self._base_source.copy()
        scale_x = pixmap.width() / slide_width_inches
        scale_y = pixmap.height() / slide_height_inches

        logo_left = int(round(11.60 * scale_x))
        logo_height = min(pixmap.height(), int(round(0.80 * scale_y)))
        logo_image = self._base_source.toImage().copy(
            logo_left,
            0,
            max(0, pixmap.width() - logo_left),
            logo_height,
        )
        for logo_y in range(logo_image.height()):
            for logo_x in range(logo_image.width()):
                color = logo_image.pixelColor(logo_x, logo_y)
                channels = (color.red(), color.green(), color.blue())
                if min(channels) > 165 and max(channels) - min(channels) < 18:
                    color.setAlpha(0)
                    logo_image.setPixelColor(logo_x, logo_y, color)

        cleaned_image = pixmap.toImage()
        cleanup_start = int(round(0.80 * scale_y))
        cleanup_end = min(
            cleaned_image.height(),
            int(round(1.22 * scale_y)),
        )
        for cleanup_y in range(cleanup_start, cleanup_end):
            for cleanup_x in range(cleaned_image.width()):
                color = cleaned_image.pixelColor(cleanup_x, cleanup_y)
                channels = (color.red(), color.green(), color.blue())
                if min(channels) > 150 and max(channels) - min(channels) < 12:
                    cleaned_image.setPixelColor(
                        cleanup_x,
                        cleanup_y,
                        QColor("#FFFFFF"),
                    )
        pixmap = QPixmap.fromImage(cleaned_image)
        painter = QPainter(pixmap)
        painter.fillRect(
            QRectF(0, 0, pixmap.width(), 1.02 * scale_y),
            QColor("#FFFFFF"),
        )
        painter.drawPixmap(logo_left, 0, QPixmap.fromImage(logo_image))
        painter.end()
        return pixmap

    def apply_navigation_overlay(
        self,
        items: list[str],
        active_index: int | None,
        height_inches: float,
        active_background: str,
        font_size_points: float,
    ) -> bool:
        """Draw a fast navigation approximation over the current preview image."""
        names = [str(item).strip() for item in items if str(item).strip()]
        if self._base_source.isNull() or not names:
            return False

        slide_width_inches = 13.333333
        slide_height_inches = 7.5
        navigation_left_inches = 0.0
        navigation_right_inches = 11.55
        if self._navigation_source.isNull():
            self._navigation_source = self._clean_navigation_source()
        pixmap = self._navigation_source.copy()
        scale_x = pixmap.width() / slide_width_inches
        scale_y = pixmap.height() / slide_height_inches
        navigation_height = max(0.42, min(float(height_inches), 0.72)) * scale_y
        navigation_left = navigation_left_inches * scale_x
        navigation_right = navigation_right_inches * scale_x
        cell_width = (navigation_right - navigation_left) / len(names)

        painter = QPainter(pixmap)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        active_color = QColor(active_background)
        if not active_color.isValid():
            active_color = QColor("#FFFFFF")
        valid_active_index = (
            active_index
            if active_index is not None and 0 <= active_index < len(names)
            else None
        )
        if valid_active_index is not None:
            active_left = navigation_left + valid_active_index * cell_width
            painter.fillRect(
                QRectF(active_left, 0, cell_width, navigation_height),
                active_color,
            )

        separator_pen = QPen(QColor("#D3D9DE"))
        separator_pen.setWidthF(max(1.0, scale_x * 0.008))
        painter.setPen(separator_pen)
        for index in range(1, len(names)):
            separator_x = navigation_left + index * cell_width
            painter.drawLine(
                int(round(separator_x)),
                int(round(0.13 * scale_y)),
                int(round(separator_x)),
                int(round(max(0.13 * scale_y, navigation_height - 0.11 * scale_y))),
            )

        underline_height = max(2.0, 0.035 * scale_y)
        painter.fillRect(
            QRectF(
                navigation_left,
                navigation_height - underline_height,
                pixmap.width() - navigation_left,
                underline_height,
            ),
            QColor("#D3D9DE"),
        )
        if valid_active_index is not None:
            painter.fillRect(
                QRectF(
                    navigation_left + valid_active_index * cell_width,
                    navigation_height - underline_height,
                    cell_width,
                    underline_height,
                ),
                QColor("#C90000"),
            )

        font = QFont("Microsoft YaHei")
        font.setBold(True)
        font.setPixelSize(
            max(11, int(round(float(font_size_points) * scale_y / 72.0)))
        )
        painter.setFont(font)
        for index, name in enumerate(names):
            if index == valid_active_index:
                text_color = (
                    QColor("#FFFFFF")
                    if active_color.lightness() < 128
                    else QColor("#C90000")
                )
            else:
                text_color = QColor("#515960")
            painter.setPen(text_color)
            painter.drawText(
                QRectF(
                    navigation_left + index * cell_width,
                    0,
                    cell_width,
                    navigation_height - 0.035 * scale_y,
                ),
                Qt.AlignmentFlag.AlignCenter,
                name,
            )

        painter.end()

        self._source = pixmap
        self.setText("")
        self._fit_image()
        return True

    @property
    def has_image(self) -> bool:
        return not self._source.isNull()

    def show_loading(self, message: str) -> None:
        self.loading_overlay.setText(message)
        self.loading_overlay.setGeometry(self.rect())
        self.loading_overlay.show()
        self.loading_overlay.raise_()

    def hide_loading(self) -> None:
        self.loading_overlay.hide()

    def _fit_image(self) -> None:
        if self._source.isNull():
            return
        available = self.contentsRect().size()
        if available.width() <= 0 or available.height() <= 0:
            return
        self.setPixmap(
            self._source.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_image()
        self.loading_overlay.setGeometry(self.rect())


class SlidePreviewPane(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_module_id = ""
        self.current_slide_id = ""
        self._image_kind = "none"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 14, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("当前页展示")
        title.setObjectName("previewTitle")
        header.addWidget(title)
        header.addStretch()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.refresh_button.setEnabled(False)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.page_label = QLabel("未选择页面")
        self.page_label.setObjectName("previewPageLabel")
        self.page_label.setWordWrap(True)
        layout.addWidget(self.page_label)

        self.canvas = SlideCanvas()
        layout.addWidget(self.canvas, 1)

        self.status_label = QLabel("预览为只读画面，正式内容仍在左侧结构化编辑。")
        self.status_label.setObjectName("previewStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_selection(
        self,
        module_id: str,
        slide_id: str,
        module_name: str,
        slide_name: str,
    ) -> None:
        self.current_module_id = module_id
        self.current_slide_id = slide_id
        self.page_label.setText(f"{module_name}  /  {slide_name}")
        self.refresh_button.setEnabled(bool(slide_id))

    def clear_selection(self, message: str = "请选择模块中的具体页面") -> None:
        self.current_module_id = ""
        self.current_slide_id = ""
        self.page_label.setText("未选择页面")
        self.refresh_button.setEnabled(False)
        self.canvas.set_message(message)
        self._image_kind = "none"
        self.status_label.setText("预览为只读画面，正式内容仍在左侧结构化编辑。")

    def set_loading(self, target_name: str = "") -> None:
        self.refresh_button.setEnabled(False)
        target = f"“{target_name}”" if target_name else "当前页面"
        if self.canvas.has_image:
            if self._image_kind == "base":
                source = "模板页面"
            elif self._image_kind == "instant":
                self.canvas.hide_loading()
                return
            else:
                source = "上一次画面"
            self.canvas.show_loading(
                f"正在加载{target}\n\n当前显示：{source}"
            )
            self.status_label.setText(
                f"正在加载{target}，完成后会自动替换当前画面。"
            )
        else:
            self.canvas.set_message("正在生成当前页预览…")
            self.canvas.show_loading(f"正在加载{target}")
            self.status_label.setText(
                "正在渲染当前页并调用 PowerPoint/WPS，请稍候。"
            )

    def apply_navigation_overlay(
        self,
        items: list[str],
        active_index: int | None,
        height_inches: float,
        active_background: str,
        font_size_points: float,
    ) -> bool:
        if not self.canvas.apply_navigation_overlay(
            items,
            active_index,
            height_inches,
            active_background,
            font_size_points,
        ):
            return False
        self._image_kind = "instant"
        self.canvas.hide_loading()
        self.status_label.setText(
            f"导航即时预览：高度 {height_inches:.2f} in，字号 "
            f"{font_size_points:g} pt；后台完成后自动替换为Office真实预览。"
        )
        return True

    def set_base_preview(
        self,
        data: bytes,
        source_slide: int,
        target_name: str,
    ) -> None:
        if not self.canvas.set_image_data(data):
            return
        self._image_kind = "base"
        self.canvas.show_loading(
            f"模板第 {source_slide} 页\n\n正在加载“{target_name}”的实时内容"
        )
        self.status_label.setText(
            f"已显示模板第 {source_slide} 页 · 实时文字与图片正在后台加载"
        )

    def set_preview(
        self,
        data: bytes,
        backend: str,
        page_number: int,
        *,
        cached: bool = False,
    ) -> None:
        if not self.canvas.set_image_data(data):
            self.set_error("预览图片读取失败")
            return
        self._image_kind = "live"
        self.canvas.hide_loading()
        self.refresh_button.setEnabled(True)
        source = "内存缓存" if cached else f"{backend} 导出"
        self.status_label.setText(f"最终PPT第 {page_number} 页 · {source} · 只读预览")

    def set_error(self, message: str) -> None:
        self.canvas.hide_loading()
        if self.canvas.has_image:
            message += "；当前保留上一次成功画面。"
        else:
            self.canvas.set_message("当前页暂时无法展示")
        self.refresh_button.setEnabled(bool(self.current_slide_id))
        self.status_label.setText(message)

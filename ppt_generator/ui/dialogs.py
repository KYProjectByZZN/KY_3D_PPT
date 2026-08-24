"""Small editors used by the desktop main window."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..project import NavigationItem, PresentationStyle


class TextValueDialog(QDialog):
    def __init__(self, title: str, value: str, max_chars: int | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 420)
        layout = QVBoxLayout(self)
        hint = "支持多行文字"
        if max_chars:
            hint += f"；模板建议不超过 {max_chars} 字"
        layout.addWidget(QLabel(hint))
        self.editor = QPlainTextEdit(value)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def value(self) -> str:
        return self.editor.toPlainText()


class TableValueDialog(QDialog):
    def __init__(
        self,
        title: str,
        value: Any,
        rows: int,
        columns: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(max(720, columns * 150), max(430, rows * 42 + 130))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"固定表格尺寸：{rows} 行 × {columns} 列；样式由 PPT 模板保留"))
        self.table = QTableWidget(rows, columns)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        matrix = value if isinstance(value, list) else []
        for row in range(rows):
            for column in range(columns):
                cell_value = ""
                if row < len(matrix) and isinstance(matrix[row], list) and column < len(matrix[row]):
                    cell_value = str(matrix[row][column])
                self.table.setItem(row, column, QTableWidgetItem(cell_value))
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def value(self) -> list[list[str]]:
        return [
            [
                self.table.item(row, column).text() if self.table.item(row, column) else ""
                for column in range(self.table.columnCount())
            ]
            for row in range(self.table.rowCount())
        ]


class NavigationEditorDialog(QDialog):
    """Edit project navigation labels, order, and template-module ownership."""

    def __init__(
        self,
        navigation_items: list[NavigationItem],
        modules: list[tuple[str, str]],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("编辑顶部导航栏目")
        self.resize(860, 520)
        self._items = deepcopy(navigation_items)
        self._modules = list(modules)
        self._module_names = {key: name for key, name in modules}

        layout = QVBoxLayout(self)
        hint = QLabel(
            "导航支持 1～7 项；同一PPT模块只能属于一个栏目。重新分配时会自动从其它栏目移除。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["导航名称", "包含的PPT模块"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()
        controls.addWidget(self._button("新增", self.add_item))
        controls.addWidget(self._button("重命名", self.rename_item))
        controls.addWidget(self._button("分配模块", self.choose_modules))
        controls.addWidget(self._button("删除", self.delete_item))
        controls.addSpacing(16)
        controls.addWidget(self._button("上移", lambda: self.move_item(-1)))
        controls.addWidget(self._button("下移", lambda: self.move_item(1)))
        controls.addStretch()
        layout.addLayout(controls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_table()

    def _button(self, text: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    def _selected_row(self) -> int:
        row = self.table.currentRow()
        return row if 0 <= row < len(self._items) else -1

    def _refresh_table(self, selected_row: int | None = None) -> None:
        current_row = self._selected_row() if selected_row is None else selected_row
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.name))
            module_names = [
                self._module_names.get(key, key) for key in item.module_keys
            ]
            self.table.setItem(row, 1, QTableWidgetItem("、".join(module_names)))
        if self._items:
            self.table.selectRow(min(max(current_row, 0), len(self._items) - 1))

    def _name_from_user(self, title: str, current: str = "") -> str | None:
        name, accepted = QInputDialog.getText(
            self,
            title,
            "栏目名称（最多10个字符）",
            text=current,
        )
        if not accepted:
            return None
        return name.strip()

    def _validate_name(self, name: str, ignored_row: int = -1) -> None:
        NavigationItem(name).validate()
        if any(
            row != ignored_row and item.name.strip() == name.strip()
            for row, item in enumerate(self._items)
        ):
            raise ValueError(f"导航栏目名称不能重复：{name.strip()}")

    def add_item(self, name: str | None = None) -> None:
        if len(self._items) >= 7:
            QMessageBox.warning(self, "无法新增", "顶部导航最多支持7个栏目。")
            return
        name = self._name_from_user("新增导航栏目") if name is None else name.strip()
        if name is None:
            return
        try:
            self._validate_name(name)
        except ValueError as exc:
            QMessageBox.warning(self, "栏目名称无效", str(exc))
            return
        self._items.append(NavigationItem(name))
        self._refresh_table(len(self._items) - 1)

    def rename_item(self, name: str | None = None) -> None:
        row = self._selected_row()
        if row < 0:
            return
        if name is None:
            name = self._name_from_user("修改导航栏目", self._items[row].name)
        else:
            name = name.strip()
        if name is None:
            return
        try:
            self._validate_name(name, row)
        except ValueError as exc:
            QMessageBox.warning(self, "栏目名称无效", str(exc))
            return
        self._items[row].name = name
        self._refresh_table(row)

    def delete_item(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        if len(self._items) <= 1:
            QMessageBox.warning(self, "无法删除", "顶部导航至少保留1个栏目。")
            return
        self._items.pop(row)
        self._refresh_table(min(row, len(self._items) - 1))

    def move_item(self, offset: int) -> None:
        row = self._selected_row()
        target = row + offset
        if row < 0 or not 0 <= target < len(self._items):
            return
        self._items[row], self._items[target] = self._items[target], self._items[row]
        self._refresh_table(target)

    def set_module_keys(self, row: int, module_keys: list[str]) -> None:
        if not 0 <= row < len(self._items):
            raise IndexError("导航栏目行号无效")
        known_keys = {key for key, _ in self._modules}
        unknown = [key for key in module_keys if key not in known_keys]
        if unknown:
            raise ValueError(f"PPT模块不存在：{unknown[0]}")
        selected = list(dict.fromkeys(module_keys))
        for index, item in enumerate(self._items):
            if index != row:
                item.module_keys = [key for key in item.module_keys if key not in selected]
        self._items[row].module_keys = selected
        self._refresh_table(row)

    def choose_modules(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        picker = QDialog(self)
        picker.setWindowTitle(f"分配PPT模块 · {self._items[row].name}")
        picker.resize(520, 480)
        layout = QVBoxLayout(picker)
        layout.addWidget(QLabel("勾选归属于当前导航栏目的PPT模块："))
        module_list = QListWidget()
        selected_keys = set(self._items[row].module_keys)
        for key, name in self._modules:
            item = QListWidgetItem(f"{name}  ({key})")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if key in selected_keys else Qt.CheckState.Unchecked
            )
            module_list.addItem(item)
        layout.addWidget(module_list, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(picker.accept)
        buttons.rejected.connect(picker.reject)
        layout.addWidget(buttons)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        self.set_module_keys(
            row,
            [
                str(module_list.item(index).data(Qt.ItemDataRole.UserRole))
                for index in range(module_list.count())
                if module_list.item(index).checkState() == Qt.CheckState.Checked
            ],
        )

    def _accept_if_valid(self) -> None:
        try:
            PresentationStyle(navigation_items=deepcopy(self._items)).validate()
        except ValueError as exc:
            QMessageBox.warning(self, "导航配置无效", str(exc))
            return
        self.accept()

    @property
    def navigation_items(self) -> list[NavigationItem]:
        return deepcopy(self._items)

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ppt_generator.auto_solution_application import AutoSolutionApplication
from ppt_generator.auto_solution_repository import JsonAutoSolutionRepository
from ppt_generator.ui.auto_solution_editor import AutoSolutionEditor


class AutoSolutionV2UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_requirement_confirmation_to_candidate_page(self) -> None:
        with TemporaryDirectory() as temporary:
            application = AutoSolutionApplication(
                repository=JsonAutoSolutionRepository(Path(temporary) / "store.json"),
                actor="ui_tester",
            )
            editor = AutoSolutionEditor(application=application)
            editor.resize(1600, 900)
            editor.show()
            requirement = editor.requirement_widget
            requirement.meta_edits["customerName"].setText("界面客户")
            requirement.meta_edits["projectName"].setText("界面外观检测")
            requirement.meta_edits["productName"].setText("冲压壳体")
            requirement.basic_edits["productType"].setText("金属冲压件")
            original = "85×45×12mm不锈钢件，振动盘上料，OK/NG分选，检测划伤和缺口，节拍1.5秒/件。"
            requirement.original_edit.setPlainText(original)

            requirement.parse_requirement()
            self.assertGreater(requirement.suggestion_table.rowCount(), 0)
            self.assertEqual(requirement.original_edit.toPlainText(), original)
            requirement.apply_selected_suggestions()
            self.assertEqual(requirement.original_edit.toPlainText(), original)
            saved = requirement.save_record()
            self.assertIsNotNone(saved)
            self.assertEqual(requirement.record_table.rowCount(), 1)

            requirement.request_candidate_generation()
            self.qt_app.processEvents()
            self.assertEqual(editor.stage_stack.currentIndex(), 2)
            self.assertIsNotNone(editor.candidate_widget.current_candidate)
            self.assertEqual(editor.candidate_widget.station_table.rowCount(), 3)
            self.assertIn(
                "工位数量和相对位置必须严格如下",
                editor.candidate_widget.prompt_edit.toPlainText(),
            )
            self.assertFalse(editor.candidate_widget.image_button.isEnabled())
            editor.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ppt_generator.ui.app import create_application
from ppt_generator.ui.scheme_visual_lab import SchemeVisualLabWidget


class SchemeVisualLabUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = create_application([])

    def test_demo_loads_as_an_independent_review_workspace(self) -> None:
        widget = SchemeVisualLabWidget()
        widget.resize(1600, 820)
        widget.show()
        self.application.processEvents()
        try:
            self.assertIsNotNone(widget.current_result)
            self.assertTrue(widget.preview_widget.renderer().isValid())
            self.assertIn("独立实验", widget.isolation_label.text())
            self.assertIn("layoutHash", widget.layout_output.toPlainText())
            self.assertIn("recipeHash", widget.recipe_output.toPlainText())
            self.assertIn("正向提示词", widget.prompt_output.toPlainText())
            self.assertGreater(widget.checklist_table.rowCount(), 5)
            self.assertFalse(widget.ai_generate_button.isEnabled())
            self.assertTrue(widget.export_svg_button.isEnabled())
        finally:
            widget.close()
            self.application.processEvents()

    def test_invalid_json_reports_inline_without_blocking_dialog(self) -> None:
        widget = SchemeVisualLabWidget()
        try:
            widget.spec_editor.setPlainText("{invalid json")
            widget.generate()
            self.application.processEvents()

            self.assertIsNone(widget.current_result)
            self.assertIn("输入校验失败", widget.status_label.text())
            self.assertFalse(widget.export_svg_button.isEnabled())
            self.assertEqual(widget.checklist_table.rowCount(), 0)
        finally:
            widget.close()


if __name__ == "__main__":
    unittest.main()

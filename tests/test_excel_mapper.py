from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from ppt_generator import (
    ExcelMappingRule,
    MappingTarget,
    apply_excel_mappings,
    detect_header_row,
    load_excel_preview,
    suggest_text_mappings,
)


class ExcelMapperTests(unittest.TestCase):
    def _workbook(self, directory: Path) -> Path:
        path = directory / "mapping.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "方案数据"
        sheet.append(["字段", "值", "说明", "状态"])
        sheet.append(["项目标题", "Excel自动映射测试方案", "测试", "有效"])
        sheet.append([])
        table_rows = [
            ["检测节拍", "30 pcs/min", "工业光源", "LED"],
            ["设备电压", "220V", "工业相机", "面阵"],
            ["设备功率", "2.5kW", "工业镜头", "FA"],
            ["运行环境", "Windows", "数据接口", "MES"],
            ["视觉软件", "Openex", "产品范围", "按样品"],
            ["图片格式", "PNG", "检测输出", "OK/NG"],
            ["数据格式", "CSV", "工作环境", "室内"],
        ]
        for row in table_rows:
            sheet.append(row)
        workbook.save(path)
        return path

    def test_preview_header_and_mapping_application(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            path = self._workbook(Path(temp_dir))
            preview = load_excel_preview(path)
            sheet = preview.sheet("方案数据")

            self.assertEqual(detect_header_row(sheet), 1)
            result = apply_excel_mappings(
                path,
                [
                    ExcelMappingRule("方案数据", "B2", "project_title"),
                    ExcelMappingRule(
                        "方案数据", "A4:D10", "equipment_parameters", mode="table"
                    ),
                ],
                slot_specs={
                    "project_title": {"kind": "text"},
                    "equipment_parameters": {"kind": "table", "rows": 7, "columns": 4},
                },
            )

            self.assertEqual(result.values["project_title"], "Excel自动映射测试方案")
            self.assertEqual(len(result.values["equipment_parameters"]), 7)
            self.assertEqual(result.values["equipment_parameters"][0][0], "检测节拍")

    def test_suggests_adjacent_key_value_mapping(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            path = self._workbook(Path(temp_dir))
            sheet = load_excel_preview(path).sheet("方案数据")

            suggestions = suggest_text_mappings(
                sheet,
                [MappingTarget("project_title", "项目标题")],
            )

            self.assertEqual(len(suggestions), 1)
            self.assertEqual(suggestions[0].source_range, "B2")
            self.assertEqual(suggestions[0].target_slot, "project_title")

    def test_rejects_table_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            path = self._workbook(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "需要 7×4"):
                apply_excel_mappings(
                    path,
                    [ExcelMappingRule("方案数据", "A4:B5", "equipment_parameters", mode="table")],
                    slot_specs={
                        "equipment_parameters": {"kind": "table", "rows": 7, "columns": 4}
                    },
                )


if __name__ == "__main__":
    unittest.main()

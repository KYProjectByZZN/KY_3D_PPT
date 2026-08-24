from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppt_generator.auto_solution_application import AutoSolutionApplication
from ppt_generator.auto_solution_repository import JsonAutoSolutionRepository
from ppt_generator.requirement_management import (
    InspectionRequirement,
    RequirementRecord,
    RequirementSuggestion,
    RuleBasedRequirementParser,
    apply_requirement_suggestions,
)
from ppt_generator.solution_generation import (
    CandidateStation,
    CandidateSolutionGenerator,
    DrawingPromptBuilder,
    DrawingSpecification,
    HistoricalSolutionRetriever,
)


FIXED_TIME = "2026-08-24T10:00:00+08:00"


class AutoSolutionV2Tests(unittest.TestCase):
    def application(self, root: Path, include_demo_history: bool = True) -> AutoSolutionApplication:
        return AutoSolutionApplication(
            repository=JsonAutoSolutionRepository(
                root / "store.json",
                include_demo_history=include_demo_history,
            ),
            clock=lambda: FIXED_TIME,
            actor="test_engineer",
        )

    def test_parser_returns_proposals_and_never_overwrites_manual_or_original(self) -> None:
        record = RequirementRecord(
            id="REQ-ID",
            requirement_no="REQ-20260824-001",
            original_requirement=(
                "金属件尺寸85×45×12mm，不锈钢，振动盘上料，OK/NG分选，"
                "检测划伤、压伤和缺口，节拍1.5秒/件，表面反光。"
            ),
        )
        record.structured_requirement.basic_info.material = "客户指定铝合金"
        original = record.original_requirement

        suggestions = RuleBasedRequirementParser().suggest(record)

        self.assertEqual(record.original_requirement, original)
        material = next(
            value for value in suggestions if value.field_path == "basicInfo.material"
        )
        self.assertEqual(material.current_value, "客户指定铝合金")
        applied = apply_requirement_suggestions(record, suggestions)
        self.assertNotIn("basicInfo.material", applied)
        self.assertEqual(record.structured_requirement.basic_info.material, "客户指定铝合金")
        self.assertEqual(record.structured_requirement.basic_info.size, "85×45×12 mm")
        self.assertEqual(record.structured_requirement.capacity_and_cycle.target_cycle, "1.5 s/件")
        self.assertEqual(record.original_requirement, original)

    def test_requirement_crud_copy_archive_and_version_snapshot(self) -> None:
        with TemporaryDirectory() as temporary:
            app = self.application(Path(temporary), include_demo_history=False)
            record = app.new_requirement()
            record.customer_name = "昆山客户"
            record.project_name = "外观检测线"
            record.product_name = "壳体"
            created = app.save_requirement(record)
            self.assertEqual(created.version, 1)

            created.project_name = "外观检测线（修订）"
            updated = app.save_requirement(created)
            self.assertEqual(updated.version, 2)
            history = app.requirement_history(updated.id)
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0].action, "create")
            self.assertEqual(history[1].before["projectName"], "外观检测线")
            self.assertEqual(history[1].after["projectName"], "外观检测线（修订）")

            copied = app.copy_requirement(updated.id)
            self.assertNotEqual(copied.id, updated.id)
            self.assertNotEqual(copied.requirement_no, updated.requirement_no)
            self.assertEqual(copied.version, 1)
            self.assertTrue(copied.project_name.endswith("（复制）"))

            self.assertTrue(app.delete_requirement(copied.id))
            archived = app.archive_requirement(updated.id)
            self.assertEqual(archived.status, "archived")
            self.assertEqual(len(app.list_requirement_summaries()), 0)
            self.assertEqual(len(app.list_requirement_summaries(include_archived=True)), 1)

            reloaded = self.application(Path(temporary), include_demo_history=False)
            self.assertEqual(reloaded.get_requirement(updated.id).version, 3)

    def test_empty_history_does_not_fabricate_reference(self) -> None:
        with TemporaryDirectory() as temporary:
            app = self.application(Path(temporary), include_demo_history=False)
            record = app.new_requirement()
            record.product_name = "未知新产品"
            record.structured_requirement.inspection_items = [InspectionRequirement("裂纹")]
            saved = app.save_requirement(record)

            self.assertEqual(app.retrieve_history(saved.id), [])
            candidate = app.generate_candidate(saved.id)
            self.assertEqual(candidate.historical_references, [])
            self.assertEqual(len(candidate.stations), 3)
            self.assertIn("工位数量和相对位置必须严格如下", candidate.drawing_prompt)
            self.assertIn("S01", candidate.drawing_prompt)
            self.assertIn("产品从设备左侧", candidate.drawing_prompt)

            edited = app.save_candidate_edits(
                candidate.id,
                ["人工上料", "复合检测"],
                [
                    CandidateStation("S10", "人工上料工位", "人工放置产品"),
                    CandidateStation("S20", "复合检测工位", "相机与测量模块检测"),
                ],
                candidate.drawing_specification,
            )
            self.assertEqual(edited.drawing_specification.process_flow, edited.process_flow)
            self.assertEqual(
                [value["stationId"] for value in edited.drawing_specification.stations],
                ["S10", "S20"],
            )
            self.assertEqual(
                edited.drawing_specification.stations[1]["position"],
                "从左到右第 2/2 个工位",
            )
            self.assertIn("S10", edited.drawing_prompt)

    def test_three_mock_requirements_complete_end_to_end(self) -> None:
        mock_requirements = (
            {
                "customer": "客户A",
                "project": "冲压件外观检测",
                "product": "金属壳体",
                "type": "金属冲压件",
                "original": "尺寸85×45×12mm，不锈钢，振动盘上料，OK/NG分选，检测划伤、压伤、缺口和尺寸，节拍1.5秒/件，表面反光。",
            },
            {
                "customer": "客户B",
                "project": "透明件检测",
                "product": "透明塑料盖",
                "type": "透明塑料件",
                "original": "透明塑料件120×60×20mm，皮带线上料和皮带线下料，检测尺寸、缺口、脏污和有无，节拍2.0秒/件，产品透明且易划伤。",
            },
            {
                "customer": "客户C",
                "project": "电子件字符检测",
                "product": "电子装配件",
                "type": "电子装配件",
                "original": "产品35×25×8mm，料盘上料、料盘收料，检测字符、二维码、装配和有无，节拍3.0秒/件。",
            },
        )
        with TemporaryDirectory() as temporary:
            app = self.application(Path(temporary))
            candidates = []
            for mock in mock_requirements:
                record = app.new_requirement()
                record.customer_name = mock["customer"]
                record.project_name = mock["project"]
                record.product_name = mock["product"]
                record.original_requirement = mock["original"]
                record.structured_requirement.basic_info.product_type = mock["type"]
                suggestions = app.parse_requirement(record)
                app.apply_suggestions(record, suggestions)
                saved = app.save_requirement(record)
                matches = app.retrieve_history(saved.id)
                self.assertGreaterEqual(len(matches), 1)
                candidate = app.generate_candidate(saved.id)
                candidates.append(candidate)
                self.assertEqual(candidate.requirement_id, saved.id)
                self.assertEqual(len(candidate.stations), 3)
                self.assertGreaterEqual(len(candidate.historical_references), 1)
                self.assertIn("输入→输出主线", candidate.drawing_prompt)
                self.assertIn("相机/光源/夹具", candidate.drawing_prompt)
            self.assertEqual(len(candidates), 3)

    def test_drawing_specification_round_trip_and_prompt_rebuild(self) -> None:
        specification = DrawingSpecification(
            drawing_type="二维俯视图",
            product={"name": "壳体", "size": "10×20 mm"},
            overall_layout="左进右出，三个工位从左到右排列",
            process_flow=["上料", "检测", "下料"],
            stations=[
                {
                    "stationId": "S01",
                    "name": "检测工位",
                    "position": "中部",
                    "description": "固定产品后检测",
                    "fixedParts": ["机架"],
                    "movingParts": ["输送带"],
                    "visionParts": ["相机", "光源"],
                    "fixture": "定位治具",
                }
            ],
            motion_relations=["产品由左向右移动"],
            key_structures=["机架"],
            annotations=["标注工位编号"],
            prohibited_elements=["禁止机械臂"],
            reference_images=[],
        )
        restored = DrawingSpecification.from_dict(specification.to_dict())
        prompt = DrawingPromptBuilder().build(restored)
        self.assertEqual(restored.to_dict(), specification.to_dict())
        self.assertIn("固定部件=机架", prompt)
        self.assertIn("视觉部件=相机、光源", prompt)
        self.assertIn("禁止机械臂", prompt)


if __name__ == "__main__":
    unittest.main()

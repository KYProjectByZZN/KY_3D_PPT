from __future__ import annotations

import unittest

from ppt_generator import (
    EvidenceRef,
    ModuleModel,
    RequirementModel,
    SolutionModel,
    SolutionStation,
    ValidationIssue,
    ValidationResult,
    confidence_grade,
)


class AutoSolutionModelTests(unittest.TestCase):
    def test_requirement_round_trip_preserves_missing_states_and_sources(self) -> None:
        requirement = RequirementModel()
        requirement.fields["product"].value = "筒形壳体"
        requirement.fields["product"].state = "confirmed"
        requirement.fields["product"].source_type = "customer"
        requirement.fields["product"].source_ref = "客户需求表A-01"
        requirement.fields["cycle_time"].state = "need_confirm"

        restored = RequirementModel.from_dict(requirement.to_dict())

        self.assertEqual(restored.fields["product"].value, "筒形壳体")
        self.assertEqual(restored.fields["product"].source_type, "customer")
        self.assertEqual(restored.fields["cycle_time"].state, "need_confirm")
        self.assertEqual(restored.fields["material"].state, "unknown")
        self.assertEqual(restored.fields["material"].value, "")

    def test_ai_inference_cannot_be_confirmed_requirement(self) -> None:
        requirement = RequirementModel()
        field = requirement.fields["accuracy"]
        field.value = "0.01 mm"
        field.state = "confirmed"
        field.source_type = "ai_inference"

        with self.assertRaisesRegex(ValueError, "AI推测"):
            requirement.to_dict()

    def test_solution_module_and_validation_round_trip(self) -> None:
        solution = SolutionModel(
            process=["上料", "定位", "检测", "下料"],
            stations=[
                SolutionStation(
                    station_id="S01",
                    name="定位工位",
                    function="稳定定位产品",
                    module_ids=["MOD-LOC-001"],
                    expected_cycle_time="1.2 s",
                    sources=[EvidenceRef("standard_module", "MOD-LOC-001")],
                    confidence=92,
                    locked=True,
                )
            ],
            module_ids=["MOD-LOC-001"],
        )
        module = ModuleModel(
            module_id="MOD-LOC-001",
            name="标准定位模块",
            validation_status="verified",
            engineering_assets=["定位模块.step"],
        )
        validation = ValidationResult(
            passed=False,
            rule_version="draft-1",
            issues=[
                ValidationIssue(
                    issue_id="ISSUE-001",
                    severity="blocking",
                    object_id="S01",
                    rule="定位完整性",
                    message="定位基准待确认",
                    block_output=True,
                )
            ],
        )

        restored_solution = SolutionModel.from_dict(solution.to_dict())
        restored_module = ModuleModel.from_dict(module.to_dict())
        restored_validation = ValidationResult.from_dict(validation.to_dict())

        self.assertEqual(restored_solution.stations[0].confidence, 92)
        self.assertTrue(restored_solution.stations[0].locked)
        self.assertEqual(restored_module.validation_status, "verified")
        self.assertTrue(restored_validation.issues[0].block_output)
        self.assertEqual(confidence_grade(92), "A")
        self.assertEqual(confidence_grade(80), "B")
        self.assertEqual(confidence_grade(50), "C")

    def test_blocking_issue_prevents_passed_result(self) -> None:
        validation = ValidationResult(
            passed=True,
            issues=[
                ValidationIssue(
                    issue_id="ISSUE-001",
                    severity="blocking",
                    object_id="S01",
                    rule="节拍",
                    message="节拍不满足",
                    block_output=True,
                )
            ],
        )
        with self.assertRaisesRegex(ValueError, "阻断问题"):
            validation.to_dict()


if __name__ == "__main__":
    unittest.main()

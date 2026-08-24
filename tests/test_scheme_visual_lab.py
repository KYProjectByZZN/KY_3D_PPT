from __future__ import annotations

import copy
import unittest
import xml.etree.ElementTree as ET

from ppt_generator.scheme_visual_lab import (
    MAX_STATIONS,
    SchemeVisualLabService,
    demo_drawing_specification,
)
from ppt_generator.solution_generation import DrawingSpecification


class SchemeVisualLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SchemeVisualLabService()

    def test_same_spec_produces_byte_identical_artifacts(self) -> None:
        specification = demo_drawing_specification()

        first = self.service.run(specification)
        second = self.service.run(specification)

        self.assertEqual(first.layout_plan.to_dict(), second.layout_plan.to_dict())
        self.assertEqual(first.svg.encode("utf-8"), second.svg.encode("utf-8"))
        self.assertEqual(
            first.prompt_recipe.to_dict(),
            second.prompt_recipe.to_dict(),
        )
        self.assertEqual(first.layout_plan.layout_hash, second.layout_plan.layout_hash)
        self.assertEqual(
            first.prompt_recipe.recipe_hash,
            second.prompt_recipe.recipe_hash,
        )

    def test_svg_and_prompt_preserve_station_count_order_and_scope(self) -> None:
        result = self.service.run(demo_drawing_specification())
        root = ET.fromstring(result.svg)
        station_ids = [
            element.attrib["data-station-id"]
            for element in root.iter()
            if "data-station-id" in element.attrib
        ]

        self.assertEqual(station_ids, ["ST01", "ST02", "ST03"])
        self.assertIn("严格保留 3 个工位", result.prompt_recipe.positive_prompt)
        self.assertLess(
            result.prompt_recipe.positive_prompt.index("ST01"),
            result.prompt_recipe.positive_prompt.index("ST02"),
        )
        self.assertLess(
            result.prompt_recipe.positive_prompt.index("ST02"),
            result.prompt_recipe.positive_prompt.index("ST03"),
        )
        self.assertIn("未确认的机械臂与旋转机构", result.prompt_recipe.negative_prompt)
        self.assertIn("结构示意图", result.svg)
        self.assertIn("非 CAD 施工图", result.svg)

    def test_visual_parts_only_appear_when_explicitly_confirmed(self) -> None:
        raw = demo_drawing_specification().to_dict()
        for station in raw["stations"]:
            station["visionParts"] = []
        without_visuals = self.service.run(DrawingSpecification.from_dict(raw))

        self.assertNotIn("工业相机", without_visuals.svg)
        self.assertNotIn("环形光源", without_visuals.svg)
        self.assertNotIn("工业相机", without_visuals.prompt_recipe.positive_prompt)
        self.assertNotIn("环形光源", without_visuals.prompt_recipe.positive_prompt)

        raw["stations"][0]["visionParts"] = ["线扫相机", "条形光源"]
        with_visuals = self.service.run(DrawingSpecification.from_dict(raw))
        self.assertIn("线扫相机", with_visuals.svg)
        self.assertIn("条形光源", with_visuals.svg)
        self.assertIn("线扫相机", with_visuals.prompt_recipe.positive_prompt)
        self.assertIn("条形光源", with_visuals.prompt_recipe.positive_prompt)

    def test_station_order_changes_layout_hash_and_svg(self) -> None:
        original_raw = demo_drawing_specification().to_dict()
        reordered_raw = copy.deepcopy(original_raw)
        reordered_raw["stations"][0], reordered_raw["stations"][1] = (
            reordered_raw["stations"][1],
            reordered_raw["stations"][0],
        )

        original = self.service.run(DrawingSpecification.from_dict(original_raw))
        reordered = self.service.run(DrawingSpecification.from_dict(reordered_raw))

        self.assertNotEqual(
            original.layout_plan.layout_hash,
            reordered.layout_plan.layout_hash,
        )
        self.assertNotEqual(original.svg, reordered.svg)
        self.assertEqual(
            [station.station_id for station in reordered.layout_plan.stations],
            ["ST02", "ST01", "ST03"],
        )

    def test_invalid_station_counts_and_duplicate_ids_are_rejected(self) -> None:
        empty = demo_drawing_specification()
        empty.stations = []
        with self.assertRaisesRegex(ValueError, "stations"):
            self.service.run(empty)

        too_many_raw = demo_drawing_specification().to_dict()
        prototype = too_many_raw["stations"][0]
        too_many_raw["stations"] = []
        for index in range(MAX_STATIONS + 1):
            station = copy.deepcopy(prototype)
            station["stationId"] = f"ST{index + 1:02d}"
            station["name"] = f"工位 {index + 1}"
            too_many_raw["stations"].append(station)
        with self.assertRaisesRegex(ValueError, "1～8"):
            self.service.run(DrawingSpecification.from_dict(too_many_raw))

        duplicate_raw = demo_drawing_specification().to_dict()
        duplicate_raw["stations"][1]["stationId"] = "ST01"
        with self.assertRaisesRegex(ValueError, "不得重复"):
            self.service.run(DrawingSpecification.from_dict(duplicate_raw))

    def test_station_part_collections_must_be_arrays(self) -> None:
        raw = demo_drawing_specification().to_dict()
        raw["stations"][0]["visionParts"] = "相机"
        with self.assertRaisesRegex(ValueError, "visionParts 必须是数组"):
            self.service.run(DrawingSpecification.from_dict(raw))


if __name__ == "__main__":
    unittest.main()

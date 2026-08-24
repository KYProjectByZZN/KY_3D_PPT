from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from ppt_generator.module_service import ensure_project_modules
from ppt_generator.project import DeviceModule, FlowNode, PptProject, load_project, save_project
from ppt_generator.scheme_service import (
    SchemeError,
    initialize_equipment_scheme,
    materialize_equipment_scheme,
    remove_device_module,
)
from ppt_generator.template_renderer import load_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "templates" / "NAT6704_v2.template.json"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class SchemeServiceTests(unittest.TestCase):
    def test_legacy_flow_values_initialize_once_and_round_trip_as_schema_v5(self) -> None:
        project = PptProject(
            values={
                "flow_step_01": "人工上料",
                "flow_step_02": "视觉检测",
                "flow_step_03": "",
            }
        )

        initialize_equipment_scheme(project)
        project.equipment_scheme.flow_nodes.clear()
        initialize_equipment_scheme(project)

        self.assertTrue(project.equipment_scheme.initialized)
        self.assertEqual(project.equipment_scheme.flow_nodes, [])

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            path = Path(temp_dir) / "scheme.kyppt.json"
            save_project(project, path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            restored = load_project(path)

        self.assertEqual(raw["schema_version"], 5)
        self.assertTrue(restored.equipment_scheme.initialized)
        self.assertEqual(restored.equipment_scheme.flow_nodes, [])

    def test_materializes_flow_pages_overview_and_device_pages(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        project = PptProject()
        ensure_project_modules(project, manifest)
        project.equipment_scheme.initialized = True
        project.equipment_scheme.flow_nodes = [
            FlowNode(name=f"步骤{index}") for index in range(1, 16)
        ]

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            image_a = Path(temp_dir) / "feed.png"
            image_b = Path(temp_dir) / "vision.png"
            overview = Path(temp_dir) / "overview.png"
            for path in (image_a, image_b, overview):
                path.write_bytes(PNG_1X1)
            feed = DeviceModule(
                name="上料定位模块",
                module_type="上料",
                function="完成产品上料和定位",
                action="接收产品后送入检测位置",
                image_path=str(image_a),
                page_template_key="equipment_module_page_7",
            )
            vision = DeviceModule(
                name="视觉检测模块",
                module_type="视觉检测",
                function="完成多工位视觉检测",
                action="触发相机并输出检测结果",
                image_path=str(image_b),
                page_template_key="equipment_module_page_8",
            )
            project.equipment_scheme.equipment_modules = [feed, vision]
            project.equipment_scheme.flow_nodes[0].equipment_module_id = feed.id
            project.equipment_scheme.flow_nodes[1].equipment_module_id = vision.id
            project.equipment_scheme.overview_image = str(overview)
            project.equipment_scheme.overview_description = "设备由上料和视觉检测模块组成。"

            result = materialize_equipment_scheme(project, manifest)

        flow_module = next(
            item for item in project.modules if item.template_module_key == "inspection_flow"
        )
        device_module = next(
            item for item in project.modules if item.template_module_key == "equipment_module"
        )
        overview_module = next(
            item for item in project.modules if item.template_module_key == "equipment_overview"
        )

        self.assertEqual(result.flow_pages, 2)
        self.assertEqual(result.equipment_pages, 2)
        self.assertTrue(result.overview_updated)
        self.assertEqual(flow_module.slides[0].overrides["flow_step_08"], "步骤8")
        self.assertEqual(flow_module.slides[1].overrides["flow_step_01"], "步骤9")
        self.assertEqual(flow_module.slides[1].overrides["flow_step_08"], "")
        self.assertEqual(len(device_module.slides), 2)
        self.assertEqual(
            device_module.slides[0].overrides["equipment_module_title_s7"],
            "3.1.1  上料定位模块",
        )
        self.assertIn(
            "步骤1",
            device_module.slides[0].overrides["equipment_module_description_s7"],
        )
        self.assertEqual(
            device_module.slides[1].overrides["equipment_module_title_s8"],
            "3.1.2  视觉检测模块",
        )
        self.assertEqual(
            overview_module.slides[0].overrides["equipment_description"],
            "设备由上料和视觉检测模块组成。",
        )

    def test_rejects_missing_module_image_and_protects_references(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        project = PptProject()
        ensure_project_modules(project, manifest)
        project.equipment_scheme.initialized = True
        module = DeviceModule(name="翻转模块")
        node = FlowNode(name="产品翻转", equipment_module_id=module.id)
        project.equipment_scheme.equipment_modules = [module]
        project.equipment_scheme.flow_nodes = [node]

        with self.assertRaisesRegex(SchemeError, "有效方案图"):
            materialize_equipment_scheme(project, manifest)
        with self.assertRaisesRegex(SchemeError, "仍被流程节点引用"):
            remove_device_module(project, module.id)

        removed = remove_device_module(project, module.id, clear_links=True)
        self.assertEqual(removed.id, module.id)
        self.assertEqual(node.equipment_module_id, "")


if __name__ == "__main__":
    unittest.main()

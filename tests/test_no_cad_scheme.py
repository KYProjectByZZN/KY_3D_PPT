from __future__ import annotations

import copy
import unittest
import xml.etree.ElementTree as ET

from ppt_generator.no_cad_scheme import (
    EquipmentScene,
    MODULE_BY_TYPE,
    NoCadSchemeService,
)


class NoCadSchemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = NoCadSchemeService()

    def test_demo_scene_passes_logic_gate_in_expected_order(self) -> None:
        scene = self.service.create_demo_scene()
        result = self.service.evaluate(scene)

        self.assertTrue(result.can_generate_ai)
        self.assertFalse(any(issue.level == "blocking" for issue in result.issues))
        self.assertEqual(
            [node.module_type for node in scene.nodes],
            [
                "vibratory_bowl_feed",
                "linear_feeder",
                "stop_position",
                "top_vision",
                "side_vision",
                "pusher_reject",
                "ok_ng_bins",
            ],
        )
        self.assertEqual(len(scene.connections), len(scene.nodes) - 1)

    def test_missing_inspection_and_wrong_entry_are_blocked(self) -> None:
        no_inspection = self.service.create_demo_scene()
        no_inspection.nodes[:] = [
            node
            for node in no_inspection.nodes
            if MODULE_BY_TYPE[node.module_type].category != "inspect"
        ]
        self.service.rebuild_connections(no_inspection)
        self.service.auto_layout(no_inspection)
        missing_result = self.service.evaluate(no_inspection)
        self.assertFalse(missing_result.can_generate_ai)
        self.assertIn("NO_INSPECTION", {issue.code for issue in missing_result.issues})

        wrong_entry = self.service.create_demo_scene()
        feed_id = wrong_entry.nodes[0].node_id
        self.service.move_module(wrong_entry, feed_id, 1)
        self.service.auto_layout(wrong_entry)
        entry_result = self.service.evaluate(wrong_entry)
        self.assertFalse(entry_result.can_generate_ai)
        self.assertIn("ENTRY_NOT_FEED", {issue.code for issue in entry_result.issues})
        self.assertIn("FEED_POSITION", {issue.code for issue in entry_result.issues})

    def test_reject_before_inspection_is_blocked(self) -> None:
        scene = self.service.create_demo_scene()
        reject = next(
            node
            for node in scene.nodes
            if MODULE_BY_TYPE[node.module_type].category == "reject"
        )
        self.service.move_module(scene, reject.node_id, -3)
        self.service.auto_layout(scene)

        result = self.service.evaluate(scene)

        self.assertFalse(result.can_generate_ai)
        codes = {issue.code for issue in result.issues}
        self.assertIn("REJECT_BEFORE_INSPECTION", codes)
        self.assertIn("INSPECTION_AFTER_REJECT", codes)

    def test_module_operations_rebuild_one_adjacent_flow(self) -> None:
        scene = self.service.create_minimum_scene()
        added = self.service.add_module(scene, "stop_position", index=1)
        self.service.replace_module(scene, added.node_id, "rotary_position")
        self.service.move_module(scene, added.node_id, 1)
        expected = [
            (scene.nodes[index].node_id, scene.nodes[index + 1].node_id)
            for index in range(len(scene.nodes) - 1)
        ]
        self.assertEqual(
            [(link.source_id, link.target_id) for link in scene.connections],
            expected,
        )
        self.assertEqual(
            next(node for node in scene.nodes if node.node_id == added.node_id).module_type,
            "rotary_position",
        )

        self.service.remove_module(scene, added.node_id)
        self.assertNotIn(added.node_id, [node.node_id for node in scene.nodes])
        self.assertEqual(len(scene.connections), len(scene.nodes) - 1)

    def test_auto_layout_preserves_locked_coordinates_and_reports_conflict(self) -> None:
        scene = self.service.create_demo_scene()
        locked = scene.nodes[3]
        locked.x = 20
        locked.y = 280
        locked.width = 190
        locked.locked = True

        self.service.auto_layout(scene)
        result = self.service.evaluate(scene)

        self.assertEqual((locked.x, locked.y, locked.width), (20, 280, 190))
        self.assertFalse(result.can_generate_ai)
        self.assertIn("FLOW_DIRECTION", {issue.code for issue in result.issues})
        self.assertIn("LOCKED_NODES", {issue.code for issue in result.issues})

    def test_locked_module_rejects_structural_operations(self) -> None:
        scene = self.service.create_demo_scene()
        node = scene.nodes[3]
        node.locked = True

        with self.assertRaisesRegex(ValueError, "已锁定"):
            self.service.replace_module(scene, node.node_id, "bottom_vision")
        with self.assertRaisesRegex(ValueError, "已锁定"):
            self.service.move_module(scene, node.node_id, 1)
        with self.assertRaisesRegex(ValueError, "已锁定"):
            self.service.remove_module(scene, node.node_id)

        reordered = [value.node_id for value in scene.nodes]
        reordered[2], reordered[3] = reordered[3], reordered[2]
        with self.assertRaisesRegex(ValueError, "已锁定"):
            self.service.reorder_modules(scene, reordered)

    def test_same_scene_produces_identical_hash_svg_and_brief(self) -> None:
        raw = self.service.create_demo_scene().to_dict()
        first_scene = EquipmentScene.from_dict(copy.deepcopy(raw))
        second_scene = EquipmentScene.from_dict(copy.deepcopy(raw))

        first = self.service.evaluate(first_scene)
        second = self.service.evaluate(second_scene)

        self.assertEqual(first.scene_hash, second.scene_hash)
        self.assertEqual(first.svg.encode("utf-8"), second.svg.encode("utf-8"))
        self.assertEqual(first.generation_brief, second.generation_brief)
        root = ET.fromstring(first.svg)
        svg_nodes = [
            element.attrib["data-node-id"]
            for element in root.iter()
            if "data-node-id" in element.attrib
        ]
        self.assertEqual(svg_nodes, [node.node_id for node in first_scene.nodes])

    def test_generation_brief_uses_catalog_components_and_gate_status(self) -> None:
        scene = self.service.create_demo_scene()
        result = self.service.evaluate(scene)
        self.assertIn("顶部相机", result.generation_brief)
        self.assertIn("侧面相机", result.generation_brief)
        self.assertIn("逻辑门禁：通过", result.generation_brief)

        scene.nodes[2].module_type = "unregistered_machine"
        blocked = self.service.evaluate(scene)
        self.assertFalse(blocked.can_generate_ai)
        self.assertIn("逻辑门禁：未通过", blocked.generation_brief)

    def test_builds_independent_overview_and_module_visual_targets(self) -> None:
        scene = self.service.create_demo_scene()
        first = self.service.evaluate(scene)

        self.assertEqual(len(first.visual_targets), len(scene.nodes) + 1)
        self.assertEqual(first.visual_targets[0].target_id, "overview")
        self.assertEqual(
            [value.target_id for value in first.visual_targets[1:]],
            [value.node_id for value in scene.nodes],
        )
        self.assertIn("Authoritative module structure JSON", first.visual_target("M04").prompt)
        self.assertIn("顶部相机", first.visual_target("M04").prompt)

        hashes = {value.target_id: value.target_hash for value in first.visual_targets}
        scene.nodes[3].structure["customNotes"] = "相机支架必须独立安装"
        second = self.service.evaluate(scene)

        self.assertNotEqual(hashes["overview"], second.visual_target("overview").target_hash)
        self.assertNotEqual(hashes["M04"], second.visual_target("M04").target_hash)
        self.assertEqual(hashes["M05"], second.visual_target("M05").target_hash)

    def test_scene_round_trip_keeps_custom_structure_prompt_and_image_binding(self) -> None:
        scene = self.service.create_minimum_scene()
        node = scene.nodes[1]
        node.structure["motionRelations"] = ["相机固定，产品沿主线移动"]
        node.prompt_requirements = "仅显示一个检测位"
        result = self.service.evaluate(scene)
        target = result.visual_target(node.node_id)
        provenance = {"targetHash": target.target_hash, "batchId": "batch-1"}
        self.service.bind_accepted_image(
            scene,
            node.node_id,
            "module.png",
            provenance,
        )

        restored = EquipmentScene.from_dict(scene.to_dict())
        restored_result = self.service.evaluate(restored)

        self.assertEqual(restored.nodes[1].image_path, "module.png")
        self.assertEqual(restored.nodes[1].image_provenance, provenance)
        self.assertIn("仅显示一个检测位", restored_result.visual_target(node.node_id).prompt)
        self.assertEqual(restored_result.visual_target(node.node_id).target_hash, target.target_hash)

    def test_module_add_remove_and_order_keep_one_visual_bundle_per_module(self) -> None:
        scene = self.service.create_minimum_scene()
        initial = self.service.evaluate(scene)
        existing = {
            target.target_id: target.structure
            for target in initial.visual_targets[1:]
        }

        added = self.service.add_module(scene, "stop_position", index=1)
        self.service.auto_layout(scene)
        after_add = self.service.evaluate(scene)

        self.assertEqual(len(after_add.visual_targets), len(scene.nodes) + 1)
        self.assertEqual(
            [target.target_id for target in after_add.visual_targets[1:]],
            [node.node_id for node in scene.nodes],
        )
        self.assertTrue(after_add.visual_target(added.node_id).structure["components"])
        self.assertTrue(after_add.visual_target(added.node_id).prompt)
        for target_id, structure in existing.items():
            self.assertEqual(after_add.visual_target(target_id).structure, structure)
            self.assertIn(
                f"Module identity: {target_id}/",
                after_add.visual_target(target_id).prompt,
            )

        self.service.move_module(scene, added.node_id, 1)
        self.service.auto_layout(scene)
        after_move = self.service.evaluate(scene)
        self.assertEqual(
            [target.target_id for target in after_move.visual_targets[1:]],
            [node.node_id for node in scene.nodes],
        )
        self.assertEqual(
            after_move.visual_target(added.node_id).structure,
            after_add.visual_target(added.node_id).structure,
        )

        self.service.remove_module(scene, added.node_id)
        self.service.auto_layout(scene)
        after_remove = self.service.evaluate(scene)
        self.assertEqual(len(after_remove.visual_targets), len(scene.nodes) + 1)
        with self.assertRaisesRegex(ValueError, "不存在视觉生成目标"):
            after_remove.visual_target(added.node_id)

    def test_structure_change_invalidates_only_stale_accepted_images(self) -> None:
        scene = self.service.create_minimum_scene()
        first = self.service.evaluate(scene)
        for target_id in ("overview", scene.nodes[1].node_id, scene.nodes[2].node_id):
            target = first.visual_target(target_id)
            self.service.bind_accepted_image(
                scene,
                target_id,
                f"{target_id}.png",
                {"targetHash": target.target_hash},
            )

        scene.nodes[1].structure["customNotes"] = "检测模块改为独立支架"
        changed = self.service.evaluate(scene)
        stale = self.service.invalidate_stale_images(scene, changed)

        self.assertIn("overview", stale)
        self.assertIn(scene.nodes[1].node_id, stale)
        self.assertNotIn(scene.nodes[2].node_id, stale)
        self.assertEqual(scene.overview_image, "")
        self.assertEqual(scene.nodes[1].image_path, "")
        self.assertEqual(scene.nodes[2].image_path, f"{scene.nodes[2].node_id}.png")


if __name__ == "__main__":
    unittest.main()

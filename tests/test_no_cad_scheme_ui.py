from __future__ import annotations

import base64
import os
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt

from ppt_generator.no_cad_scheme import MODULE_BY_TYPE
from ppt_generator.ui.app import create_application
from ppt_generator.ui.module_visual_overview import (
    ImagePreviewDialog,
    ModuleVisualOverviewDialog,
)
from ppt_generator.ui.no_cad_scheme_editor import NoCadSchemeEditor
from ppt_generator.ui.openai_image_dialog import OpenAIImageDialog
from ppt_generator.openai_image import OpenAIImageBatch, OpenAIImageCandidate


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class NoCadSchemeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = create_application([])

    def setUp(self) -> None:
        self.widget = NoCadSchemeEditor()
        self.widget.resize(1900, 980)
        self.widget.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.application.processEvents()

    def _select_catalog(self, module_type: str) -> None:
        for row in range(self.widget.catalog_list.count()):
            item = self.widget.catalog_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == module_type:
                self.widget.catalog_list.setCurrentRow(row)
                return
        self.fail(f"catalog module not found: {module_type}")

    def test_demo_is_ready_for_logic_review(self) -> None:
        self.assertEqual(self.widget.catalog_list.count(), 16)
        self.assertEqual(self.widget.flow_list.count(), 7)
        self.assertTrue(self.widget.current_result.can_generate_ai)
        self.assertTrue(self.widget.preview_widget.renderer().isValid())
        self.assertIn("逻辑通过", self.widget.status_label.text())
        self.assertIn("sceneHash", self.widget.scene_json_output.toPlainText())
        self.assertIn("模块顺序不得", self.widget.generation_brief_output.toPlainText())
        self.assertTrue(self.widget.ai_generate_button.isEnabled())
        self.assertIn("Codex Pro", self.widget.ai_generate_button.text())
        self.assertEqual(
            self.widget.visual_overview_button.text(),
            "模块效果总览",
        )

    def test_visual_overview_has_one_card_per_target_and_tracks_added_module(self) -> None:
        dialog = ModuleVisualOverviewDialog(
            self.widget.current_result.visual_targets,
            project_name=self.widget.scene.project_name,
            product_name=self.widget.scene.product_name,
            parent=self.widget,
        )
        dialog.show()
        self.application.processEvents()

        self.assertEqual(len(dialog.cards), len(self.widget.scene.nodes) + 1)
        self.assertEqual(dialog._column_count, 3)
        self.assertEqual(
            [card.target_id for card in dialog.cards],
            [target.target_id for target in self.widget.current_result.visual_targets],
        )
        self.assertIn("已采用 0 个", dialog.summary_label.text())
        self.assertFalse(dialog.cards[0].open_button.isEnabled())

        self._select_catalog("belt_transfer")
        self.widget.add_selected_module()
        added_id = self.widget.flow_list.currentItem().data(
            Qt.ItemDataRole.UserRole
        )
        dialog.set_targets(self.widget.current_result.visual_targets)
        self.application.processEvents()
        self.assertEqual(len(dialog.cards), len(self.widget.scene.nodes) + 1)
        self.assertIn(added_id, [card.target_id for card in dialog.cards])
        dialog.resize(700, 700)
        self.application.processEvents()
        self.assertEqual(dialog._column_count, 1)
        dialog.close()

    def test_visual_overview_click_opens_the_bound_target_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "module.png"
            image.write_bytes(PNG_1X1)
            target = self.widget.current_result.visual_target("M04")
            self.widget.service.bind_accepted_image(
                self.widget.scene,
                target.target_id,
                str(image),
                {"targetHash": target.target_hash, "provider": "test"},
            )
            self.widget.refresh(target_id=target.target_id)
            dialog = ModuleVisualOverviewDialog(
                self.widget.current_result.visual_targets,
                parent=self.widget,
            )
            card = next(
                value for value in dialog.cards if value.target_id == target.target_id
            )
            self.assertTrue(card.has_image)
            self.assertTrue(card.open_button.isEnabled())

            with patch(
                "ppt_generator.ui.module_visual_overview.ImagePreviewDialog"
            ) as preview_dialog:
                card.image_label.clicked.emit()
                preview_dialog.assert_called_once()
                opened_target = preview_dialog.call_args.args[0]
                self.assertEqual(opened_target.target_id, target.target_id)
                preview_dialog.return_value.exec.assert_called_once()
            dialog.close()

    def test_large_image_viewer_supports_fit_actual_size_and_zoom(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "viewer.png"
            image.write_bytes(PNG_1X1)
            target = replace(
                self.widget.current_result.visual_target("overview"),
                image_path=str(image),
            )
            dialog = ImagePreviewDialog(target, self.widget)
            dialog.show()
            self.application.processEvents()

            dialog.actual_size()
            self.assertFalse(dialog._fit_to_window)
            self.assertEqual(dialog._zoom, 1.0)
            dialog.change_zoom(1.25)
            self.assertEqual(dialog._zoom, 1.25)
            dialog.fit_to_window()
            self.assertTrue(dialog._fit_to_window)
            dialog.close()

    def test_replace_add_move_and_delete_refresh_scene(self) -> None:
        original_count = len(self.widget.scene.nodes)
        original_targets = len(self.widget.current_result.visual_targets)
        self.widget.flow_list.setCurrentRow(3)
        selected_id = self.widget.flow_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self._select_catalog("bottom_vision")
        self.widget.replace_selected_module()
        replaced = next(node for node in self.widget.scene.nodes if node.node_id == selected_id)
        self.assertEqual(replaced.module_type, "bottom_vision")

        self._select_catalog("belt_transfer")
        self.widget.add_selected_module()
        self.assertEqual(len(self.widget.scene.nodes), original_count + 1)
        self.assertEqual(
            len(self.widget.current_result.visual_targets),
            original_targets + 1,
        )
        added_id = self.widget.flow_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.widget.move_selected(1)
        self.assertEqual(
            len(self.widget.scene.connections),
            len(self.widget.scene.nodes) - 1,
        )
        self.widget.remove_selected_module()
        self.assertEqual(len(self.widget.scene.nodes), original_count)
        self.assertEqual(
            len(self.widget.current_result.visual_targets),
            original_targets,
        )
        self.assertNotIn(added_id, [node.node_id for node in self.widget.scene.nodes])

    def test_logic_failure_is_visible_after_removing_inspection(self) -> None:
        self.widget.scene.nodes[:] = [
            node
            for node in self.widget.scene.nodes
            if MODULE_BY_TYPE[node.module_type].category != "inspect"
        ]
        self.widget.service.rebuild_connections(self.widget.scene)
        self.widget.service.auto_layout(self.widget.scene)
        self.widget.refresh()

        self.assertFalse(self.widget.current_result.can_generate_ai)
        self.assertIn("逻辑未通过", self.widget.status_label.text())
        self.assertIn("NO_INSPECTION", self.widget.scene_json_output.toPlainText())
        self.assertIn("逻辑未通过", self.widget.ai_generate_button.text())
        self.assertFalse(self.widget.ai_generate_button.isEnabled())

    def test_locked_property_survives_auto_layout(self) -> None:
        self.widget.flow_list.setCurrentRow(2)
        node = self.widget._selected_node()
        assert node is not None
        self.widget.locked_check.setChecked(True)
        self.widget.apply_properties()
        node.x = 777
        node.y = 281
        self.widget.auto_layout()

        self.assertTrue(node.locked)
        self.assertEqual((node.x, node.y), (777, 281))

    def test_openai_dialog_renders_scene_control_png_without_persisting_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dialog = OpenAIImageDialog(
                scene_snapshot=self.widget.scene.to_dict(),
                result=self.widget.current_result,
                api_key="sk-ui-session-only",
                output_root=Path(temp_dir),
                parent=self.widget,
            )
            dialog.show()
            self.application.processEvents()

            control = dialog._render_control_image()

            self.assertTrue(control.is_file())
            self.assertTrue(control.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(dialog.api_key(), "sk-ui-session-only")
            self.assertNotIn("sk-ui-session-only", dialog.metadata_output.toPlainText())
            self.assertEqual(dialog.provider_combo.currentIndex(), 0)
            self.assertEqual(
                dialog.target_combo.count(),
                len(self.widget.current_result.visual_targets),
            )
            self.assertEqual(dialog.target.target_id, "overview")
            self.assertIn("Codex Pro", dialog.provider_combo.currentText())
            self.assertFalse(dialog.api_key_edit.isVisible())
            self.assertTrue(dialog.login_button.isVisible())

            dialog.provider_combo.setCurrentIndex(1)
            self.application.processEvents()
            self.assertTrue(dialog.api_key_edit.isVisible())
            self.assertFalse(dialog.login_button.isVisible())
            self.assertIn("单独充值", dialog.credentials_note.text())
            dialog.close()

    def test_ai_dialog_selects_target_inside_and_clears_previous_target_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "candidate.png"
            image.write_bytes(PNG_1X1)
            overview = self.widget.current_result.visual_target("overview")
            batch = OpenAIImageBatch(
                batch_id="batch-overview",
                scene_hash=overview.target_hash,
                provider="test",
                model="test-model",
                request_id="request-overview",
                created_at=datetime.now(timezone.utc).isoformat(),
                output_dir=root,
                manifest_path=root / "generation.json",
                candidates=(
                    OpenAIImageCandidate(
                        candidate_id="candidate-01",
                        image_path=image,
                        sha256="b" * 64,
                    ),
                ),
            )
            dialog = OpenAIImageDialog(
                scene_snapshot=self.widget.scene.to_dict(),
                result=self.widget.current_result,
                output_root=root,
                parent=self.widget,
            )
            dialog._generation_succeeded(batch)
            self.assertIs(dialog.batch, batch)
            self.assertTrue(dialog.accept_button.isEnabled())

            module_index = dialog.target_combo.findData("M04")
            dialog.target_combo.setCurrentIndex(module_index)
            self.application.processEvents()

            module_target = self.widget.current_result.visual_target("M04")
            self.assertEqual(dialog.target.target_id, "M04")
            self.assertIn(module_target.title, dialog.scene_label.text())
            self.assertEqual(dialog.brief_output.toPlainText(), module_target.prompt)
            self.assertIsNone(dialog.batch)
            self.assertEqual(dialog.candidate_combo.count(), 0)
            self.assertFalse(dialog.accept_button.isEnabled())
            self.assertIn("尚未采用效果图", dialog.preview_label.text())
            dialog.close()

    def test_ai_dialog_restores_only_current_project_target_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "candidate.png"
            image.write_bytes(PNG_1X1)
            target = self.widget.current_result.visual_target("M04")
            batch = OpenAIImageBatch(
                batch_id="batch-history",
                scene_hash=target.target_hash,
                provider="test",
                model="test-model",
                request_id="request-history",
                created_at=datetime.now(timezone.utc).isoformat(),
                output_dir=root,
                manifest_path=root / "generation.json",
                candidates=(
                    OpenAIImageCandidate(
                        candidate_id="candidate-01",
                        image_path=image,
                        sha256="c" * 64,
                    ),
                ),
            )
            project_id = "1" * 32
            matching = {
                "schemaVersion": "project-ai-image-batch/v1",
                "projectId": project_id,
                "generationTarget": {
                    "targetId": target.target_id,
                    "targetKind": target.target_kind,
                    "targetHash": target.target_hash,
                    "title": target.title,
                },
                "batch": batch.to_dict(),
            }
            foreign = {
                **matching,
                "projectId": "2" * 32,
                "batch": {**batch.to_dict(), "batchId": "foreign"},
            }
            stale = {
                **matching,
                "generationTarget": {
                    **matching["generationTarget"],
                    "targetHash": "f" * 64,
                },
                "batch": {**batch.to_dict(), "batchId": "stale"},
            }
            dialog = OpenAIImageDialog(
                scene_snapshot=self.widget.scene.to_dict(),
                result=self.widget.current_result,
                target=target,
                output_root=root,
                project_id=project_id,
                batch_history=[matching, foreign, stale],
                parent=self.widget,
            )

            self.assertEqual(dialog.history_combo.count(), 2)
            dialog.history_combo.setCurrentIndex(1)
            self.application.processEvents()
            self.assertEqual(dialog.batch.batch_id, "batch-history")
            self.assertTrue(dialog.accept_button.isEnabled())
            self.assertFalse(dialog.preview_label.pixmap().isNull())
            dialog.close()

    def test_ai_dialog_previews_and_opens_current_accepted_effect_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "accepted.png"
            image.write_bytes(PNG_1X1)
            target = self.widget.current_result.visual_target("M04")
            self.widget.service.bind_accepted_image(
                self.widget.scene,
                target.target_id,
                str(image),
                {"targetHash": target.target_hash, "provider": "test"},
            )
            self.widget.refresh(target_id=target.target_id)
            current_target = self.widget.current_result.visual_target(target.target_id)
            dialog = OpenAIImageDialog(
                scene_snapshot=self.widget.scene.to_dict(),
                result=self.widget.current_result,
                target=current_target,
                parent=self.widget,
            )
            self.assertTrue(dialog.view_accepted_button.isEnabled())
            self.assertFalse(dialog.preview_label.pixmap().isNull())

            with patch(
                "ppt_generator.ui.openai_image_dialog.ImagePreviewDialog"
            ) as preview_dialog:
                dialog.view_accepted_button.click()
                opened_target = preview_dialog.call_args.args[0]
                self.assertEqual(opened_target.target_id, target.target_id)
                self.assertEqual(opened_target.image_path, str(image))
                preview_dialog.return_value.exec.assert_called_once()
            dialog.close()

    @patch("ppt_generator.ui.no_cad_scheme_editor.OpenAIImageDialog")
    def test_ai_dialog_can_return_multiple_target_images_for_scene_binding(
        self,
        dialog_class,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            overview_image = root / "overview.png"
            module_image = root / "module.png"
            overview_image.write_bytes(PNG_1X1)
            module_image.write_bytes(PNG_1X1)
            overview = self.widget.current_result.visual_target("overview")
            module = self.widget.current_result.visual_target("M04")
            instance = dialog_class.return_value
            instance.api_key.return_value = ""
            instance.accepted_selection = None
            instance.accepted_selections = [
                {
                    "targetId": overview.target_id,
                    "targetHash": overview.target_hash,
                    "imagePath": str(overview_image),
                    "provider": "test",
                },
                {
                    "targetId": module.target_id,
                    "targetHash": module.target_hash,
                    "imagePath": str(module_image),
                    "provider": "test",
                },
            ]
            instance.batch = None
            instance.target = module
            instance.project_batch_records.return_value = []
            project_id = "3" * 32
            self.widget.set_project_context(
                project_id,
                self.widget.scene.to_dict(),
                [],
            )

            self.widget.generate_ai_effect()

            self.assertEqual(self.widget.scene.overview_image, str(overview_image))
            bound_module = next(
                node for node in self.widget.scene.nodes if node.node_id == module.target_id
            )
            self.assertEqual(bound_module.image_path, str(module_image))
            self.assertIn("已回写 2 个效果图目标", self.widget.status_label.text())
            kwargs = dialog_class.call_args.kwargs
            self.assertEqual(kwargs["project_id"], project_id)
            self.assertEqual(kwargs["output_root"].name, project_id)
            self.assertEqual(kwargs["batch_history"], [])

    @patch("ppt_generator.ui.no_cad_scheme_editor.OpenAIImageDialog")
    def test_generated_batch_history_emits_project_owned_workspace(self, dialog_class) -> None:
        project_id = "4" * 32
        self.widget.set_project_context(project_id, self.widget.scene.to_dict(), [])
        target = self.widget.current_result.visual_target("overview")
        record = {
            "schemaVersion": "project-ai-image-batch/v1",
            "projectId": project_id,
            "generationTarget": {
                "targetId": target.target_id,
                "targetHash": target.target_hash,
            },
            "batch": {"batchId": "batch-owned", "candidates": []},
        }
        instance = dialog_class.return_value
        instance.api_key.return_value = ""
        instance.project_batch_records.return_value = [record]
        instance.accepted_selections = []
        instance.accepted_selection = None
        instance.batch = None
        events: list[dict] = []
        self.widget.workspace_changed.connect(events.append)

        self.widget.generate_ai_effect()

        self.assertEqual(self.widget.candidate_batch_records, [record])
        self.assertTrue(events[-1]["candidateHistoryChanged"])
        self.assertEqual(events[-1]["projectId"], project_id)
        self.assertEqual(events[-1]["aiImageBatches"], [record])

    def test_each_visual_target_has_editable_structure_and_accepted_image_binding(self) -> None:
        self.assertEqual(
            self.widget.target_combo.count(),
            len(self.widget.scene.nodes) + 1,
        )
        self.widget.flow_list.setCurrentRow(3)
        self.application.processEvents()
        target_id = self.widget.target_combo.currentData()
        node = self.widget._selected_node()
        assert node is not None
        self.assertEqual(target_id, node.node_id)

        structure = json.loads(self.widget.target_structure_editor.toPlainText())
        structure["customNotes"] = "检测模块相机支架独立安装"
        self.widget.target_structure_editor.setPlainText(
            json.dumps(structure, ensure_ascii=False)
        )
        self.widget.target_prompt_requirements_edit.setPlainText("只显示一个检测位")
        self.widget.apply_target_definition()

        self.assertEqual(node.structure["customNotes"], "检测模块相机支架独立安装")
        self.assertIn("只显示一个检测位", self.widget.target_prompt_output.toPlainText())

        committed: list[dict] = []
        self.widget.scheme_committed.connect(committed.append)
        self.widget.commit_scheme()
        self.assertEqual(len(committed), 1)
        self.assertEqual(committed[0]["nodes"][3]["nodeId"], node.node_id)

    def test_acceptance_records_selected_module_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.widget.current_result.visual_target("M04")
            image = root / "candidate.png"
            image.write_bytes(PNG_1X1)
            manifest = root / "generation.json"
            candidate = OpenAIImageCandidate(
                candidate_id="candidate-01",
                image_path=image,
                sha256="a" * 64,
            )
            batch = OpenAIImageBatch(
                batch_id="batch-01",
                scene_hash=target.target_hash,
                provider="test",
                model="test-model",
                request_id="request-01",
                created_at=datetime.now(timezone.utc).isoformat(),
                output_dir=root,
                manifest_path=manifest,
                candidates=(candidate,),
            )
            dialog = OpenAIImageDialog(
                scene_snapshot=self.widget.scene.to_dict(),
                result=self.widget.current_result,
                target=target,
                output_root=root,
                project_id="5" * 32,
                parent=self.widget,
            )
            batch_events: list[list[dict]] = []
            dialog.batch_records_changed.connect(batch_events.append)
            dialog._generation_succeeded(batch)
            self.assertEqual(batch_events[-1][0]["batch"]["batchId"], "batch-01")
            dialog.accept_current()

            accepted = json.loads((root / "accepted.json").read_text(encoding="utf-8"))
            self.assertEqual(accepted["generationTarget"]["targetId"], "M04")
            self.assertEqual(dialog.accepted_selection["targetHash"], target.target_hash)
            self.assertEqual(len(dialog.accepted_selections), 1)
            record = dialog.project_batch_records()[0]
            self.assertEqual(record["projectId"], "5" * 32)
            self.assertEqual(record["acceptedCandidateId"], candidate.candidate_id)
            self.assertEqual(
                batch_events[-1][0]["acceptedCandidateId"],
                candidate.candidate_id,
            )
            dialog.close()


if __name__ == "__main__":
    unittest.main()

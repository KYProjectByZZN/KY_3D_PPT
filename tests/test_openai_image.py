from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ppt_generator.no_cad_scheme import NoCadSchemeService
from ppt_generator.openai_image import (
    DEFAULT_OPENAI_IMAGE_MODEL,
    OpenAIImageError,
    OpenAIImageProvider,
    prepare_openai_image_request,
)


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeImages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def edit(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(ONE_PIXEL_PNG).decode("ascii"),
                    revised_prompt="",
                )
                for _ in range(kwargs["n"])
            ],
            _request_id="req_test_123",
        )


class FakeModels:
    def retrieve(self, model: str):
        return SimpleNamespace(id=model)


class FakeClient:
    def __init__(self) -> None:
        self.images = FakeImages()
        self.models = FakeModels()


class OpenAIImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = NoCadSchemeService()
        self.scene = self.service.create_demo_scene()
        self.result = self.service.evaluate(self.scene)

    def _request(self, root: Path, *, count: int = 1):
        control = root / "control.png"
        control.write_bytes(ONE_PIXEL_PNG)
        return prepare_openai_image_request(
            self.scene,
            self.result,
            control_image_path=control,
            output_root=root / "candidates",
            candidate_count=count,
        )

    def test_provider_saves_traceable_candidates_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_client = FakeClient()
            provider = OpenAIImageProvider(
                client_factory=lambda **_kwargs: fake_client
            )
            request = self._request(root, count=2)

            batch = provider.generate(request, "sk-test-secret")

            self.assertEqual(provider.test_connection("sk-test-secret"), DEFAULT_OPENAI_IMAGE_MODEL)
            self.assertEqual(len(batch.candidates), 2)
            self.assertEqual(batch.scene_hash, self.result.scene_hash)
            self.assertEqual(batch.request_id, "req_test_123")
            self.assertTrue(all(value.image_path.is_file() for value in batch.candidates))
            manifest_text = batch.manifest_path.read_text(encoding="utf-8")
            self.assertNotIn("sk-test-secret", manifest_text)
            manifest = json.loads(manifest_text)
            self.assertEqual(manifest["request"]["sceneHash"], self.result.scene_hash)
            self.assertEqual(manifest["request"]["model"], DEFAULT_OPENAI_IMAGE_MODEL)
            self.assertEqual(fake_client.images.calls[0]["n"], 2)
            self.assertEqual(fake_client.images.calls[0]["quality"], "medium")

    def test_module_target_request_uses_its_own_hash_prompt_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            control = root / "control.png"
            control.write_bytes(ONE_PIXEL_PNG)
            target = self.result.visual_target("M04")

            request = prepare_openai_image_request(
                self.scene,
                self.result,
                control_image_path=control,
                output_root=root / "candidates",
                target_id="M04",
            )

            self.assertEqual(request.scene_hash, target.target_hash)
            self.assertEqual(request.prompt, target.prompt)
            self.assertEqual(
                request.scene_snapshot["generationTarget"]["targetId"],
                "M04",
            )
            self.assertIn("equipmentScene", request.scene_snapshot)

    def test_blocked_or_stale_scene_is_never_handed_to_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            control = root / "control.png"
            control.write_bytes(ONE_PIXEL_PNG)

            stale_result = self.result
            self.scene.nodes[2].name = "changed after evaluation"
            with self.assertRaisesRegex(OpenAIImageError, "发生变化"):
                prepare_openai_image_request(
                    self.scene,
                    stale_result,
                    control_image_path=control,
                    output_root=root,
                )

            blocked_scene = self.service.create_demo_scene()
            blocked_scene.nodes[:] = [
                value
                for value in blocked_scene.nodes
                if "vision" not in value.module_type
            ]
            self.service.rebuild_connections(blocked_scene)
            self.service.auto_layout(blocked_scene)
            blocked_result = self.service.evaluate(blocked_scene)
            with self.assertRaisesRegex(OpenAIImageError, "逻辑门禁"):
                prepare_openai_image_request(
                    blocked_scene,
                    blocked_result,
                    control_image_path=control,
                    output_root=root,
                )

    def test_provider_rejects_missing_key_and_invalid_image_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self._request(root)
            provider = OpenAIImageProvider(client_factory=lambda **_kwargs: FakeClient())
            with self.assertRaisesRegex(OpenAIImageError, "API Key"):
                provider.generate(request, "")

            bad_client = FakeClient()
            bad_client.images.edit = lambda **_kwargs: SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(b"not-png").decode("ascii"))]
            )
            bad_provider = OpenAIImageProvider(
                client_factory=lambda **_kwargs: bad_client
            )
            with self.assertRaisesRegex(OpenAIImageError, "不是有效 PNG"):
                bad_provider.generate(request, "sk-test")

    def test_provider_rejects_wrong_count_and_redacts_key_from_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self._request(root, count=2)
            wrong_count_client = FakeClient()
            wrong_count_client.images.edit = lambda **_kwargs: SimpleNamespace(data=[])
            provider = OpenAIImageProvider(
                client_factory=lambda **_kwargs: wrong_count_client
            )
            with self.assertRaisesRegex(OpenAIImageError, "数量"):
                provider.generate(request, "sk-count-test")

            secret = "sk-must-not-leak"
            failed_client = FakeClient()

            def fail(**_kwargs):
                raise RuntimeError(f"upstream rejected {secret}")

            failed_client.images.edit = fail
            failed_provider = OpenAIImageProvider(
                client_factory=lambda **_kwargs: failed_client
            )
            with self.assertRaises(OpenAIImageError) as captured:
                failed_provider.generate(request, secret)
            self.assertNotIn(secret, str(captured.exception))
            self.assertIn("***", str(captured.exception))

    def test_api_quota_error_points_to_codex_pro_mode(self) -> None:
        provider = OpenAIImageProvider()

        message = provider._safe_provider_error(
            RuntimeError("429 insufficient_quota: credit balance exhausted"),
            "sk-not-shown",
        )

        self.assertIn("API 余额不足", message)
        self.assertIn("Codex Pro", message)
        self.assertNotIn("sk-not-shown", message)


if __name__ == "__main__":
    unittest.main()

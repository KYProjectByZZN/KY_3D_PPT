from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from ppt_generator.codex_image import (
    CodexCommandResult,
    CodexImageError,
    CodexImageProvider,
)
from ppt_generator.no_cad_scheme import NoCadSchemeService
from ppt_generator.openai_image import prepare_openai_image_request


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeCodexRunner:
    def __init__(self, *, signed_in: bool = True, mode: str = "files") -> None:
        self.signed_in = signed_in
        self.mode = mode
        self.calls: list[tuple[tuple[str, ...], Path | None, str, int]] = []

    def __call__(self, command, cwd, stdin_text, timeout_seconds):
        command = tuple(command)
        self.calls.append((command, cwd, stdin_text, timeout_seconds))
        if command[-2:] == ("login", "status"):
            if self.signed_in:
                return CodexCommandResult(0, stderr="Logged in using ChatGPT\n")
            return CodexCommandResult(1, stderr="Not logged in\n")
        if command[-1:] == ("login",):
            self.signed_in = True
            return CodexCommandResult(0, stdout="Login successful\n")
        if "exec" in command:
            assert cwd is not None
            if self.mode == "usage-limit":
                return CodexCommandResult(
                    1, stderr="You have reached your usage limit."
                )
            if self.mode == "embedded":
                encoded = base64.b64encode(ONE_PIXEL_PNG).decode("ascii")
                return CodexCommandResult(
                    0,
                    stdout=json.dumps(
                        {
                            "type": "item.completed",
                            "thread_id": "thread-embedded",
                            "image_url": f"data:image/png;base64,{encoded}",
                        }
                    ),
                )
            for index in range(1, 3):
                (cwd / f"candidate_{index:02d}.png").write_bytes(ONE_PIXEL_PNG)
            return CodexCommandResult(
                0,
                stdout=json.dumps(
                    {"type": "thread.started", "thread_id": "thread-files"}
                ),
            )
        raise AssertionError(f"unexpected Codex command: {command}")


class CodexImageProviderTests(unittest.TestCase):
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

    def test_login_and_status_use_chatgpt_authentication(self) -> None:
        runner = FakeCodexRunner(signed_in=False)
        provider = CodexImageProvider(
            codex_bin="codex-test", command_runner=runner
        )

        with self.assertRaisesRegex(CodexImageError, "尚未登录"):
            provider.test_connection()

        message = provider.login()

        self.assertIn("ChatGPT", message)
        self.assertIn("会员套餐额度", provider.test_connection())
        self.assertTrue(any(call[0][-1] == "login" for call in runner.calls))

    def test_generate_saves_codex_candidates_and_trace_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = FakeCodexRunner()
            provider = CodexImageProvider(
                codex_bin="codex-test", command_runner=runner
            )

            batch = provider.generate(self._request(root, count=2))

            self.assertEqual(batch.provider, "codex-pro")
            self.assertEqual(batch.request_id, "thread-files")
            self.assertEqual(len(batch.candidates), 2)
            self.assertTrue(all(item.image_path.is_file() for item in batch.candidates))
            manifest = json.loads(batch.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schemaVersion"], "codex-image-batch/v1")
            self.assertEqual(manifest["codex"]["authMode"], "chatgpt")
            self.assertEqual(manifest["result"]["provider"], "codex-pro")
            exec_call = next(call for call in runner.calls if "exec" in call[0])
            self.assertIn("workspace-write", exec_call[0])
            self.assertIn("forced_login_method=\"chatgpt\"", exec_call[0])
            self.assertIn("imagegen", exec_call[2])

    def test_embedded_png_result_is_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = CodexImageProvider(
                codex_bin="codex-test",
                command_runner=FakeCodexRunner(mode="embedded"),
            )

            batch = provider.generate(self._request(root))

            self.assertEqual(len(batch.candidates), 1)
            self.assertEqual(batch.request_id, "thread-embedded")
            self.assertEqual(batch.candidates[0].image_path.read_bytes(), ONE_PIXEL_PNG)

    def test_usage_limit_has_codex_specific_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = CodexImageProvider(
                codex_bin="codex-test",
                command_runner=FakeCodexRunner(mode="usage-limit"),
            )

            with self.assertRaisesRegex(CodexImageError, "会员使用额度"):
                provider.generate(self._request(Path(temp_dir)))


if __name__ == "__main__":
    unittest.main()


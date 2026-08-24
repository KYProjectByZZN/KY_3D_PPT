from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from ppt_generator import PptProject, ensure_project_modules, load_manifest
from ppt_generator.preview import (
    OfficePreviewSession,
    PreviewError,
    ensure_template_thumbnail,
    physical_slide_number,
    preview_fingerprint,
    render_page_preview,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "templates" / "冲压筒形壳体检测方案NAT6704_v2.pptx"
MANIFEST = PROJECT_ROOT / "templates" / "NAT6704_v2.template.json"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class PreviewServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = PptProject(
            template_path=str(TEMPLATE),
            manifest_path=str(MANIFEST),
        )
        ensure_project_modules(self.project, load_manifest(MANIFEST))

    def test_physical_slide_number_uses_final_enabled_order(self) -> None:
        first = self.project.modules[0]
        second = self.project.modules[1]
        first.enabled = False
        self.assertEqual(
            physical_slide_number(self.project, second.id, second.slides[0].id),
            1,
        )
        with self.assertRaisesRegex(PreviewError, "未启用"):
            physical_slide_number(self.project, first.id, first.slides[0].id)

    def test_render_page_preview_supports_injected_exporter(self) -> None:
        module = self.project.modules[4]
        slide = module.slides[0]
        calls: list[tuple[int, str]] = []

        def fake_renderer(
            project,
            module_id,
            slide_id,
            destination,
            *,
            overwrite=False,
        ):
            self.assertEqual(module_id, module.id)
            self.assertEqual(slide_id, slide.id)
            destination.write_bytes(b"PK\x03\x04")
            return destination

        def fake_exporter(pptx_path, page_number, output_path):
            calls.append((page_number, pptx_path.name))
            output_path.write_bytes(PNG_1X1)
            return "测试后端"

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            output = Path(temp_dir) / "preview.png"
            path, backend, page_number = render_page_preview(
                self.project,
                module.id,
                slide.id,
                output,
                renderer=fake_renderer,
                exporter=fake_exporter,
            )
            self.assertEqual(path, output.resolve())
            self.assertEqual(backend, "测试后端")
            self.assertEqual(page_number, 5)
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
            self.assertEqual(calls, [(1, "current_project.pptx")])

    def test_preview_fingerprint_changes_after_content_or_style_change(self) -> None:
        module = self.project.modules[4]
        slide = module.slides[0]
        before = preview_fingerprint(self.project, module.id, slide.id)
        self.assertEqual(
            before,
            preview_fingerprint(self.project, module.id, slide.id),
        )
        slide.overrides["equipment_title"] = "更新后的设备标题"
        self.assertNotEqual(
            before,
            preview_fingerprint(self.project, module.id, slide.id),
        )
        after_content = preview_fingerprint(self.project, module.id, slide.id)
        self.project.presentation_style.navigation_background = "#DDEEFF"
        self.assertNotEqual(
            after_content,
            preview_fingerprint(self.project, module.id, slide.id),
        )

    def test_office_session_reuses_one_helper_process(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            directory = Path(temp_dir)
            helper = directory / "fake_office_server.py"
            helper.write_text(
                "import json, sys\n"
                "from pathlib import Path\n"
                "print(json.dumps({'event':'ready','ok':True,'backend':'测试Office'}), flush=True)\n"
                "for line in sys.stdin:\n"
                "    request=json.loads(line)\n"
                "    if request.get('command') == 'shutdown': break\n"
                "    Path(request['output']).write_bytes(b'\\x89PNG\\r\\n\\x1a\\nFAKE')\n"
                "    print(json.dumps({'event':'export','ok':True,'backend':'测试Office'}), flush=True)\n",
                encoding="utf-8",
            )
            session = OfficePreviewSession(helper_path=helper, timeout_seconds=5)
            try:
                source = directory / "source.pptx"
                source.write_bytes(b"PK\x03\x04")
                first = directory / "first.png"
                second = directory / "second.png"
                self.assertEqual(session.export(source, 1, first), "测试Office")
                process_id = session.process_id
                self.assertIsNotNone(process_id)
                self.assertEqual(session.export(source, 1, second), "测试Office")
                self.assertEqual(session.process_id, process_id)
                self.assertTrue(first.read_bytes().startswith(b"\x89PNG"))
                self.assertTrue(second.read_bytes().startswith(b"\x89PNG"))
            finally:
                session.close()
            self.assertIsNone(session.process_id)

    def test_template_thumbnail_cache_skips_second_office_export(self) -> None:
        class FakeOfficeSession:
            def __init__(self) -> None:
                self.calls = 0
                self.slide_numbers: list[int] = []
                self.input_names: list[str] = []

            def export(self, pptx_path, slide_number, output_path, **_kwargs):
                self.calls += 1
                self.slide_numbers.append(slide_number)
                self.input_names.append(pptx_path.name)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(PNG_1X1)
                return "测试Office"

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
            office = FakeOfficeSession()
            cache_root = Path(temp_dir) / "cache"
            path, backend, cached = ensure_template_thumbnail(
                self.project,
                cache_root,
                23,
                office,
            )
            self.assertEqual((backend, cached), ("测试Office", False))
            self.assertEqual(office.calls, 1)
            self.assertEqual(office.slide_numbers, [23])
            self.assertEqual(office.input_names, ["template.pptx"])
            self.assertTrue(path.is_file())

            second_path, backend, cached = ensure_template_thumbnail(
                self.project,
                cache_root,
                23,
                office,
            )
            self.assertEqual(second_path, path)
            self.assertEqual((backend, cached), ("持久缓存", True))
            self.assertEqual(office.calls, 1)


if __name__ == "__main__":
    unittest.main()

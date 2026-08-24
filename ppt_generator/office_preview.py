"""Export one PPTX slide to PNG through an installed Office application."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


OFFICE_BACKENDS = (
    ("Microsoft PowerPoint", "PowerPoint.Application"),
    ("WPS 演示", "KWPP.Application"),
)


class OfficeApplicationSession:
    """Keep one private PowerPoint/WPS process alive for repeated exports."""

    def __init__(self) -> None:
        self.application: Any = None
        self.backend_name = ""
        self._pythoncom: Any = None
        self._com_initialized = False

    def start(self) -> str:
        if self.application is not None:
            return self.backend_name
        import pythoncom
        import win32com.client

        self._pythoncom = pythoncom
        pythoncom.CoInitialize()
        self._com_initialized = True
        errors: list[str] = []
        for backend_name, prog_id in OFFICE_BACKENDS:
            application: Any = None
            try:
                application = win32com.client.DispatchEx(prog_id)
                try:
                    application.DisplayAlerts = 1
                except Exception:
                    pass
                self.application = application
                self.backend_name = backend_name
                return backend_name
            except Exception as exc:
                errors.append(f"{backend_name}：{exc}")
                if application is not None:
                    try:
                        application.Quit()
                    except Exception:
                        pass
        self.close()
        raise RuntimeError("；".join(errors))

    def export(
        self,
        input_path: Path,
        slide_number: int,
        output_path: Path,
    ) -> str:
        self.start()
        presentation: Any = None
        try:
            presentation = self.application.Presentations.Open(
                str(input_path),
                True,
                False,
                False,
            )
            count = int(presentation.Slides.Count)
            if not 1 <= slide_number <= count:
                raise ValueError(f"页码超出范围：{slide_number}，文件共 {count} 页")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            presentation.Slides.Item(slide_number).Export(
                str(output_path),
                "PNG",
                1600,
                900,
            )
            if not output_path.is_file():
                raise RuntimeError("Office 未生成预览图片")
            return self.backend_name
        finally:
            if presentation is not None:
                try:
                    presentation.Close()
                except Exception:
                    pass

    def close(self) -> None:
        if self.application is not None:
            try:
                self.application.Quit()
            except Exception:
                pass
            self.application = None
        if self._com_initialized and self._pythoncom is not None:
            self._pythoncom.CoUninitialize()
            self._com_initialized = False


def export_slide(input_path: Path, slide_number: int, output_path: Path) -> str:
    session = OfficeApplicationSession()
    try:
        return session.export(input_path, slide_number, output_path)
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one PPTX slide to PNG")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--slide", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not input_path.is_file() or input_path.suffix.lower() != ".pptx":
        parser.error(f"PPTX 文件不存在：{input_path}")
    if args.slide < 1:
        parser.error("页码必须大于等于 1")

    try:
        backend = export_slide(input_path, args.slide, output_path)
    except Exception as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps({"backend": backend}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

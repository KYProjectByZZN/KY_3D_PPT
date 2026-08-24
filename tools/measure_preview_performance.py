"""Measure cold and warm current-page preview latency with the default project."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ppt_generator import PptProject, ensure_project_modules, load_manifest
from ppt_generator.preview import OfficePreviewSession, render_page_preview


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--module-index", type=int, default=4)
    parser.add_argument("--page-index", type=int, default=0)
    args = parser.parse_args()

    template = PROJECT_ROOT / "templates" / "冲压筒形壳体检测方案NAT6704_v2.pptx"
    manifest_path = PROJECT_ROOT / "templates" / "NAT6704_v2.template.json"
    data_path = PROJECT_ROOT / "examples" / "NAT6704_v2_test_data.json"
    project = PptProject(
        project_name="预览性能测试",
        template_path=str(template),
        manifest_path=str(manifest_path),
        values=json.loads(data_path.read_text(encoding="utf-8")),
    )
    ensure_project_modules(project, load_manifest(manifest_path))
    module = project.modules[args.module_index]
    slide = module.slides[args.page_index]

    timings: list[float] = []
    office_session = OfficePreviewSession()
    try:
        with tempfile.TemporaryDirectory(prefix="kyppt_benchmark_") as temp_dir:
            for run in range(1, args.runs + 1):
                output = Path(temp_dir) / f"preview_{run}.png"
                started = time.perf_counter()
                _, backend, page_number = render_page_preview(
                    project,
                    module.id,
                    slide.id,
                    output,
                    office_session=office_session,
                )
                elapsed = time.perf_counter() - started
                timings.append(elapsed)
                print(
                    f"run={run} seconds={elapsed:.3f} backend={backend} "
                    f"physical_page={page_number} bytes={output.stat().st_size}"
                )
    finally:
        office_session.close()
    print("timings=" + ",".join(f"{item:.3f}" for item in timings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

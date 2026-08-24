"""Create an offscreen screenshot and basic metrics for desktop UI review."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QTableWidgetSelectionRange

from ppt_generator import ExcelMappingRule
from ppt_generator.preview import preview_fingerprint
from ppt_generator.ui.app import create_application
from ppt_generator.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "ui_desktop_mvp.png",
    )
    parser.add_argument(
        "--view", choices=["modules", "scheme", "excel"], default="modules"
    )
    parser.add_argument(
        "--wait-preview-seconds",
        type=float,
        default=0,
        help="Keep processing UI events until the current-page preview finishes.",
    )
    parser.add_argument(
        "--preview-cycle",
        action="store_true",
        help="Load two pages, then return to the first page to verify caching.",
    )
    parser.add_argument(
        "--capture-template-stage",
        action="store_true",
        help="Capture the immediate template thumbnail before live preview replaces it.",
    )
    args = parser.parse_args()

    application = create_application([])
    window = MainWindow()
    window.resize(1800, 940)
    if args.view == "excel":
        demo_excel = PROJECT_ROOT / "examples" / "excel_mapping_demo.xlsx"
        demo_rules = PROJECT_ROOT / "examples" / "excel_mapping_demo.json"
        window.tabs.setCurrentIndex(2)
        window.source_inner_tabs.setCurrentIndex(0)
        window._load_excel_path(str(demo_excel), log=False)
        raw = json.loads(demo_rules.read_text(encoding="utf-8"))
        window.project.excel_mappings = [
            ExcelMappingRule.from_dict(item) for item in raw["mappings"]
        ]
        window._refresh_excel_mapping_table()
        window.excel_header_spin.setValue(6)
        window.excel_preview_table.setRangeSelected(
            QTableWidgetSelectionRange(5, 0, 11, 3), True
        )
    elif args.view == "modules":
        window.tabs.setCurrentIndex(1)
        equipment_page = window.module_editor.tree.topLevelItem(4).child(0)
        window.module_editor.tree.setCurrentItem(equipment_page)
    else:
        window.tabs.setCurrentIndex(1)
        window.module_workspace_tabs.setCurrentIndex(1)
        window.scheme_editor.tabs.setCurrentIndex(1)
        if window.scheme_editor.flow_table.rowCount():
            window.scheme_editor.flow_table.selectRow(0)
    window.show()
    application.processEvents()
    if args.capture_template_stage:
        template_deadline = time.monotonic() + 0.15
        while time.monotonic() < template_deadline:
            application.processEvents()
            time.sleep(0.01)
    deadline = time.monotonic() + max(0, args.wait_preview_seconds)
    preview_timings: list[float] = []
    while args.wait_preview_seconds > 0 and time.monotonic() < deadline:
        application.processEvents()
        if window.slide_preview.status_label.text().startswith("最终PPT第"):
            break
        time.sleep(0.05)
    if args.preview_cycle and args.view == "modules":
        pages = [
            window.module_editor.tree.topLevelItem(5).child(0),
            window.module_editor.tree.topLevelItem(4).child(0),
        ]
        for page in pages:
            started = time.perf_counter()
            window.module_editor.tree.setCurrentItem(page)
            application.processEvents()
            module_id = window.slide_preview.current_module_id
            slide_id = window.slide_preview.current_slide_id
            cache_key = preview_fingerprint(window.project, module_id, slide_id)
            page_deadline = time.monotonic() + max(1, args.wait_preview_seconds)
            while time.monotonic() < page_deadline:
                application.processEvents()
                if cache_key in window._preview_cache:
                    break
                time.sleep(0.02)
            preview_timings.append(time.perf_counter() - started)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(args.output), "PNG"):
        raise RuntimeError(f"界面截图保存失败：{args.output}")
    print(
        f"screenshot={args.output.resolve()} tabs={window.tabs.count()} "
        f"modules={window.module_editor.tree.topLevelItemCount()} "
        f"page_fields={window.module_editor.field_table.rowCount()} "
        f"global_fields={window.field_table.rowCount()} "
        f"preview_status={window.slide_preview.status_label.text()} "
        f"preview_cycle={','.join(f'{item:.3f}' for item in preview_timings)} "
        f"memory_cache={len(window._preview_cache)} "
        f"image_kind={window.slide_preview._image_kind}"
    )
    window.close()
    application.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

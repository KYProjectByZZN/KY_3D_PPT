"""Build three end-to-end auto-solution v2 demo results and UI captures."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ppt_generator.auto_solution_application import AutoSolutionApplication
from ppt_generator.auto_solution_repository import JsonAutoSolutionRepository


MOCK_REQUIREMENTS = (
    {
        "customer": "演示客户A",
        "project": "金属冲压壳体外观检测",
        "product": "冲压壳体",
        "productType": "金属冲压件",
        "original": (
            "产品尺寸85×45×12mm，不锈钢，振动盘上料，OK/NG分选，"
            "检测划伤、压伤、缺口和尺寸，节拍1.5秒/件，表面反光，要求连续生产。"
        ),
    },
    {
        "customer": "演示客户B",
        "project": "透明塑料盖尺寸与缺陷检测",
        "product": "透明塑料盖",
        "productType": "透明塑料件",
        "original": (
            "透明塑料件120×60×20mm，皮带线上料和皮带线下料，"
            "检测尺寸、缺口、脏污和有无，节拍2.0秒/件，产品透明且易划伤。"
        ),
    },
    {
        "customer": "演示客户C",
        "project": "托盘电子件字符检测",
        "product": "电子装配件",
        "productType": "电子装配件",
        "original": (
            "产品35×25×8mm，料盘上料、料盘收料，检测字符、二维码、装配和有无，"
            "节拍3.0秒/件，需要防静电。"
        ),
    },
)


def build_demo(output_path: Path, requirement_image: Path, candidate_image: Path) -> None:
    for path in (output_path, requirement_image, candidate_image):
        path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temporary:
        app = AutoSolutionApplication(
            repository=JsonAutoSolutionRepository(Path(temporary) / "store.json"),
            actor="演示工程师",
        )
        results = []
        requirement_ids = []
        for mock in MOCK_REQUIREMENTS:
            requirement = app.new_requirement()
            requirement.customer_name = mock["customer"]
            requirement.project_name = mock["project"]
            requirement.product_name = mock["product"]
            requirement.original_requirement = mock["original"]
            requirement.structured_requirement.basic_info.product_type = mock["productType"]
            suggestions = app.parse_requirement(requirement)
            applied = app.apply_suggestions(requirement, suggestions)
            saved = app.save_requirement(requirement)
            matches = app.retrieve_history(saved.id)
            candidate = app.generate_candidate(saved.id)
            requirement_ids.append(saved.id)
            results.append(
                {
                    "requirement": saved.to_dict(),
                    "parser": app.parser_name,
                    "suggestions": [value.to_dict() for value in suggestions],
                    "appliedPaths": applied,
                    "historicalMatches": [
                        {
                            **value.to_reference_dict(),
                            "productType": value.record.product_type,
                            "inspectionItems": value.record.inspection_items,
                        }
                        for value in matches
                    ],
                    "candidateSolution": candidate.to_dict(),
                }
            )
        output_path.write_text(
            json.dumps(
                {
                    "title": "自动方案 v2 三组 Mock 端到端结果",
                    "notice": "所有历史引用均标明 demo，仅用于验证流程，不代表公司真实项目。",
                    "resultCount": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        capture_ui(app, requirement_ids[0], requirement_image, candidate_image)


def capture_ui(
    application: AutoSolutionApplication,
    requirement_id: str,
    requirement_image: Path,
    candidate_image: Path,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ppt_generator.ui.auto_solution_editor import AutoSolutionEditor
    from ppt_generator.ui.styles import APP_QSS

    qt_app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    qt_app.setStyle("Fusion")
    qt_app.setFont(QFont("Microsoft YaHei UI", 10))
    qt_app.setStyleSheet(APP_QSS)
    widget = AutoSolutionEditor(application=application)
    widget.resize(1800, 980)
    widget.show()
    widget.requirement_widget.refresh_records(select_id=requirement_id)
    widget.stage_list.setCurrentRow(0)
    qt_app.processEvents()
    if not widget.grab().save(str(requirement_image), "PNG"):
        raise RuntimeError(f"无法保存需求管理页面图：{requirement_image}")
    widget.candidate_widget.set_requirement_id(requirement_id)
    widget.stage_list.setCurrentRow(2)
    qt_app.processEvents()
    if not widget.grab().save(str(candidate_image), "PNG"):
        raise RuntimeError(f"无法保存候选方案页面图：{candidate_image}")
    widget.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/自动方案_v2_三组Mock结果.json"),
    )
    parser.add_argument(
        "--requirement-image",
        type=Path,
        default=Path("output/ui_自动方案_v2_需求管理.png"),
    )
    parser.add_argument(
        "--candidate-image",
        type=Path,
        default=Path("output/ui_自动方案_v2_候选方案.png"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = (args.output, args.requirement_image, args.candidate_image)
    existing = [path for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError("输出已存在；如需替换请使用 --overwrite：" + "，".join(map(str, existing)))
    build_demo(args.output, args.requirement_image, args.candidate_image)
    print(args.output)
    print(args.requirement_image)
    print(args.candidate_image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

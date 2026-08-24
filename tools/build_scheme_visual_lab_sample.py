"""Build deterministic Scheme Visual Lab review artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ppt_generator.scheme_visual_lab import (
    SchemeVisualLabService,
    demo_drawing_specification,
)


def build_sample(svg_path: Path, recipe_path: Path, ui_image_path: Path) -> None:
    for path in (svg_path, recipe_path, ui_image_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    result = SchemeVisualLabService().run(demo_drawing_specification())
    svg_path.write_text(result.svg, encoding="utf-8")
    recipe_path.write_text(
        json.dumps(result.prompt_recipe.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    capture_ui(ui_image_path)


def capture_ui(ui_image_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ppt_generator.ui.scheme_visual_lab import SchemeVisualLabWidget
    from ppt_generator.ui.styles import APP_QSS

    application = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    application.setStyleSheet(APP_QSS)
    widget = SchemeVisualLabWidget()
    widget.resize(1900, 980)
    widget.show()
    application.processEvents()
    if not widget.grab().save(str(ui_image_path), "PNG"):
        raise RuntimeError(f"无法保存方案图实验室界面图：{ui_image_path}")
    widget.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--svg",
        type=Path,
        default=Path("output/方案图实验室_结构示意图.svg"),
    )
    parser.add_argument(
        "--recipe",
        type=Path,
        default=Path("output/方案图实验室_PromptRecipe.json"),
    )
    parser.add_argument(
        "--ui-image",
        type=Path,
        default=Path("output/ui_方案图实验室.png"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = (args.svg, args.recipe, args.ui_image)
    existing = [path for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "输出已存在；如需替换请使用 --overwrite：" + "，".join(map(str, existing))
        )
    build_sample(args.svg, args.recipe, args.ui_image)
    print(args.svg)
    print(args.recipe)
    print(args.ui_image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build deterministic no-CAD logic scheme review artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ppt_generator.no_cad_scheme import MODULE_BY_TYPE, NoCadSchemeService


def build_sample(
    svg_path: Path,
    scene_path: Path,
    passed_image_path: Path,
    blocked_image_path: Path,
) -> None:
    for path in (svg_path, scene_path, passed_image_path, blocked_image_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    service = NoCadSchemeService()
    scene = service.create_demo_scene()
    result = service.evaluate(scene)
    svg_path.write_text(result.svg, encoding="utf-8")
    scene_path.write_text(
        json.dumps(
            {"scene": scene.to_dict(), "result": result.to_dict()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    capture_ui(passed_image_path, blocked_image_path)


def capture_ui(passed_image_path: Path, blocked_image_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ppt_generator.ui.no_cad_scheme_editor import NoCadSchemeEditor
    from ppt_generator.ui.styles import APP_QSS

    application = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    application.setStyleSheet(APP_QSS)
    widget = NoCadSchemeEditor()
    widget.resize(1920, 1040)
    widget.show()
    application.processEvents()
    if not widget.grab().save(str(passed_image_path), "PNG"):
        raise RuntimeError(f"无法保存逻辑通过界面图：{passed_image_path}")

    widget.scene.nodes[:] = [
        node
        for node in widget.scene.nodes
        if MODULE_BY_TYPE[node.module_type].category != "inspect"
    ]
    widget.service.rebuild_connections(widget.scene)
    widget.service.auto_layout(widget.scene)
    widget.refresh()
    application.processEvents()
    if not widget.grab().save(str(blocked_image_path), "PNG"):
        raise RuntimeError(f"无法保存逻辑阻断界面图：{blocked_image_path}")
    widget.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--svg",
        type=Path,
        default=Path("output/无CAD设备逻辑方案.svg"),
    )
    parser.add_argument(
        "--scene",
        type=Path,
        default=Path("output/无CAD设备逻辑方案.scene.json"),
    )
    parser.add_argument(
        "--passed-image",
        type=Path,
        default=Path("output/ui_无CAD设备逻辑方案_通过.png"),
    )
    parser.add_argument(
        "--blocked-image",
        type=Path,
        default=Path("output/ui_无CAD设备逻辑方案_阻断.png"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = (args.svg, args.scene, args.passed_image, args.blocked_image)
    existing = [path for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "输出已存在；如需替换请使用 --overwrite：" + "，".join(map(str, existing))
        )
    build_sample(args.svg, args.scene, args.passed_image, args.blocked_image)
    for path in targets:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

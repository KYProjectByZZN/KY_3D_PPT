"""Command-line entry point for configuration-driven template rendering."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ppt_generator import TemplateRenderError, render_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 JSON 配置替换 PPTX 模板中的文字、表格和图片")
    parser.add_argument("--template", type=Path, required=True, help="原始 PPTX 模板")
    parser.add_argument("--manifest", type=Path, required=True, help="模板 Slot 配置 JSON")
    parser.add_argument("--data", type=Path, required=True, help="本次渲染数据 JSON")
    parser.add_argument("--output", type=Path, required=True, help="新 PPTX 输出路径")
    parser.add_argument(
        "--module",
        action="append",
        dest="modules",
        help="仅保留指定模块，可重复传入；默认保留全部模块",
    )
    parser.add_argument(
        "--module-order",
        help="模块排序，以英文逗号分隔；未列出的已启用模块按配置顺序追加",
    )
    parser.add_argument("--overwrite", action="store_true", help="明确允许覆盖已有输出文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = render_template(
            template_path=args.template,
            manifest_path=args.manifest,
            data_path=args.data,
            output_path=args.output,
            overwrite=args.overwrite,
            enabled_modules=args.modules,
            module_order=(
                [item.strip() for item in args.module_order.split(",") if item.strip()]
                if args.module_order
                else None
            ),
        )
    except (FileNotFoundError, FileExistsError, OSError, TemplateRenderError) as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 2
    print(f"PPT 已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

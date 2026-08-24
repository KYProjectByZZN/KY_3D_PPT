"""Command-line entry point for KY PPT Generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from ppt_generator import build_presentation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成一个可编辑的16:9 PowerPoint文件")
    parser.add_argument("--title", required=True, help="封面标题")
    parser.add_argument("--subtitle", default="", help="封面副标题")
    parser.add_argument("--bullet", action="append", default=[], help="内容要点，可重复传入")
    parser.add_argument("--output", type=Path, default=Path("output/demo.pptx"), help="输出PPTX路径")
    parser.add_argument("--overwrite", action="store_true", help="明确允许覆盖已有文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = build_presentation(
        title=args.title,
        subtitle=args.subtitle,
        bullets=args.bullet,
        output_path=args.output,
        overwrite=args.overwrite,
    )
    print(f"PPT已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

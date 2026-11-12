"""Add traceable red rectangles and labels to an existing CATIA evidence image."""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(item.strip()) for item in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x1,y1,x2,y2")
    x1, y1, x2, y2 = parts
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        raise argparse.ArgumentTypeError("box must have non-negative coordinates and x2>x1, y2>y1")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--box", action="append", type=parse_box, required=True,
                        help="Pixel rectangle x1,y1,x2,y2; repeatable")
    parser.add_argument("--label", default="CHECK")
    args = parser.parse_args()
    with Image.open(args.input) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    stroke = max(4, min(width, height) // 160)
    font = ImageFont.load_default()
    for box in args.box:
        x1, y1, x2, y2 = box
        if x2 > width or y2 > height:
            parser.error(f"box {box} exceeds image size {width}x{height}")
        draw.rectangle(box, outline=(230, 0, 0), width=stroke)
        label_box = draw.textbbox((x1, y1), args.label, font=font, stroke_width=1)
        label_height = label_box[3] - label_box[1] + 8
        label_width = label_box[2] - label_box[0] + 12
        top = max(0, y1 - label_height)
        draw.rectangle((x1, top, min(width, x1 + label_width), y1), fill=(230, 0, 0))
        draw.text((x1 + 6, top + 3), args.label, fill="white", font=font, stroke_width=1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, quality=94)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


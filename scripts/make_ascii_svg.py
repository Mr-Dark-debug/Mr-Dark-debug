#!/usr/bin/env python3
"""Convert a prepared portrait into an accessible, one-shot animated ASCII SVG.

Conceptual inspiration: https://github.com/AVIVASHISHTA29/AVIVASHISHTA29
This implementation and its visual system are original to this profile.
"""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageEnhance, ImageOps

try:
    from scripts.fetch_contributions import atomic_write_text
except ModuleNotFoundError:
    from fetch_contributions import atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "assets" / "source-prepped.png"
DEFAULT_OUTPUT = ROOT / "generated" / "prashant-ascii.svg"
WIDTH = 360
HEIGHT = 470
COLS = 100
ROWS = 58
RAMP = " .,:;ox%#@"
INK = "#d7e0ea"


def image_to_rows(source: Path, columns: int = COLS, rows: int = ROWS) -> list[str]:
    if columns < 90 or columns > 110:
        raise ValueError("ASCII portrait must use 90–110 columns")
    if rows < 1:
        raise ValueError("rows must be positive")
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("L")
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Sharpness(image).enhance(1.25)
    image = image.resize((columns, rows), Image.Resampling.LANCZOS)
    pixels = image.load()
    output: list[str] = []
    for y in range(rows):
        characters: list[str] = []
        for x in range(columns):
            luminance = pixels[x, y] / 255.0
            luminance = luminance**1.10
            if luminance >= 0.93:
                characters.append(" ")
                continue
            index = round((1.0 - luminance) * (len(RAMP) - 1))
            characters.append(RAMP[max(0, min(len(RAMP) - 1, index))])
        output.append("".join(characters))
    return output


def render_ascii_svg(rows: Sequence[str], static: bool = False) -> str:
    if not rows:
        raise ValueError("ASCII portrait rows cannot be empty")
    if any(len(row) > COLS for row in rows):
        raise ValueError(f"ASCII portrait rows cannot exceed {COLS} columns")
    art_x = 16
    art_y = 44
    art_width = 328
    row_height = 6.34
    font_size = 6.1
    title = "Prashant Choudhary ASCII portrait"
    desc = "A monochrome ASCII rendering generated from Prashant's supplied portrait photograph."
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{title}</title><desc id="desc">{html.escape(desc)}</desc>',
        '<defs><linearGradient id="panel" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#101722"/><stop offset="1" stop-color="#0b0f14"/></linearGradient></defs>',
        '<rect x="0.5" y="0.5" width="359" height="469" rx="14" fill="url(#panel)" stroke="#273240"/>',
        '<path d="M0 35.5H360" stroke="#273240"/>',
        '<rect x="18" y="14" width="7" height="7" rx="2" fill="#39d98a"/>',
        '<text x="31" y="22" fill="#748193" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">portrait.py --render</text>',
    ]
    for index, row in enumerate(rows):
        baseline = art_y + index * row_height + 5.2
        safe = html.escape(row)
        text = (
            f'<text xml:space="preserve" x="{art_x}" y="{baseline:.2f}" fill="{INK}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{font_size}" '
            f'textLength="{art_width}" lengthAdjust="spacing">{safe}</text>'
        )
        if static:
            parts.append(text)
            continue
        row_top = art_y + index * row_height
        delay = 0.05 + index * 0.032
        parts.append(
            f'<clipPath id="line-{index}"><rect x="{art_x}" y="{row_top:.2f}" width="0" height="{row_height + 1:.2f}">'
            f'<animate attributeName="width" from="0" to="{art_width}" begin="{delay:.3f}s" dur=".24s" fill="freeze"/>'
            "</rect></clipPath>"
        )
        parts.append(f'<g clip-path="url(#line-{index})">{text}</g>')
    parts.extend(
        [
            '<path d="M16 423.5H344" stroke="#273240"/>',
            '<text x="16" y="446" fill="#607080" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">identity</text>',
            '<text x="82" y="446" fill="#8af7bd" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11" font-weight="700">Prashant Choudhary</text>',
            '<text x="344" y="446" fill="#607080" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9">source: real portrait</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = image_to_rows(args.source)
    svg = render_ascii_svg(rows, static=bool(os.environ.get("STATIC")))
    atomic_write_text(args.output, svg + "\n")
    print(f"wrote {args.output}: {WIDTH}x{HEIGHT}, {COLS} columns, {len(svg):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

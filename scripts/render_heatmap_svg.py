#!/usr/bin/env python3
"""Render normalized contribution data as an accessible animated SVG."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

try:
    from scripts.fetch_contributions import atomic_write_text
except ModuleNotFoundError:  # Direct execution: python scripts/render_heatmap_svg.py
    from fetch_contributions import atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "contributions.json"
DEFAULT_OUTPUT = ROOT / "generated" / "contrib-heatmap.svg"
WIDTH = 860
HEIGHT = 258
CELL = 11
GAP = 3
STEP = CELL + GAP
GRID_LEFT = 62
GRID_TOP = 58
PALETTE = ("#18202b", "#123a2c", "#176b43", "#20a464", "#39d98a", "#8af7bd")


def _level(count: int, positive_counts: Sequence[int]) -> int:
    if count <= 0:
        return 0
    if not positive_counts:
        return 1
    maximum = max(positive_counts)
    ratio = count / maximum if maximum else 0
    if ratio <= 0.15:
        return 1
    if ratio <= 0.35:
        return 2
    if ratio <= 0.60:
        return 3
    if ratio <= 0.82:
        return 4
    return 5


def _validate_payload(payload: Mapping[str, object]) -> list[dict[str, object]]:
    raw_days = payload.get("days")
    if not isinstance(raw_days, list) or len(raw_days) != 371:
        raise ValueError("contribution payload must contain exactly 371 days")
    days: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in raw_days:
        if not isinstance(entry, dict):
            raise ValueError("each contribution day must be an object")
        date_text = entry.get("date")
        count = entry.get("count")
        if not isinstance(date_text, str) or not isinstance(count, int) or count < 0:
            raise ValueError("invalid contribution day")
        dt.date.fromisoformat(date_text)
        if date_text in seen:
            raise ValueError(f"duplicate contribution date: {date_text}")
        seen.add(date_text)
        days.append({"date": date_text, "count": count})
    days.sort(key=lambda item: str(item["date"]))
    return days


def render_svg(payload: Mapping[str, object], static: bool = False) -> str:
    days = _validate_payload(payload)
    username = html.escape(str(payload.get("username", "Mr-Dark-debug")))
    positives = [int(day["count"]) for day in days if int(day["count"]) > 0]
    as_of = dt.date.fromisoformat(str(payload["as_of"]))

    month_labels: list[tuple[int, str]] = []
    last_month: tuple[int, int] | None = None
    for column in range(53):
        date = dt.date.fromisoformat(str(days[column * 7]["date"]))
        key = (date.year, date.month)
        if key != last_month and column > 0:
            month_labels.append((column, date.strftime("%b")))
        last_month = key

    title = f"{username} contribution activity"
    desc = "A 53-week GitHub contribution calendar generated from public profile data."
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{title}</title>",
        f"<desc id=\"desc\">{desc}</desc>",
    ]
    if not static:
        parts.append(
            "<style>"
            "@keyframes reveal{0%{opacity:0;transform:translateY(-5px) scale(.72)}100%{opacity:1;transform:translateY(0) scale(1)}}"
            ".cell{opacity:0;transform-box:fill-box;transform-origin:center;animation:reveal .34s cubic-bezier(.2,.8,.2,1) both}"
            "@media (prefers-reduced-motion:reduce){.cell{animation:none!important;opacity:1!important;transform:none!important}}"
            "</style>"
        )
    parts.extend(
        [
            '<rect x="0.5" y="0.5" width="859" height="257" rx="14" fill="#0b0f14" stroke="#273240"/>',
            '<path d="M0 35.5H860" stroke="#273240"/>',
            '<rect x="22" y="15" width="7" height="7" rx="2" fill="#39d98a"/>',
            '<text x="40" y="23" fill="#8b98a7" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">public activity · 53 weeks</text>',
            f'<text x="838" y="23" fill="#607080" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11">as of {as_of.isoformat()}</text>',
        ]
    )

    for column, label in month_labels:
        x = GRID_LEFT + column * STEP
        parts.append(f'<text x="{x}" y="50" fill="#748193" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9">{label}</text>')
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = GRID_TOP + row * STEP + 9
        parts.append(f'<text x="22" y="{y}" fill="#607080" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9">{label}</text>')

    for index, day in enumerate(days):
        column, row = divmod(index, 7)
        x = GRID_LEFT + column * STEP
        y = GRID_TOP + row * STEP
        count = int(day["count"])
        date_text = str(day["date"])
        level = _level(count, positives)
        plural = "" if count == 1 else "s"
        class_attr = "" if static else ' class="cell"'
        delay_attr = "" if static else f' style="animation-delay:{column * 0.017 + row * 0.025:.3f}s"'
        parts.append(
            f'<rect{class_attr} x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{PALETTE[level]}"{delay_attr}>'
            f'<title>{html.escape(date_text)}: {count} contribution{plural}</title></rect>'
        )

    legend_y = 166
    parts.append('<text x="698" y="175" fill="#607080" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9">less</text>')
    for index, color in enumerate(PALETTE):
        parts.append(f'<rect x="{727 + index * 15}" y="{legend_y}" width="10" height="10" rx="2" fill="{color}"/>')
    parts.append('<text x="822" y="175" fill="#607080" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9">more</text>')
    parts.append('<path d="M22 191.5H838" stroke="#273240"/>')

    total = int(payload.get("total_contributions", 0))
    active = int(payload.get("active_days", 0))
    current = int(dict(payload.get("current_streak", {})).get("length", 0))
    longest = int(dict(payload.get("longest_streak", {})).get("length", 0))
    best = dict(payload.get("best_day", {}))
    best_count = int(best.get("count", 0))
    best_date = html.escape(str(best.get("date", "—")))
    font = 'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'
    parts.extend(
        [
            f'<text x="22" y="218" fill="#d7e0ea" {font} font-size="13"><tspan fill="#8af7bd" font-weight="700">{total:,}</tspan><tspan fill="#8b98a7"> contributions · {active} active days</tspan></text>',
            f'<text x="838" y="218" fill="#8b98a7" text-anchor="end" {font} font-size="12">best <tspan fill="#d7e0ea">{best_count}</tspan> · {best_date}</text>',
            f'<text x="22" y="241" fill="#8b98a7" {font} font-size="12">current streak <tspan fill="#59d6c7">{current}d</tspan> · longest <tspan fill="#59d6c7">{longest}d</tspan></text>',
            f'<text x="838" y="241" fill="#607080" text-anchor="end" {font} font-size="11">generated by Python · public data</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    svg = render_svg(payload, static=bool(os.environ.get("STATIC")))
    atomic_write_text(args.output, svg + "\n")
    print(f"wrote {args.output}: {WIDTH}x{HEIGHT}, {len(svg):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

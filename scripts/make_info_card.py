#!/usr/bin/env python3
"""Generate the AI/Python-first terminal identity card."""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path

try:
    from scripts.fetch_contributions import atomic_write_text
except ModuleNotFoundError:
    from fetch_contributions import atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "generated" / "info-card.svg"
WIDTH = 490
HEIGHT = 470
PROFILE_ROWS = (
    ("role", "AI products · backend systems"),
    ("language", "Python · FastAPI · automation"),
    ("focus", "LLMs · NLP · agents · RAG"),
    ("models", "Transformers · PyTorch · local AI"),
    ("systems", "APIs · workers · Postgres · Docker"),
    ("study", "M.Sc. NLP · University of Trier"),
    ("previous", "AI/ML Backend Engineer · EnactOn"),
    ("building", "Vidrial · PocketLLM · MugShot Studio"),
    ("status", "Germany · open to AI engineering roles"),
)


def render_info_card(static: bool = False) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">Prashant Choudhary · AI engineering profile</title>',
        '<desc id="desc">Terminal-style summary of Prashant’s AI, Python, LLM, NLP, education, and product work.</desc>',
    ]
    if not static:
        parts.append(
            "<style>"
            "@keyframes enter{0%{opacity:0;transform:translateX(-8px)}100%{opacity:1;transform:translateX(0)}}"
            ".row{opacity:0;animation:enter .42s cubic-bezier(.2,.8,.2,1) both}"
            "@media (prefers-reduced-motion:reduce){.row{animation:none!important;opacity:1!important;transform:none!important}}"
            "</style>"
        )
    parts.extend(
        [
            '<defs><linearGradient id="panel" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#101722"/><stop offset="1" stop-color="#0b0f14"/></linearGradient></defs>',
            '<rect x="0.5" y="0.5" width="489" height="469" rx="14" fill="url(#panel)" stroke="#273240"/>',
            '<path d="M0 35.5H490" stroke="#273240"/>',
            '<rect x="18" y="14" width="7" height="7" rx="2" fill="#39d98a"/>',
            '<text x="31" y="22" fill="#748193" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10">profile.py --mode engineering</text>',
            '<text x="24" y="72" fill="#d7e0ea" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="21" font-weight="700">PRASHANT CHOUDHARY</text>',
            '<text x="24" y="99" fill="#8af7bd" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="14" font-weight="700">AI ENGINEER · PYTHON ENGINEER</text>',
            '<text x="24" y="121" fill="#59d6c7" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">NLP / LLM BUILDER</text>',
            '<path d="M24 142.5H466" stroke="#273240"/>',
        ]
    )
    font = 'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'
    for index, (label, value) in enumerate(PROFILE_ROWS):
        y = 171 + index * 29
        class_attr = "" if static else ' class="row"'
        delay_attr = "" if static else f' style="animation-delay:{0.14 + index * 0.09:.2f}s"'
        parts.append(f'<g{class_attr}{delay_attr}>')
        parts.append(f'<text x="24" y="{y}" fill="#607080" {font} font-size="11">{html.escape(label)}</text>')
        value_color = "#d7e0ea"
        weight = "700" if label in {"language", "focus", "study"} else "500"
        parts.append(f'<text x="116" y="{y}" fill="{value_color}" {font} font-size="12.5" font-weight="{weight}">{html.escape(value)}</text>')
        parts.append("</g>")
    parts.extend(
        [
            '<path d="M24 441.5H466" stroke="#273240"/>',
            f'<text x="24" y="458" fill="#607080" {font} font-size="9">verified profile · July 2026</text>',
            f'<text x="466" y="458" fill="#39d98a" text-anchor="end" {font} font-size="9">● available</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    svg = render_info_card(static=bool(os.environ.get("STATIC")))
    atomic_write_text(args.output, svg + "\n")
    print(f"wrote {args.output}: {WIDTH}x{HEIGHT}, {len(svg):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

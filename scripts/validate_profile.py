#!/usr/bin/env python3
"""Validate generated profile assets, README references, workflow, and safety."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SVG_SPECS = {
    ROOT / "generated" / "prashant-ascii.svg": (360, 470),
    ROOT / "generated" / "info-card.svg": (490, 470),
    ROOT / "generated" / "contrib-heatmap.svg": (860, 258),
}
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "update-profile-art.yml"
DATA = ROOT / "data" / "contributions.json"


def find_forbidden(text: str) -> list[str]:
    checks = (
        (r"(?i)\bmcp_token\b", "mcp_token"),
        (r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b", "GitHub token"),
        (r"\bsk-[A-Za-z0-9_-]{20,}\b", "API key"),
        (r"(?i)[?&](?:token|mcp_token|signature|sig)=[^&\s\"']+", "signed or tokenized URL"),
        (r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "private email"),
        (r"(?i)\bC:\\Users\\|/Users/|/home/", "local absolute path"),
        (r"(?i)<script\b", "JavaScript"),
        (r"(?i)<link\b[^>]*stylesheet", "external CSS"),
    )
    return [label for pattern, label in checks if re.search(pattern, text)]


def _numeric(value: str) -> int:
    match = re.fullmatch(r"(\d+)(?:px)?", value.strip())
    if not match:
        raise ValueError(f"non-numeric SVG dimension: {value}")
    return int(match.group(1))


def validate_svg(path: Path, expected: tuple[int, int]) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"{path.relative_to(ROOT)}: invalid XML ({exc})"]
    width = _numeric(root.attrib.get("width", ""))
    height = _numeric(root.attrib.get("height", ""))
    view_box = root.attrib.get("viewBox", "")
    if (width, height) != expected:
        errors.append(f"{path.relative_to(ROOT)}: expected {expected}, found {(width, height)}")
    if view_box != f"0 0 {expected[0]} {expected[1]}":
        errors.append(f"{path.relative_to(ROOT)}: incorrect viewBox {view_box!r}")
    source = path.read_text(encoding="utf-8")
    if "<title" not in source or "<desc" not in source:
        errors.append(f"{path.relative_to(ROOT)}: missing accessible title/description")
    for finding in find_forbidden(source):
        errors.append(f"{path.relative_to(ROOT)}: forbidden {finding}")
    return errors


def validate_readme() -> list[str]:
    errors: list[str] = []
    source = README.read_text(encoding="utf-8")
    required = (
        "Prashant Choudhary",
        "AI Engineer",
        "Python Engineer",
        "NLP / LLM Builder",
        "University of Trier",
        "EnactOn Technologies",
        "Vidrial",
        "PocketLLM",
        "CinePair",
    )
    for phrase in required:
        if phrase not in source:
            errors.append(f"README.md: missing required phrase {phrase!r}")
    stale = ("Coffee Addict", "Based in **India**", "Quote of the Day", "giphy.com", "komarev.com", "shields.io")
    for phrase in stale:
        if phrase.lower() in source.lower():
            errors.append(f"README.md: stale or cluttered content {phrase!r}")
    image_sources = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', source)
    for image_source in image_sources:
        if re.match(r"https?://", image_source):
            errors.append(f"README.md: external image service {image_source}")
            continue
        target = (ROOT / image_source).resolve()
        if ROOT not in target.parents or not target.is_file():
            errors.append(f"README.md: broken image path {image_source}")
    for finding in find_forbidden(source):
        errors.append(f"README.md: forbidden {finding}")
    return errors


def validate_data() -> list[str]:
    errors: list[str] = []
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    days = payload.get("days")
    if payload.get("username") != "Mr-Dark-debug":
        errors.append("data/contributions.json: incorrect username")
    if not isinstance(days, list) or len(days) != 371:
        errors.append("data/contributions.json: expected exactly 371 days")
    elif any(not isinstance(day.get("count"), int) or day["count"] < 0 for day in days):
        errors.append("data/contributions.json: invalid contribution count")
    return errors


def validate_workflow() -> list[str]:
    source = WORKFLOW.read_text(encoding="utf-8")
    requirements = (
        "workflow_dispatch:",
        'cron: "17 4 * * *"',
        "contents: write",
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "python scripts/fetch_contributions.py",
        "python scripts/render_heatmap_svg.py",
        "python scripts/validate_profile.py",
        "git diff --cached --quiet",
        "[skip ci]",
    )
    errors = [f"workflow: missing {item!r}" for item in requirements if item not in source]
    if re.search(r"(?m)^\s+(?:pull-requests|issues|actions):\s+write\s*$", source):
        errors.append("workflow: permission exceeds contents: write")
    for finding in find_forbidden(source):
        if finding != "private email":  # GitHub's documented bot noreply identity is intentional.
            errors.append(f"workflow: forbidden {finding}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path, dimensions in SVG_SPECS.items():
        errors.extend(validate_svg(path, dimensions))
    errors.extend(validate_readme())
    errors.extend(validate_data())
    errors.extend(validate_workflow())

    tracked_env = [path for path in ROOT.rglob(".env") if ".git" not in path.parts]
    if tracked_env:
        errors.extend(f"unexpected .env file: {path.relative_to(ROOT)}" for path in tracked_env)
    if errors:
        print("profile validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("profile validation passed: 3 SVGs, README paths, contribution data, workflow, and security")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

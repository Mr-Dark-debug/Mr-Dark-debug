from __future__ import annotations

import datetime as dt
import unittest
import xml.etree.ElementTree as ET

from scripts import fetch_contributions as fetch
from scripts import make_ascii_svg as ascii_art
from scripts import make_info_card as info
from scripts import render_heatmap_svg as heatmap
from scripts import validate_profile as validate


def sample_days() -> list[fetch.ContributionDay]:
    start = dt.date(2025, 7, 27)
    return [
        fetch.ContributionDay(start + dt.timedelta(days=index), 3 if index in {365, 366, 368} else 0)
        for index in range(371)
    ]


def sample_payload() -> dict[str, object]:
    return fetch.build_payload(
        sample_days(),
        generated_at=dt.datetime(2026, 7, 30, tzinfo=dt.timezone.utc),
        as_of=dt.date(2026, 7, 30),
    )


class ContributionTests(unittest.TestCase):
    def test_parse_sibling_tooltips_and_stats(self) -> None:
        source = """
        <td data-date="2026-07-28" id="day-1" class="ContributionCalendar-day"></td>
        <tool-tip for="day-1">3 contributions on July 28th.</tool-tip>
        <td data-date="2026-07-29" id="day-2" class="ContributionCalendar-day"></td>
        <tool-tip for="day-2">No contributions on July 29th.</tool-tip>
        """
        parsed = fetch.parse_contribution_html(source)
        self.assertEqual(parsed[0].count, 3)
        normalized = fetch.normalize_days(parsed, end_date=dt.date(2026, 7, 30))
        payload = fetch.build_payload(
            normalized,
            generated_at=dt.datetime(2026, 7, 30, tzinfo=dt.timezone.utc),
            as_of=dt.date(2026, 7, 30),
        )
        self.assertEqual(payload["best_day"], {"date": "2026-07-28", "count": 3})
        self.assertEqual(len(payload["days"]), 371)

    def test_duplicate_dates_are_rejected(self) -> None:
        day = fetch.ContributionDay(dt.date(2026, 7, 30), 1)
        with self.assertRaisesRegex(ValueError, "duplicate contribution date"):
            fetch.normalize_days([day, day], end_date=day.date)


class HeatmapTests(unittest.TestCase):
    def test_heatmap_svg_is_accessible_and_complete(self) -> None:
        svg = heatmap.render_svg(sample_payload(), static=True)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 860 258")
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        self.assertGreaterEqual(len(rects), 371)
        self.assertIn('<title id="title">', svg)
        self.assertIn('<desc id="desc">', svg)
        self.assertNotIn("<script", svg.lower())

    def test_animated_heatmap_freezes_and_respects_reduced_motion(self) -> None:
        svg = heatmap.render_svg(sample_payload())
        self.assertIn("both", svg)
        self.assertIn("prefers-reduced-motion", svg)


class PortraitTests(unittest.TestCase):
    def test_ascii_renderer_has_exact_geometry_and_no_script(self) -> None:
        rows = [(" .,:;ox%#@" * 10)[:100] for _ in range(58)]
        svg = ascii_art.render_ascii_svg(rows, static=True)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 360 470")
        self.assertNotIn("<script", svg.lower())
        self.assertIn("Prashant Choudhary", svg)


class InfoCardTests(unittest.TestCase):
    def test_info_card_prioritizes_ai_python_nlp(self) -> None:
        svg = info.render_info_card(static=True)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 490 470")
        for phrase in ("AI ENGINEER", "PYTHON ENGINEER", "LLMs", "NLP", "University of Trier", "EnactOn"):
            self.assertIn(phrase, svg)
        self.assertNotIn("<script", svg.lower())


class ValidationTests(unittest.TestCase):
    def test_forbidden_content_detection(self) -> None:
        findings = validate.find_forbidden("?mcp_token=secret&next=1 user@example.com")
        self.assertIn("mcp_token", findings)
        self.assertIn("private email", findings)


if __name__ == "__main__":
    unittest.main()

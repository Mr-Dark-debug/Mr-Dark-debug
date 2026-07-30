#!/usr/bin/env python3
"""Fetch and summarize public GitHub profile contributions without a token."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_USER = "Mr-Dark-debug"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "contributions.json"
CONTRIBUTIONS_URL = "https://github.com/users/{username}/contributions"


@dataclass(frozen=True, order=True)
class ContributionDay:
    date: dt.date
    count: int


class ContributionHTMLParser(HTMLParser):
    """Associate contribution cells with their sibling GitHub tooltips."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: dict[str, dt.date] = {}
        self.counts: dict[str, int] = {}
        self._tooltip_for: str | None = None
        self._tooltip_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "td" and "ContributionCalendar-day" in classes:
            cell_id = values.get("id")
            date_text = values.get("data-date")
            if cell_id and date_text:
                try:
                    parsed = dt.date.fromisoformat(date_text)
                except ValueError as exc:
                    raise ValueError(f"invalid GitHub contribution date: {date_text}") from exc
                if cell_id in self.cells:
                    raise ValueError(f"duplicate contribution cell id: {cell_id}")
                self.cells[cell_id] = parsed
        elif tag == "tool-tip" and values.get("for") in self.cells:
            self._tooltip_for = values["for"]
            self._tooltip_text = []

    def handle_data(self, data: str) -> None:
        if self._tooltip_for is not None:
            self._tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip" or self._tooltip_for is None:
            return
        text = " ".join("".join(self._tooltip_text).split())
        if re.search(r"\bno contributions?\b", text, flags=re.IGNORECASE):
            count = 0
        else:
            match = re.search(r"([\d,]+)\s+contributions?\b", text, flags=re.IGNORECASE)
            if not match:
                raise ValueError(f"cannot parse contribution tooltip: {text!r}")
            count = int(match.group(1).replace(",", ""))
        self.counts[self._tooltip_for] = count
        self._tooltip_for = None
        self._tooltip_text = []


def parse_contribution_html(source: str) -> list[ContributionDay]:
    parser = ContributionHTMLParser()
    parser.feed(source)
    parser.close()
    if not parser.cells:
        raise ValueError("GitHub contribution calendar cells were not found")

    missing = sorted(set(parser.cells) - set(parser.counts))
    if missing:
        raise ValueError(f"GitHub contribution tooltips missing for {len(missing)} cells")

    by_date: dict[dt.date, int] = {}
    for cell_id, date in parser.cells.items():
        if date in by_date:
            raise ValueError(f"duplicate contribution date: {date.isoformat()}")
        count = parser.counts[cell_id]
        if count < 0:
            raise ValueError(f"negative contribution count for {date.isoformat()}")
        by_date[date] = count
    return [ContributionDay(date, by_date[date]) for date in sorted(by_date)]


def fetch_days(username: str = DEFAULT_USER, timeout: int = 30) -> list[ContributionDay]:
    url = CONTRIBUTIONS_URL.format(username=username)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mr-Dark-debug-profile-art/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        source = response.read().decode("utf-8")
    return parse_contribution_html(source)


def normalize_days(
    days: Iterable[ContributionDay],
    end_date: dt.date | None = None,
    weeks: int = 53,
) -> list[ContributionDay]:
    if weeks < 1:
        raise ValueError("weeks must be positive")
    supplied = list(days)
    if not supplied:
        raise ValueError("cannot normalize an empty contribution calendar")

    lookup: dict[dt.date, int] = {}
    for day in supplied:
        if day.count < 0:
            raise ValueError(f"negative contribution count for {day.date.isoformat()}")
        if day.date in lookup:
            raise ValueError(f"duplicate contribution date: {day.date.isoformat()}")
        lookup[day.date] = day.count

    as_of = end_date or dt.datetime.now(dt.timezone.utc).date()
    days_until_saturday = (5 - as_of.weekday()) % 7
    grid_end = as_of + dt.timedelta(days=days_until_saturday)
    grid_start = grid_end - dt.timedelta(days=weeks * 7 - 1)
    return [
        ContributionDay(grid_start + dt.timedelta(days=offset), lookup.get(grid_start + dt.timedelta(days=offset), 0))
        for offset in range(weeks * 7)
    ]


def _streaks(days: Sequence[ContributionDay], as_of: dt.date) -> tuple[dict[str, object], dict[str, object]]:
    eligible = [day for day in days if day.date <= as_of]
    current_end_index = len(eligible) - 1
    if current_end_index >= 0 and eligible[current_end_index].date == as_of and eligible[current_end_index].count == 0:
        current_end_index -= 1

    current_length = 0
    cursor = current_end_index
    while cursor >= 0 and eligible[cursor].count > 0:
        current_length += 1
        cursor -= 1
    current_start = eligible[cursor + 1].date.isoformat() if current_length else None
    current_end = eligible[current_end_index].date.isoformat() if current_length else None

    longest_length = run = 0
    longest_start: str | None = None
    longest_end: str | None = None
    run_start: dt.date | None = None
    for day in eligible:
        if day.count > 0:
            if run == 0:
                run_start = day.date
            run += 1
            if run > longest_length:
                longest_length = run
                longest_start = run_start.isoformat() if run_start else None
                longest_end = day.date.isoformat()
        else:
            run = 0
            run_start = None

    return (
        {"length": current_length, "start": current_start, "end": current_end},
        {"length": longest_length, "start": longest_start, "end": longest_end},
    )


def build_payload(
    days: Sequence[ContributionDay],
    username: str = DEFAULT_USER,
    generated_at: dt.datetime | None = None,
    as_of: dt.date | None = None,
) -> dict[str, object]:
    if not days:
        raise ValueError("cannot summarize an empty contribution calendar")
    snapshot_date = as_of or dt.datetime.now(dt.timezone.utc).date()
    eligible = [day for day in days if day.date <= snapshot_date]
    if not eligible:
        raise ValueError("calendar contains no days on or before as_of")

    current, longest = _streaks(days, snapshot_date)
    total = sum(day.count for day in eligible)
    active_days = sum(day.count > 0 for day in eligible)
    best = max(eligible, key=lambda day: (day.count, day.date))
    monthly: dict[str, int] = {}
    for day in eligible:
        key = day.date.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + day.count

    generated = generated_at or dt.datetime.combine(snapshot_date, dt.time.min, tzinfo=dt.timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=dt.timezone.utc)
    generated_text = generated.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "username": username,
        "generated_at": generated_text,
        "as_of": snapshot_date.isoformat(),
        "range": {"start": days[0].date.isoformat(), "end": snapshot_date.isoformat()},
        "grid_range": {"start": days[0].date.isoformat(), "end": days[-1].date.isoformat()},
        "total_contributions": total,
        "active_days": active_days,
        "average_on_active_days": round(total / active_days, 1) if active_days else 0.0,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best.date.isoformat(), "count": best.count},
        "monthly_totals": [{"month": month, "total": monthly[month]} for month in sorted(monthly)],
        "days": [{"date": day.date.isoformat(), "count": day.count} for day in days],
    }


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=DEFAULT_USER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    as_of = dt.datetime.now(dt.timezone.utc).date()
    fetched = fetch_days(args.username, args.timeout)
    normalized = normalize_days(fetched, end_date=as_of)
    payload = build_payload(normalized, username=args.username, as_of=as_of)
    atomic_write_text(args.output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(
        f"wrote {args.output}: {len(normalized)} days, "
        f"{payload['total_contributions']} contributions, "
        f"{payload['active_days']} active days"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

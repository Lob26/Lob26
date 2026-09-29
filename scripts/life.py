"""Play the last year of GitHub contributions as Conway's Game of Life.

Generation 0 is the contribution calendar as GitHub draws it. Then every day at
or above SEED_LEVEL becomes a live cell and the board evolves on a torus until
it dies, settles, or hits MAX_GENERATIONS, and fades back to the calendar.

Needs GITHUB_TOKEN (any token that can read the user's public profile). Runs
weekly from .github/workflows/life.yml; the SVGs are committed so the README
never depends on a third-party image service.

    GITHUB_TOKEN=$(gh auth token) uv run --no-project scripts/life.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

USER = os.environ.get("LIFE_USER", "Lob26")
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
SEED_LEVEL = 2
MAX_GENERATIONS = 90
MARGIN_ROWS = 4  # empty rows above and below the calendar so gliders have room

CELL, GAP, PAD = 11, 3, 2
PITCH = CELL + GAP
CALENDAR_HOLD_MS, GEN_MS, END_HOLD_MS, FADE_MS = 2600, 140, 900, 700

THEMES = {
    "dark": {"empty": "#1f1d2e", "live": "#f6c177"},
    "light": {"empty": "#f2e9e1", "live": "#d7827e"},
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { contributionLevel } } }
    }
  }
}
"""


def fetch_calendar(login: str, token: str) -> list[list[int]]:
    """Weeks × weekdays of contribution levels 0–4; the first week may be partial."""
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL error for {login}: {payload['errors']}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = []
    for week in weeks:
        days = [LEVELS[d["contributionLevel"]] for d in week["contributionDays"]]
        # GitHub's first week starts mid-week; pad at the top so weekdays align.
        calendar.append([0] * (7 - len(days)) + days if week is weeks[0] else days + [0] * (7 - len(days)))
    return calendar


def step(board: list[list[bool]]) -> list[list[bool]]:
    rows, cols = len(board), len(board[0])
    nxt = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = sum(board[(r + dr) % rows][(c + dc) % cols]
                    for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
            nxt[r][c] = n == 3 or (board[r][c] and n == 2)
    return nxt


def simulate(calendar: list[list[int]]) -> tuple[list[list[int]], list[list[list[bool]]]]:
    """Return the level grid for generation 0 and the boolean boards after it.

    Stops early when a board repeats (still life or oscillator), so the loop never
    spends seconds replaying a blinker.
    """
    cols, rows = len(calendar), 7 + 2 * MARGIN_ROWS
    levels = [[0] * cols for _ in range(rows)]
    for c, week in enumerate(calendar):
        for d, level in enumerate(week):
            levels[MARGIN_ROWS + d][c] = level

    board = [[lvl >= SEED_LEVEL for lvl in row] for row in levels]
    boards, seen = [board], {str(board)}
    for _ in range(MAX_GENERATIONS):
        board = step(board)
        key = str(board)
        boards.append(board)
        if key in seen or not any(map(any, board)):
            break
        seen.add(key)
    return levels, boards


def render(levels: list[list[int]], boards: list[list[list[bool]]], theme: dict) -> str:
    rows, cols = len(levels), len(levels[0])
    width, height = PAD * 2 + cols * PITCH - GAP, PAD * 2 + rows * PITCH - GAP
    gens = len(boards)
    total = CALENDAR_HOLD_MS + gens * GEN_MS + END_HOLD_MS + FADE_MS

    def kt(ms: float) -> str:
        return f"{ms / total:.5f}"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'role="img" aria-labelledby="title">',
        f"<title id=\"title\">{USER}'s last year of GitHub contributions, played as Conway's Game of Life</title>",
        f'<defs><pattern id="grid" width="{PITCH}" height="{PITCH}" patternUnits="userSpaceOnUse" x="{PAD}" y="{PAD}">'
        f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{theme["empty"]}"/></pattern></defs>',
        f'<rect x="{PAD}" y="{PAD}" width="{width - 2 * PAD}" height="{height - 2 * PAD}" fill="url(#grid)"/>',
    ]
    for r in range(rows):
        for c in range(cols):
            start = levels[r][c] / 4
            timeline = [(0.0, start), (CALENDAR_HOLD_MS, start)]
            prev = start
            for g, board in enumerate(boards):
                value = 1.0 if board[r][c] else 0.0
                if value != prev:
                    at = CALENDAR_HOLD_MS + g * GEN_MS
                    timeline += [(at, prev), (at, value)]
                    prev = value
            if start == 0 and len(timeline) == 2:
                continue
            fade_from = total - FADE_MS
            timeline += [(fade_from, prev), (total, start)]
            times = ";".join(kt(ms) for ms, _ in timeline)
            values = ";".join(f"{v:g}" for _, v in timeline)
            out.append(
                f'<rect x="{PAD + c * PITCH}" y="{PAD + r * PITCH}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{theme["live"]}" fill-opacity="{start:g}">'
                f'<animate attributeName="fill-opacity" dur="{total}ms" repeatCount="indefinite" '
                f'keyTimes="{times}" values="{values}"/></rect>'
            )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required to read the contribution calendar")
    levels, boards = simulate(fetch_calendar(USER, token))
    OUT_DIR.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = OUT_DIR / f"life-{name}.svg"
        path.write_text(render(levels, boards, theme), encoding="utf-8")
        print(f"{path.name}: {path.stat().st_size / 1024:.1f} KiB, {len(boards) - 1} generations")


if __name__ == "__main__":
    main()

"""Render the README hero: Hello, World! typed, run and deleted in six stacks.

Output is a self-contained animated SVG (SMIL, no scripts, no web fonts) because
GitHub serves README images through a sandboxed proxy that drops both. Every
glyph gets an explicit x, so the fallback monospace font can differ per viewer
without the typing clip drifting off the characters.

    uv run --no-project scripts/hello_world.py
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

OUT_DIR = Path(__file__).resolve().parent.parent / "assets"

THEMES = {
    "dark": {
        "window": "#191724", "bar": "#1f1d2e", "pane": "#16141f", "border": "#2a2740",
        "hl": "#211f30", "text": "#e0def4", "muted": "#6e6a86", "cursor": "#f6c177",
        "kw": "#c4a7e7", "fn": "#ebbcba", "str": "#f6c177", "tag": "#9ccfd8",
        "punct": "#908caa", "deco": "#eb6f92", "dots": ("#eb6f92", "#f6c177", "#9ccfd8"),
    },
    "light": {
        "window": "#fffaf3", "bar": "#f2e9e1", "pane": "#faf4ed", "border": "#dfdad9",
        "hl": "#f4ede8", "text": "#575279", "muted": "#9893a5", "cursor": "#d7827e",
        "kw": "#286983", "fn": "#b4637a", "str": "#a3620f", "tag": "#3e7c86",
        "punct": "#797593", "deco": "#907aa9", "dots": ("#b4637a", "#ea9d34", "#56949f"),
    },
}

Token = tuple[str, str]  # (text, css class)


@dataclass(frozen=True)
class Snippet:
    filename: str
    language: str
    lines: list[list[Token]]
    command: str
    output: str
    rendered: bool  # frontends render an <h1>; backends print to stdout


def t(text: str, cls: str = "plain") -> Token:
    return (text, cls)


SNIPPETS = [
    Snippet("hello.py", "Python", [
        [t("print", "fn"), t("(", "punct"), t('"Hello, World!"', "str"), t(")", "punct")],
    ], "python hello.py", "Hello, World!", False),
    Snippet("main.go", "Go", [
        [t("package", "kw"), t(" main")],
        [],
        [t("import", "kw"), t(" "), t('"fmt"', "str")],
        [],
        [t("func", "kw"), t(" "), t("main", "fn"), t("() {", "punct")],
        [t("    fmt."), t("Println", "fn"), t("(", "punct"), t('"Hello, World!"', "str"), t(")", "punct")],
        [t("}", "punct")],
    ], "go run main.go", "Hello, World!", False),
    Snippet("main.rs", "Rust", [
        [t("fn", "kw"), t(" "), t("main", "fn"), t("() {", "punct")],
        [t("    "), t("println!", "deco"), t("(", "punct"), t('"Hello, World!"', "str"), t(");", "punct")],
        [t("}", "punct")],
    ], "cargo run", "Hello, World!", False),
    Snippet("App.vue", "Vue", [
        [t("<", "punct"), t("template", "tag"), t(">", "punct")],
        [t("  "), t("<", "punct"), t("h1", "tag"), t(">", "punct"), t("Hello, World!"),
         t("</", "punct"), t("h1", "tag"), t(">", "punct")],
        [t("</", "punct"), t("template", "tag"), t(">", "punct")],
    ], "npm run dev", "localhost:5173", True),
    Snippet("App.tsx", "React", [
        [t("export", "kw"), t(" "), t("default", "kw"), t(" "), t("function", "kw"), t(" "),
         t("App", "fn"), t("() {", "punct")],
        [t("  "), t("return", "kw"), t(" "), t("<", "punct"), t("h1", "tag"), t(">", "punct"),
         t("Hello, World!"), t("</", "punct"), t("h1", "tag"), t(">", "punct")],
        [t("}", "punct")],
    ], "npm run dev", "localhost:5173", True),
    Snippet("app.ts", "Angular", [
        [t("@Component", "deco"), t("({", "punct")],
        [t("  selector: "), t("'app-root'", "str"), t(",", "punct")],
        [t("  template: "), t("'<h1>Hello, World!</h1>'", "str"), t(",", "punct")],
        [t("})", "punct")],
        [t("export", "kw"), t(" "), t("class", "kw"), t(" "), t("App", "fn"), t(" {}", "punct")],
    ], "ng serve", "localhost:4200", True),
]

# Geometry (px). CW is the monospace advance at FONT_SIZE; glyphs are placed on it.
W = 760
FONT_SIZE = 15
CW = 9.0
LH = 24
BAR_H = 40
PAD_X = 20
GUTTER = 36
MAX_LINES = max(len(s.lines) for s in SNIPPETS)
CODE_TOP = BAR_H + 16
CODE_H = MAX_LINES * LH + 16
PANE_TOP = CODE_TOP + CODE_H
PANE_H = 76
H = PANE_TOP + PANE_H
CODE_X = PAD_X + GUTTER
PANE_X = PAD_X + 4

# Timing (ms)
TYPE_MS, TYPE_JITTER = 34, (-12, 26)
CMD_MS = 34
DELETE_MS = 13
rng = random.Random(26)


def line_text(line: list[Token]) -> str:
    return "".join(text for text, _ in line)


class Timeline:
    """Records the value of every animated attribute whenever it changes."""

    def __init__(self) -> None:
        self.now = 0
        self.series: dict[str, list[tuple[int, str]]] = defaultdict(list)

    def set(self, key: str, value: str) -> None:
        points = self.series[key]
        if points and points[-1][0] == self.now:
            points[-1] = (self.now, value)
        elif not points or points[-1][1] != value:
            points.append((self.now, value))

    def wait(self, ms: int) -> None:
        self.now += ms


def cursor_to(tl: Timeline, row: int, col: int) -> None:
    tl.set("cursor.x", f"{CODE_X + col * CW:.1f}")
    tl.set("cursor.y", f"{CODE_TOP + 8 + row * LH + 3}")
    tl.set("hl.y", f"{CODE_TOP + 8 + row * LH}")
    tl.set("hl.o", "1")


def cursor_to_pane(tl: Timeline, col: int) -> None:
    tl.set("cursor.x", f"{PANE_X + 2 * CW + col * CW:.1f}")
    tl.set("cursor.y", f"{PANE_TOP + 14}")
    tl.set("hl.o", "0")


def build_timeline() -> Timeline:
    tl = Timeline()
    for si in range(len(SNIPPETS)):
        tl.set(f"tab{si}", "0")
        tl.set(f"cmd{si}", "0")
        tl.set(f"out{si}", "0")
        for li in range(len(SNIPPETS[si].lines)):
            tl.set(f"s{si}l{li}", "0")
    for row in range(MAX_LINES):
        tl.set(f"num{row}", "0")
    cursor_to(tl, 0, 0)

    for si, snip in enumerate(SNIPPETS):
        tl.set(f"tab{si}", "1")
        tl.set("num0", "1")
        cursor_to(tl, 0, 0)
        tl.wait(450)

        for li, line in enumerate(snip.lines):
            if li > 0:
                tl.set(f"num{li}", "1")
                cursor_to(tl, li, 0)
                tl.wait(140)
            text = line_text(line)
            indent = len(text) - len(text.lstrip(" "))
            # Editors auto-indent: the leading whitespace lands with the newline.
            if indent:
                tl.set(f"s{si}l{li}", f"{indent * CW:.1f}")
                cursor_to(tl, li, indent)
            for col in range(indent + 1, len(text) + 1):
                tl.wait(TYPE_MS + rng.randint(*TYPE_JITTER) + (70 if text[col - 1] in "({,;" else 0))
                tl.set(f"s{si}l{li}", f"{col * CW:.1f}")
                cursor_to(tl, li, col)

        tl.wait(500)
        cursor_to_pane(tl, 0)
        for col in range(1, len(snip.command) + 1):
            tl.wait(CMD_MS + rng.randint(0, 25))
            tl.set(f"cmd{si}", f"{(col + 2) * CW:.1f}")
            cursor_to_pane(tl, col)
        tl.wait(420)
        tl.set(f"out{si}", "1")
        tl.wait(1800)

        tl.set(f"cmd{si}", "0")
        tl.set(f"out{si}", "0")
        last = len(snip.lines) - 1
        cursor_to(tl, last, len(line_text(snip.lines[last])))
        tl.wait(250)
        for li in range(last, -1, -1):
            text = line_text(snip.lines[li])
            for col in range(len(text) - 1, -1, -1):
                tl.wait(DELETE_MS)
                tl.set(f"s{si}l{li}", f"{col * CW:.1f}")
                cursor_to(tl, li, col)
            if li > 0:
                tl.wait(DELETE_MS)
                tl.set(f"num{li}", "0")
                cursor_to(tl, li - 1, len(line_text(snip.lines[li - 1])))
        tl.wait(300)
        tl.set(f"tab{si}", "0")

    tl.wait(150)
    return tl


def animate(tl: Timeline, key: str, attr: str) -> str:
    total = tl.now
    points = tl.series[key]
    key_times = ";".join(f"{ms / total:.5f}" for ms, _ in points)
    values = ";".join(v for _, v in points)
    return (f'<animate attributeName="{attr}" dur="{total}ms" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{key_times}" values="{values}"/>')


def glyph_runs(line: list[Token], x0: float, y: float) -> str:
    """One <text> per same-class run of non-space glyphs, each glyph pinned to its cell."""
    parts, col = [], 0
    for text, cls in line:
        run_start, run = col, ""
        for ch in text + " ":
            if ch == " " or col == run_start + len(text):
                if run:
                    xs = " ".join(f"{x0 + (col - len(run) + i) * CW:.1f}" for i in range(len(run)))
                    parts.append(f'<text class="{cls}" x="{xs}" y="{y}">{escape(run)}</text>')
                    run = ""
                if col == run_start + len(text):
                    break
                col += 1
            else:
                run += ch
                col += 1
    return "".join(parts)


def render(theme: dict, tl: Timeline) -> str:
    c = theme
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
             'role="img" aria-labelledby="title">')
    o.append('<title id="title">Hello, World! typed, run and deleted in Python, Go, Rust, Vue, React and Angular</title>')
    o.append("<style>"
             "text{font-family:ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,'Liberation Mono',monospace;"
             f"font-size:{FONT_SIZE}px;fill:{c['text']}}}"
             + "".join(f".{k}{{fill:{c[k]}}}" for k in ("kw", "fn", "str", "tag", "punct", "deco", "muted"))
             + ".plain{} .h1{font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:22px}"
             "</style>")

    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{c["window"]}"/>')
    o.append(f'<path d="M0.5 {BAR_H}V10.5a10 10 0 0 1 10-10H{W - 10.5}a10 10 0 0 1 10 10V{BAR_H}Z" fill="{c["bar"]}"/>')
    o.append(f'<line x1="0" x2="{W}" y1="{BAR_H}" y2="{BAR_H}" stroke="{c["border"]}"/>')
    for i, dot in enumerate(c["dots"]):
        o.append(f'<circle cx="{20 + i * 18}" cy="{BAR_H / 2}" r="5.5" fill="{dot}"/>')

    for si, snip in enumerate(SNIPPETS):
        o.append(f'<g opacity="0">{animate(tl, f"tab{si}", "opacity")}'
                 f'<text x="84" y="{BAR_H / 2 + 5}">{snip.filename}</text>'
                 f'<text class="muted" x="{W - 20}" y="{BAR_H / 2 + 5}" text-anchor="end">{snip.language}</text></g>')

    o.append(f'<rect x="1" y="0" width="{W - 2}" height="{LH}" fill="{c["hl"]}">'
             f'{animate(tl, "hl.y", "y")}{animate(tl, "hl.o", "opacity")}</rect>')

    for row in range(MAX_LINES):
        y = CODE_TOP + 8 + row * LH + 17
        o.append(f'<text class="muted" x="{CODE_X - 16}" y="{y}" text-anchor="end" opacity="0">'
                 f'{row + 1}{animate(tl, f"num{row}", "opacity")}</text>')

    defs = []
    for si, snip in enumerate(SNIPPETS):
        for li, line in enumerate(snip.lines):
            if not line:
                continue
            top = CODE_TOP + 8 + li * LH
            cid = f"s{si}l{li}"
            defs.append(f'<clipPath id="{cid}"><rect x="{CODE_X - 1}" y="{top}" width="0" height="{LH}">'
                        f'{animate(tl, cid, "width")}</rect></clipPath>')
            o.append(f'<g clip-path="url(#{cid})">{glyph_runs(line, CODE_X, top + 17)}</g>')

    o.append(f'<path d="M0.5 {PANE_TOP}V{H - 10.5}a10 10 0 0 0 10 10H{W - 10.5}a10 10 0 0 0 10-10V{PANE_TOP}Z" fill="{c["pane"]}"/>')
    o.append(f'<line x1="0" x2="{W}" y1="{PANE_TOP}" y2="{PANE_TOP}" stroke="{c["border"]}"/>')
    o.append(f'<text class="muted" x="{PANE_X}" y="{PANE_TOP + 28}">$</text>')
    for si, snip in enumerate(SNIPPETS):
        cid = f"cmd{si}"
        defs.append(f'<clipPath id="{cid}"><rect x="{PANE_X}" y="{PANE_TOP + 8}" width="0" height="{LH}">'
                    f'{animate(tl, cid, "width")}</rect></clipPath>')
        o.append(f'<g clip-path="url(#{cid})">'
                 f'{glyph_runs([t(snip.command)], PANE_X + 2 * CW, PANE_TOP + 28)}</g>')
        if snip.rendered:
            out = (f'<text class="muted" x="{PANE_X}" y="{PANE_TOP + 58}">➜ {snip.output}</text>'
                   f'<text class="h1" x="{PANE_X + 20 * CW}" y="{PANE_TOP + 60}">Hello, World!</text>')
        else:
            out = f'<text x="{PANE_X}" y="{PANE_TOP + 58}">{snip.output}</text>'
        o.append(f'<g opacity="0">{animate(tl, f"out{si}", "opacity")}{out}</g>')

    o.append(f'<rect width="2" height="18" fill="{c["cursor"]}">'
             f'{animate(tl, "cursor.x", "x")}{animate(tl, "cursor.y", "y")}'
             '<animate attributeName="opacity" values="1;0" dur="1.06s" repeatCount="indefinite" calcMode="discrete"/>'
             '</rect>')

    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{c["border"]}"/>')
    o.insert(3, "<defs>" + "".join(defs) + "</defs>")
    o.append("</svg>")
    return "\n".join(o) + "\n"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        global rng
        rng = random.Random(26)  # same keystroke rhythm in both themes
        tl = build_timeline()
        path = OUT_DIR / f"hello-{name}.svg"
        path.write_text(render(theme, tl), encoding="utf-8")
        print(f"{path.name}: {path.stat().st_size / 1024:.1f} KiB, loop {tl.now / 1000:.1f}s")


if __name__ == "__main__":
    main()

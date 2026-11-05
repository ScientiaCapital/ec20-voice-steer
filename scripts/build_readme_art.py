"""Rebuild the README art in docs/assets: the banner and the signal-path diagram, each in light and dark.

Light and dark exist for GitHub's `<picture>` switch. The colors are the Epiphan Brand colors that the Epiphan Edge
Claude Kit's scripts/build_readme_art.py uses. The logos in docs/assets/epiphan-logo*.svg are copies of the
official Brand assets. This script embeds a logo's drawing unchanged and never rewrites those files.

The art shows only what the repo documents: the array stand-in and the VISCA path exist, the real array and the
Dante path to Pearl Nano are bench tests. It holds no real names, rooms, devices, IP addresses or dates. Keep the
image alt text in README.md in step with BANNER_LABEL and DIAGRAM_LABEL.

    python3 scripts/build_readme_art.py
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"
FONT = "Söhne,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
MONO = "Söhne Mono,ui-monospace,SFMono-Regular,Menlo,monospace"

LIGHT = {
    "bg": "#f1f2f0",
    "fg": "#111111",
    "muted": "#5a5a5a",
    "box": "#ffffff",
    "line": "#c9ccd4",
    "arrow": "#4a4aaf",
    "accent": "#0c3d34",
    "logo": "epiphan-logo-horizontal.svg",
}
DARK = {
    "bg": "#0d231f",
    "fg": "#ffffff",
    "muted": "#cfd3dc",
    "box": "#0c3d34",
    "line": "#316472",
    "arrow": "#d7daf9",
    "accent": "#6651fc",
    "logo": "epiphan-logo-horizontal-light.svg",
}
GREEN = "#83ce41"

BANNER_LABEL = "Epiphan ec20-voice-steer: the ceiling mic array points the EC20, with no tracking processor in between"
DIAGRAM_LABEL = (
    "A ceiling microphone array, or a laptop standing in for it, sends a VISCA over IP preset recall to the EC20 on "
    "UDP 52381. Pearl Mini records the EC20 over NDI or RTSP and Epiphan Edge shares the clip. A bench test also "
    "sends Dante audio from the array into the EC20 and on to Pearl Nano over RTSP or SRT."
)


def logo_drawing(name: str) -> str:
    """The logo's drawing, without the XML declaration or its own <svg> wrapper."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", (ASSETS / name).read_text(encoding="utf-8"))
    return re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg.strip(), flags=re.DOTALL)


def banner(t: dict[str, str]) -> str:
    pills = []
    for i, label in enumerate(("Talker in zone", "VISCA preset recall", "EC20 moves")):
        y = 28 + i * 44
        pills.append(
            f'<rect x="600" y="{y}" width="240" height="32" rx="8" fill="{t["accent"]}"/>\n'
            f'  <circle cx="620" cy="{y + 16}" r="6" fill="{GREEN}"/>\n'
            f'  <text x="634" y="{y + 21}" font-family="{FONT}" font-size="15" font-weight="600" '
            f'fill="#ffffff">{escape(label)}</text>'
        )
    pill_markup = "\n  ".join(pills)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="200" viewBox="0 0 880 200" role="img" aria-label="{escape(BANNER_LABEL)}">
  <rect width="880" height="200" rx="16" fill="{t["bg"]}"/>
  <svg x="30" y="14" width="180" height="50" viewBox="0 0 358.2 99.5">{logo_drawing(t["logo"])}</svg>
  <text x="48" y="120" font-family="{FONT}" font-size="36" font-weight="600" fill="{t["fg"]}">ec20-voice-steer</text>
  <text x="50" y="158" font-family="{FONT}" font-size="19" fill="{t["muted"]}">The mic array points the camera. Nothing in between</text>
  {pill_markup}
</svg>
"""


def node(x: int, y: int, w: int, h: int, title: str, sub: str, t: dict[str, str], *, mono: bool = False) -> str:
    font = f' font-family="{MONO}"' if mono else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t["box"]}" stroke="{t["line"]}"/>\n  '
        f'<text x="{x + w / 2}" y="{y + h / 2 - 6}" text-anchor="middle" dominant-baseline="middle" font-size="14" '
        f'font-weight="600" fill="{t["fg"]}"{font}>{escape(title)}</text>\n  '
        f'<text x="{x + w / 2}" y="{y + h / 2 + 13}" text-anchor="middle" dominant-baseline="middle" font-size="12" '
        f'fill="{t["muted"]}">{escape(sub)}</text>'
    )


def arrow(x1: int, y1: int, x2: int, y2: int, t: dict[str, str], label: str = "") -> str:
    out = (
        f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{t["arrow"]}" stroke-width="2" fill="none" marker-end="url(#head)"/>'
    )
    if label:
        out += (
            f'\n  <text x="{(x1 + x2) / 2}" y="{min(y1, y2) - 9}" text-anchor="middle" font-size="11" '
            f'fill="{t["muted"]}">{escape(label)}</text>'
        )
    return out


def dashed(x1: int, y1: int, x2: int, y2: int, t: dict[str, str]) -> str:
    return (
        f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{t["arrow"]}" stroke-width="2" stroke-dasharray="5 4" '
        'fill="none" marker-end="url(#head)"/>'
    )


def diagram(t: dict[str, str]) -> str:
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="330" viewBox="0 0 880 330" role="img" '
            f'aria-label="{escape(DIAGRAM_LABEL)}" font-family="{FONT}">'
        ),
        (
            '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["arrow"]}"/></marker></defs>'
        ),
        f'<rect width="880" height="330" rx="16" fill="{t["bg"]}"/>',
        node(20, 60, 190, 60, "Ceiling mic array", "or the laptop stand-in", t),
        arrow(210, 90, 328, 90, t, "VISCA over IP"),
        f'<text x="269" y="110" text-anchor="middle" font-size="11" fill="{t["muted"]}">UDP 52381</text>',
        node(330, 60, 160, 60, "EC20", "recalls the zone preset", t),
        arrow(490, 90, 568, 90, t, "NDI or RTSP"),
        node(570, 60, 130, 60, "Pearl Mini", "records the shots", t),
        arrow(700, 90, 738, 90, t),
        node(740, 60, 120, 60, "Epiphan Edge", "share the clip", t),
        dashed(115, 122, 345, 200, t),
        f'<text x="200" y="182" text-anchor="middle" font-size="11" fill="{t["muted"]}">Dante audio</text>',
        node(330, 200, 160, 60, "EC20 audio in", "Dante, one stereo pair", t),
        dashed(490, 230, 568, 230, t),
        f'<text x="529" y="221" text-anchor="middle" font-size="11" fill="{t["muted"]}">RTSP or SRT</text>',
        node(570, 200, 150, 60, "Pearl Nano", "no Dante input", t),
        f'<circle cx="34" cy="296" r="5" fill="{GREEN}"/>',
        f'<text x="46" y="301" font-size="13" fill="{t["fg"]}">Solid: the voice-steer path (T1 to T3). Dashed: Dante audio to Pearl Nano (T5).</text>',
        "</svg>",
    ]
    return "\n  ".join(parts) + "\n"


def main() -> None:
    for name, theme in (("light", LIGHT), ("dark", DARK)):
        (ASSETS / f"banner-{name}.svg").write_text(banner(theme), encoding="utf-8")
        (ASSETS / f"architecture-{name}.svg").write_text(diagram(theme), encoding="utf-8")
    print(f"wrote banner and signal-path art (light, dark) in {ASSETS}")


if __name__ == "__main__":
    main()

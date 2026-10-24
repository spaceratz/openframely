"""1:1 wall template (SVG, print at 100% on A3 or tape two A4s): frame outline, window, GPO screw
holes and the board, measured from the GPO screws. Tape it over the GPO to check where the calendar lands.

Run: uvx ... python checks/wall_template.py   (./run.sh does it)
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import params as P  # noqa: E402


def main() -> int:
    m = 10.0
    w, h = P.OUTER_W + 2 * m, P.OUTER_H + 2 * m
    cx, cy = w / 2, h / 2  # frame centre on the page (SVG y grows down, so flip Y)

    def pt(x: float, y: float) -> tuple[float, float]:
        return cx + x, cy - y

    def rect(x: float, y: float, rw: float, rh: float, style: str, r: float = 0) -> str:
        x0, y0 = pt(x - rw / 2, y + rh / 2)
        return f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{rw:.2f}" height="{rh:.2f}" rx="{r}" {style}/>'

    gx, gy = P.GPO_X, P.GPO_Y
    parts = [
        rect(0, 0, P.OUTER_W, P.OUTER_H, 'fill="none" stroke="#000" stroke-width="0.8"', P.CORNER_R),
        rect(P.WIN_OFFSET_X, P.WIN_OFFSET_Y, P.WIN_W, P.WIN_H, 'fill="#eee" stroke="#666" stroke-width="0.6"'),
        rect(gx, gy, P.GPO_GRID_W, P.GPO_GRID_L, 'fill="none" stroke="#c00" stroke-width="0.6" stroke-dasharray="2,1"', 3),
        rect(P.BOARD_X, P.BOARD_Y, P.BOARD_W, P.BOARD_H, 'fill="none" stroke="#080" stroke-width="0.6" stroke-dasharray="2,1"'),
    ]
    for dy in (-P.GPO_SCREW_C / 2, P.GPO_SCREW_C / 2):
        x, y = pt(gx, gy + dy)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="none" stroke="#c00" stroke-width="0.8"/>')
        parts.append(f'<path d="M{x - 4:.2f},{y:.2f}H{x + 4:.2f}M{x:.2f},{y - 4:.2f}V{y + 4:.2f}" stroke="#c00" stroke-width="0.2"/>')
    tx, ty = pt(-P.OUTER_W / 2 + 6, P.OUTER_H / 2 - 10)
    lines = [
        f"OpenFramely wall template, 1:1 ({P.PRESET}, {P.GPO_PRESET}). Print at 100%: check the 100 mm bar.",
        f"Line up the red crosses on the GPO's two screw holes ({P.GPO_SCREW_C:.0f} mm apart).",
        f"Black: frame outline {P.OUTER_W:.0f} x {P.OUTER_H:.0f} mm. Grey: visible screen. Green: board.",
    ]
    for i, t in enumerate(lines):
        parts.append(f'<text x="{tx:.2f}" y="{ty + i * 5:.2f}" font-family="sans-serif" font-size="3.5">{t}</text>')
    bx, by = pt(-P.OUTER_W / 2 + 6, -P.OUTER_H / 2 + 8)
    parts.append(f'<path d="M{bx:.2f},{by:.2f}h100" stroke="#000" stroke-width="0.6"/>')
    parts.append(f'<text x="{bx:.2f}" y="{by - 2:.2f}" font-family="sans-serif" font-size="3">100 mm</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}mm" height="{h:.1f}mm" '
           f'viewBox="0 0 {w:.2f} {h:.2f}">\n' + "\n".join(parts) + "\n</svg>\n")
    (ROOT / "wall-template.svg").write_text(svg)
    print("wrote wall-template.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())

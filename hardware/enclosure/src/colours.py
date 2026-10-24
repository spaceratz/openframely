"""Colour comparison: the assembled frame (with panel) in each filament colour, side by side.
Renders only; the geometry is identical. ./run.sh render writes renders/colours.png from it."""

from __future__ import annotations

import _parts
import params as P
from cadgen import build123d as bd
from cadgen import srgb, step


@step(out="../STEP/colours.step")
def colours():
    out = []
    gap = 40.0
    for i, (name, hexc) in enumerate(P.FRAME_COLOURS.items()):
        dx = (i % 2) * (P.OUTER_W + gap)
        dy = -(i // 2) * (P.OUTER_H + gap)
        for side in ("left", "right"):
            f = bd.Pos(dx, dy, 0) * _parts.frame_half(side)
            f.color = srgb(hexc)
            f.label = f"{name}_{side}"
            out.append(f)
        panel = bd.Pos(dx, dy, 0) * _parts.panel_stand_in()
        panel.color = srgb("#1A1D22")
        panel.label = f"{name}_panel"
        out.append(panel)
    return bd.Compound(children=out, label="colours")


if __name__ == "__main__":
    colours()

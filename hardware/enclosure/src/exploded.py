"""Exploded view for the assembly guide: parts pulled apart along Z in fitting order."""

from __future__ import annotations

import _parts
import params as P
from cadgen import build123d as bd
from cadgen import srgb, step

# (part factory, Z offset, colour) in assembly order: wall first, frame last
STACK = [
    (_parts.gpo_stand_in, 0, "#B0463C"),
    (_parts.back_plate, 30, "#D9D6CE"),
    (_parts.cable_stand_in, 30, "#1F5FA8"),
    (_parts.gpo_saddle, 60, "#E8E4DA"),
    (_parts.board_stand_in, 85, "#2D6A4F"),
    (_parts.panel_stand_in, 130, "#1A1D22"),
]


@step(out="../STEP/exploded.step")
def exploded():
    parts = []
    for factory, dz, colour in STACK:
        p = bd.Pos(0, 0, dz) * factory()
        p.color = srgb(colour)
        parts.append(p)
    for bar in _parts.clamp_bars():
        b = bd.Pos(0, 0, 160) * bar
        b.color = srgb("#E07A3F")
        parts.append(b)
    for side in ("left", "right"):
        f = bd.Pos(-30 if side == "left" else 30, 0, 200) * _parts.frame_half(side)
        f.color = srgb(P.FRAME_COLOUR)
        parts.append(f)
    return bd.Compound(children=parts, label=f"exploded_{P.PRESET}")


if __name__ == "__main__":
    exploded()

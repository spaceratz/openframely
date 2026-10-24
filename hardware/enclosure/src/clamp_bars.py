"""Printed parts: the panel clamp bars and the two frame joiners (print all on one plate)."""

from __future__ import annotations

import _parts
from cadgen import build123d as bd
from cadgen import srgb, step


@step(out="../STEP/clamp_bars.step")
def clamp_bars():
    bars = _parts.clamp_bars()
    for b in bars:
        b.color = srgb("#E07A3F")
    return bd.Compound(children=bars, label="clamp_bars")


if __name__ == "__main__":
    clamp_bars()

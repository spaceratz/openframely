"""Printed part: gpo_saddle. Generated outputs: STEP/gpo_saddle.step, STL/gpo_saddle.stl."""

from __future__ import annotations

import _parts
from cadgen import srgb, step


@step(out="../STEP/gpo_saddle.step")
def gpo_saddle():
    part = _parts.gpo_saddle()
    part.label = "gpo_saddle"
    part.color = srgb("#F2F1EC")
    return part


if __name__ == "__main__":
    gpo_saddle()

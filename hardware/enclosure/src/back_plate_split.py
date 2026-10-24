"""Optional: the back plate in two halves (preset key "plate_split": true) for 210-220 mm beds."""

from __future__ import annotations

import _parts
from cadgen import build123d as bd
from cadgen import srgb, step


@step(out="../STEP/back_plate_split.step")
def back_plate_split():
    halves = _parts.back_plate_halves() + [_parts.plate_splice()]
    for h in halves:
        h.color = srgb("#D9D6CE")
    return bd.Compound(children=halves, label="back_plate_split")


if __name__ == "__main__":
    back_plate_split()

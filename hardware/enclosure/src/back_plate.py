"""Printed part: back_plate. Generated outputs: STEP/back_plate.step, STL/back_plate.stl."""

from __future__ import annotations

import _parts
from cadgen import srgb, step


@step(out="../STEP/back_plate.step")
def back_plate():
    part = _parts.back_plate()
    part.label = "back_plate"
    part.color = srgb("#F2F1EC")
    return part


if __name__ == "__main__":
    back_plate()

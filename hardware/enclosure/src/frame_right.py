"""Printed part: frame_right. Generated outputs: STEP/frame_right.step, STL/frame_right.stl."""

from __future__ import annotations

import _parts
import params as P
from cadgen import srgb, step


@step(out="../STEP/frame_right.step")
def frame_right():
    part = _parts.frame_half("right")
    part.label = "frame_right"
    part.color = srgb(P.FRAME_COLOUR)
    return part


if __name__ == "__main__":
    frame_right()

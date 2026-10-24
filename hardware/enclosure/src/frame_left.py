"""Printed part: frame_left. Generated outputs: STEP/frame_left.step, STL/frame_left.stl."""

from __future__ import annotations

import _parts
import params as P
from cadgen import srgb, step


@step(out="../STEP/frame_left.step")
def frame_left():
    part = _parts.frame_half("left")
    part.label = "frame_left"
    part.color = srgb(P.FRAME_COLOUR)
    return part


if __name__ == "__main__":
    frame_left()

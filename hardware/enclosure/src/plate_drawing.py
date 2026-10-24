"""Dimensioned drawing of the back plate: GPO cut-out, keyholes and frame-screw tabs."""

from __future__ import annotations

from pathlib import Path

import cadgen
import params as P
from cadgen.eng_drawing import Sheet, eng_drawing


@eng_drawing(out="../PDF/back_plate_drawing.pdf")
def plate_drawing():
    part = cadgen.read_step(Path(__file__).parent / "../STEP/back_plate.step")
    sheet = Sheet("A3", scale=0.5, title="BACK PLATE", part_number="OFLY-PLATE", material="PETG",
                  revision="A", general_tolerance="ISO 2768-m",
                  notes=["KEYHOLES ONLY FOR WALLS WITHOUT A GPO", "PRINT FLAT, WALL SIDE DOWN"])
    top, front, right = sheet.three_views(part)
    top.overall()
    y = P.PLATE_Y + P.PLATE_H / 2 - 22
    top.dim((P.PLATE_X - 100, y, P.BACK_T), (P.PLATE_X + 100, y, P.BACK_T))
    front.overall()
    return sheet


if __name__ == "__main__":
    plate_drawing()

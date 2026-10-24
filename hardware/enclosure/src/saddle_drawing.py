"""Dimensioned drawing of the GPO saddle (the part that must match the wall box exactly)."""

from __future__ import annotations

from pathlib import Path

import cadgen
import params as P
from cadgen.eng_drawing import Sheet, eng_drawing


@eng_drawing(out="../PDF/gpo_saddle_drawing.pdf")
def saddle_drawing():
    part = cadgen.read_step(Path(__file__).parent / "../STEP/gpo_saddle.step")
    sheet = Sheet("A3", title="GPO SADDLE", part_number="OFLY-SADDLE", material="PETG",
                  revision="A", general_tolerance="ISO 2768-m",
                  notes=[f"FITS {P.GPO_PRESET.upper()}: SCREWS {P.GPO_SCREW_C:.0f} MM APART", "PRINT COVER-DOWN"])
    top, front, right, iso = sheet.three_views(part, iso=True)
    top.overall()
    gx, gy, z = P.GPO_X, P.GPO_Y, P.BACK_T + 5.0
    top.dim((gx, gy - P.GPO_SCREW_C / 2, z), (gx, gy + P.GPO_SCREW_C / 2, z))
    top.hole((gx, gy + P.GPO_SCREW_C / 2, z), P.GPO_SCREW_D, count=2)
    front.overall()
    return sheet


if __name__ == "__main__":
    saddle_drawing()

"""Service pose: the frame lifted off its hooks (HOOK_DROP up, then 60 mm out from the wall)."""

from __future__ import annotations

import _parts
import params as P
from cadgen import build123d as bd
from cadgen import srgb, step


@step(out="../STEP/service_pose.step")
def service_pose():
    lift = bd.Location((0, P.HOOK_DROP, 60))
    out = []
    for f, colour in ((_parts.back_plate, "#D9D6CE"), (_parts.gpo_saddle, "#E8E4DA"), (_parts.board_stand_in, "#2D6A4F"),
                      (_parts.cable_stand_in, "#1F5FA8")):
        p = f()
        p.color = srgb(colour)
        out.append(p)
    for side in ("left", "right"):
        h = _parts.frame_half(side).moved(lift)
        h.color = srgb(P.FRAME_COLOUR)
        out.append(h)
    panel = _parts.panel_stand_in().moved(lift)
    panel.color = srgb("#1A1D22")
    out.append(panel)
    return bd.Compound(children=out, label="service_pose")


if __name__ == "__main__":
    service_pose()

"""Write ASSEMBLY.md: fitting and servicing steps, with numbers taken from the model.

Run: uvx ... python checks/assembly_guide.py   (./run.sh does it)
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import _parts  # noqa: E402
import params as P  # noqa: E402


def main() -> int:
    z_cover, z_top = _parts.saddle_levels()
    mech_removed = P.GPO_MECH == "removed"
    steps = [
        f"# Fitting and servicing ({P.PRESET}, {P.GPO_PRESET}, mechanism {P.GPO_MECH})",
        "",
        "Print list and hardware: `BOM.md`. Exploded view: `renders/exploded.png`.",
        "",
        "## Before you start",
        "",
        "- **Mains work is for a licensed electrician.** In Australia that includes removing the",
        "  socket mechanism and fitting the 5 V supply in the wall cavity. Everything after that is low voltage.",
        "- Print `STL/coupons.stl` first (under an hour) and check the fits: the panel corner in the frame",
        "  corner, the hook finger on the tongue, a snap hook through a wall slot, the bottom latch.",
        "",
        "## 1. Prepare the parts (bench)",
        "",
        "1. Glue the two frame halves: snap the two joiners through the top and bottom walls across the",
        "   seam, slip the two lip splices into their recesses behind the lip, then wick thin CA (or 2K",
        "   epoxy) into the seam and under the joiners from the back. The V-groove on the front stays clean.",
        ("2. Press the speakers into their pods, then screw" if P.SPEAKERS else "2. Screw")
        + " the board to its 4 standoffs, connector side to the wall.",
        "",
        "## 2. On the wall",
        "",
        (
            "1. With the mechanism removed and the 5 V lead coming out of the wall box, unscrew the old"
            if mech_removed
            else "1. Unscrew the GPO's faceplate"
        ),
        "   faceplate screws. Hold the back plate over the box (the grid fits through its cut-out).",
        "2. Put the saddle over the grid, feed the 5 V lead out through its side notch, and fit the",
        f"   two **M3.5 x 30** screws through the saddle into the box ({P.GPO_SCREW_C:.0f} mm apart). Tighten until snug",
        "   so the plate cannot shift.",
        "3. Run the lead along the plate, under the two printed clips, up the left side of the board,",
        "   and plug it into the board's USB-C.",
        "4. Stick the WiFi antenna to the inside of the frame's right wall, above the side clamp bar.",
        *(
            [
                "5. Push the PIR module's dome into the hole in the frame's bottom wall (a dab of hot glue",
                "   holds it) and plug its lead into the board's PIR header.",
            ]
            if P.PIR
            else []
        ),
        "",
        "## 3. Panel into the frame",
        "",
        "1. Lay the frame face-down on a towel. Drop the panel in, screen down.",
        "2. Put 0.8 mm foam tape on the clamp bars and push each one's two hooks out through the slots",
        "   in the wall until they click flush. To take one out, press its barbs in from outside with a",
        "   small screwdriver.",
        "3. Connect the eDP ribbon and the touch flex to the panel.",
        "",
        "## 4. Hang it",
        "",
        f"1. Plug the eDP ribbon and touch flex into the board (you have about {P.EDP_SLACK:.0f} mm of slack to do it).",
        f"2. Hold the frame flat to the wall, about **{P.HOOK_DROP:.0f} mm higher** than its final position.",
        "3. Lower it: the fingers inside the top wall drop in behind the plate's two tongues and the two",
        "   bottom latches click. No screws.",
        "",
        "## Servicing",
        "",
        "Grip the sides (finger recesses), lift firmly 8 mm so the bottom latches let go, and pull the frame off. Unplug the ribbon and",
        "flex at the board if you need the frame right off. The board, lead and saddle stay on the wall,",
        "leaving the board, SD card and USB ports accessible.",
        "",
    ]
    (ROOT / "ASSEMBLY.md").write_text("\n".join(steps))
    print(f"wrote ASSEMBLY.md ({len(steps)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

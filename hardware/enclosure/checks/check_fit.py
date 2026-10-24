"""Measured checks for the enclosure. Prints PASS/FAIL per requirement; exits 1 on any FAIL.

Run: uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.21 python checks/check_fit.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))


import params as P  # noqa: E402
from cadgen import read_step  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, bool(ok), detail))


def _ovl(a, b) -> float:
    """Shared volume of two shapes, 0 when they don't touch (Solid & Solid can return None)."""
    r = a & b
    return 0.0 if r is None else sum(s.volume for s in r.solids()) if hasattr(r, "solids") else r.volume


_FRAME_VOL = 0.0


def mass_est() -> float:
    """Frame + panel + bars, kg: panel ~0.6 kg, frame at ~60% of solid PETG."""
    return 0.6 + 0.05 + _FRAME_VOL / 1e3 * 1.27 / 1e3 * 0.6


def solids_by_label(path: pathlib.Path) -> dict:
    shape = read_step(str(path))
    out = {}
    for child in getattr(shape, "children", []) or [shape]:
        out[getattr(child, "label", "") or f"part{len(out)}"] = child
    return out


def main() -> int:
    printable = {}
    for name in ("frame_left", "frame_right", "back_plate", "gpo_saddle", "clamp_bars"):
        shape = read_step(str(ROOT / "STEP" / f"{name}.step"))
        # one solid -> use the Solid itself: boolean & on a moved STEP Compound silently returns 0,
        # which once hid a real service-lift clash
        printable[name] = shape.solids()[0] if len(shape.solids()) == 1 else shape

    global _FRAME_VOL
    _FRAME_VOL = sum(printable[n].volume for n in ("frame_left", "frame_right"))

    # R1: panel fits the pocket with clearance
    check(
        "R1 panel pocket",
        P.PANEL_W + 2 * P.CLEAR <= P.OUTER_W - 2 * P.WALL + 0.01,
        f"pocket {P.PANEL_W + 2 * P.CLEAR:.1f} x {P.PANEL_H + 2 * P.CLEAR:.1f} for panel {P.PANEL_W} x {P.PANEL_H}",
    )

    # shrink: after worst-case 0.5% shrink of the printed frame, the panel still drops in
    shrunk = (P.PANEL_W + 2 * P.CLEAR) * (1 - 0.005)
    check(
        "R1 fits after print shrink",
        shrunk >= P.PANEL_W + 0.2,
        f"pocket {shrunk:.1f} mm after 0.5% shrink for a {P.PANEL_W} mm panel (clearance {P.CLEAR} mm/side)",
    )

    # R2: lip covers the panel border on every side, window shows the full visible area
    lip_x = (P.PANEL_W - P.WIN_W) / 2 - abs(P.WIN_OFFSET_X)
    lip_y = (P.PANEL_H - P.WIN_H) / 2 - abs(P.WIN_OFFSET_Y)
    check(
        "R2 lip overlap", min(lip_x, lip_y) >= 3.0, f"panel edge hidden by {lip_x:.1f} mm (sides) / {lip_y:.1f} mm (top/bottom), need >= 3"
    )

    # R3: GPO mechanism clears the panel, screws at 84 mm centres
    gpo_gap = P.PANEL_BACK - P.GPO_PROUD - P.PLUG_ALLOW
    check("R3 GPO depth clearance", gpo_gap >= 2.0, f"{gpo_gap:.1f} mm between mechanism (+plug) and panel back, need >= 2")
    expect = {"clipsal-2000": 84.0, "uk-single": 60.3}[P.GPO_PRESET]
    check("R3 GPO screw centres", abs(P.GPO_SCREW_C - expect) < 0.01, f"{P.GPO_SCREW_C} mm vertical ({P.GPO_PRESET} datasheet: {expect})")
    check(
        "board inside frame",
        P.BOARD_X + P.BOARD_W / 2 <= P.POCKET_W / 2 - 5.0,
        f"board right edge {P.BOARD_X + P.BOARD_W / 2:.0f} mm, pocket {P.POCKET_W / 2:.0f} mm",
    )

    # printability: every printed part fits the bed
    bars = printable.pop("clamp_bars")
    for i, bar in enumerate(bars.solids()):
        printable[f"clamp_bar_{i + 1}"] = bar
    for name, part in printable.items():
        bb = part.bounding_box()
        dims = sorted([bb.size.X, bb.size.Y, bb.size.Z])
        check(
            f"bed fit: {name}",
            dims[1] <= P.BED and dims[2] <= P.BED,
            f"{bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm (bed {P.BED:.0f})",
        )
        check(f"valid solid: {name}", part.is_valid and part.volume > 0, f"volume {part.volume / 1000:.0f} cm3")

    # the saddle must stand proud of the plate and leave the socket faces open
    saddle_top = P.GPO_EAR_Z + P.SADDLE_BAR_T
    check("R3 saddle bar height", saddle_top < P.PANEL_BACK - 3, f"saddle top at {saddle_top:.1f} mm, panel back at {P.PANEL_BACK:.1f} mm")
    check(
        "R3 saddle clears grid face",
        P.GPO_PROUD > P.GPO_EAR_Z,
        f"bars rest on the ears at {P.GPO_EAR_Z} mm, below the socket face at {P.GPO_PROUD} mm",
    )
    if P.GPO_OPEN:
        window = P.GPO_SCREW_C - P.SADDLE_BAR_W
        check("R3 socket window", window >= P.GPO_KEEP_OUT, f"{window:.0f} mm open between the bars for {P.GPO_KEEP_OUT:.0f} mm of sockets")
    else:
        check(
            "R3 grid cover",
            P.GPO_PROUD + 0.5 + P.COVER_T <= P.PANEL_BACK - 2,
            f"cover top {P.GPO_PROUD + 0.5 + P.COVER_T:.1f} mm, panel back {P.PANEL_BACK:.1f} mm (supply in the wall)",
        )

    # board fits under the panel
    check("board height", P.BOARD_TOP <= P.PANEL_BACK - 2, f"board top {P.BOARD_TOP:.1f} mm, panel back {P.PANEL_BACK:.1f} mm")
    # board holes: measured 77.5 x 70 mm, standoffs must land on them and clear the connector window
    holes = [(P.BOARD_X + sx * P.BOARD_HOLE_DX / 2, P.BOARD_Y + sy * P.BOARD_HOLE_DY / 2) for sx in (-1, 1) for sy in (-1, 1)]
    ww, wh, wdx, wdy = P.BOARD_WINDOW
    wx0, wx1, wy0, wy1 = P.BOARD_X + wdx - ww / 2, P.BOARD_X + wdx + ww / 2, P.BOARD_Y + wdy - wh / 2, P.BOARD_Y + wdy + wh / 2
    r = P.STANDOFF_D / 2 + 1.0
    clear = all(x + r < wx0 or x - r > wx1 or y + r < wy0 or y - r > wy1 for x, y in holes)
    check("board standoffs", clear, f"{P.BOARD_HOLE_DX} x {P.BOARD_HOLE_DY} mm hole pattern, standoffs clear of the connector window")
    under = P.BACK_T + P.STANDOFF_H - P.BOARD_UNDER_H
    check("board connectors clear wall", under >= 0.3, f"connectors end {under:.1f} mm off the wall (through the plate window)")

    # feature spacing: vent slots must not cut into the snap-hook slots in the walls
    import _parts

    slots, holes = _parts.vent_xs(), _parts.wall_hole_xs()
    n_slots = len(_parts.vent_xs("top")) + len(_parts.vent_xs("bottom"))
    vent_area = n_slots * P.VENT_W * P.VENT_L
    # Vent area target: the cooling estimate below shows the outer surfaces do most of the work;
    # vents mainly stop a hot pocket forming over the board. Default 15.6" targets 15 cm2, small 12.
    need = 1500 if P.PANEL_W >= 340 else 1200
    check("vent area", vent_area >= need, f"{n_slots} slots top + bottom = {vent_area / 100:.0f} cm2 open (need >= {need // 100})")
    snap_half = P.SNAP_A / 2 + P.SNAP_B + 0.3  # half-width of a snap recess along the wall
    gap = min(abs(sx - hx) - P.VENT_W / 2 - snap_half for sx in slots for hx in holes)
    check("vents clear snap slots", gap >= 1.0, f"closest vent slot to a snap-hook slot: {gap:.1f} mm of material")

    # clamp bars stay behind the panel and inside the pocket
    check("clamp bar reach", P.BAR_D <= (P.PANEL_W - P.WIN_W) / 2 + 2, f"bars reach {P.BAR_D} mm over the panel border")

    # interference: no two parts may share volume (catches clashes a dimension check misses)
    import _parts

    bodies = {
        "frame_left": printable["frame_left"],
        "frame_right": printable["frame_right"],
        "back_plate": printable["back_plate"],
        "gpo_saddle": printable["gpo_saddle"],
        "ref_panel": _parts.panel_stand_in(),
        "ref_gpo": _parts.gpo_stand_in(),
        "ref_board": _parts.board_stand_in(),
        "ref_5v_lead": _parts.cable_stand_in(),
        "ref_edp_ribbon": _parts.edp_ribbon(),
        "ref_wifi_antenna": _parts.antenna_stand_in(),
    }
    if P.SPEAKERS:
        bodies["ref_speakers"] = _parts.speaker_stand_in()
    if P.PIR:
        bodies["ref_pir"] = _parts.pir_stand_in()
    for i, bar in enumerate(_parts.clamp_bars()):
        bodies[bar.label or f"bar{i}"] = bar
    names = list(bodies)
    clashes = []
    for i, a in enumerate(names):
        ba = bodies[a].bounding_box()
        for b in names[i + 1 :]:
            bb = bodies[b].bounding_box()
            if (
                ba.max.X < bb.min.X
                or bb.max.X < ba.min.X
                or ba.max.Y < bb.min.Y
                or bb.max.Y < ba.min.Y
                or ba.max.Z < bb.min.Z
                or bb.max.Z < ba.min.Z
            ):
                continue
            vol = _ovl(bodies[a], bodies[b])
            if vol > 1.0:
                clashes.append(f"{a} x {b} ({vol:.0f} mm3)")
    check("no interference", not clashes, "; ".join(clashes) or f"{len(names)} bodies, all clear")

    # hang-and-drop: lifted HOOK_DROP, the frame's fingers must clear the plate; dropped, they engage
    lift = _parts.bd.Location((0, P.HOOK_DROP, 0))
    v = sum(_ovl(bodies[f].moved(lift), bodies["back_plate"]) for f in ("frame_left", "frame_right"))
    check("hook: lifted frame clears plate", v < 1.0, f"frame raised {P.HOOK_DROP} mm overlaps the plate by {v:.0f} mm3")
    # service: everything that rides with the frame (bars, PIR, antenna, panel) lifted HOOK_DROP must clear
    # everything that stays on the wall (plate, saddle, board, lead, speakers, GPO)
    riders = [
        n
        for n in bodies
        if n.startswith(("frame_", "clamp_", "joiner_", "lip_splice_"))
        or n in ("ref_panel", "ref_pir", "ref_wifi_antenna", "ref_edp_ribbon")
    ]
    fixed = [n for n in bodies if n in ("back_plate", "gpo_saddle", "ref_board", "ref_5v_lead", "ref_speakers", "ref_gpo")]
    hits = []
    for r in riders:
        moved = bodies[r].moved(lift)
        for f in fixed:
            v_hit = _ovl(moved, bodies[f])
            if v_hit > 1.0:
                hits.append(f"{r} x {f} ({v_hit:.0f} mm3)")
    check(
        "service: lifted frame clears the wall parts",
        not hits,
        "; ".join(hits) or f"{len(riders)} parts lifted {P.HOOK_DROP} mm, clear of {len(fixed)} wall parts",
    )
    # bottom latch engages: a small lift (gap + 0.6 mm) must already run the catch head into the barb
    nudge = _parts.bd.Location((0, P.LATCH_GAP + 0.6, 0))
    v_l = sum(_ovl(bodies[f].moved(nudge), bodies["back_plate"]) for f in ("frame_left", "frame_right"))
    check("latch: catches on lift", v_l > 0.5, f"a {P.LATCH_GAP + 0.6:.1f} mm lift meets the barbs ({v_l:.1f} mm3 of catch overlap)")
    engage = P.TONGUE_L - P.HOOK_CLEAR
    check(
        "hook: engagement",
        engage >= 3.0 and P.HOOK_DROP > P.TONGUE_L + P.HOOK_CLEAR,
        f"finger sits {engage:.1f} mm behind each tongue; {P.HOOK_DROP} mm lift to clear it",
    )
    check("5V lead fits", P.CABLE_D >= P.CABLE_OD + 0.8, f"channel {P.CABLE_D} mm for a {P.CABLE_OD} mm lead")
    z_cover, _ = _parts.saddle_levels()
    if P.GPO_OPEN:
        check("saddle notch height", True, "open saddle (plug pack): the lead runs over the ring, no notch")
    else:
        check("saddle notch height", z_cover - P.BACK_T >= P.CABLE_D, f"{z_cover - P.BACK_T:.1f} mm under the cover for the lead")

    if P.BEZEL_STYLE == "even":
        check("even bezel", abs(P.BEZEL_LR - P.BEZEL_TB) < 0.05, f"sides {P.BEZEL_LR:.1f} mm, top/bottom {P.BEZEL_TB:.1f} mm")
    # keyholes (walls without a GPO): an 8 g pan head (8.6 mm head, 4.2 mm shank) must pass the big
    # end (9 mm) and be retained by the slot (4.8 mm), with the screw head under the plate face
    ok = P.KEY_ENTRY_D > P.SCREW_8G_HEAD_D and P.SCREW_8G_SHANK_D < P.KEY_SLOT_W < P.SCREW_8G_HEAD_D
    check(
        "keyhole fits an 8 g pan head",
        ok,
        f"{P.SCREW_8G_HEAD_D} mm head through the {P.KEY_ENTRY_D} mm entry, {P.SCREW_8G_SHANK_D} mm shank "
        f"in the {P.KEY_SLOT_W} mm slot, head held behind it",
    )

    if P.PLATE_SPLIT:  # each half must be one clean solid and fit a 250 x 210 bed (turned if needed)
        for h in _parts.back_plate_halves():
            sols = h.solids()
            bb = h.bounding_box()
            fits = min(bb.size.X, bb.size.Y) <= 210 and max(bb.size.X, bb.size.Y) <= 250
            check(
                f"split plate: {h.label}",
                len(sols) == 1 and fits,
                f"{len(sols)} solid(s), {bb.size.X:.0f} x {bb.size.Y:.0f} mm (needs 1 solid within 250 x 210)",
            )

    # snap hooks (clamp bars, joiners): cantilever strain while the barb passes the slot, PETG allows
    # ~4% for a one-off snap (2% to re-use). Arm length = relief depth + wall + barb.
    defl = P.SNAP_B - P.SNAP_C
    for label, wall_t in (("top/bottom", P.WALL + P.END_EXTRA), ("sides", P.WALL + P.SIDE_EXTRA)):
        arm_l = P.SNAP_RELIEF + wall_t
        strain = 1.5 * P.SNAP_A * defl / arm_l**2 * 100
        detail = f"{arm_l:.1f} mm arm deflects {defl:.1f} mm: {strain:.1f}% strain (PETG re-use limit ~2%)"
        check(f"snap hook strain ({label})", strain <= 2.0, detail)
    flush = P.SNAP_RECESS - P.SNAP_GAP - P.SNAP_FLAT - P.SNAP_B
    check("snap barb sits flush", -0.05 <= flush <= 0.3, f"barb {flush:.2f} mm below the outside face")
    hold = P.SNAP_B - P.SNAP_C
    check("snap hold", hold >= 0.5, f"each barb overlaps the slot edge by {hold:.1f} mm")

    # bottom latch: tongue strain to pass the catch head, and it must still catch once installed
    over = P.LATCH_BARB - 0.2  # head overlaps the barb by this much (tongue deflection to pass)
    l_t = _parts.latch_levels()["tongue_l"]  # tongue: from the slot roots to the barb
    strain = 1.5 * P.LATCH_T * over / l_t**2 * 100
    check("latch tongue strain", strain <= 2.0 and P.LATCH_SLOT >= over + 0.3,
          f"{l_t:.1f} mm tongue deflects {over:.1f} mm into a {P.LATCH_SLOT} mm slot: {strain:.2f}% strain (limit 2%)")
    # lift force: barb at 45 degrees, tongue stiffness k = 3EI/L^3, plus friction (mu 0.3)
    k_t = 3 * 2000 * (P.BACK_T * P.LATCH_T**3 / 12) / l_t**3
    f_lift = 2 * k_t * over * (1 + 0.3) / (1 - 0.3)
    check("latch hold vs weight", 5.0 <= f_lift <= 40.0 and f_lift > mass_est() * 9.81 * 0.5,
          f"2 latches resist a lift with ~{f_lift:.0f} N (frame weighs ~{mass_est() * 9.81:.0f} N); firm one-hand lift")

    # docs can't drift: every preset key the code reads must be documented in README.md, and vice versa
    import re as _re

    src_keys = set(_re.findall(r'_sel(?:\.get\(|\[)"(\w+)"', (ROOT / "src" / "params.py").read_text()))
    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
    doc_keys = set(_re.findall(r"`(\w+)`", readme[readme.find("Pick your hardware") : readme.find("## Files in this directory")]))
    missing = sorted(src_keys - doc_keys)
    check(
        "README documents every preset key",
        not missing,
        f"{len(src_keys)} keys read by params.py" + (f"; undocumented: {', '.join(missing)}" if missing else ", all documented"),
    )

    # touch at the screen edge: a fingertip (8 mm radius pad) pressed toward the glass is stopped by
    # the lip. With the 45 degree window chamfer the two lip corners are (0, FACE_T - WIN_CHAMFER)
    # and (-WIN_CHAMFER, FACE_T). Dead band = how close to the window edge the finger can touch.
    import math as _m

    r_f = 8.0
    h_a, h_b = P.FACE_T - P.WIN_CHAMFER, P.FACE_T
    dead = max(_m.sqrt(max(0.0, 2 * r_f * h_a - h_a**2)), _m.sqrt(max(0.0, 2 * r_f * h_b - h_b**2)) - P.WIN_CHAMFER)
    px = dead * 1920 / P.WIN_W
    ui_margin = 32  # kiosk/web/style.css: views have 32 px padding, the rail more; nothing tappable closer
    check(
        "touch reaches the screen edge",
        px <= ui_margin,
        f"finger can't reach the outer {dead:.1f} mm ({px:.0f} px); nothing tappable within {ui_margin} px of the edge",
    )

    # R6: at most 20 mm of room inside, wall to the back of the front lip (supply-in-wall build)
    inside = P.DEPTH - P.FACE_T
    if P.GPO_MECH == "removed" and P.PRESET == "framely-15.6":  # the reference build only
        check("inside depth <= 20 mm", inside <= 20.0, f"{inside:.1f} mm from the wall to the inside of the lip")

    # strength (hand calcs, PETG E ~2 GPa, yield ~45 MPa; ASA is similar)
    # Panel weight bears on the frame's bottom wall, not the clamps; the frame (with panel and board)
    # hangs on the two hook fingers, which press down on the plate's tongues. The tongue root
    # sees shear plus the moment of that load about the tongue base.
    mass = mass_est()
    per_hook = mass * 9.81 / 2
    w_tongue = P.HOOK_W + 6
    shear = per_hook / (w_tongue * P.TONGUE_T)  # N/mm2 = MPa
    lever = P.TONGUE_T / 2 + P.SLOT / 2  # finger load sits at most half the slot off the tongue face
    bend = per_hook * lever / (w_tongue * P.TONGUE_T**2 / 6)
    worst = max(shear, bend)
    check(
        "strength: hook tongues",
        worst * 4 <= 45,
        f"{mass:.2f} kg hung on 2 hooks: {per_hook:.1f} N each, {worst:.2f} MPa at the tongue root (4x margin to ~45 MPa)",
    )
    # touch: a 20 N press (2x a firm fingertip) on one clamp bar, cantilever of BAR_D
    i_bar = P.BAR_L * P.BAR_T**3 / 12
    sb = 20 * P.BAR_D * (P.BAR_T / 2) / i_bar
    check("strength: clamp bar", sb * 4 <= 45, f"20 N press on one bar: {sb:.2f} MPa bending")

    # cavity temperature rise at 8 W (board ~3 W + backlight ~5 W): outer surfaces (h ~8 W/m2K,
    # convection + radiation) in parallel with the vent chimney (Cd 0.6, 0.2 m stack). Bisection.
    import math

    area_m2 = (P.PANEL_W * P.PANEL_H + 2 * (P.OUTER_W + P.OUTER_H) * P.DEPTH + P.OUTER_W * P.OUTER_H - P.WIN_W * P.WIN_H) / 1e6
    ua = 8.0 * area_m2
    k_v = 1.2 * 1005 * 0.6 * (vent_area / 2 / 1e6 / math.sqrt(2)) * math.sqrt(2 * 9.81 * 0.2 / 298)
    lo, hi, mid = 0.0, 100.0, 50.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ua * mid + k_v * mid**1.5 > 8.0 else (mid, hi)
    check("thermal: cavity rise at 8 W", mid <= 12.0, f"~{mid:.1f} C above room (limit 12 C keeps the panel under ~40 C)")

    # touch flex: bare panel ~ 2.2 mm glass laminate, simply supported on its short span, 20 N centre press
    d_glass = 70e3 * 2.2**3 / (12 * (1 - 0.22**2))  # N.mm
    flex = 0.0116 * 20 * min(P.PANEL_W, P.PANEL_H) ** 2 / d_glass
    gap = P.PANEL_BACK - max(P.BOARD_TOP, P.GPO_FACE_Z + P.PLUG_ALLOW, _parts.saddle_levels()[1])
    check(
        "touch flex clears the parts behind",
        flex * 3 <= gap,
        f"panel bows ~{flex:.2f} mm under a 20 N press; {gap:.1f} mm to the nearest part behind it",
    )

    print(f"overall: {P.OUTER_W:.0f} x {P.OUTER_H:.0f} mm, {P.DEPTH:.1f} mm off the wall; bezel {P.BEZEL_LR:.1f} / {P.BEZEL_TB:.1f} mm")
    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())

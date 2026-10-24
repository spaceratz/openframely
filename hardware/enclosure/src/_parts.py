"""Part factories for the wall enclosure. Models (one file per printed part) call these.

Coordinates: X right, Y up, Z out from the wall (wall at Z=0), frame centre at X=Y=0.
Every part is returned in its installed position, so the assembly is just a list.
"""

from __future__ import annotations

import params as P
from cadgen import build123d as bd

# ---------------------------------------------------------------- helpers


def rbox(w: float, h: float, d: float, r: float, x: float = 0, y: float = 0, z: float = 0) -> bd.Part:
    """Rounded-rectangle prism, centred on (x, y), from z to z+d."""
    return bd.Pos(x, y, z) * bd.extrude(bd.RectangleRounded(w, h, r) if r > 0 else bd.Rectangle(w, h), d)


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> bd.Part:
    return bd.Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * bd.extrude(bd.Rectangle(x1 - x0, y1 - y0), z1 - z0)


def cyl(d: float, h: float, x: float, y: float, z: float = 0, axis: str = "Z") -> bd.Part:
    c = bd.extrude(bd.Circle(d / 2), h)
    if axis == "Y":  # along +Y, starting at y
        return bd.Pos(x, y, z) * bd.Rot(-90, 0, 0) * c
    if axis == "-Y":
        return bd.Pos(x, y, z) * bd.Rot(90, 0, 0) * c
    if axis == "X":
        return bd.Pos(x, y, z) * bd.Rot(0, 90, 0) * c
    if axis == "-X":
        return bd.Pos(x, y, z) * bd.Rot(0, -90, 0) * c
    return bd.Pos(x, y, z) * c


# ---------------------------------------------------------------- frame


def _frame_shell() -> bd.Part:
    """One-piece frame: side walls + front lip with the viewing window."""
    shell = rbox(P.OUTER_W, P.OUTER_H, P.DEPTH, P.CORNER_R)
    shell -= rbox(P.POCKET_W, P.POCKET_H, P.DEPTH - P.FACE_T, P.POCKET_R)  # inner radius fixed: the relief holes clear it
    # corner reliefs: the panel's corners are square, the pocket's are rounded
    for sx in (-1, 1):
        for sy in (-1, 1):
            shell -= cyl(
                P.CORNER_RELIEF_D,
                P.DEPTH - P.FACE_T,
                sx * (P.PANEL_W / 2 - P.CORNER_RELIEF_D / 4),
                P.PANEL_Y + sy * (P.PANEL_H / 2 - P.CORNER_RELIEF_D / 4),
            )
    shell -= rbox(P.WIN_W, P.WIN_H, P.DEPTH + 2, 1.0, P.WIN_OFFSET_X, P.WIN_OFFSET_Y, -1)
    # bevel the window on the viewer side: a 45 degree chamfer frustum
    c = P.WIN_CHAMFER
    bevel = bd.Pos(P.WIN_OFFSET_X, P.WIN_OFFSET_Y, P.DEPTH - c) * bd.loft(
        [bd.Rectangle(P.WIN_W, P.WIN_H), bd.Pos(0, 0, c + 0.01) * bd.Rectangle(P.WIN_W + 2 * c + 0.02, P.WIN_H + 2 * c + 0.02)]
    )
    shell -= bevel
    # soften the outer front edge
    front = shell.edges().group_by(bd.Axis.Z)[-1]
    outer = [e for e in front if max(abs(e.center().X), abs(e.center().Y)) > max(P.WIN_W, P.WIN_H) / 2 + 2]
    shell = bd.chamfer(outer, P.FRONT_CHAMFER)  # the front face prints on the bed: chamfer, not fillet
    # back (wall-side) outer edge: a small chamfer so a slightly uneven wall shows a soft shadow, not a gap
    if P.BACK_CHAMFER > 0:
        back = shell.edges().group_by(bd.Axis.Z)[0]
        back_outer = [e for e in back if max(abs(e.center().X) - P.OUTER_W / 2, abs(e.center().Y) - P.OUTER_H / 2) > -0.5]
        shell = bd.chamfer(back_outer, P.BACK_CHAMFER)
    if not shell.is_valid:
        raise ValueError("front edge chamfer produced an invalid solid")
    # reveal: a thin recessed line inset from the outer edge, so the bezel reads as a separate
    # face plate (and hides the small step a face-down print can leave on its first layer)
    if P.SHADOW_GAP > 0:
        inset = P.FRONT_CHAMFER + 2.5
        ow, oh = P.OUTER_W - 2 * inset, P.OUTER_H - 2 * inset
        ring = rbox(ow, oh, P.SHADOW_DEPTH + 1, max(P.CORNER_R - inset, 1.0), 0, 0, P.DEPTH - P.SHADOW_DEPTH)
        ring -= rbox(
            ow - 2 * P.SHADOW_GAP,
            oh - 2 * P.SHADOW_GAP,
            P.SHADOW_DEPTH + 2,
            max(P.CORNER_R - inset - P.SHADOW_GAP, 0.8),
            0,
            0,
            P.DEPTH - P.SHADOW_DEPTH - 0.5,
        )
        shell -= ring
    return shell


def _frame_features() -> tuple[bd.Part, bd.Part]:
    """(material to add, material to remove) for screw bosses, slots and vents."""
    add: list[bd.Part] = []
    cut: list[bd.Part] = []
    # bottom: a catch inside the bottom wall under each plate latch tongue (see latch_catch)
    for x in P.LATCH_X:
        add.append(latch_catch(x))
    # top edge: fingers that hook in behind the plate's tongues (see hook_geometry)
    for x in P.LATCH_X:
        add.append(hook_finger(x))

    # clamp bars and joiners snap through slots in the walls (see snap_hook / snap_slot)
    for (x, y), wall_t, axis, sgn_barb in snap_points():
        cut.append(snap_slot(x, y, wall_t, axis, sgn_barb))

    # vents: slots in the top wall (exhaust) and bottom wall (intake), clear of the panel zone
    z_mid = P.PANEL_BACK / 2
    for sgn in (-1, 1):
        for x in vent_xs("top" if sgn > 0 else "bottom"):
            wall_t = P.WALL + P.END_EXTRA
            cut.append(bd.Pos(x, sgn * (P.OUTER_H / 2 - wall_t / 2), z_mid) * bd.Box(P.VENT_W, wall_t + 2, P.VENT_L))

    # cable notch (bottom wall, optional mains-free USB-C feed if not using the GPO)
    if P.LOGO:  # debossed name on the outside of the bottom wall, left of the vent row
        txt = bd.extrude(bd.Text(P.LOGO, font_size=P.LOGO_SIZE), P.LOGO_DEPTH + 0.1)
        tb = txt.bounding_box()
        lx = -P.POCKET_W / 2 + 14 + tb.size.X / 2
        # text lies in XZ on the wall face, reading upright from below, sunk LOGO_DEPTH into the wall
        centred = bd.Pos(-tb.center().X, -tb.center().Y, 0) * txt
        cut.append(bd.Pos(lx, -P.OUTER_H / 2 + P.LOGO_DEPTH, P.DEPTH * 0.45) * bd.Rot(90, 0, 0) * centred)
    # finger recesses on the outer face of both side walls, low down: grip to lift the frame off its hooks.
    # 45 degree roof toward the wall side so the face-down print needs no support.
    if P.GRIP_DEPTH > 0 and P.DEPTH >= 27.0:  # shallow frames (13.3") have no room above the support taper
        for sgn in (-1, 1):
            x_out = sgn * P.OUTER_W / 2
            y0 = -P.OUTER_H / 2 + P.GRIP_FROM_BOTTOM
            z0, z1 = P.FRONT_CHAMFER + 3.0, P.DEPTH - P.BACK_CHAMFER - 3.0 - P.GRIP_DEPTH
            prof = bd.Polyline((0, z0), (P.GRIP_DEPTH, z0), (P.GRIP_DEPTH, z1), (0, z1 + P.GRIP_DEPTH), close=True)
            wedge = bd.extrude(bd.Plane.XZ * bd.make_face(prof), P.GRIP_L)
            cut.append(bd.Pos(x_out - sgn * P.GRIP_DEPTH, y0 + P.GRIP_L, 0) * (wedge if sgn > 0 else bd.mirror(wedge, bd.Plane.YZ)))
    if P.PIR:  # PIR lens hole through the bottom wall
        cut.append(cyl(P.PIR_D, P.WALL + P.END_EXTRA + 0.4, P.PIR_X, -P.OUTER_H / 2 - 0.2, P.PIR_Z, "Y"))
    nx = -P.POCKET_W / 2 + 22.0  # near the bottom-left corner
    cut.append(box(nx - 10, nx + 10, -P.OUTER_H / 2 - 1, -P.POCKET_H / 2 + 0.1, -0.1, 6))

    fuse = lambda parts: parts[0].fuse(*parts[1:]) if len(parts) > 1 else parts[0]  # noqa: E731
    return (fuse(add) if add else None), fuse(cut)


def wall_hole_xs() -> list[float]:
    """X of every snap-hook slot in the top/bottom walls (clamp bars and joiners)."""
    return [x for (x, _), _, axis, _ in snap_points() if axis == "Y"]


def wall_blocked_x(wall: str = "both") -> list[tuple[float, float]]:
    """X ranges of the top/bottom walls that are covered from inside (clamp bars, joiners, plate tabs).
    wall: "top", "bottom" or "both" (the PIR lens only blocks the bottom wall)."""
    m = P.VENT_W / 2 + 1.0
    spans = [(x - P.BAR_L / 2 - m, x + P.BAR_L / 2 + m) for x in P.CLAMP_TOP_X]
    spans.append((P.JOINER_X - P.JOINER_L / 2 - m, P.JOINER_X + P.JOINER_L / 2 + m))
    if wall in ("bottom", "both"):  # latch catches sit inside the bottom wall
        spans += [(x - P.LATCH_T / 2 - m, x + P.LATCH_T / 2 + 0.2 + P.LATCH_HEAD_W + m) for x in P.LATCH_X]
    if wall in ("top", "both"):  # hook fingers sit inside the top wall at the frame-screw X positions
        spans += [(x - P.HOOK_W / 2 - m - 1, x + P.HOOK_W / 2 + m + 1) for x in P.LATCH_X]
    if P.LOGO and wall in ("bottom", "both"):
        lx0 = -P.POCKET_W / 2 + 14
        spans.append((lx0 - m, lx0 + len(P.LOGO) * P.LOGO_SIZE * 0.55 + m))
    if P.PIR and wall in ("bottom", "both"):
        spans.append((P.PIR_X - P.PIR_D / 2 - m - 2, P.PIR_X + P.PIR_D / 2 + m + 2))
    return spans


def vent_xs(wall: str = "both") -> list[float]:
    """Vent slots across the top/bottom walls, skipping anywhere a bar, tab or screw sits behind them."""
    edge = P.POCKET_W / 2 - P.POCKET_R - P.VENT_W  # clear of the inside corner, not the outside radius
    # grid anchored on the seam (half-pitch either side), so corner and pocket sizes never shift it
    n = int(edge // P.VENT_PITCH) + 1
    xs = [P.SPLIT_X + (k + 0.5) * P.VENT_PITCH for k in range(-n - 1, n)]
    xs = [x for x in xs if abs(x) <= edge]
    xs = [x for x in xs if all(abs(x - h) >= P.VENT_KEEP for h in wall_hole_xs())]
    if wall == "both":  # union of both walls' slots (for anything that must avoid every slot)
        return sorted(set(vent_xs("top")) | set(vent_xs("bottom")))
    xs = [x for x in xs if not any(a <= x <= b for a, b in wall_blocked_x(wall))]
    return [x for x in xs if abs(x - P.SPLIT_X) > P.VENT_PITCH]  # keep the seam solid


def frame_full() -> bd.Part:
    shell = _frame_shell()
    add, cut = _frame_features()
    if add is not None:
        shell += add
    shell -= cut
    return shell


def _splice_recess(grow: float = 0.0) -> bd.Part:
    """Shallow recesses in the back of the lip, either side of the split, top and bottom.

    A thin splice plate glued into them bridges the seam flush with the lip, so the halves can't
    step at the front. It sits in the panel border (hidden behind the panel's own bezel).
    """
    y0, y1 = P.WIN_H / 2 + P.WIN_CHAMFER + 1.0, P.POCKET_H / 2 - 0.6
    z0 = P.DEPTH - P.FACE_T
    out = []
    for sgn in (-1, 1):
        lo, hi = sorted((sgn * y0, sgn * y1))
        # cut into the lip's back face (z0 .. z0 + SPLICE_T); the plate fills it flush, in front of the panel gap
        out.append(
            box(P.SPLIT_X - P.SPLICE_L / 2 - grow, P.SPLIT_X + P.SPLICE_L / 2 + grow, lo - grow, hi + grow, z0, z0 + P.SPLICE_T + grow)
        )
    return out[0] + out[1]


def frame_half(side: str) -> bd.Part:
    """Left or right half of the frame, split on X = SPLIT_X so each fits the bed.

    The halves line up on the joiner bars (walls) and two splice plates (lip), then get glued.
    """
    full = frame_full()
    big = P.OUTER_W
    keep = box(-big, P.SPLIT_X, -big, big, -1, P.DEPTH + 1) if side == "left" else box(P.SPLIT_X, big, -big, big, -1, P.DEPTH + 1)
    part = (full & keep) - _splice_recess(grow=P.SPLICE_CLEAR)
    # seam groove: each half gets a 45 degree chamfer on its front edge at the split, so the joined
    # seam reads as a deliberate V line (same width as the reveal) instead of a glue line
    if P.SEAM_V > 0:
        v = P.SEAM_V
        tri = bd.Polyline((P.SPLIT_X - v, P.DEPTH + 0.01), (P.SPLIT_X + v, P.DEPTH + 0.01), (P.SPLIT_X, P.DEPTH - v), close=True)
        groove = bd.extrude(bd.Plane.XZ * bd.make_face(tri), P.OUTER_H, both=True)
        part -= groove
    part.label = f"frame_{side}"
    return part


# ---------------------------------------------------------------- hang-and-drop top mount


def hook_levels() -> dict[str, float]:
    """Y/Z datums of the top hook. y_b is the base of the plate's tongue."""
    y_top = P.POCKET_H / 2  # inside face of the frame's top wall
    y_b = y_top - P.HOOK_CLEAR - P.TONGUE_L - 1.5  # tongue top stays 1.5 mm under the top wall
    z_slot = P.BACK_T + P.SLOT  # underside of the tongue
    return {"y_top": y_top, "y_b": y_b, "z_slot": z_slot, "z_tongue": z_slot + P.TONGUE_T}


def hook_finger(x: float) -> bd.Part:
    """Finger on the inside of the frame's top wall. Its front face slopes at 45 degrees up to the
    wall above the tongue, so it prints without supports (frame prints face-down)."""
    h = hook_levels()
    y_tip = h["y_b"] + P.HOOK_CLEAR
    z0, z1 = P.HOOK_CLEAR, h["z_slot"] - P.HOOK_CLEAR
    y_slope = h["y_b"] + P.TONGUE_L + P.HOOK_CLEAR  # slope starts above the tongue
    run = h["y_top"] - y_slope
    pts = [(y_tip, z0), (h["y_top"] + 0.5, z0), (h["y_top"] + 0.5, z1 + run), (y_slope, z1), (y_tip, z1)]
    prof = bd.Polyline(*[(px, pz) for px, pz in pts], close=True)
    sk = bd.Plane.YZ * bd.make_face(prof)
    return bd.Pos(x - P.HOOK_W / 2, 0, 0) * bd.extrude(sk, P.HOOK_W)


def hook_tongue(x: float) -> bd.Part:
    """Plate top tab + riser + upward tongue standing SLOT off the plate face."""
    h = hook_levels()
    w = P.HOOK_W + 6
    tab = box(x - w / 2, x + w / 2, P.PLATE_H / 2 - 2, h["y_b"], 0, P.BACK_T)
    tab += box(x - w / 2, x + w / 2, h["y_b"] - P.RISER, h["y_b"], 0, h["z_tongue"])
    tab += box(x - w / 2, x + w / 2, h["y_b"] - 0.01, h["y_b"] + P.TONGUE_L, h["z_slot"], h["z_tongue"])
    return tab


# ---------------------------------------------------------------- bottom snap latch


def latch_levels() -> dict[str, float]:
    """Y datums (installed): plate bottom edge, tongue tip (barb), catch head, frame floor.
    The tongue tip sits HOOK_DROP + 1 above the floor, so the lifted frame's bottom wall clears it;
    lifted, the head rises into a notch in the plate beside the tongue."""
    y_edge, y_floor = P.PLATE_Y - P.PLATE_H / 2, -P.POCKET_H / 2
    y_barb = y_floor + P.HOOK_DROP + 1.0
    y_head = y_barb - P.LATCH_GAP
    y_root = y_edge + P.LATCH_SLOT_TOP  # where the tongue joins the plate
    return {"y_edge": y_edge, "y_head": y_head, "y_barb": y_barb, "y_floor": y_floor, "y_root": y_root,
            "tongue_l": y_root - y_barb, "y_notch": y_head + P.HOOK_DROP + 0.6}


def latch_tongue(x: float) -> bd.Part:
    """Plate side: a tongue hanging below the plate's bottom edge, its barb pointing +X.
    45 degree faces both ways: dropping the frame on clicks it, a firm lift pushes it aside."""
    lv = latch_levels()
    t, b = P.LATCH_T / 2, P.LATCH_BARB
    tongue = box(x - t, x + t, lv["y_barb"], lv["y_edge"] + 0.5, 0, P.BACK_T)
    y0 = lv["y_barb"]
    prof = bd.Polyline((x + t - 0.01, y0), (x + t + b, y0 + b), (x + t + b, y0 + b + 0.4), (x + t - 0.01, y0 + 2 * b + 0.4), close=True)
    return tongue + bd.extrude(bd.make_face(prof), P.BACK_T)


def latch_relief(x: float) -> bd.Part:
    """Slots either side of the tongue, running LATCH_SLOT_TOP into the plate, so the tongue is long
    enough to flex; the wide one is on the side it bends toward."""
    lv = latch_levels()
    t = P.LATCH_T / 2
    y0, y1 = lv["y_edge"] - 1, lv["y_root"]
    hx1 = x + t + 0.2 + P.LATCH_HEAD_W + 0.6  # notch the lifted catch head rises into
    return (box(x - t - P.LATCH_SLOT, x - t, y0, y1, -1, P.BACK_T + 1) + box(x + t, x + t + 0.6, y0, y1, -1, P.BACK_T + 1)
            + box(x + t, hx1, y0, max(lv["y_notch"], lv["y_edge"] + 0.5), -1, P.BACK_T + 1))


def latch_catch(x: float) -> bd.Part:
    """Frame side: a post up from the inside of the bottom wall carrying a head that sits under the
    barb. Its wall-side face tapers at 45 degrees so the face-down frame prints it without supports."""
    lv = latch_levels()
    hx0 = x + P.LATCH_T / 2 + P.LATCH_BARB - (P.LATCH_BARB - 0.2)  # head overlaps the barb by LATCH_BARB - 0.2
    head = box(hx0, hx0 + P.LATCH_HEAD_W, lv["y_head"] - P.LATCH_HEAD_H, lv["y_head"], 0.4, 20)
    post = box(hx0 + P.LATCH_HEAD_W - P.LATCH_POST_W, hx0 + P.LATCH_HEAD_W, lv["y_floor"] - 0.5, lv["y_head"], 0.4, 20)
    z_top = P.BACK_T - 0.4  # head's top face (wall side)
    run = lv["y_head"] - (lv["y_floor"] - 0.5)
    y_lo = lv["y_floor"] - 0.5
    taper = bd.Polyline((y_lo, -1), (lv["y_head"], -1), (lv["y_head"], z_top), (y_lo, z_top + run), close=True)
    wedge = bd.Pos(hx0 - 1, 0, 0) * bd.extrude(bd.Plane.YZ * bd.make_face(taper), P.LATCH_HEAD_W + 2)
    return (head + post) & wedge


# ---------------------------------------------------------------- snap hooks (clamp bars, joiners)


def snap_points() -> list:
    """((x, y) on the inside face of the wall, wall thickness, wall normal axis, barb direction) for every
    snap hook. Two hooks per bar, barbs pointing away from each other so the bar can't slide free."""
    in_x, in_y = P.POCKET_W / 2, P.POCKET_H / 2
    t_tb, t_lr = P.WALL + P.END_EXTRA, P.WALL + P.SIDE_EXTRA
    pts = []
    for sgn in (-1, 1):
        for cx, dx in [(x, P.SNAP_DX) for x in P.CLAMP_TOP_X] + [(P.JOINER_X, P.JOINER_SNAP_DX)]:
            for s in (-1, 1):
                pts.append(((cx + s * dx, sgn * in_y), t_tb, "Y", s))
        for cy in P.CLAMP_SIDE_Y:
            for s in (-1, 1):
                pts.append(((sgn * in_x, cy + s * P.SNAP_DX), t_lr, "X", s))
    return pts


def _snap_place(part: bd.Part, x: float, y: float, axis: str) -> bd.Part:
    """Local (u = out through the wall, v = barb direction, z) to frame coordinates."""
    if axis == "Y":  # top/bottom walls: u = +/-Y, v = X
        sgn = 1 if y > 0 else -1
        return bd.Pos(x, y, 0) * (bd.Rot(0, 0, 90) * part if sgn > 0 else bd.Rot(0, 0, -90) * bd.mirror(part, bd.Plane.XZ))
    sgn = 1 if x > 0 else -1
    return bd.Pos(x, y, 0) * (part if sgn > 0 else bd.Rot(0, 0, 180) * bd.mirror(part, bd.Plane.XZ))


def _local_v(part: bd.Part, sgn_barb: int) -> bd.Part:
    return part if sgn_barb > 0 else bd.mirror(part, bd.Plane.XZ)


def _snap_u_r(wall_t: float) -> float:
    return wall_t - P.SNAP_RECESS + P.SNAP_GAP  # barb's retaining face (u)


def snap_hook(x: float, y: float, wall_t: float, axis: str, sgn_barb: int) -> tuple[bd.Part, bd.Part]:
    """(arm + barb to add to the bar, relief slots to cut from the bar). Full bar height in Z, so the
    bar prints flat and the arm bends in-layer."""
    a, b = P.SNAP_A / 2, P.SNAP_B
    z0, z1 = P.BAR_Z0, P.BAR_Z1
    u_r = _snap_u_r(wall_t)
    arm = bd.Pos(0, 0, z0) * bd.extrude(bd.Rectangle(u_r + P.SNAP_FLAT + b, 2 * a, align=(bd.Align.MIN, bd.Align.CENTER)), z1 - z0)
    barb = bd.Pos(0, 0, z0) * bd.extrude(bd.make_face(bd.Polyline(
        (u_r, a - 0.01), (u_r, a + b), (u_r + P.SNAP_FLAT, a + b), (u_r + P.SNAP_FLAT + b, a - 0.01), close=True)), z1 - z0)
    w_away, w_side = P.SNAP_RELIEF_W
    relief = box(-P.SNAP_RELIEF, 0.01, -a - w_away, -a, z0 - 1, z1 + 1) + box(-P.SNAP_RELIEF, 0.01, a, a + w_side, z0 - 1, z1 + 1)
    return _snap_place(_local_v(arm + barb, sgn_barb), x, y, axis), _snap_place(_local_v(relief, sgn_barb), x, y, axis)


def snap_slot(x: float, y: float, wall_t: float, axis: str, sgn_barb: int) -> bd.Part:
    """Wall side: slot the arm passes through (room to deflect away from the barb), plus a recess on
    the outside where the barb sits flush. Press the barb in from outside to release the bar."""
    a, b, c = P.SNAP_A / 2, P.SNAP_B, P.SNAP_C
    z0, z1 = P.BAR_Z0 - c, P.BAR_Z1 + c
    slot = box(-0.1, wall_t + 0.1, -a - b, a + c, z0, z1)
    recess = box(wall_t - P.SNAP_RECESS, wall_t + 0.1, -a - b - 0.3, a + b + 0.3, z0 - 0.5, z1 + 0.5)
    return _snap_place(_local_v(slot + recess, sgn_barb), x, y, axis)


# ---------------------------------------------------------------- back plate


def _gpo_cutout() -> bd.Part:
    """The GPO grid passes through the plate (sockets and switches stay reachable)."""
    return rbox(P.GPO_GRID_W + 1.0, P.GPO_GRID_L + 1.0, P.BACK_T + 2, 3.0, P.GPO_X, P.GPO_Y, -1)


def back_plate() -> bd.Part:
    px, py = P.PLATE_X, P.PLATE_Y
    plate = rbox(P.PLATE_W, P.PLATE_H, P.BACK_T, 4.0, px, py)

    for x in P.LATCH_X:
        plate += hook_tongue(x)  # top edge: hang-and-drop hooks
        plate += latch_tongue(x)  # bottom edge: snap latch tongue (its relief slots are cut below)

    # ribs to stop the plate flexing (vertical, either side of the GPO), notched where the 5 V lead crosses
    for rx in rib_xs():
        rib = box(rx - 1.2, rx + 1.2, py - P.PLATE_H / 2 + 6, py + P.PLATE_H / 2 - 6, P.BACK_T, P.BACK_T + 6)
        for seg in cable_path_xy():
            rib -= _cable_clearance(seg, extra=1.0)
        plate += rib
    # clips that hold the 5 V lead in its channel
    for cx, cy, along in clip_points():
        plate += cable_clip(cx, cy, along)
    # strain relief: a cradle behind the USB-C plug so a tug on the lead can't lever the board's socket
    plate += usb_cradle()
    # speaker pods (sound leaves through the bottom wall vents just below)
    if P.SPEAKERS:
        for sx, sy in speaker_xy():
            plate += speaker_pod(sx, sy)

    plate -= _gpo_cutout()
    for x in P.LATCH_X:
        plate -= latch_relief(x)

    # window under the board's connector edge (USB-A/USB-C/SD hang down toward the wall)
    ww, wh, wdx, wdy = P.BOARD_WINDOW
    plate -= rbox(ww, wh, P.BACK_T + 2, 2.0, P.BOARD_X + wdx, P.BOARD_Y + wdy, -1)
    # slot for the USB-C plug body (it sits lower than the plate face); the cradle walls stand either side
    ux, uy = _uc_point()
    pw = P.UC_PLUG_W + 2 * 0.4
    plate -= box(ux - pw / 2, ux + pw / 2, P.BOARD_Y + P.BOARD_H / 2 - 1, uy + 0.4, -1, P.BACK_T + 1)

    # board standoffs
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = P.BOARD_X + sx * P.BOARD_HOLE_DX / 2
            y = P.BOARD_Y + sy * P.BOARD_HOLE_DY / 2
            plate += cyl(P.STANDOFF_D, P.STANDOFF_H, x, y, P.BACK_T)
            plate -= cyl(P.STANDOFF_HOLE, P.STANDOFF_H + 0.1, x, y, P.BACK_T + 0.05)

    # cable tie slots
    for x in (P.BOARD_X - P.BOARD_W / 2 - 4,):
        for y in (-20, 20):
            plate -= box(x - 1.5, x + 1.5, y - 3, y + 3, -1, P.BACK_T + 1)

    # keyhole hangers for walls without a GPO (2 x 8 g pan-head screws, 200 mm apart)
    for x in (px - 100, px + 100):
        y = py + P.PLATE_H / 2 - 22
        sw = P.GPO_GRID_W / 2 + P.SADDLE_RING + 0.5 + P.SADDLE_FLANGE + 1.0  # saddle footprint + 1 mm
        sl = P.GPO_GRID_L / 2 + P.SADDLE_RING + 0.5 + P.SADDLE_FLANGE + 1.0
        k_lo, k_hi = y - P.KEY_SLOT_L - P.KEY_SLOT_W / 2 - 0.1, y + P.KEY_ENTRY_D / 2  # keyhole extent in Y
        if abs(x - P.GPO_X) < sw + P.KEY_ENTRY_D / 2 and k_lo < P.GPO_Y + sl and k_hi > P.GPO_Y - sl:
            continue  # under the GPO saddle (high GPO): unusable there, and it would graze the GPO window
        plate -= cyl(P.KEY_ENTRY_D, P.BACK_T + 2, x, y, -1)
        plate -= box(x - P.KEY_SLOT_W / 2, x + P.KEY_SLOT_W / 2, y - P.KEY_SLOT_L, y, -1, P.BACK_T + 1)
        plate -= cyl(P.KEY_SLOT_W + 0.2, P.BACK_T + 2, x, y - P.KEY_SLOT_L, -1)  # round end of the slot

    plate.label = "back_plate"
    return plate


def saddle_levels() -> tuple[float, float]:
    """(underside of the cover, top of the saddle). Open variant: no cover, top of the bars."""
    z_bars = P.GPO_EAR_Z + P.SADDLE_BAR_T
    if P.GPO_OPEN:
        return z_bars, z_bars
    z_cover = max(P.GPO_FACE_Z + 0.5, z_bars, P.BACK_T + P.CABLE_D + 0.5)
    return z_cover, z_cover + P.COVER_T


def gpo_saddle() -> bd.Part:
    """Clamps the back plate to the wall using only the GPO's two mounting screws.

    Without its faceplate, a Clipsal grid is held by two screws through ears at each end of its
    long axis (84 mm centres). The saddle's two bars rest on those ears, so tightening the screws
    loads the grid and wall box directly. Its flange presses the back plate flat to the wall.

    Closed variant (supply in the wall): a cover over the grid with a grommet for the 5 V lead.
    Open variant (PLUG_ALLOW > 0): the socket faces stay open between the bars.

    Prints cover-down with no supports: the bars run solid up to the cover, and the flange
    underside is a 45 degree skirt instead of a flat overhang.
    """
    gx, gy = P.GPO_X, P.GPO_Y
    z_plate = P.BACK_T
    z_ear = P.GPO_EAR_Z
    z_cover, z_top = saddle_levels()
    ring_w = P.GPO_GRID_W + 2 * P.SADDLE_RING + 1.0
    ring_l = P.GPO_GRID_L + 2 * P.SADDLE_RING + 1.0
    in_w, in_l = P.GPO_GRID_W + 1.0, P.GPO_GRID_L + 1.0

    # ring wall, plate face up to the top
    s = rbox(ring_w, ring_l, z_top - z_plate, 4.0, gx, gy, z_plate)
    s -= rbox(in_w, in_l, z_top - z_plate + 2, 3.0, gx, gy, z_plate - 1)
    # flange: flat on the plate, 45 degree skirt toward the ring (prints without supports)
    f = P.SADDLE_FLANGE
    skirt = bd.loft(
        [
            bd.Pos(gx, gy, z_plate) * bd.RectangleRounded(ring_w + 2 * f, ring_l + 2 * f, 6.0),
            bd.Pos(gx, gy, z_plate + P.SADDLE_FLANGE_T) * bd.RectangleRounded(ring_w + 2 * f, ring_l + 2 * f, 6.0),
        ]
    )
    taper = bd.loft(
        [
            bd.Pos(gx, gy, z_plate + P.SADDLE_FLANGE_T) * bd.RectangleRounded(ring_w + 2 * f, ring_l + 2 * f, 6.0),
            bd.Pos(gx, gy, z_plate + P.SADDLE_FLANGE_T + f) * bd.RectangleRounded(ring_w + 0.02, ring_l + 0.02, 4.0),
        ]
    )
    flange = (skirt + taper) & box(gx - ring_w, gx + ring_w, gy - ring_l, gy + ring_l, z_plate, z_top)
    flange -= rbox(in_w, in_l, z_top - z_plate + 2, 3.0, gx, gy, z_plate - 1)
    s += flange
    # bars across the grid at the screw positions: from the ears up to the cover/top, solid
    for dy in (-P.GPO_SCREW_C / 2, P.GPO_SCREW_C / 2):
        # inside the plate cut-out the bar drops to the ears; over the plate it starts at the plate face
        s += box(gx - in_w / 2, gx + in_w / 2, gy + dy - P.SADDLE_BAR_W / 2, gy + dy + P.SADDLE_BAR_W / 2, z_ear, z_cover)
    if not P.GPO_OPEN:
        s += rbox(ring_w, ring_l, P.COVER_T, 4.0, gx, gy, z_cover)
        # exit notch for the 5 V lead in the +X side, from the plate face up to the cover
        s -= box(
            gx + in_w / 2 - 1,
            gx + ring_w / 2 + f + 1,
            gy + P.CABLE_Y - P.CABLE_D / 2,
            gy + P.CABLE_Y + P.CABLE_D / 2,
            z_plate - 0.1,
            z_cover,
        )
    # screw holes + head recesses from the top
    for dy in (-P.GPO_SCREW_C / 2, P.GPO_SCREW_C / 2):
        s -= cyl(P.GPO_SCREW_D, z_top - z_ear + 0.2, gx, gy + dy, z_ear - 0.1)
        s -= cyl(P.GPO_HEAD_D, P.GPO_HEAD_H + 0.1, gx, gy + dy, z_top - P.GPO_HEAD_H)
    # finger notches in the long sides (through the ring and flange)
    for sx in (-1, 1):
        xe = gx + sx * (ring_w / 2 + f)
        s -= box(min(xe, gx + sx * in_w / 2), max(xe, gx + sx * in_w / 2), gy - 9, gy + 9, z_plate + P.SADDLE_FLANGE_T, z_top + 1)
    s.label = "gpo_saddle"
    return s


# ---------------------------------------------------------------- clamp bars


def _bar(x0: float, x1: float, y0: float, y1: float, hooks: list) -> bd.Part:
    b = box(x0, x1, y0, y1, P.BAR_Z0, P.BAR_Z1)
    for (hx, hy), wall_t, axis, sgn_barb in hooks:
        add, relief = snap_hook(hx, hy, wall_t, axis, sgn_barb)
        b = (b - relief) + add
    return b


def clamp_bars() -> list[bd.Part]:
    """Bars that press the panel into the lip (foam tape between), each held by two snap hooks
    through the frame wall: no screws, no inserts."""
    in_x, in_y = P.POCKET_W / 2, P.POCKET_H / 2
    pts = snap_points()
    near = lambda cx, cy, half: [p for p in pts if abs(p[0][0] - cx) <= half and abs(p[0][1] - cy) < 0.01]  # noqa: E731
    near_x = lambda cx, cy, half: [p for p in pts if abs(p[0][1] - cy) <= half and abs(p[0][0] - cx) < 0.01]  # noqa: E731
    bars: list[bd.Part] = []
    for x in P.CLAMP_TOP_X:
        for sgn, name in ((1, "top"), (-1, "bottom")):
            y_wall = sgn * in_y
            y_in = y_wall - sgn * (P.BAR_D_TOP if sgn > 0 else P.BAR_D)
            b = _bar(x - P.BAR_L / 2, x + P.BAR_L / 2, min(y_wall, y_in), max(y_wall, y_in), near(x, y_wall, P.BAR_L / 2))
            b.label = f"clamp_{name}_{'left' if x < 0 else 'right'}"
            bars.append(b)
    for y in P.CLAMP_SIDE_Y:
        for sgn, name in ((1, "right"), (-1, "left")):
            x_wall = sgn * in_x
            x_in = x_wall - sgn * P.BAR_D
            b = _bar(min(x_wall, x_in), max(x_wall, x_in), y - P.BAR_L / 2, y + P.BAR_L / 2, near_x(x_wall, y, P.BAR_L / 2))
            b.label = f"clamp_{name}"
            bars.append(b)
    # joiners: span the split line, hooked into both halves (and glued)
    for sgn, name in ((1, "top"), (-1, "bottom")):
        y_wall = sgn * in_y
        y_in = y_wall - sgn * (P.BAR_D_TOP if sgn > 0 else P.BAR_D)
        b = _bar(P.JOINER_X - P.JOINER_L / 2, P.JOINER_X + P.JOINER_L / 2, min(y_wall, y_in), max(y_wall, y_in),
                 near(P.JOINER_X, y_wall, P.JOINER_L / 2))
        b.label = f"joiner_{name}"
        bars.append(b)
    for sgn, name in ((1, "top"), (-1, "bottom")):
        y_lo, y_hi = (0.0, P.OUTER_H) if sgn > 0 else (-P.OUTER_H, 0.0)
        sp = _splice_recess() & box(-P.OUTER_W, P.OUTER_W, y_lo, y_hi, -1, P.DEPTH + 1)
        sp.label = f"lip_splice_{name}"
        bars.append(sp)
    return bars


# ---------------------------------------------------------------- 5 V lead route


def cable_z() -> float:
    return P.BACK_T + P.CABLE_OD / 2 + 0.3  # lead lies on the plate face


def _uc_point() -> tuple[float, float]:
    """Where the USB-C plug's cable end sits (above the board's top edge, plug pointing -Y)."""
    return P.BOARD_X + P.UC_DX, P.BOARD_Y + P.BOARD_H / 2 + P.UC_PLUG_L - 4


def cable_path_xy() -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Straight runs of the lead on the plate, from the saddle's side notch to the USB-C plug."""
    gx, gy = P.GPO_X, P.GPO_Y
    x_exit = gx + P.GPO_GRID_W / 2 + P.SADDLE_RING + P.SADDLE_FLANGE + 2
    if P.GPO_MECH == "plug":  # lead comes down outside the saddle flange, not through a notch
        x_exit += P.CABLE_OD / 2 + 3.0
    ux, uy = _uc_point()
    x_turn = P.BOARD_X - P.BOARD_W / 2 - 6  # go up the left side of the board
    y_run = uy + 10
    x_rise = gx + P.GPO_APERTURE_W / 2 - P.CABLE_OD / 2 - 1.5  # up out of the box, inside the aperture
    pts = [(x_rise, gy + P.CABLE_Y), (x_exit, gy + P.CABLE_Y), (x_turn, gy + P.CABLE_Y), (x_turn, y_run), (ux, y_run), (ux, uy)]
    return list(zip(pts[:-1], pts[1:], strict=True))


def _seg_solid(a: tuple[float, float], b: tuple[float, float], d: float, z: float) -> bd.Part:
    (x0, y0), (x1, y1) = a, b
    if abs(x1 - x0) > abs(y1 - y0):
        lo, hi = sorted((x0, x1))
        body = cyl(d, hi - lo, lo, y0, z, "X")
    else:
        lo, hi = sorted((y0, y1))
        body = cyl(d, hi - lo, x0, lo, z, "Y")
    return body + bd.Pos(x1, y1, z) * bd.Sphere(d / 2) + bd.Pos(x0, y0, z) * bd.Sphere(d / 2)


def _cable_clearance(seg, extra: float = 0.5) -> bd.Part:
    """Rectangular channel around a run, from the plate face up, for notching ribs."""
    (x0, y0), (x1, y1) = seg
    r = P.CABLE_D / 2 + extra
    return box(min(x0, x1) - r, max(x0, x1) + r, min(y0, y1) - r, max(y0, y1) + r, P.BACK_T - 0.01, P.BACK_T + 20)


def rib_xs() -> list[float]:
    return [P.GPO_X - P.GPO_GRID_W / 2 - 14, P.GPO_X + P.GPO_GRID_W / 2 + 14, P.BOARD_X - P.BOARD_W / 2 - 14]


def clip_points() -> list[tuple[float, float, str]]:
    """One clip at the middle of the longest horizontal run and one on the longest vertical run,
    both on open plate (never on a run inside the saddle, never near a bend)."""
    x_safe = P.GPO_X + P.GPO_GRID_W / 2 + P.SADDLE_RING + P.SADDLE_FLANGE + 8.0
    runs = [(a, b) for a, b in cable_path_xy() if min(a[0], b[0]) >= x_safe - 0.01]
    horiz = [r for r in runs if abs(r[0][1] - r[1][1]) < 0.01]
    vert = [r for r in runs if abs(r[0][0] - r[1][0]) < 0.01]
    pick = []
    for group, along in ((horiz, "X"), (vert, "Y")):
        if group:
            (x0, y0), (x1, y1) = max(group, key=lambda r: abs(r[1][0] - r[0][0]) + abs(r[1][1] - r[0][1]))
            pick.append(((x0 + x1) / 2, (y0 + y1) / 2, along))
    return pick


def cable_clip(x: float, y: float, along: str) -> bd.Part:
    """Printed bridge over the lead: two posts and a 45-degree-roofed top (prints without supports)."""
    zc, r = cable_z(), P.CABLE_D / 2
    top = zc + r + 1.6
    w_along, w_across = 6.0, P.CABLE_D + 5.0
    if along == "X":
        c = box(x - w_along / 2, x + w_along / 2, y - w_across / 2, y + w_across / 2, P.BACK_T, top)
        c -= box(x - w_along, x + w_along, y - r, y + r, P.BACK_T - 0.1, zc + r)
        c -= bd.Pos(x, y, zc + r) * bd.Rot(0, 90, 0) * bd.extrude(bd.RegularPolygon(r, 4, rotation=45), w_along + 2, both=True)
    else:
        c = box(x - w_across / 2, x + w_across / 2, y - w_along / 2, y + w_along / 2, P.BACK_T, top)
        c -= box(x - r, x + r, y - w_along, y + w_along, P.BACK_T - 0.1, zc + r)
        c -= bd.Pos(x, y, zc + r) * bd.Rot(90, 0, 0) * bd.extrude(bd.RegularPolygon(r, 4, rotation=45), w_along + 2, both=True)
    return c


def cable_stand_in() -> bd.Part:
    """The 5 V lead (reference): up out of the wall box, out the saddle notch, along the plate, to the plug."""
    zc = cable_z()
    segs = cable_path_xy()
    (sx, sy), _ = segs[0]
    if P.GPO_MECH == "plug":
        # out of the plug pack's +X side, over the saddle ring, down to the plate beyond the flange
        (xe, ye), _ = segs[1]
        zp = P.GPO_PROUD + P.PLUG_ALLOW / 2
        zp = max(zp, P.GPO_PROUD + P.CABLE_OD / 2 + 0.5)  # clears the socket body under it
        lead = _seg_solid((P.GPO_X + 18.0 + P.CABLE_OD / 2, ye), (xe, ye), P.CABLE_OD, zp)
        lead += cyl(P.CABLE_OD, zp - zc, xe, ye, zc)  # drop to the plate, beyond the saddle flange
        segs = segs[1:]
    else:
        lead = cyl(P.CABLE_OD, zc + 15, sx, sy, -15)  # up out of the wall box through the empty grid aperture
    for a_, b_ in segs:
        lead += _seg_solid(a_, b_, P.CABLE_OD, zc)
    ux, uy = _uc_point()
    plug_z = P.BACK_T + P.STANDOFF_H - 1.6  # USB-C socket centre, under the board
    plug = box(
        ux - P.UC_PLUG_W / 2, ux + P.UC_PLUG_W / 2, P.BOARD_Y + P.BOARD_H / 2, uy, plug_z - P.UC_PLUG_H / 2, plug_z + P.UC_PLUG_H / 2
    )
    out = lead + plug
    out.label = "ref_5v_lead"
    return out


# ---------------------------------------------------------------- reference parts (not printed)


def panel_stand_in() -> bd.Part:
    p = box(-P.PANEL_W / 2, P.PANEL_W / 2, P.PANEL_Y - P.PANEL_H / 2, P.PANEL_Y + P.PANEL_H / 2, P.PANEL_BACK, P.PANEL_BACK + P.PANEL_T)
    p.label = "ref_panel"
    return p


def gpo_stand_in() -> bd.Part:
    """Clipsal grid without its faceplate: a thin flange with screw ears at each end (low), and the
    socket/switch body in the middle standing GPO_PROUD off the wall."""
    g = rbox(P.GPO_GRID_W, P.GPO_GRID_L, P.GPO_EAR_Z, 3.0, P.GPO_X, P.GPO_Y)
    body_l = P.GPO_SCREW_C - P.SADDLE_BAR_W - 2.0
    if P.GPO_MECH == "removed":  # empty grid: aperture open for the 5 V lead
        g -= rbox(P.GPO_APERTURE_W, body_l - 6.0, P.GPO_EAR_Z + 1, 3.0, P.GPO_X, P.GPO_Y, -0.5)
    else:
        g += rbox(P.GPO_GRID_W - 4.0, body_l, P.GPO_PROUD, 3.0, P.GPO_X, P.GPO_Y)
    for dy in (-P.GPO_SCREW_C / 2, P.GPO_SCREW_C / 2):
        g -= cyl(P.GPO_SCREW_D, P.GPO_EAR_Z + 0.2, P.GPO_X, P.GPO_Y + dy, -0.1)
    if P.PLUG_ALLOW > 0:  # a plug pack in the lower socket
        g += box(P.GPO_X - 18, P.GPO_X + 18, P.GPO_Y - 34, P.GPO_Y - 4, P.GPO_PROUD, P.GPO_PROUD + P.PLUG_ALLOW)
    g.label = "ref_gpo_and_plug"
    return g


def board_stand_in() -> bd.Part:
    z = P.BACK_T + P.STANDOFF_H
    b = box(P.BOARD_X - P.BOARD_W / 2, P.BOARD_X + P.BOARD_W / 2, P.BOARD_Y - P.BOARD_H / 2, P.BOARD_Y + P.BOARD_H / 2, z, z + P.BOARD_T)
    b += box(P.BOARD_X - 25, P.BOARD_X + 25, P.BOARD_Y - 25, P.BOARD_Y + 25, z + P.BOARD_T, z + P.BOARD_T + P.BOARD_TOP_H)  # shield can
    y_edge = P.BOARD_Y + P.BOARD_H / 2
    # USB-A / USB-C / SD on the wall side, between the top mounting holes
    cx = P.BOARD_HOLE_DX / 2 - P.STANDOFF_D / 2 - 1.5
    b += box(P.BOARD_X - cx, P.BOARD_X + 20, y_edge - 14, y_edge - 2, z - P.BOARD_UNDER_H, z)
    b.label = "ref_board"
    return b


# ---------------------------------------------------------------- board leads


def speaker_xy() -> list[tuple[float, float]]:
    """Two speaker pods on the plate's lower edge, firing down at the bottom vents."""
    y = P.BOARD_Y - P.BOARD_H / 2 - P.SPEAKER_D / 2 - 3.0  # just under the board, clear of it
    x0 = P.BOARD_X - P.BOARD_W / 2 + P.SPEAKER_D / 2
    return [(x0, y), (x0 + P.SPEAKER_D + 10.0, y)]


def speaker_pod(x: float, y: float) -> bd.Part:
    """Ring that holds a 40 mm speaker on the plate face (press fit + a dab of hot glue)."""
    r = P.SPEAKER_D / 2
    pod = cyl(P.SPEAKER_D + 4.0, P.SPEAKER_H, x, y, P.BACK_T)
    pod -= cyl(P.SPEAKER_D + 0.4, P.SPEAKER_H + 1, x, y, P.BACK_T + 1.0)  # 1 mm floor
    pod -= box(x - 6, x + 6, y + r - 1, y + r + 4, P.BACK_T + 1.0, P.BACK_T + P.SPEAKER_H + 1)  # lead notch
    return pod


def speaker_stand_in() -> bd.Part:
    pods = [cyl(P.SPEAKER_D, P.SPEAKER_H - 1.0, x, y, P.BACK_T + 1.0) for x, y in speaker_xy()]
    s = pods[0]
    for c in pods[1:]:
        s += c
    s.label = "ref_speakers"
    return s


def edp_ribbon() -> bd.Part:
    """Flat eDP ribbon from the board's right edge across to the panel's connector region.

    Modelled as a 1 mm strip lying on top of the board's shield can, then along the panel's back:
    the gap behind the panel must stay clear for it (the interference check enforces that)."""
    z = P.PANEL_BACK - 1.2
    x0 = P.BOARD_X + P.BOARD_W / 2 - 6.0
    x1 = P.POCKET_W / 2 - P.BAR_D - 2.0  # stops short of the side clamp bar
    r = box(x0, x1, P.BOARD_Y - P.EDP_W / 2, P.BOARD_Y + P.EDP_W / 2, z, z + 1.0)
    r.label = "ref_edp_ribbon"
    return r


def antenna_stand_in() -> bd.Part:
    """Adhesive WiFi antenna on the inside of the right wall, above the side clamp bar, away from
    the GPO's metal box and the panel's metal back."""
    length, width = P.ANTENNA
    x = P.POCKET_W / 2
    y0 = P.BAR_L / 2 + 6.0
    a = box(x - 1.0, x, y0, y0 + length, P.BACK_T + 1.0, P.BACK_T + 1.0 + width)
    a.label = "ref_wifi_antenna"
    return a


def pir_stand_in() -> bd.Part:
    """AM312-style PIR: 10 mm dome in the bottom-wall hole, its little board standing behind it."""
    y_wall = -P.POCKET_H / 2
    dome = cyl(P.PIR_D - 0.4, P.WALL + P.END_EXTRA, P.PIR_X, y_wall - (P.WALL + P.END_EXTRA) + 0.3, P.PIR_Z, "Y")
    body = box(P.PIR_X - 6.0, P.PIR_X + 6.0, y_wall, y_wall + 10.0, P.PIR_Z - 4.0, P.PIR_Z + 4.0)
    p = dome + body
    p.label = "ref_pir"
    return p


def usb_cradle() -> bd.Part:
    """U-shaped cradle on the plate around the USB-C plug body, open toward the board.

    The plug is held from the sides and behind, so pulling on the lead loads the plate, not the
    board's surface-mount socket. Height stops just under the plug's top, so the plug lifts out.
    """
    ux, uy = _uc_point()
    plug_z = P.BACK_T + P.STANDOFF_H - 1.6
    top = plug_z + P.UC_PLUG_H / 2 - 0.5
    w, wall = P.UC_PLUG_W + 2 * 0.4, 2.0
    y0 = P.BOARD_Y + P.BOARD_H / 2 + 3.0  # starts clear of the board edge
    c = box(ux - w / 2 - wall, ux + w / 2 + wall, y0, uy + wall, P.BACK_T, top)
    c -= box(ux - w / 2, ux + w / 2, y0 - 1, uy + 0.4, P.BACK_T - 0.1, top + 1)  # plug pocket
    c -= box(ux - P.CABLE_D / 2, ux + P.CABLE_D / 2, uy - 1, uy + wall + 1, cable_z() - P.CABLE_D / 2, top + 1)  # lead exit
    return c


def _plate_splice(grow: float = 0.0) -> bd.Part:
    """Flat splice let into the FRONT face of both plate halves across the cut. A recess open upward
    prints without supports; its Y span keeps clear of the board standoffs (y +-46) and the 5 V lead (y 22)."""
    x0, w, t = P.PLATE_SPLIT_X, P.PLATE_LAP, P.SPLICE_T
    y0, y1 = P.PLATE_Y - 38.0, P.PLATE_Y + 14.0
    return box(x0 - w - grow, x0 + w + grow, y0 - grow, y1 + grow, P.BACK_T - t - grow, P.BACK_T + 0.01)


def back_plate_halves() -> list[bd.Part]:
    """The back plate cut straight at PLATE_SPLIT_X; a glued splice in a wall-side recess joins it."""
    plate = back_plate() - _plate_splice(grow=P.SPLICE_CLEAR)
    big = 1000.0
    cut = box(-big, P.PLATE_SPLIT_X, -big, big, -1, 50)
    left, right = plate & cut, plate - cut
    left.label, right.label = "back_plate_left", "back_plate_right"
    return [left, right]


def plate_splice() -> bd.Part:
    sp = _plate_splice()
    sp.label = "plate_splice"
    return sp

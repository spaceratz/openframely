"""Fit-test coupons: small cut-outs of the real parts to print first (about 45 min, ~25 g).

1. frame corner: window bevel, lip, pocket corner + relief, reveal line. Lay a panel corner in it.
2. hook pair: one frame finger + the matching plate tongue. Checks the hang-and-drop fit.
3. bottom latch: frame bottom wall with its catch + the plate's latch tongue. Checks the click and the lift-off.
4. snap hook: a short clamp-bar stub with one hook + the matching wall piece. Checks the click and release.
The saddle is already small, so print that one whole.
"""

from __future__ import annotations

import _parts
import params as P
from cadgen import build123d as bd
from cadgen import srgb, step


def _cut(part: bd.Part, x0: float, x1: float, y0: float, y1: float) -> bd.Part:
    return part & _parts.box(x0, x1, y0, y1, -1, P.DEPTH + 1)


def _solid_x(x: float, step: float = 0.5) -> float:
    """Nearest X to x where a cut through the top/bottom wall misses every vent slot and wall hole
    by 2 mm, so a coupon never ends in a sliver (positions move with the panel preset)."""
    vents = [(v - P.VENT_W / 2 - 2, v + P.VENT_W / 2 + 2) for v in _parts.vent_xs()]
    holes = [(h - P.SNAP_A / 2 - P.SNAP_B - 2.5, h + P.SNAP_A / 2 + P.SNAP_B + 2.5) for h in _parts.wall_hole_xs()]
    bad = vents + holes
    for i in range(400):
        for cand in (x + i * step, x - i * step):
            if not any(a <= cand <= b for a, b in bad):
                return cand
    return x


@step(out="../STEP/coupons.step")
def coupons():
    fl = _parts.frame_half("left")
    plate = _parts.back_plate()
    x_c, y_c = -P.OUTER_W / 2, P.OUTER_H / 2  # top-left outer corner
    corner = _cut(fl, x_c - 1, _solid_x(x_c + 45), y_c - 45, y_c + 1)
    hx = P.LATCH_X[0]
    hx0, hx1 = _solid_x(hx - 14), _solid_x(hx + 14)
    hook_f = _cut(fl, hx0, hx1, P.OUTER_H / 2 - 24, P.OUTER_H / 2 + 1)
    # plate side of the hook: exactly the tongue tab (its own solid), so the cut leaves no sliver
    hook_t = _parts.hook_tongue(hx)
    # bottom latch: frame bottom wall with the catch, and the plate's bottom edge with the tongue
    lv = _parts.latch_levels()
    lx0, lx1 = _solid_x(hx - 14), _solid_x(hx + 16)
    scr_f = _cut(fl, lx0, lx1, -P.OUTER_H / 2 - 1, lv["y_head"] + 2)
    keep = _parts.box(hx - 14, hx + 16, lv["y_barb"] - 1, lv["y_edge"] + P.LATCH_SLOT_TOP + 8, -1, P.BACK_T + 0.01)
    scr_t = (plate & keep)
    if len(scr_t.solids()) > 1:  # keep the piece carrying the tongue
        scr_t = max(scr_t.solids(), key=lambda so: so.volume)
    # snap hook: one bottom clamp bar cut short around its first hook, and the wall it clicks into
    (sx, sy), wt, axis, sb = next(p for p in _parts.snap_points() if p[2] == "Y" and p[0][1] < 0)
    bar = next(b for b in _parts.clamp_bars() if b.label.startswith("clamp_bottom"))
    snap_b = bar & _parts.box(sx - 9, sx + 9, -P.OUTER_H, 0, -1, P.DEPTH + 1)
    snap_w = _cut(fl if sx < P.SPLIT_X else _parts.frame_half("right"), sx - 9, sx + 9, -P.OUTER_H / 2 - 1, -P.POCKET_H / 2 + 0.01)
    snap_w = snap_w & _parts.box(sx - 9, sx + 9, -P.OUTER_H, 0, P.BAR_Z0 - 4, P.BAR_Z1 + 4)
    out = []
    # frame pieces print face-down like the frame; plate pieces flat like the plate. Packed in rows
    # on one bed (max 200 mm wide) so the plate fits a 256 mm printer.
    x = y = row_h = 0.0
    for name, part, flip in [("coupon_corner", corner, True), ("coupon_hook_frame", hook_f, True),
                             ("coupon_hook_plate", hook_t, False), ("coupon_latch_frame", scr_f, True),
                             ("coupon_latch_plate", scr_t, False), ("coupon_snap_bar", snap_b, False),
                             ("coupon_snap_wall", snap_w, False)]:
        if flip:
            part = bd.Rot(180, 0, 0) * part
        bb = part.bounding_box()
        if x + bb.size.X > 200:
            x, y, row_h = 0.0, y + row_h + 6, 0.0
        p = bd.Pos(x - bb.min.X, y - bb.min.Y, -bb.min.Z) * part
        x += bb.size.X + 6
        row_h = max(row_h, bb.size.Y)
        p.label = name
        p.color = srgb("#F2F1EC")
        out.append(p)
    return bd.Compound(children=out, label="fit_test_coupons")


if __name__ == "__main__":
    coupons()

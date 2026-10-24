"""Write print-ready STLs from the saved STEP files, each part already in its print orientation.

- frame halves: face-down (front lip on the bed, walls up). Best per dfam orientations.
- back plate: flat, wall side on the bed.
- gpo saddle: cover-down.
- clamp bars, joiners, lip splices: laid out flat on one plate, largest face down.

Uses OCCT's mesher via build123d (in the cadgen environment) rather than cadgen's @stl
exporter: on these parts cadgen 0.7.21's tessellator left open seams at T-junctions
(vent slots, rib ends). Every mesh written here is checked watertight by checks/dfam.
"""

from __future__ import annotations

import pathlib
import sys

from cadgen import build123d as bd
from cadgen import read_step

ROOT = pathlib.Path(__file__).resolve().parent.parent
# saddle prints top-down in both variants (open/plug saddle: 3.8% support, measured)
FACE_DOWN = ("frame_left", "frame_right", "gpo_saddle")
FLAT = ("back_plate", "coupons")  # coupons are oriented per piece in src/coupons.py


def on_bed(shape: bd.Shape) -> bd.Shape:
    """Move a shape so it sits on Z=0, centred on X/Y."""
    bb = shape.bounding_box()
    return bd.Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


def lay_flat(solid: bd.Solid) -> bd.Solid:
    """Rotate a bar so its thinnest dimension is Z (largest face on the bed)."""
    bb = solid.bounding_box()
    dims = {"X": bb.size.X, "Y": bb.size.Y, "Z": bb.size.Z}
    thin = min(dims, key=lambda k: dims[k])
    if thin == "X":
        solid = bd.Rot(0, 90, 0) * solid
    elif thin == "Y":
        solid = bd.Rot(90, 0, 0) * solid
    return on_bed(solid)


def main() -> int:
    out = ROOT / "STL"
    out.mkdir(exist_ok=True)
    import json as _json

    try:
        _split = _json.loads((ROOT / "src" / "preset.json").read_text()).get("plate_split", False)
    except (OSError, ValueError):
        _split = False
    if _split:  # the halves replace the one-piece plate
        (out / "back_plate.stl").unlink(missing_ok=True)
    for name in FACE_DOWN + FLAT:
        if _split and name == "back_plate":
            continue
        shape = read_step(str(ROOT / "STEP" / f"{name}.step"))
        if name in FACE_DOWN:
            shape = bd.Rot(180, 0, 0) * shape
        bd.export_stl(on_bed(shape), str(out / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.15)
        print("wrote", f"STL/{name}.stl")

    import json

    sys.path.insert(0, str(ROOT / "src"))
    import params

    P_SPLIT_X = params.PLATE_SPLIT_X
    try:
        split = json.loads((ROOT / "src" / "preset.json").read_text()).get("plate_split", False)
    except (OSError, ValueError):
        split = False
    if split:
        for half in read_step(str(ROOT / "STEP" / "back_plate_split.step")).solids():
            bb = half.bounding_box()
            side = "back_plate_left" if bb.center().X < P_SPLIT_X else "back_plate_right"
            name = "plate_splice" if bb.size.Z < 2 and bb.size.X < 25 else side
            bd.export_stl(on_bed(half), str(out / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.15)
            print("wrote", f"STL/{name}.stl")
    else:
        for name in ("back_plate_left", "back_plate_right", "plate_splice"):
            (out / f"{name}.stl").unlink(missing_ok=True)

    bars = [lay_flat(s) for s in read_step(str(ROOT / "STEP" / "clamp_bars.step")).solids()]
    placed, x, y, row_h = [], 0.0, 0.0, 0.0
    for b in sorted(bars, key=lambda s: -s.bounding_box().size.X):
        bb = b.bounding_box()
        if x + bb.size.X > 200:
            x, y, row_h = 0.0, y + row_h + 6, 0.0
        placed.append(bd.Pos(x - bb.min.X, y - bb.min.Y, 0) * b)
        x += bb.size.X + 6
        row_h = max(row_h, bb.size.Y)
    bd.export_stl(on_bed(bd.Compound(children=placed)), str(out / "clamp_bars.stl"), tolerance=0.02, angular_tolerance=0.15)
    print("wrote STL/clamp_bars.stl (one plate,", len(placed), "pieces)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Shared dimensions for the wall enclosure (mm). Change here, rerun ./run.sh.

Frame: X = width (left/right), Y = height (up/down), Z = out from the wall (wall at Z=0).
Values marked ASSUMPTION are best guesses to check against your hardware (see BRIEF.md).
"""

import json
import pathlib

# --- presets: pick with OFLY_PRESET=<name> ./run.sh ---
# Panel numbers are outline W x H, visible window W x H, thickness. Add your own here.
PANELS = {
    # XCX-NV156FHM-N4Z Q5 (BOE NV156FHM-N4Z family, 15.6" FHD eDP), measured: glass 364 x 214 mm, 5 mm
    # thick, with a further 10 mm of cables and backlight driver below the glass (outline 364 x 224).
    # The glass has an 11 mm border all round where nothing displays and touch doesn't reach, so the
    # visible window is 342 x 192 and the hidden band is 21 mm at the bottom (10 + 11), 11 at the top.
    "framely-15.6": dict(PANEL_W=364.0, PANEL_H=224.0, WIN_W=342.0, WIN_H=192.0, PANEL_T=5.0, BOTTOM_BORDER=21.0),
    "generic-13.3": dict(PANEL_W=306.0, PANEL_H=186.0, WIN_W=294.0, WIN_H=165.0, PANEL_T=7.0),  # typical 13.3" eDP
    "generic-17.3": dict(PANEL_W=400.0, PANEL_H=232.0, WIN_W=382.0, WIN_H=215.0, PANEL_T=10.0),  # typical 17.3" eDP
}
GPOS = {
    # AU/NZ Clipsal 2000 series family (2025, 2032VH ...): 84 mm fixing centres (datasheets)
    "clipsal-2000": dict(GPO_SCREW_C=84.0, GPO_GRID_W=70.0, GPO_GRID_L=110.0),
    # UK/IE single-gang back box: 60.3 mm fixing centres
    "uk-single": dict(GPO_SCREW_C=60.3, GPO_GRID_W=72.0, GPO_GRID_L=78.0),
}
# Selection lives in src/preset.json (a file, so cadgen's build cache sees a change; an env var
# would not be tracked). ./run.sh writes it from OFLY_PRESET / OFLY_GPO when those are set.
_sel = json.loads((pathlib.Path(__file__).with_name("preset.json")).read_text())
PRESET = _sel["panel"]
GPO_PRESET = _sel["gpo"]
_panel, _gpo = PANELS[PRESET], GPOS[GPO_PRESET]

# --- panel ---
PANEL_W, PANEL_H = _panel["PANEL_W"], _panel["PANEL_H"]
PANEL_T = _panel["PANEL_T"]  # bare panel + backlight thickness
WIN_W, WIN_H = _panel["WIN_W"], _panel["WIN_H"]
BOTTOM_BORDER = _panel.get("BOTTOM_BORDER", (PANEL_H - WIN_H) / 2)  # hidden panel band below the visible area
TOP_BORDER = PANEL_H - WIN_H - BOTTOM_BORDER
TOP_GAP = 10.0  # empty space inside the case above the panel (it must not sit hard against the top)
PANEL_Y = -TOP_GAP / 2  # panel centre in frame coordinates (the frame is centred on its pocket)
WIN_OFFSET_X = float(_sel.get("win_dx", 0.0))  # ASSUMPTION: visible area centred left/right on the panel
# window centre in frame coordinates: panel centre + the bottom/top border split + any measured correction
WIN_OFFSET_Y = PANEL_Y + (BOTTOM_BORDER - TOP_BORDER) / 2 + float(_sel.get("win_dy", 0.0))

# --- frame shell ---
# panel-to-pocket clearance per side. Covers PETG/ASA print shrink across the 366 mm pocket
# (0.3-0.5%, i.e. up to 1.8 mm total) plus 0.3 mm of play, so an unscaled print still takes the panel.
SHRINK = 0.005  # worst-case PETG/ASA shrink
CLEAR = round((PANEL_W * SHRINK) / 2 + 0.3, 1)
WALL = 3.0  # side wall thickness
FACE_T = 3.0  # front lip thickness
WIN_CHAMFER = 1.6  # bevel on the window edge so the lip doesn't shadow the screen
SHADOW_GAP = 0.8  # recessed reveal between the bezel face and the side walls (0 = off)
SHADOW_DEPTH = 0.6
# frame colour (renders only; print in the filament you like). Pick with "colour" in preset.json.
FRAME_COLOURS = {"white": "#F2F1EC", "warm-grey": "#B9B2A7", "charcoal": "#2E3136", "oak": "#C9A274"}
FRAME_COLOUR = FRAME_COLOURS[_sel.get("colour", "white")]
SEAM_V = 0.6
# Split the back plate in two (lap joint, glued) for 210-220 mm beds (Prusa MK4 / Core One)
PLATE_SPLIT = bool(_sel.get("plate_split", False))
PLATE_LAP = 10.0  # splice overlap either side of the cut (PLATE_SPLIT_X is set from the layout below)
LOGO = _sel.get("logo", "openframely")  # debossed on the bottom edge ("" = off)
LOGO_SIZE, LOGO_DEPTH = 5.0, 0.4

# keyholes in the back plate, for walls without a GPO (8 g pan-head screws, 200 mm apart)
KEY_ENTRY_D, KEY_SLOT_W, KEY_SLOT_L = 9.0, 4.8, 12.0
SCREW_8G_HEAD_D, SCREW_8G_SHANK_D = 8.6, 4.2  # V-groove half-width at the frame split on the front face (0 = off)
CORNER_R = max(float(_sel.get("corner_r", 6.0)), 3.0 + 3.0)  # outside radius: >= pocket radius + wall, so the corner stays 3 mm thick
POCKET_R = 3.0  # inside corner radius of the panel pocket (independent of CORNER_R)
CORNER_RELIEF_D = 3.0  # relief holes in the pocket corners for the square panel corners
GRIP_DEPTH, GRIP_L, GRIP_FROM_BOTTOM = 2.0, 30.0, 25.0  # side-wall finger recesses for lifting the frame
BACK_CHAMFER = 1.0  # wall-side outer edge (top of the face-down print, no overhang)
FRONT_CHAMFER = 1.5  # outside front edge (45 degrees: prints cleanly face-down)

# --- Clipsal 2000 series, faceplate removed (datasheets 2025-WE twin GPO and 2032VH-WE plate) ---
# Both: plate 116 x 76 x 13 mm, fixing centres 84 mm, vertical or horizontal mount.
GPO_SCREW_C = _gpo["GPO_SCREW_C"]  # mounting screw centres, vertical orientation
GPO_GRID_W, GPO_GRID_L = _gpo["GPO_GRID_W"], _gpo["GPO_GRID_L"]  # ASSUMPTION: grid footprint, no cover plate
GPO_PROUD = 9.0  # ASSUMPTION: grid front face height off the wall
GPO_KEEP_OUT = GPO_SCREW_C - 14.0  # ASSUMPTION: socket + switch faces lie between the screw ears
GPO_SCREW_D = 4.0  # clearance for the M3.5 GPO screws
GPO_HEAD_D, GPO_HEAD_H = 7.2, 2.4  # M3.5 pan/countersunk head recess
GPO_EAR_Z = 3.0  # ASSUMPTION: grid screw ears sit ~3 mm off the wall (plaster + grid flange)
GPO_Y = float(_sel.get("gpo_y", 0.0))  # GPO height vs frame centre (+ = GPO above centre). GPO_X is derived.
GPO_GRID_T = 3.0  # grid flange alone (mechanism removed)
GPO_APERTURE_W = 54.0  # ASSUMPTION: opening in the grid once the mechanism is out (lead passes up through it)

# --- saddle: clamps the back plate under the GPO's own two screws ---
SADDLE_RING = 3.0  # ring wall around the grid
SADDLE_BAR_W = 11.0  # bars across the grid at the screw positions
SADDLE_BAR_T = 5.0  # bar thickness (needs GPO screws ~5 mm longer: 25 -> 30 mm, standard sizes)
SADDLE_FLANGE = 6.0  # flange overlap onto the back plate around the cut-out
SADDLE_FLANGE_T = 1.2  # flange edge thickness; its underside tapers at 45 degrees

# --- power ---
# GPO_MECH = "removed": the 240 V -> 5 V supply lives in the wall cavity (or just outside the wall
#   box), an electrician removes/terminates the socket mechanism, and only a thin 5 V lead comes
#   out through the empty grid aperture. The saddle closes over the grid and the lead leaves
#   through a side notch at plate level. (Default.)
# GPO_MECH = "plug": the socket mechanism stays and a slim plug pack sits in one socket; the
#   saddle leaves the socket faces open. Needs PLUG_ALLOW of depth.
GPO_MECH = _sel.get("mech", "removed")
PLUG_ALLOW = 18.0 if GPO_MECH == "plug" else 0.0
GPO_OPEN = GPO_MECH == "plug"
CABLE_OD = 5.0  # ASSUMPTION: 5 V lead outer diameter (USB-C cable ~4 mm, 2-core 0.75 flex ~5.6 mm)
CABLE_D = CABLE_OD + 1.0  # notch / clip channel width
# lead rises inside the empty grid aperture and exits the saddle between the bars
CABLE_Y = min(22.0, (GPO_SCREW_C - 11.0 - 2.0 - 6.0) / 2 - CABLE_OD / 2 - 1.0)
PLUG_Y = -19.0  # plug pack centre (lower socket) when GPO_MECH == "plug"
if GPO_MECH == "plug":
    CABLE_Y = PLUG_Y  # the lead leaves the plug pack's side and runs straight out
COVER_T = 1.6  # saddle cover over the grid when it's closed

# --- depth stack (from the wall outwards) ---
BACK_T = 4.0  # back plate thickness
PANEL_GAP = 2.5  # clearance between the GPO (and plug, if any) and the back of the panel
# (PANEL_BACK is computed below, once the board stack is known)
# --- back plate (one print, sits flat on the wall inside the frame) ---
# Layout follows the panel: board to the right of the GPO, plate spanning both, hooks/screws inset
# board centre: right of the saddle (with a 20 mm cable lane) but at least 18 mm in from the wall
# GPO sits at the frame centre when there's room; on small panels the frame shifts right on the
# wall (GPO_X < 0) so the board still fits beside the saddle with a 20 mm cable lane.
# DP159K-V3.0 board, measured: 84 mm along the connector edge (X here), 83 mm along the other edges
BOARD_W, BOARD_H, BOARD_T = 84.0, 83.0, 1.6
_bw = BOARD_W / 2
_saddle_half = GPO_GRID_W / 2 + 3.0 + 6.0 + 1.0  # grid + ring + flange
_board_max_x = (PANEL_W + 2 * CLEAR) / 2 - 18.0 - _bw  # board centre, 18 mm in from the wall
# default: the wall box is 30 mm LEFT of the calendar's centre (as seen from the front); "gpo_x" overrides
GPO_X = min(float(_sel.get("gpo_x", -30.0)), _board_max_x - _bw - 20.0 - _saddle_half)
BOARD_X = min(GPO_X + _saddle_half + 20.0 + _bw, _board_max_x)  # just right of the saddle, 20 mm cable lane
PLATE_X0, PLATE_X1 = GPO_X - _saddle_half - 14.0, BOARD_X + _bw + 14.0
# split-plate cut: centred in the board's own width, between its left and right standoff columns
# (clear of the ribs, the 5 V lead's turn and the saddle), so both halves stay one solid each
PLATE_SPLIT_X = BOARD_X
PLATE_W, PLATE_H = PLATE_X1 - PLATE_X0, min(196.0, PANEL_H - 28.0) + TOP_GAP  # the pocket grew by TOP_GAP too
PLATE_X, PLATE_Y = (PLATE_X0 + PLATE_X1) / 2, 0.0
LATCH_X = (PLATE_X0 + 22.0, PLATE_X1 - 19.0)  # hooks at the top, snap latches at the bottom

# --- bottom snap latch (no screws) ---
# A tongue on the plate's bottom edge flexes sideways (X, in the plate's plane, so it prints flat).
# Its barb sits just above a catch on the inside of the frame's bottom wall: the frame can't lift
# off its top hooks until a firm lift ramps the barb aside. Hanging the frame clicks it in.
LATCH_T = 2.4  # tongue thickness (X, the bending direction); full plate thickness in Z
LATCH_BARB = 1.2  # barb overhang (X); the catch head overlaps it by LATCH_BARB - 0.2
LATCH_SLOT = 1.6  # free space on the tongue's other side, so it can bend away
LATCH_SLOT_TOP = 9.0  # the slots run this far into the plate above its bottom edge (tongue length)
LATCH_HEAD_W, LATCH_HEAD_H = 5.0, 2.0  # catch head on the frame (X, Y)
LATCH_POST_W = 3.4  # post holding the head up off the frame's bottom wall
LATCH_GAP = 0.4  # catch head to barb, installed

# --- hang-and-drop top mount ---
# The plate's top tabs carry an upward tongue standing off the wall; the frame has a finger on the
# inside of its top wall. Fit: hold the frame HOOK_DROP high, push it flat to the wall and drop it:
# the fingers slide in behind the tongues and the bottom latches click. Remove: firm lift, pull off.
HOOK_DROP = 8.0
HOOK_W = 16.0
TONGUE_L, TONGUE_T, SLOT = 6.0, 2.5, 3.0  # tongue length (Y), thickness (Z), gap behind it (beyond BACK_T)
RISER = 5.0  # riser block under the tongue
HOOK_CLEAR = 0.4

# --- panel clamp bars (separate prints, pinned through the frame walls with printed push-pins) ---
BAR_T = 8.0  # thickness (Z)
BAR_D = min(9.0, (PANEL_W - WIN_W) / 2 - 1.0, BOTTOM_BORDER - 1.0)  # bottom/side bars: overlap the hidden border
BAR_D_TOP = TOP_GAP + 1.2 + min(6.0, TOP_BORDER - 1.0)  # top bars reach across the gap onto the top border
BAR_FOAM = 0.8  # gap for foam tape between bar and panel back


# short clamp bars on the top and bottom walls: at +/- W/3, nudged outward to clear the plate's
# hook/screw tabs (tab is HOOK_W + 6 wide) so bars, tabs and hook fingers never overlap
def _clear_of_tabs(x: float) -> float:
    gap = 30.0 / 2 + (16.0 + 6.0) / 2 + 4.0  # BAR_L/2 + hook tab/2 + margin
    for t in LATCH_X:
        if abs(x - t) < gap:
            x = t + gap if x >= t else t - gap
    return x


CLAMP_TOP_X = tuple(round(_clear_of_tabs(sx * PANEL_W / 3)) for sx in (-1, 1))
JOINER_X = 0.0  # long bars on the top/bottom walls that also join the frame halves
CLAMP_SIDE_Y = (0.0,)  # short clamp bars on the left and right walls
BAR_L, JOINER_L, JOINER_SNAP_DX = 30.0, 70.0, 20.0

# --- snap hooks (no screws): each clamp bar and joiner has two hooks on its wall face. A hook
# is a flat arm (full bar height, prints flat with the bar) that pushes out through a slot in the
# frame wall; its barb clicks over the slot edge into a shallow recess on the outside and sits
# flush. Relief slots run the arm back into the bar so it is long enough to flex. Release: press
# the barb in from outside with a small screwdriver.
SNAP_A = 1.2  # arm thickness (flex direction)
SNAP_B = 0.8  # barb overhang; the arm deflects SNAP_B - SNAP_C going through the slot
SNAP_C = 0.2  # clearance round the arm in the wall slot
SNAP_FLAT, SNAP_GAP = 0.4, 0.2  # barb flat land; barb to recess floor, installed
SNAP_RELIEF = 7.0  # relief slots run the arm this far back into the bar (longer arm, gentler flex)
SNAP_RELIEF_W = (1.0, 0.4)  # relief slot widths: barb-away side (it bends that way), barb side
SNAP_RELIEF_BACK = 1.2  # bar material left behind the relief slots
SNAP_DX = 8.0  # the two hooks on a 30 mm clamp bar sit at +/- this from its centre, barbs pointing out
SNAP_RECESS = SNAP_GAP + SNAP_FLAT + SNAP_B + 0.1  # outside recess depth: the barb sits flush

# --- board (DP159K-V3.0) ---
# From docs/board-photos: the shield-can side faced the panel in the original case, the connector
# side (USB-C, USB-A, SD, PWR) faced the back. Same here: connectors toward the wall, dropping into
# a window in the back plate, so the board can sit low.
# Leads from the board (docs/board-photos/board-front.jpg):
#   eDP ribbon ~40 mm wide flat flex from the board's right edge to the panel's connector
#   touch flex ~20 mm wide from the board's top edge
#   2 speakers (YASS 8 ohm 2 W, ~40 mm dia) on red/black leads
#   WiFi u.FL pigtail (black), antenna needs to sit away from the GPO's metal box
EDP_W, EDP_EDGE = 40.0, "right"  # ribbon width, which panel edge it reaches
# Service: the panel rides in the frame, the board on the plate, so the eDP ribbon and touch flex
# join them. Lifting the frame off needs ~100 mm of slack to reach the board's ZIF latches; then
# unplug them and the frame comes away. The stock ribbon (docs/board-photos) is a ~200 mm loop.
EDP_SLACK = 100.0  # ASSUMPTION: the stock ribbon leaves at least this much slack once installed
SPEAKER_D, SPEAKER_H = 40.0, 6.0  # ASSUMPTION: speaker basket diameter and depth
# keep the two speakers (pods on the back plate under the board, sound out through the bottom vents)
# when there's room below the board; small panels drop them (the calendar works fine silent)
SPEAKERS = (PANEL_H - 28.0) / 2 - BOARD_H / 2 >= SPEAKER_D + 6.0
# PIR motion sensor: off (the DP159K build has none). Set True to add an AM312-style
# module (10 mm dome) looking out through a hole in the bottom wall, if a board has a PIR header.
PIR = False
PIR_D = 10.4  # lens hole for an AM312 10 mm dome, only used when PIR = True
PIR_X = 42.0  # bottom wall, between the seam joiner (ends x 35) and the plate rib (x ~49)
# Supported GPO height: the saddle must stay clear of the frame's bottom/top wall parts (joiners,
# PIR) through the service lift. checks/check_fit.py enforces it; -25..+35 mm passes for the 15.6" with the box 30 mm left.
ANTENNA = (36.0, 8.0)  # WiFi pigtail antenna pad: length x width, stuck to the top-right inside wall
BOARD_Y = 0.0  # (BOARD_X is derived from the panel width above)
# mounting holes (measured): 77.5 mm apart along the connector edge and the edge opposite it,
# 70 mm apart along the two edges without connectors. The connector edge is the top (+Y) here,
# so 77.5 runs along X and 70 along Y. Holes are centred on the board.
BOARD_HOLE_DX, BOARD_HOLE_DY = 77.5, 70.0
STANDOFF_H, STANDOFF_D, STANDOFF_HOLE = 2.0, 7.0, 2.5  # low: the connector side drops into the plate window
# the board is 10 mm thick overall, parts on both sides included (measured)
BOARD_STACK = 10.0
# ~7 mm connector side (USB/SD/USB-C, PCB included), ~3 mm chip side
BOARD_UNDER_H = 7.0 - 1.6  # connector side below the PCB, into the plate window
BOARD_TOP_H = BOARD_STACK - BOARD_UNDER_H - 1.6  # 3.0 mm: chips + FFC connectors on the panel side
# The USB-C power socket is on the board's top edge (wall side); the plug goes in from above (+Y)
# USB-C, measured: its centre is 19 mm in from the board's left edge (15 mm from the nearest
# mounting hole, which sits 3.25 mm in: (84 - 77.5) / 2)
UC_DX = -BOARD_W / 2 + 19.0
UC_PLUG_L, UC_PLUG_W, UC_PLUG_H = 22.0, 12.0, 6.5  # ASSUMPTION: USB-C plug + strain relief
# plate window under the connector edge + plug: w, h, dx, dy. Runs between the two top standoffs
# (1 mm of plate round each), so the connectors drop through and the standoffs keep solid ground.
# Y: from 18 mm inside the board's top (connector) edge to 2 mm past it. The connectors hang below the
# PCB inside the board outline; the USB-C plug and its cradle sit on solid plate beyond the edge.
_win_y0, _win_y1 = BOARD_H / 2 - 18.0, BOARD_H / 2 + 2.0
BOARD_WINDOW = (BOARD_HOLE_DX - STANDOFF_D - 2.2, _win_y1 - _win_y0, 0.0, (_win_y0 + _win_y1) / 2)

# --- ventilation (top exhaust, bottom intake) ---
VENT_W, VENT_L, VENT_COUNT = 4.0, 10.0, 13  # slots fit the cavity height
VENT_PITCH = 7.0 if PANEL_W >= 340 else 5.5  # denser on small panels to keep >= 15 cm2 open
VENT_KEEP = 8.0  # no vent slot within this of a wall pin hole centre

# --- printing ---
BED = 256.0  # largest single print (Bambu P1/X1/A1, Prusa MK4 is 250)
SPLIT_X = 0.0  # frame halves join at the centre line
SPLICE_L, SPLICE_T, SPLICE_CLEAR = 60.0, 1.2, 0.15  # lip splice plates across the split (glued)

GPO_FACE_Z = GPO_PROUD if GPO_MECH != "removed" else GPO_GRID_T  # top of what's left on the wall box
BOARD_TOP = BACK_T + STANDOFF_H + BOARD_T + BOARD_TOP_H
_saddle_top = max(GPO_EAR_Z + 5.0, BACK_T + CABLE_OD + 1.0 + 0.5) + 1.6  # mirrors _parts.saddle_levels()
PANEL_BACK = max(
    _saddle_top + 1.5,  # the saddle cover over the GPO
    GPO_FACE_Z + PLUG_ALLOW + PANEL_GAP,  # Z of the panel's back face: whichever is taller,
    BOARD_TOP + 2.0,  # the GPO (+plug) or the board
    BACK_T + 6.0 + 2.0,
)  # or the plate's stiffening ribs
DEPTH = PANEL_BACK + PANEL_T + FACE_T  # overall depth off the wall
PIR_Z = BACK_T + 4.0  # lens centre: low, so the module (10 mm tall) stays under the panel and above the plate

POCKET_W = PANEL_W + 2 * CLEAR
POCKET_H = PANEL_H + 2 * CLEAR + TOP_GAP
# Bezel = visible frame width around the window, seen from the front.
#   "tight": smallest outline; the bezel follows the panel's own border (wider top/bottom).
#   "even":  side walls thickened (outside only) so all four bezels match. Calmer on a wall.
BEZEL_STYLE = _sel.get("bezel", "even")
_bezel_tb = (POCKET_H - WIN_H) / 2 + WALL - abs(WIN_OFFSET_Y)
_bezel_lr = (POCKET_W - WIN_W) / 2 + WALL - abs(WIN_OFFSET_X)
SIDE_EXTRA = max(0.0, _bezel_tb - _bezel_lr) if BEZEL_STYLE == "even" else 0.0  # thicker left/right walls
END_EXTRA = max(0.0, _bezel_lr - _bezel_tb) if BEZEL_STYLE == "even" else 0.0  # thicker top/bottom walls
OUTER_W = POCKET_W + 2 * (WALL + SIDE_EXTRA)
OUTER_H = POCKET_H + 2 * (WALL + END_EXTRA)
BEZEL_LR, BEZEL_TB = _bezel_lr + SIDE_EXTRA, _bezel_tb + END_EXTRA
BAR_Z0 = PANEL_BACK - BAR_FOAM - BAR_T  # clamp bar Z range
BAR_Z1 = PANEL_BACK - BAR_FOAM
BAR_ZC = (BAR_Z0 + BAR_Z1) / 2

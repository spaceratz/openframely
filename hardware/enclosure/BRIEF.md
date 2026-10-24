# Design notes

What the enclosure is designed around, where each number comes from, and which values are
best guesses. Every guess is a constant in `src/params.py` marked `ASSUMPTION`; measure your
hardware, change it and run `./run.sh`.

## Requirements

| # | Requirement | Value |
|---|---|---|
| R1 | Hold the panel | glass **364 x 214 x 5 mm**, plus **10 mm** of cables and backlight driver below the glass: outline **364 x 224 mm**. XCX-NV156FHM-N4Z Q5 (BOE NV156FHM-N4Z family) |
| R2 | Front lip covers the dead border | the glass has an **11 mm** border all round with no image and no touch, so the visible window is **342 x 192 mm**; the lip hides 21 mm at the bottom (10 + 11), 11 mm at the top and sides |
| R3 | Room above the panel | **10 mm** empty gap inside the case above the panel, so it never sits hard against the top wall |
| R4 | Mount over a power point | standard Clipsal wall box, faceplate removed, held by its **two screws only** |
| R5 | Wall box off-centre | box **30 mm left** of the calendar's centre (default `gpo_x`); its height doesn't matter |
| R6 | Slim | at most **20 mm** inside, wall to the back of the front lip (supply-in-wall build) |
| R7 | Serviceable | the frame comes off without disturbing the wall parts |
| R8 | Screw-free enclosure | only the wall fixing and the board's own mounting holes use screws; everything else clips |

## Known dimensions

| Item | Value | Source |
|---|---|---|
| Clipsal 2000 Series twin GPO (2025-WE) plate | 116 L x 76 W x 13 D mm | Schneider product datasheet 2025-WE |
| GPO mounting screw centres | **84 mm** | same datasheet ("Mounting Centers 84 mm"); 2032VH plate matches |
| GPO mounting screws | M3.5 (AS/NZS standard flush-box screw), ~25 mm | Australian wiring convention |
| Board | DP159K-V3.0, **84 x 83 mm** (84 along the connector edge), USB-C power, ~10 mm thick (7 mm connector side, 3 mm chip side), mounting holes **77.5 x 70 mm** (77.5 along the connector edge), USB-C centre **19 mm** in from the nearest side edge | measured; photos in `docs/board-photos/` |

## Cross-checks

- **Visible window 342 x 192 mm** (measured: glass minus the 11 mm dead border). The datasheet active
  area for a 15.6" 1920x1080 panel is 344.16 x 193.59 mm, so the lip covers about 1 mm of the
  outermost pixels on each side. The wall app keeps 32 px (about 6 mm) clear of every edge, so
  nothing on screen is hidden or untappable.
- The board's device tree only describes the MIPI side of its LT8911 MIPI-to-eDP bridge (a
  placeholder `sitronix,st7703` 68 x 121 mm), so it can't identify the real panel.
- The Clipsal **2032VH** plate and the **2025-WE** GPO both list 116 x 76 x 13 mm with **84 mm
  fixing centres**, so the saddle fits either.

## Assumptions

1. **Window position** (`WIN_OFFSET_X`, `WIN_OFFSET_Y`): placed from the 21 / 11 mm border split
   and centred left/right. Fine-tune with `win_dx` / `win_dy` in `src/preset.json`.
2. **Power:** the 240 V to 5 V supply lives in the wall cavity. An electrician removes the socket
   mechanism (`mech: "removed"`), leaving the grid on the box, and routes a 5 V lead (`CABLE_OD`
   5 mm) up through the empty aperture. `mech: "plug"` keeps a socket with a slim plug pack
   (about 16 mm deeper).
3. **The two screws:** the grid's screw ears sit ~3 mm off the wall (`GPO_EAR_Z`) and the empty
   aperture is ~54 mm wide (`GPO_APERTURE_W`). The saddle's bars rest on the ears, so the screws
   need to be ~5 mm longer (M3.5 x 30 instead of 25).
4. **Board mounting:** holes measured at **77.5 mm** apart along the connector edge (and the edge
   opposite) and **70 mm** along the other two (`BOARD_HOLE_DX`, `BOARD_HOLE_DY`), on an 84 x 83 mm
   board. Connector side to the wall; USB-C on the top edge, 19 mm in from the left. All measured.
5. **Material:** PETG or ASA (warm backlight). The frame prints as two halves; every part fits a
   256 mm bed, `plate_split` covers 250 x 210 beds.
6. **Heat:** board plus backlight make roughly 8 W, so about 15 cm² of vents top and bottom.
7. **Wall:** flat plaster, box flush. If the plate rocks on the box, a 1 mm shim ring is easy to add.
8. **eDP ribbon slack** (`EDP_SLACK` 100 mm): enough to reach the board's latches with the frame
   lifted away. Measure yours.
9. **Panel weight** ~0.6 kg and **stiffness** of a 2.2 mm glass laminate, for the strength and
   touch-flex checks. Both have more than 3x margin.
10. **Material properties** for the checks: PETG, E ~2 GPa, yield ~45 MPa (ASA is similar).
11. **No motion sensor** (`PIR = False`). Set it True to add a lens hole for an AM312-style
    module in the bottom wall, if your board has a PIR header.

## Every ASSUMPTION constant in `src/params.py`

| Constant(s) | What it is | Assumed |
|---|---|---|
| `WIN_OFFSET_X`, `WIN_OFFSET_Y` | window position on the panel | from the 21 / 11 mm border split, centred left/right (assumption 1) |
| `GPO_GRID_W`, `GPO_GRID_L`, `GPO_PROUD`, `GPO_EAR_Z`, `GPO_APERTURE_W`, `GPO_KEEP_OUT` | Clipsal grid without its faceplate | 70 x 110 mm, socket face 9 mm off the wall, ears 3 mm, empty aperture 54 mm (assumption 3) |
| `CABLE_OD` | 5 V lead | 5 mm (assumption 2) |
| `UC_PLUG_L`, `UC_PLUG_W`, `UC_PLUG_H` | USB-C plug body with strain relief | 22 x 12 x 6.5 mm |
| `SPEAKER_D`, `SPEAKER_H` | stock speakers | 40 mm diameter, 6 mm deep |
| `EDP_SLACK` | spare eDP ribbon | 100 mm (assumption 8) |

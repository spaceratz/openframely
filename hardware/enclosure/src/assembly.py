"""Whole enclosure in its installed position, with reference panel, GPO + plug pack and board."""

from __future__ import annotations

import params as P
from _parts import (
    antenna_stand_in,
    board_stand_in,
    cable_stand_in,
    edp_ribbon,
    gpo_stand_in,
    panel_stand_in,
    pir_stand_in,
    speaker_stand_in,
)
from back_plate import back_plate
from cadgen import build123d as bd
from cadgen import srgb, step
from clamp_bars import clamp_bars
from frame_left import frame_left
from frame_right import frame_right
from gpo_saddle import gpo_saddle

REF = {"ref_panel": "#1A1D22", "ref_gpo_and_plug": "#B0463C", "ref_board": "#2D6A4F", "ref_5v_lead": "#1F5FA8",
       "ref_edp_ribbon": "#C9CCD1", "ref_speakers": "#3A3A3A", "ref_wifi_antenna": "#111111", "ref_pir": "#F4F1E8"}


@step(out="../STEP/assembly.step")
def assembly():
    refs = [panel_stand_in(), gpo_stand_in(), board_stand_in(), cable_stand_in(), edp_ribbon(), antenna_stand_in()]
    if P.SPEAKERS:
        refs.append(speaker_stand_in())
    if P.PIR:
        refs.append(pir_stand_in())
    for r in refs:
        r.color = srgb(REF[r.label])
    printed = [frame_left(), frame_right(), back_plate(), gpo_saddle(), clamp_bars()]
    return bd.Compound(children=printed + refs, label="openframely_enclosure")


if __name__ == "__main__":
    assembly()

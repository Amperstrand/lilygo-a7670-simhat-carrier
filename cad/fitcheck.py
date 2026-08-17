"""Gridfinity-compatible quick-print fit-check tray.

A 3x4-unit Gridfinity tray (125.5 x 167.5 mm) containing the EXACT carrier
XY layout at low height: A7670 bosses with real M1.6 pilots at true hole
coordinates, SimHat support pads + fences at true positions, and the
110x20 antenna channel at true size. Purpose: ~15-minute dimensional
verification of the full-carrier layout; afterwards it doubles as a
shallow Gridfinity desk tray holding the antenna + small parts.

Gridfinity male-base geometry per the canonical spec implementation
(kennetek/gridfinity-rebuilt-openscad, src/core/standard.scad):
  - grid unit 42 mm, base top 41.5/unit (0.5 gap)
  - dovetail profile: bottom inset 2.95 (r0.8) -> 45 deg -> inset 2.15 at
    z=0.8 -> vertical to z=2.6 -> 45 deg -> inset 0 (r3.75) at z=4.75
Drops onto any standard Gridfinity baseplate; also stands alone on a desk.
Boards sit proud of the low walls (by design - the bosses, pads and fences
are the fit gauges, not the walls).
"""

from __future__ import annotations

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

from cad import holder
from cad import parameters as P
from cad.parameters import Measured as M

GRID_UNIT = 42.0
GRID_CLEAR = 0.5
BASE_INSET_BOTTOM = 2.95
BASE_INSET_MID = 2.15
BASE_Z_MID = 0.8
BASE_Z_SHOULDER = 2.6
BASE_Z_TOP = 4.75
BASE_R_TOP = 3.75
BASE_R_BOTTOM = 0.8

UNITS_X, UNITS_Y = 3, 4
FOOTPRINT_X = GRID_UNIT * UNITS_X - GRID_CLEAR
FOOTPRINT_Y = GRID_UNIT * UNITS_Y - GRID_CLEAR

WEB_T = 0.6
WEB_OVERLAP = 0.3                 # webs sink into the base ring so fuses
                                  # share volume, not just coplanar faces
WEB_Z0 = BASE_Z_TOP - WEB_OVERLAP
WEB_Z1 = WEB_Z0 + WEB_T
WALL_T = 1.2
WALL_TOP_Z = 7.0
PIN_D = 1.25         # gauge pins: STEP drills the corner holes ~Ø1.35 (the
                     # Ø1.73 DXF figure is the plated spec); pins gauge hole
                     # POSITION, diameter stays a caliper check
PIN_H = 28.0         # clears the 18650 holder (20.5 below board) + board
FENCE_TOP_Z = 24.6   # engages the flipped SimHat edge (relay-down rest)
SHIFT_Y = -14.0      # boards moved toward -Y so the antenna channel fits
                     # the +Y end without crossing the gauge pins


def _rounded_rect_wire(w: float, h: float, r: float, z: float) -> cq.Wire:
    slab = (cq.Workplane("XY", origin=(0, 0, z - 0.05))
            .rect(w, h).extrude(0.1).edges("|Z").fillet(r).val())
    face = min(slab.Faces(), key=lambda f: f.Center().z)
    return face.outerWire()


def _base_ring() -> cq.Shape:
    lo = _rounded_rect_wire(FOOTPRINT_X - 2 * BASE_INSET_BOTTOM,
                            FOOTPRINT_Y - 2 * BASE_INSET_BOTTOM,
                            BASE_R_BOTTOM, 0.0)
    mid_r = BASE_R_BOTTOM + BASE_Z_MID
    mid = _rounded_rect_wire(FOOTPRINT_X - 2 * BASE_INSET_MID,
                             FOOTPRINT_Y - 2 * BASE_INSET_MID,
                             mid_r, BASE_Z_MID)
    shoulder = _rounded_rect_wire(FOOTPRINT_X - 2 * BASE_INSET_MID,
                                  FOOTPRINT_Y - 2 * BASE_INSET_MID,
                                  mid_r, BASE_Z_SHOULDER)
    top = _rounded_rect_wire(FOOTPRINT_X, FOOTPRINT_Y, BASE_R_TOP, BASE_Z_TOP)
    builder = BRepOffsetAPI_ThruSections(True, True, 1e-5)
    for w in (lo, mid, shoulder, top):
        builder.AddWire(w.wrapped)
    builder.Build()
    frustum = cq.Shape.cast(builder.Shape())
    inset = BASE_INSET_BOTTOM + 0.02
    core = (cq.Workplane("XY")
            .rect(FOOTPRINT_X - 2 * inset, FOOTPRINT_Y - 2 * inset)
            .extrude(BASE_Z_TOP + 1).translate((0, 0, -0.5)).val())
    return cq.Shape.cast(BRepAlgoAPI_Cut(frustum.wrapped, core.wrapped).Shape())


def _web(cx, cy, w, h) -> cq.Shape:
    return (cq.Workplane("XY").center(cx, cy).rect(w, h)
            .extrude(WEB_T).translate((0, 0, WEB_Z0)).val())


def _a7670_features() -> list[cq.Shape]:
    cx = P.a7670_cx()
    solids = [_web(cx, SHIFT_Y, 22.0, M.a7670_pcb_l + 6.0)]
    for (hx, hy) in holder.a7670_holes_carrier():
        solids.append(_web(hx, hy + SHIFT_Y, 10.0, 10.0))
        solids.append(cq.Workplane("XY").moveTo(hx, hy + SHIFT_Y)
                      .circle(PIN_D / 2)
                      .extrude(PIN_H).translate((0, 0, WEB_Z1)).val())
    return solids


def _simhat_features() -> list[cq.Shape]:
    solids = [_web(P.simhat_cx(), SHIFT_Y,
                   M.simhat_pcb_w + 2 * 0.75,
                   M.simhat_pcb_l + 5.0)]
    half = M.simhat_pcb_w / 2 + P.SIMHAT_PCB_XY_CLEAR
    for (side, v) in P.SIMHAT_FENCES:
        u = side * (half + P.SIMHAT_FENCE_T / 2)
        solids.append(cq.Workplane("XY")
                      .center(holder.sh_x(u), holder.sh_y(v) + SHIFT_Y)
                      .rect(P.SIMHAT_FENCE_T, 12.0)
                      .extrude(FENCE_TOP_Z - WEB_Z1)
                      .translate((0, 0, WEB_Z1)).val())
    return solids


def _antenna_features() -> list[cq.Shape]:
    """Under-battery channel gauge: flat spine floor + two guide rails at
    the true channel width + stop at the true +Y position, mirroring the
    carrier's ANT_POS=under_battery channel (scaled to the tray layout)."""
    cx = P.a7670_cx()
    boards_top_y = M.a7670_pcb_l / 2 + SHIFT_Y
    stop_face = boards_top_y - 2.0
    entry_y = -FOOTPRINT_Y / 2 + 5.0
    half = P.ANT_W / 2 + P.ANT_SIDE_CLEAR
    solids = [_web(cx, (entry_y + stop_face) / 2,
                   2 * half + 2 * P.ANT_GUIDE_T + 2.0,
                   stop_face - entry_y)]
    for side in (-1, 1):
        solids.append(cq.Workplane("XY")
                      .center(cx + side * (half + P.ANT_GUIDE_T / 2),
                              (entry_y + stop_face) / 2)
                      .rect(P.ANT_GUIDE_T, stop_face - entry_y)
                      .extrude(P.ANT_GUIDE_H)
                      .translate((0, 0, WEB_Z1)).val())
    solids.append(cq.Workplane("XY")
                  .center(cx, stop_face + P.ANT_GUIDE_T / 2)
                  .rect(2 * half + 2 * P.ANT_GUIDE_T + 2.0, P.ANT_GUIDE_T)
                  .extrude(P.ANT_GUIDE_H)
                  .translate((0, 0, WEB_Z1)).val())
    return solids


def _stitch_strips() -> list[cq.Shape]:
    reach = FOOTPRINT_X / 2 - 2.0
    return [_web(0.0, y + SHIFT_Y, 2 * reach, 8.0) for y in (-45.0, 44.0)]


def _perimeter_wall() -> cq.Shape:
    z0 = BASE_Z_TOP - WEB_OVERLAP
    outer = (cq.Workplane("XY").rect(FOOTPRINT_X, FOOTPRINT_Y)
             .extrude(WALL_TOP_Z - z0).translate((0, 0, z0))
             .edges("|Z").fillet(BASE_R_TOP).val())
    inner = (cq.Workplane("XY")
             .rect(FOOTPRINT_X - 2 * WALL_T, FOOTPRINT_Y - 2 * WALL_T)
             .extrude(WALL_TOP_Z - z0 + 2)
             .translate((0, 0, z0 - 1)).val())
    return cq.Shape.cast(BRepAlgoAPI_Cut(outer.wrapped, inner.wrapped).Shape())


def build_fitcheck_tray():
    parts = ([_base_ring(), _perimeter_wall(), *_stitch_strips()]
             + _a7670_features() + _simhat_features() + _antenna_features())
    tray = parts[0]
    for p in parts[1:]:
        tray = tray.fuse(p)
    return cq.Workplane("XY").newObject([tray])

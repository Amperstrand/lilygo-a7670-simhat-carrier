"""Throwaway calibration mini-coupon (~8-10 min print, ~10 g).

One small plate that calibrates every printer-dependent dimension the
design depends on, BEFORE any larger print:

  1. M1.6 pilot-hole gauge: through-holes Ø1.20-1.60 in 0.10 steps,
     left to right at the top. Smallest hole an M1.6 screw self-taps
     snugly -> set A7670_PILOT_D.
  2. PCB thickness stair: U-slits 1.0/1.2/1.4/1.6 mm high along the
     left wall (bottom to top). Slide the T-SimHat edge in; the first
     free fit = PCB thickness.
  3. Antenna width slits: U-slits 19.8/20.2/20.6 mm wide along the
     right wall (bottom to top). Slide the sticker; pick the feel.
  4. Snap clip pair: the EXACT production clip profile
     (holder._clip_arm_pts at SIMHAT_PCB_XY_CLEAR) over a board-end
     pocket -> verifies clip placement and feel with the real board.

The clip profile is imported from the production module, never
duplicated, so this coupon cannot drift from the carrier geometry.
"""

from __future__ import annotations

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

from cad import holder
from cad import parameters as P
from cad.parameters import Measured as M

PLATE_W = 92.0
PLATE_L = 64.0
PLATE_T = 1.6

HOLE_DIAMS = [1.20, 1.30, 1.40, 1.50, 1.60]
HOLE_PITCH = 7.5
HOLE_ROW_Y = 28.0
HOLE_ROW_X0 = 8.0
PLUG_HOLE_D = 1.70                # true A7670 PCB hole Ø (STEP cylinders)
# One full christmas-tree plug at the true Ø1.70-hole gauge size: the
# plug bay is the screwless-mount dress rehearsal (fins Ø1.55/1.65 over a
# Ø1.70 hole, exactly as on the carrier).

WALL_T = 2.4
SLIT_TRAVEL = 7.0
PCB_SLIT_WIDTH = 4.6
PCB_SLIT_HEIGHTS = [1.0, 1.2, 1.4, 1.6]
PCB_SLIT_FLOOR = 1.6
PCB_SLIT_PITCH = 9.5
PCB_Y0 = -PLATE_L / 2 + 3.0
PCB_X_IN = -PLATE_W / 2 + 3.0

ANT_SLIT_WIDTHS = [19.8, 20.2, 20.6]
ANT_SLIT_HEIGHT = 2.0
ANT_SLIT_FLOOR = 1.6
ANT_X_PITCH = 12.0
ANT_X0 = -40.0
ANT_Y_C = 18.0

BAY_CLEAR = P.SIMHAT_PCB_XY_CLEAR
BAY_OX = 20.0
BAY_OY = -12.0
BAY_SUPPORT_H = 19.0            # production flip: relay (18.25) clears plate
PAD_TOP = PLATE_T + BAY_SUPPORT_H
# Flipped board in bay coords: the Y-flip mirrors u, so relay occupies
# u 0..16.5 (v 6.5..29.2), terminal u -16..-5.5 (v 0..15.8); free strip
# u -5.5..0 up to v 37. Two 5mm pads in that strip, on-plate (v <= 19.5):
BAY_PADS_UV = [(-2.75, 4.0), (-2.75, 17.0)]
BAY_PAD_SIZE = 5.0


def _cut(solid, cutter):
    return cq.Shape.cast(BRepAlgoAPI_Cut(solid.wrapped, cutter.wrapped).Shape())


def _plate() -> cq.Shape:
    plate = (cq.Workplane("XY").rect(PLATE_W, PLATE_L)
             .extrude(PLATE_T).val())
    for i, d in enumerate(HOLE_DIAMS):
        hole = (cq.Workplane("XY")
                .moveTo(HOLE_ROW_X0 + i * HOLE_PITCH, HOLE_ROW_Y)
                .circle(d / 2).extrude(PLATE_T + 2)
                .translate((0, 0, -1)).val())
        plate = _cut(plate, hole)
    plug_x = 42.5
    return plate


def _plug_bay() -> list[cq.Shape]:
    """Screwless-mount dress rehearsal: Ø1.70 through-hole in the plate +
    the full christmas-tree plug rooted in a 6 mm boss below it. Press the
    board-side of a spare PCB hole over the plug; fins should click
    through and release on a firm pull."""
    from cad import holder as H
    plug_x = 42.5
    boss = (cq.Workplane("XY").moveTo(plug_x, HOLE_ROW_Y)
            .circle(3.0).extrude(6.0).val())
    plug = H._plug_solid(plug_x, HOLE_ROW_Y)
    plug = plug.translate(cq.Vector(0, 0, -H.P.A7670_STANDOFF_H + 6.0))
    return [boss.fuse(plug)]


def _pcb_thickness_wall() -> list[cq.Shape]:
    solids = []
    for i, t in enumerate(PCB_SLIT_HEIGHTS):
        y_c = PCB_Y0 + i * PCB_SLIT_PITCH
        z0 = PLATE_T + PCB_SLIT_FLOOR
        block = (cq.Workplane("XY")
                 .moveTo(PCB_X_IN + SLIT_TRAVEL / 2, y_c)
                 .rect(SLIT_TRAVEL + 2 * WALL_T, PCB_SLIT_WIDTH + 2 * WALL_T)
                 .extrude(z0 + t + 1.2).val())
        slit = (cq.Workplane("XY")
                .moveTo(PCB_X_IN + SLIT_TRAVEL / 2, y_c)
                .rect(SLIT_TRAVEL, PCB_SLIT_WIDTH)
                .extrude(t).translate((0, 0, z0)).val())
        opener = (cq.Workplane("XY")
                  .moveTo(PCB_X_IN - 1.0, y_c)
                  .rect(2.0, PCB_SLIT_WIDTH)
                  .extrude(t).translate((0, 0, z0)).val())
        solids.append(_cut(block, slit.fuse(opener)))
    return solids


def _antenna_wall() -> list[cq.Shape]:
    solids = []
    for i, wdt in enumerate(ANT_SLIT_WIDTHS):
        x_c = ANT_X0 + i * ANT_X_PITCH
        z0 = PLATE_T + ANT_SLIT_FLOOR
        block = (cq.Workplane("XY")
                 .moveTo(x_c, ANT_Y_C)
                 .rect(SLIT_TRAVEL + 2 * WALL_T, wdt + 2 * WALL_T)
                 .extrude(z0 + ANT_SLIT_HEIGHT + 1.2).val())
        slit = (cq.Workplane("XY")
                .moveTo(x_c, ANT_Y_C)
                .rect(SLIT_TRAVEL, wdt)
                .extrude(ANT_SLIT_HEIGHT).translate((0, 0, z0)).val())
        opener = (cq.Workplane("XY")
                  .moveTo(x_c, ANT_Y_C + wdt / 2 + 1.0)
                  .rect(SLIT_TRAVEL, 2.0)
                  .extrude(ANT_SLIT_HEIGHT).translate((0, 0, z0)).val())
        solids.append(_cut(block, slit.fuse(opener)))
    return solids


def _bay() -> list[cq.Shape]:
    """Production-orientation clip bay: board sits FLIPPED (relay down) at
    BAY_SUPPORT_H on two pads; bay y = BAY_OY - v so the production clip
    profile engages the real v=0 end with true u layout (rigid placement,
    no mirroring). No lip: the production lip lives at the far end over
    free laminate, which a clip-end bay cannot reproduce."""
    ox, oy = BAY_OX, BAY_OY
    z_top_clip = (PAD_TOP + M.simhat_pcb_t + P.SIMHAT_PCB_T_CLEAR
                  + P.SIMHAT_HOOK_T)
    z_bot_clip = z_top_clip - P.SIMHAT_ARM_W
    solids = []

    for (u_pad, v_pad) in BAY_PADS_UV:
        solids.append(cq.Workplane("XY")
                      .center(ox + u_pad, oy - v_pad)
                      .rect(BAY_PAD_SIZE, BAY_PAD_SIZE)
                      .extrude(BAY_SUPPORT_H)
                      .translate((0, 0, PLATE_T)).val())

    half = M.simhat_pcb_w / 2 + BAY_CLEAR
    v_root = BAY_CLEAR + P.SIMHAT_HOOK_REACH_V - P.SIMHAT_ARM_LEN
    v_hi = BAY_CLEAR + P.SIMHAT_HOOK_REACH_V - 0.5
    for side in (-1, 1):
        pts = [(u, -v) for u, v in holder._clip_arm_pts(BAY_CLEAR, side)]
        arm = (cq.Workplane("XY")
               .polyline([(ox + u, oy + v) for u, v in pts]).close()
               .extrude(z_top_clip - z_bot_clip)
               .translate((0, 0, z_bot_clip)).val())
        undercut = cq.Solid.makeBox(
            2 * half, 40,
            PAD_TOP + M.simhat_pcb_t + P.SIMHAT_PCB_T_CLEAR + 1,
            cq.Vector(ox - half, oy - 20, -1))
        arm = _cut(arm, undercut)
        u_out = side * (half + P.SIMHAT_ARM_T)
        u_far = side * (half + P.SIMHAT_ARM_T + 4.0)
        u_fin = side * (half + P.SIMHAT_ARM_T + 1.0)
        u_ped = side * (half + P.SIMHAT_ARM_T / 2)
        if P.SIMHAT_ARM_PEDESTAL:
            solids.append(cq.Workplane("XY")
                          .center(ox + u_ped, oy - (v_root - 1.0 + v_hi) / 2)
                          .rect(P.SIMHAT_PED_T, v_hi - (v_root - 1.0))
                          .extrude(z_bot_clip - P.SIMHAT_PED_GAP - PLATE_T)
                          .translate((0, 0, PLATE_T)).val())
        block = (cq.Workplane("XY")
                 .center(ox + (u_out + u_far) / 2, oy - v_root - 0.75)
                 .rect(abs(u_far - u_out) + 1.2, 6.5)
                 .extrude(z_top_clip).val())
        fin = (cq.Workplane("XY")
               .center(ox + u_fin, oy - v_root - 0.5)
               .rect(P.SIMHAT_RELEASE_TAB_T, 5.0)
               .extrude(4.0)
               .translate((0, 0, z_top_clip)).val())
        solids.append(arm.fuse(block).fuse(fin))

    return solids


def build_calicheck():
    parts = ([_plate()] + _pcb_thickness_wall() + _antenna_wall() + _bay()
             + _plug_bay())
    out = parts[0]
    for p in parts[1:]:
        out = out.fuse(p)
    return cq.Workplane("XY").newObject([out])

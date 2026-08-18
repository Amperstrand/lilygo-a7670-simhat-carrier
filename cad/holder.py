"""Parametric carrier for LILYGO T-A7670X + T-SimHat (single relay).

Builds:
  - build_carrier():             the full combined carrier
  - build_coupon(variants):      snap-fit test coupon (clearance variants)
  - place_a7670()/place_simhat(): manufacturer STEP solids in carrier coords

Carrier frame: origin at footprint center, z=0 build plate. A7670 at +X
(component-up on 4 screw standoffs), T-SimHat at -X (flipped: relay down,
pin headers up, tool-less snap-in), wiring channel between them.

T-SimHat board-local coords used by cage parameters: u along board width
(0 = center), v along length measured from the clip end (v=0 = board end
facing the release tabs). Carrier Y = simhat_pcb_l/2 - v.
"""

from __future__ import annotations

import math

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

from cad import parameters as P
from cad.parameters import Measured as M

A7670_STEP = "references/T-A7670X-Board-3D.stp"
SIMHAT_STEP = "references/t-simhat-pcb.stp"


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _a7670_local_to_carrier(x, y):
    """Board-local (from PCB lower-left) -> carrier XY, honoring rotation."""
    if P.A7670_ROT_180:
        x, y = M.a7670_pcb_w - x, M.a7670_pcb_l - y
    return (P.a7670_cx() - M.a7670_pcb_w / 2 + x,
            -M.a7670_pcb_l / 2 + y)


def a7670_holes_carrier():
    """A7670 mounting hole centers in carrier XY (DXF/STEP derived)."""
    return [_a7670_local_to_carrier(hx, hy) for hx, hy in M.a7670_holes_rel]


def a7670_board_z(pcb_local_z):
    """Board-local z (0 = PCB bottom) -> carrier z."""
    return P.A7670_STANDOFF_H + pcb_local_z


def sh_x(u):
    return P.simhat_cx() + u


def sh_y(v):
    return M.simhat_pcb_l / 2 - v


def simhat_pcb_top_z():
    return P.SIMHAT_SUPPORT_H + M.simhat_pcb_t


def place_a7670() -> cq.Shape:
    solid = cq.importers.importStep(A7670_STEP).val()
    if P.A7670_ROT_180:
        solid = solid.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 180)
    bb = solid.BoundingBox()
    tx = P.a7670_cx() - (bb.xmin + bb.xmax) / 2
    ty = -(bb.ymin + bb.ymax) / 2
    tz = P.A7670_STANDOFF_H - M.a7670["pcb_slab"]["z_bottom"]
    return solid.translate(cq.Vector(tx, ty, tz))


def place_simhat(support_h=None) -> cq.Shape:
    """Flip 180 deg about Y ((x,y,z)->(-x,y,-z)): relay down, headers up.

    After the flip the STEP PCB top face (slab z_top, relay side) becomes the
    downward face resting on the support pads, so tz = support_h + slab z_top.
    """
    sh = P.SIMHAT_SUPPORT_H if support_h is None else support_h
    solid = cq.importers.importStep(SIMHAT_STEP).val()
    solid = solid.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 180)
    bb2 = solid.BoundingBox()
    tx = P.simhat_cx() - (bb2.xmin + bb2.xmax) / 2
    ty = M.simhat_pcb_l / 2 - bb2.ymax        # clip end (STEP y=0) -> +Y
    tz = sh + M.simhat["pcb_slab"]["z_top"]
    return solid.translate(cq.Vector(tx, ty, tz))


# ---------------------------------------------------------------------------
# Base frame
# ---------------------------------------------------------------------------

def _frame_extents():
    y_half = P.frame_y_half()
    x_lo = P.simhat_cx() - M.simhat_pcb_w / 2 - P.FRAME_MARGIN
    x_hi = P.a7670_cx() + M.a7670_pcb_w / 2 + P.FRAME_MARGIN
    return x_lo, -y_half, x_hi, y_half


def _rect(x0, y0, x1, y1, z0, h):
    return (cq.Workplane("XY")
            .moveTo((x0 + x1) / 2, (y0 + y1) / 2)
            .rect(x1 - x0, y1 - y0).extrude(h)
            .translate((0, 0, z0)).val())


def build_base():
    x_lo, y_lo, x_hi, y_hi = _frame_extents()
    gap_ch = P.BOARD_GAP / 2 + 0.4          # wiring channel half width
    solids = []

    outer = (cq.Workplane("XY").moveTo((x_lo + x_hi) / 2, (y_lo + y_hi) / 2)
             .rect(x_hi - x_lo, y_hi - y_lo).extrude(P.BASE_T))
    inner = (cq.Workplane("XY").moveTo((x_lo + x_hi) / 2, (y_lo + y_hi) / 2)
             .rect(x_hi - x_lo - 2 * P.RAIL_W, y_hi - y_lo - 2 * P.RAIL_W)
             .extrude(P.BASE_T + 2).translate((0, 0, -1)))
    ring = (outer.cut(inner).edges("|Z").fillet(P.OUTER_CORNER_R).val())
    solids.append(ring)

    for x0, x1 in ((gap_ch, gap_ch + P.RAIL_W),
                   (-gap_ch - P.RAIL_W, -gap_ch)):
        solids.append(_rect(x0, y_lo + P.RAIL_W, x1, y_hi - P.RAIL_W, 0, P.BASE_T))

    for u in (-3.5, 3.5):
        x = P.simhat_cx() + u
        solids.append(_rect(x - P.RAIL_W / 2, -55.0, x + P.RAIL_W / 2,
                            55.0, 0, P.BASE_T))

    if P.PROFILE == "low":
        for y in (-53.5, -28.0, 0.0, 28.0, 53.5):
            solids.append(_rect(x_lo + P.RAIL_W, y - P.RAIL_W / 2,
                                -gap_ch, y + P.RAIL_W / 2, 0, P.BASE_T))
            solids.append(_rect(gap_ch, y - P.RAIL_W / 2,
                                x_hi - P.RAIL_W, y + P.RAIL_W / 2, 0, P.BASE_T))
        for (_, v, _, _) in P.SIMHAT_FENCES:
            yf = sh_y(v)
            solids.append(_rect(x_lo + P.RAIL_W, yf - P.RAIL_W / 2,
                                -gap_ch, yf + P.RAIL_W / 2, 0, P.BASE_T))
            solids.append(_rect(gap_ch, yf - P.RAIL_W / 2,
                                x_hi - P.RAIL_W, yf + P.RAIL_W / 2, 0, P.BASE_T))
        return cq.Workplane("XY").newObject(solids).combine()

    for y in (-53.5, -28.0, 0.0, 28.0, 53.5):
        solids.append(_rect(x_lo + P.RAIL_W, y - P.RAIL_W / 2,
                            -gap_ch, y + P.RAIL_W / 2, 0, P.BASE_T))
        solids.append(_rect(gap_ch, y - P.RAIL_W / 2,
                            x_hi - P.RAIL_W, y + P.RAIL_W / 2, 0, P.BASE_T))

    return cq.Workplane("XY").newObject(solids).combine()


# ---------------------------------------------------------------------------
# A7670 standoffs (M1.6 into printed pilots)
# ---------------------------------------------------------------------------

def _plug_solid(hx, hy):
    """Christmas-tree snap plug: thin shaft through the PCB hole, stacked
    tapered fins above the board (each fin passes the plated hole with
    small finger flex, like commercial plastic board-locks), cross-slotted
    into 4 fingers."""
    pcb_top = P.A7670_STANDOFF_H + M.a7670_pcb_t
    r_s = P.PLUG_SHAFT_D / 2
    z_tip = pcb_top + P.PLUG_FIN_PITCH * len(P.PLUG_FIN_DS) + P.PLUG_FIN_H + 0.3
    plug = (cq.Workplane("XY", origin=(0, 0, P.A7670_STANDOFF_H - 0.4))
            .moveTo(hx, hy).circle(r_s)
            .extrude(z_tip - P.A7670_STANDOFF_H + 0.4).val())
    z = pcb_top + 0.15
    for fin_d in P.PLUG_FIN_DS:
        r_f = fin_d / 2
        cone = (cq.Workplane("XZ", origin=(hx, hy, 0))
                .moveTo(0, 0).lineTo(0, P.PLUG_FIN_LEAD)
                .lineTo(r_f - r_s, P.PLUG_FIN_LEAD).close()
                .revolve(360, (0, 0), (0, 1))
                .translate((0, 0, z)).val())
        ring = (cq.Workplane("XY", origin=(0, 0, z + P.PLUG_FIN_LEAD))
                .moveTo(hx, hy).circle(r_f)
                .extrude(P.PLUG_FIN_H).val())
        plug = plug.fuse(cone).fuse(ring)
        z += P.PLUG_FIN_LEAD + P.PLUG_FIN_H + P.PLUG_FIN_PITCH
    for ang in (0, 90):
        slot = (cq.Workplane("XY", origin=(0, 0, pcb_top - 0.1))
                .center(hx, hy)
                .rect(max(P.PLUG_FIN_DS) + 2, P.PLUG_SLOT_W)
                .extrude(z_tip - pcb_top + 0.2)
                .rotate(cq.Vector(hx, hy, 0), cq.Vector(0, 0, 1), ang).val())
        plug = cq.Shape.cast(BRepAlgoAPI_Cut(plug.wrapped, slot.wrapped).Shape())
    return plug


def build_standoffs():
    solids = []
    for (hx, hy) in a7670_holes_carrier():
        boss = (cq.Workplane("XY").moveTo(hx, hy)
                .circle(P.A7670_STANDOFF_OD / 2)
                .extrude(P.A7670_STANDOFF_H - P.BASE_T)
                .translate((0, 0, P.BASE_T)).val())
        foot = _rect(hx - 5, hy - 5, hx + 5, hy + 5, 0, P.BASE_T)
        parts = [boss, foot]
        if P.A7670_MOUNT == "snap_plugs":
            parts.append(_plug_solid(hx, hy))
        solids.append(parts[0].fuse(parts[1]).fuse(*parts[2:]) if len(parts) > 2
                      else boss.fuse(foot))
    return cq.Workplane("XY").newObject(solids).combine()


def cut_screw_pilots(carrier):
    if P.A7670_MOUNT != "screws":
        return carrier
    pilot_depth = P.A7670_STANDOFF_H - 1.5   # blind pilot, 1.5mm floor above z=0
    for (hx, hy) in a7670_holes_carrier():
        cutter = (cq.Workplane("XY").moveTo(hx, hy)
                  .circle(P.A7670_PILOT_D / 2)
                  .extrude(pilot_depth)
                  .translate((0, 0, P.A7670_STANDOFF_H - pilot_depth)))
        carrier = carrier.cut(cutter)
    return carrier


# ---------------------------------------------------------------------------
# T-SimHat cage: pads, fixed lip, corner clips, XY fences
# ---------------------------------------------------------------------------

def build_simhat_pads():
    solids = []
    for (u, v) in P.SIMHAT_PADS_UV:
        x, y = sh_x(u), sh_y(v)
        col = _rect(x - P.SIMHAT_PAD_SIZE / 2, y - P.SIMHAT_PAD_SIZE / 2,
                    x + P.SIMHAT_PAD_SIZE / 2, y + P.SIMHAT_PAD_SIZE / 2,
                    P.BASE_T, P.SIMHAT_SUPPORT_H - P.BASE_T)
        foot = _rect(x - P.SIMHAT_PAD_SIZE / 2 - 2, y - P.SIMHAT_PAD_SIZE / 2 - 2,
                     x + P.SIMHAT_PAD_SIZE / 2 + 2, y + P.SIMHAT_PAD_SIZE / 2 + 2,
                     0, P.BASE_T)
        solids.append(col.fuse(foot))
    return cq.Workplane("XY").newObject(solids).combine()


def _clip_slab_top():
    return simhat_pcb_top_z() + P.SIMHAT_PCB_T_CLEAR + P.SIMHAT_HOOK_T


def _clip_geometry(clear, side):
    """Shared clip coordinates in board-local (u, v)."""
    half = M.simhat_pcb_w / 2 + clear
    v_l0 = min(clear, P.SIMHAT_END_PLAY)
    v_tip = clear + P.SIMHAT_HOOK_REACH_V
    v_root = v_tip - P.SIMHAT_ARM_LEN
    return {
        "u_out": side * (half + P.SIMHAT_ARM_T),
        "u_in": side * half,
        "u_tip": side * (half - P.SIMHAT_HOOK_ENGAGE),
        "v_l0": v_l0, "v_tip": v_tip, "v_root": v_root,
        "z_top": _clip_slab_top(), "z_bot": _clip_slab_top() - P.SIMHAT_ARM_W,
    }


def _clip_arm_pts(clear, side):
    """Plan-view outline of one clip arm in board-local (u, v), including
    the hook lead-in chamfer. Shared by the carrier clips AND the coupon so
    the coupon always exercises the exact production snap geometry."""
    g = _clip_geometry(clear, side)
    c = min(P.SIMHAT_HOOK_LEAD_CHAMFER, P.SIMHAT_HOOK_ENGAGE * 0.8,
            (g["v_tip"] - g["v_l0"]) * 0.4)
    u_tip = g["u_tip"]
    gs = P.SIMHAT_ARM_ROOT_GUSSET
    return [(g["u_out"], g["v_root"] - gs), (g["u_out"], g["v_tip"]),
            (g["u_in"], g["v_tip"]), (u_tip, g["v_tip"]),
            (u_tip, g["v_l0"] + c), (u_tip + side * c, g["v_l0"]),
            (g["u_in"], g["v_l0"]), (g["u_in"], g["v_root"] - gs),
            (g["u_in"] + side * gs, g["v_root"] - gs)]


def _hook_undercut_cutter():
    """Removes arm material over the board envelope below the hook ledge,
    leaving an L-shaped hook that only bears on the PCB top edge."""
    half = M.simhat_pcb_w / 2 + P.SIMHAT_PCB_XY_CLEAR
    z = simhat_pcb_top_z() + P.SIMHAT_PCB_T_CLEAR
    return cq.Solid.makeBox(2 * half, 400, z + 1,
                            cq.Vector(sh_x(0) - half, -200, -1))


def _clip_arm(side, clear, deflect=0.0):
    g = _clip_geometry(clear, side)
    arm = (cq.Workplane("XY")
           .polyline([(sh_x(u), sh_y(v)) for u, v in _clip_arm_pts(clear, side)])
           .close().extrude(g["z_top"] - g["z_bot"])
           .translate((0, 0, g["z_bot"])).val())
    arm = cq.Shape.cast(
        BRepAlgoAPI_Cut(arm.wrapped, _hook_undercut_cutter().wrapped).Shape())
    if deflect:
        arm = arm.translate(cq.Vector(side * deflect, 0, 0))
    return arm


def _clip_anchor(side, clear):
    g = _clip_geometry(clear, side)
    u_in = side * (M.simhat_pcb_w / 2 + clear)
    u_out = side * (M.simhat_pcb_w / 2 + clear + P.SIMHAT_ARM_T)
    u_far = side * (abs(u_out) + 4.0)
    block = _rect(min(sh_x(u_in), sh_x(u_far)), sh_y(g["v_root"] - 4.0),
                  max(sh_x(u_in), sh_x(u_far)), sh_y(g["v_root"] + 2.5),
                  0, g["z_top"])
    u_fin = side * (abs(u_out) + 1.0)
    fin = _rect(sh_x(u_fin) - P.SIMHAT_RELEASE_TAB_T / 2,
                sh_y(g["v_root"] + 2.0),
                sh_x(u_fin) + P.SIMHAT_RELEASE_TAB_T / 2,
                sh_y(g["v_root"] - 3.0),
                g["z_top"], P.SIMHAT_RELEASE_TAB_H)
    return block.fuse(fin)


def _clip_pedestal(side, clear, z0):
    """Bed/plate-supported wall under the arm free span. Fuses into the
    anchor at the root end; its top stays PED_GAP below the arm underside
    so the flexure is untouched in service."""
    g = _clip_geometry(clear, side)
    half = M.simhat_pcb_w / 2 + clear
    u_c = side * (half + P.SIMHAT_ARM_T / 2)
    v_lo = g["v_root"] - 1.0
    v_hi = g["v_l0"] + P.SIMHAT_HOOK_REACH_V - 0.5
    return _rect(sh_x(u_c) - P.SIMHAT_PED_T / 2, sh_y(v_hi),
                 sh_x(u_c) + P.SIMHAT_PED_T / 2, sh_y(v_lo),
                 z0, (g["z_bot"] - P.SIMHAT_PED_GAP) - z0)


def build_simhat_clips(clear=None, deflect=0.0):
    c = P.SIMHAT_PCB_XY_CLEAR if clear is None else clear
    solids = []
    for side in (-1, 1):
        parts = [_clip_arm(side, c, deflect), _clip_anchor(side, c)]
        if P.SIMHAT_ARM_PEDESTAL:
            ped = _clip_pedestal(side, c, 0.0)
            if deflect:
                ped = ped.translate(cq.Vector(side * deflect, 0, 0))
            parts.append(ped)
        solids.append(parts[0].fuse(parts[1]).fuse(parts[2]))
    return cq.Workplane("XY").newObject(solids).combine()


def build_simhat_lip():
    c = P.SIMHAT_END_PLAY
    ledge_top = simhat_pcb_top_z() + P.SIMHAT_PCB_T_CLEAR + P.SIMHAT_LIP_T
    y_end = sh_y(M.simhat_pcb_l)
    solids = []
    for (u0, u1) in P.SIMHAT_LIP_SEGMENTS_U:
        wall = _rect(sh_x(u0), -53.5, sh_x(u1), y_end - c, 0, ledge_top)
        ledge = _rect(sh_x(u0), y_end - c, sh_x(u1),
                      y_end - c + P.SIMHAT_LIP_ENGAGE,
                      ledge_top - P.SIMHAT_LIP_T, P.SIMHAT_LIP_T)
        solids.append(wall.fuse(ledge))
    return cq.Workplane("XY").newObject(solids).combine()


def build_simhat_fences():
    half = M.simhat_pcb_w / 2 + P.SIMHAT_PCB_XY_CLEAR
    top = P.SIMHAT_SUPPORT_H + P.SIMHAT_FENCE_ENGAGE_H
    x_lo, _, x_hi, _ = _frame_extents()
    gap_ch = P.BOARD_GAP / 2 + 0.4
    solids = []
    for (side, v, v_half, bite) in P.SIMHAT_FENCES:
        push = P.SIMHAT_FENCE_BITE if bite else 0.0
        u = side * (half - push + P.SIMHAT_FENCE_T / 2)
        wall = _rect(sh_x(u) - P.SIMHAT_FENCE_T / 2, sh_y(v + v_half),
                     sh_x(u) + P.SIMHAT_FENCE_T / 2, sh_y(v - v_half),
                     P.BASE_T, top - P.BASE_T)
        foot_x1 = -gap_ch if side > 0 else x_lo + P.RAIL_W
        foot = _rect(min(sh_x(u) - P.SIMHAT_FENCE_T / 2, foot_x1),
                     sh_y(v + v_half),
                     max(sh_x(u) + P.SIMHAT_FENCE_T / 2, foot_x1),
                     sh_y(v - v_half), 0, P.BASE_T)
        solids.append(wall.fuse(foot))
    return cq.Workplane("XY").newObject(solids).combine()


def fence_bite_mm3():
    """Intended fence/PCB overlap from biting fences (friction fit), in
    STEP-slab terms -- the seated check measures against the placed
    manufacturer STEP (1.0 mm slab), not the caliper-corrected 1.25."""
    bite = max(0.0, P.SIMHAT_FENCE_BITE - P.SIMHAT_PCB_XY_CLEAR)
    slab_t = M.simhat["pcb_slab"]["z_top"] - M.simhat["pcb_slab"]["z_bottom"]
    return bite * slab_t * sum(2 * vh for _, _, vh, b in P.SIMHAT_FENCES if b)


# ---------------------------------------------------------------------------
# Tape pads, cable-tie slots, enclosure ears
# ---------------------------------------------------------------------------

def build_tape_pads():
    solids = [
        _rect(P.simhat_cx() - P.TAPE_PAD_SIZE / 2, -P.TAPE_PAD_SIZE / 2,
              P.simhat_cx() + P.TAPE_PAD_SIZE / 2, P.TAPE_PAD_SIZE / 2,
              0, P.BASE_T),
    ]
    if P.ANT_POS != "under_battery":
        solids.insert(0, _rect(P.a7670_cx() - P.TAPE_PAD_SIZE / 2,
                               -P.TAPE_PAD_SIZE / 2,
                               P.a7670_cx() + P.TAPE_PAD_SIZE / 2,
                               P.TAPE_PAD_SIZE / 2, 0, P.BASE_T))
    return cq.Workplane("XY").newObject(solids).combine()


def _ear_geometry():
    x_lo, y_lo, x_hi, y_hi = _frame_extents()
    y_half = -y_lo
    out = []
    for name, (sx, sy) in P.EARS.items():
        x_edge = x_hi if sx > 0 else x_lo
        if sx > 0 and P.ANT_POS == "side_tray" and P.PROFILE == "full":
            x_edge = antenna_geometry()["outer_x"] - 1.0
        y_c = sy * (y_half - P.EAR_W / 2 + 2.0)
        out.append({
            "name": name, "kind": "corner", "sx": sx, "x_edge": x_edge,
            "y_c": y_c, "tip_x": x_edge + sx * P.EAR_EXT,
            "slot_x": x_edge + sx * (P.EAR_EXT - 4.0),
            "slot_angle": 0,
        })
    if P.ANT_POS == "end_tray" and P.PROFILE == "full":
        y0 = _antenna_tray_geometry()["far_y"]
        out = [e for e in out if not e["name"].endswith("-near")]
        for i, tx in enumerate(P.ANT_STOP_TAB_X):
            out.append({
                "name": f"antenna_stop_tab_{i}", "kind": "stop_tab", "sx": 0,
                "x_edge": tx, "y_c": y0 - P.ANT_STOP_TAB_EXT / 2 + P.ANT_TRAY_STOP_T / 2,
                "tip_x": tx, "slot_x": tx,
                "slot_y": y0 - P.ANT_STOP_TAB_EXT / 2 + P.ANT_TRAY_STOP_T / 2,
                "slot_angle": 90,
            })
    return out


def build_ears():
    solids = []
    for e in _ear_geometry():
        if e["kind"] != "corner":
            continue
        body = _rect(min(e["x_edge"], e["tip_x"]), e["y_c"] - P.EAR_W / 2,
                     max(e["x_edge"], e["tip_x"]), e["y_c"] + P.EAR_W / 2,
                     0, P.EAR_T)
        cap = (cq.Workplane("XY").moveTo(e["tip_x"], e["y_c"])
               .circle(P.EAR_W / 2).extrude(P.EAR_T).val())
        solids.append(body.fuse(cap))
    return cq.Workplane("XY").newObject(solids).combine()


def _slot_cutter(x, y, angle):
    return (cq.Workplane("XY").moveTo(x, y)
            .slot2D(P.EAR_SLOT_L, P.EAR_SLOT_W, angle)
            .extrude(P.EAR_T + 2).translate((0, 0, -1)))


def cut_ear_slots(carrier):
    for e in _ear_geometry():
        y = e.get("slot_y", e["y_c"])
        carrier = carrier.cut(_slot_cutter(e["slot_x"], y,
                                           e.get("slot_angle", 0)))
    return carrier


def cut_tie_slots(carrier):
    for (x, y) in P.TIE_SLOTS:
        carrier = carrier.cut(_slot_cutter(x, y, 0))
    return carrier


# ---------------------------------------------------------------------------
# LTE sticker antenna channels (ANT_POS: under_battery | end_tray)
# ---------------------------------------------------------------------------

def antenna_geometry():
    """Canonical channel coordinates for the active ANT_POS."""
    if P.ANT_POS == "side_tray":
        x_hi = _frame_extents()[2]
        band_x0 = x_hi + P.ANT_SIDE_WALL_T
        band_x1 = band_x0 + P.ANT_W + 2 * P.ANT_SIDE_CLEAR
        outer_x = band_x1 + P.ANT_SIDE_WALL_T
        return {"pos": "side_tray", "x_hi": x_hi, "band_x0": band_x0,
                "band_x1": band_x1, "outer_x": outer_x,
                "stop_y": P.ANT_SIDE_STOP_Y,
                "mouth_y": -P.frame_y_half(),
                "floor_y_half": P.frame_y_half() + 2.0,
                "slide_len": P.ANT_SLIDE}
    if P.ANT_POS == "under_battery":
        _, y_lo, _, _ = _frame_extents()
        entry_y = y_lo + P.RAIL_W              # inner face of the -Y end rail
        stop_y = P.ANT_STOP_Y
        cx = P.a7670_cx()
        half = P.ANT_W / 2 + P.ANT_SIDE_CLEAR
        return {"pos": "under_battery", "entry_y": entry_y, "stop_y": stop_y,
                "cx": cx, "ch_half": half,
                "slide_len": stop_y - entry_y}
    x_lo, y_lo, _, _ = _frame_extents()
    entry_y = y_lo
    far_y = y_lo - (P.ANT_SLIDE + P.ANT_TRAY_STOP_T + 0.6)
    cx = P.ANT_X_C if P.ANT_X_C is not None else 0.0
    half = P.ANT_W / 2 + P.ANT_SIDE_CLEAR
    return {"pos": "end_tray", "entry_y": entry_y, "far_y": far_y,
            "cx": cx, "ch_half": half,
            "ch_x_lo": cx - half, "ch_x_hi": cx + half}


def _antenna_tray_geometry():
    g = antenna_geometry()
    return {"entry_y": g["entry_y"], "far_y": g["far_y"],
            "ch_x_lo": g["ch_x_lo"], "ch_x_hi": g["ch_x_hi"]}


def build_antenna_underdeck():
    """Sticker slides flat UNDER the A7670 in the 1.3 mm gap below the
    18650 holder: sparse support (center rail + entry/stop ties on the
    base strip), two short open-top guides whose inner faces lean out
    ANT_GUIDE_SLOPE_DEG (self-centering funnel), +Y stop. The cable-entry
    end of the sticker stays in the -Y mouth (beyond the battery
    footprint, open above) so the pigtail loops out freely."""
    g = antenna_geometry()
    cx, half = g["cx"], g["ch_half"]
    y0, y1 = g["entry_y"], g["stop_y"]
    h = P.ANT_GUIDE_H
    lean = h / math.tan(math.radians(P.ANT_GUIDE_SLOPE_DEG))
    solids = []

    span = cx - half - P.ANT_GUIDE_T - 2.0, cx + half + P.ANT_GUIDE_T + 2.0
    solids.append(_rect(cx - P.ANT_CENTER_RAIL_W / 2, y0,
                        cx + P.ANT_CENTER_RAIL_W / 2, y1, 0, P.ANT_FLOOR_T))
    for ty in (y0 + 3.0, y1 - 3.0):
        solids.append(_rect(span[0], ty - 1.5, span[1], ty + 1.5,
                            0, P.ANT_FLOOR_T))

    for side in (-1, 1):
        xi = cx + side * half
        xo = xi + side * P.ANT_GUIDE_T
        pts = [(xi, y0), (xi + side * lean, y1),
               (xo + side * lean, y1), (xo, y0)]
        solids.append(cq.Workplane("XY").polyline(pts).close()
                      .extrude(0.3 + P.ANT_FLOOR_T + h)
                      .translate((0, 0, P.ANT_FLOOR_T - 0.3)).val())

    stop = _rect(span[0], y1, span[1], y1 + P.ANT_GUIDE_T,
                 P.ANT_FLOOR_T - 0.3, 0.3 + h)
    solids.append(stop)
    return cq.Workplane("XY").newObject(solids).combine()


def build_antenna_sidetray():
    """Open slide-in tray on the +X frame edge: floor lapped 1.6 mm into
    the outer ring rail, inner + outer walls with a chamfered -Y mouth,
    +Y stop, and coax guide posts on the ring-rail top beside the inner
    wall (cable drops into the groove between post and wall, runs along
    the frame edge to the SMA jacks). The two +X mounting ears move onto
    the tray's outer wall via _ear_geometry()."""
    g = antenna_geometry()
    y0, y1 = g["mouth_y"], g["stop_y"] + P.ANT_SIDE_STOP_T
    fy = g["floor_y_half"]
    f = P.ANT_SIDE_ENTRY_CHAMFER
    solids = [_rect(g["x_hi"] - 1.6, -fy, g["outer_x"], fy, 0, P.ANT_FLOOR_T)]

    xi0, xi1 = g["x_hi"], g["band_x0"]
    inner_pts = [(xi1, y0), (xi1, y1), (xi0, y1), (xi0, y0 + f),
                 (xi1 - f, y0)]
    xo0, xo1 = g["band_x1"], g["outer_x"]
    outer_pts = [(xo0, y0), (xo0, y1), (xo1, y1), (xo1, y0 + f),
                 (xo0 + f, y0)]
    for pts in (inner_pts, outer_pts):
        solids.append(cq.Workplane("XY")
                      .polyline([(x, y) for x, y in pts]).close()
                      .extrude(P.ANT_FLOOR_T + P.ANT_SIDE_WALL_H).val())

    solids.append(_rect(xi0, g["stop_y"], xo1, y1,
                        0, P.ANT_FLOOR_T + P.ANT_SIDE_WALL_H))

    for cy in P.ANT_COAX_CLIP_YS:
        solids.append(_rect(g["x_hi"] - P.RAIL_W, cy - 2.0,
                            g["x_hi"] - P.RAIL_W + 1.0, cy + 2.0,
                            P.BASE_T - 0.3, P.ANT_COAX_CLIP_H + 0.3))
    return cq.Workplane("XY").newObject(solids).combine()


def build_antenna_tray():
    """end_tray alternative: floor + flared walls + stop beyond the -Y rail."""
    g = antenna_geometry()
    y0, y1 = g["far_y"], g["entry_y"]
    f = P.ANT_TRAY_ENTRY_CHAMFER
    cx = g["cx"]
    half = g["ch_half"]
    solids = []

    floor = _rect(cx - half - P.ANT_TRAY_WALL_T - 2.0, y0,
                  cx + half + P.ANT_TRAY_WALL_T + 2.0, y1 + f + 1.0,
                  0, P.ANT_FLOOR_T)

    for xi, side in ((g["ch_x_lo"], -1), (g["ch_x_hi"], 1)):
        pts = [(xi, y0), (xi, y1), (xi + side * f, y1),
               (xi + side * f, y1 + f), (xi + side * P.ANT_TRAY_WALL_T, y1 + f),
               (xi + side * P.ANT_TRAY_WALL_T, y0)]
        solids.append(cq.Workplane("XY").polyline(pts).close()
                      .extrude(P.ANT_TRAY_WALL_H).val())

    stop = _rect(cx - half - P.ANT_TRAY_WALL_T - 2.0, y0,
                 cx + half + P.ANT_TRAY_WALL_T + 2.0,
                 y0 + P.ANT_TRAY_STOP_T, 0, P.ANT_TRAY_WALL_H)
    solids.append(stop)

    for tx in P.ANT_STOP_TAB_X:
        solids.append(_rect(tx - P.EAR_W / 2, y0 - P.ANT_STOP_TAB_EXT,
                            tx + P.EAR_W / 2, y0 + P.ANT_TRAY_STOP_T,
                            0, P.EAR_T))

    return cq.Workplane("XY").newObject([floor] + solids).combine()


def build_antenna():
    if P.ANT_POS == "side_tray":
        return build_antenna_sidetray()
    if P.ANT_POS == "under_battery":
        return build_antenna_underdeck()
    if P.ANT_POS == "end_tray":
        return build_antenna_tray()
    return cq.Workplane("XY").box(0.001, 0.001, 0.001)


def cut_coax_notch(carrier):
    if P.ANT_POS != "end_tray":
        return carrier
    _, y_lo, _, _ = _frame_extents()
    cx = antenna_geometry()["cx"]
    notch = _rect(cx - P.ANT_COAX_NOTCH_W / 2, y_lo - 1.0,
                  cx + P.ANT_COAX_NOTCH_W / 2, y_lo + P.RAIL_W + 0.6,
                  0, 3.0)
    return carrier.cut(notch)


# ---------------------------------------------------------------------------
# Top-level builds
# ---------------------------------------------------------------------------

def build_carrier(clip_deflect=0.0):
    carrier = build_base()
    parts = [build_standoffs(), build_simhat_pads(), build_simhat_lip()]
    if P.SIMHAT_CLIPS_ENABLED:
        parts.append(build_simhat_clips(deflect=clip_deflect))
    parts.append(build_simhat_fences())
    if P.PROFILE == "full":
        parts.append(build_tape_pads())
    parts.append(build_ears())
    if P.ANT_POS not in ("none",) and P.PROFILE == "full":
        parts.append(build_antenna())
    for part in parts:
        carrier = carrier.union(part, tol=1e-4)
    carrier = cut_screw_pilots(carrier)
    carrier = cut_tie_slots(carrier)
    carrier = cut_ear_slots(carrier)
    carrier = cut_coax_notch(carrier)
    return carrier


def build_assembly():
    carrier = build_carrier()
    asm = cq.Assembly(name="lilygo_a7670_simhat_carrier_assembly")
    asm.add(carrier.val(), name="carrier", color=cq.Color(0.75, 0.75, 0.78, 1.0))
    asm.add(place_a7670(), name="T-A7670X_reference",
            color=cq.Color(0.1, 0.45, 0.15, 0.9))
    asm.add(place_simhat(), name="T-SimHat_reference_flipped",
            color=cq.Color(0.85, 0.65, 0.1, 0.9))
    return asm, carrier, place_a7670(), place_simhat()


def build_sections(carrier=None):
    """Split the finished carrier into independently printable, exactly
    partitioning sections (volume sum equals the whole): A7670 plate and
    SimHat cage split at x=0 spanning full Y; with ANT_POS=end_tray the -Y
    strip becomes a third tray section instead. Per-region iteration only."""
    if carrier is None:
        carrier = build_carrier().val()

    def keep(box_origin, box_dx, box_dy):
        box = cq.Solid.makeBox(box_dx, box_dy, 80,
                               cq.Vector(box_origin[0], box_origin[1], -10))
        return cq.Shape.cast(BRepAlgoAPI_Common(
            carrier.wrapped, box.wrapped).Shape())

    if P.ANT_POS == "end_tray" and P.PROFILE == "full":
        split_y = _frame_extents()[1] + 2 * P.RAIL_W
        return {
            "a7670_section": cq.Workplane("XY").newObject(
                [keep((0.0, split_y), 150, 200)]),
            "simhat_cage_section": cq.Workplane("XY").newObject(
                [keep((-150.0, split_y), 150, 200)]),
            "antenna_tray_section": cq.Workplane("XY").newObject(
                [keep((-150.0, -150.0), 300, 150 + split_y)]),
        }
    return {
        "a7670_section": cq.Workplane("XY").newObject(
            [keep((0.0, -150.0), 150, 300)]),
        "simhat_cage_section": cq.Workplane("XY").newObject(
            [keep((-150.0, -150.0), 150, 300)]),
    }


# ---------------------------------------------------------------------------
# Snap-fit test coupon: 4 clearance variants in a 2x2 grid, notch-counted
# ---------------------------------------------------------------------------

COUPON_VARIANTS = [0.20, 0.30, 0.40, 0.50]
_COUPON_CELL_W, _COUPON_CELL_L = 52.0, 40.0


def _coupon_bay(ox, oy, clear, index):
    """One bay: pair of corner clips + 2 pads + 2 fences for a board end at
    (ox, oy). Clips reuse the production clip outline (_clip_arm_pts) so the
    coupon exercises the exact carrier snap geometry. Notch count (index+1)
    marks the clearance variant."""
    solids = []
    half = M.simhat_pcb_w / 2 + clear
    z_top = _clip_slab_top()
    z_bot = z_top - P.SIMHAT_ARM_W

    for side in (-1, 1):
        arm = (cq.Workplane("XY")
               .polyline([(ox + u, oy + v) for u, v in _clip_arm_pts(clear, side)])
               .close().extrude(z_top - z_bot).translate((0, 0, z_bot)).val())
        undercut = cq.Solid.makeBox(
            2 * (M.simhat_pcb_w / 2 + clear), 400,
            simhat_pcb_top_z() + P.SIMHAT_PCB_T_CLEAR + 1,
            cq.Vector(ox - (M.simhat_pcb_w / 2 + clear), oy - 200, -1))
        arm = cq.Shape.cast(BRepAlgoAPI_Cut(arm.wrapped, undercut.wrapped).Shape())
        u_out = side * (half + P.SIMHAT_ARM_T)
        u_far = side * (half + P.SIMHAT_ARM_T + 4.0)
        u_fin = side * (half + P.SIMHAT_ARM_T + 1.0)
        v_root = clear + P.SIMHAT_HOOK_REACH_V - P.SIMHAT_ARM_LEN
        v_hi = clear + P.SIMHAT_HOOK_REACH_V - 0.5
        if P.SIMHAT_ARM_PEDESTAL:
            u_ped = side * (half + P.SIMHAT_ARM_T / 2)
            solids.append(_rect(ox + u_ped - P.SIMHAT_PED_T / 2, oy + v_hi,
                                ox + u_ped + P.SIMHAT_PED_T / 2,
                                oy + v_root - 1.0,
                                P.BASE_T, z_bot - P.SIMHAT_PED_GAP - P.BASE_T))
        block = _rect(ox + min(u_out, u_far), oy + v_root - 4.0,
                      ox + max(u_out, u_far), oy + v_root + 2.5, 0, z_top)
        fin = _rect(ox + u_fin - P.SIMHAT_RELEASE_TAB_T / 2, oy + v_root - 3.0,
                    ox + u_fin + P.SIMHAT_RELEASE_TAB_T / 2, oy + v_root + 2.0,
                    z_top, P.SIMHAT_RELEASE_TAB_H)
        solids.append(arm.fuse(block).fuse(fin))

    for u in (-3.5, 3.5):
        solids.append(_rect(ox + u - P.SIMHAT_PAD_SIZE / 2,
                            oy - P.SIMHAT_PAD_SIZE / 2,
                            ox + u + P.SIMHAT_PAD_SIZE / 2,
                            oy + P.SIMHAT_PAD_SIZE / 2,
                            P.BASE_T, P.SIMHAT_SUPPORT_H - P.BASE_T))

    for side in (-1, 1):
        u = side * (half - P.SIMHAT_FENCE_BITE + P.SIMHAT_FENCE_T / 2)
        solids.append(_rect(ox + u - P.SIMHAT_FENCE_T / 2, oy - 6.0,
                            ox + u + P.SIMHAT_FENCE_T / 2, oy + 6.0,
                            P.BASE_T,
                            P.SIMHAT_SUPPORT_H + P.SIMHAT_FENCE_ENGAGE_H - P.BASE_T))

    for i in range(index + 1):
        solids.append((cq.Workplane("XY")
                       .moveTo(ox - _COUPON_CELL_W / 2 + 5.0 + i * 3.2,
                               oy - _COUPON_CELL_L / 2 + 3.2)
                       .circle(1.1).extrude(P.BASE_T + 1.2)).val())

    return solids


def build_coupon(variants=COUPON_VARIANTS):
    w = 2 * _COUPON_CELL_W + 8
    h = 2 * _COUPON_CELL_L + 8
    solids = [_rect(-w / 2, -h / 2, w / 2, h / 2, 0, P.BASE_T)]
    for i, clr in enumerate(variants):
        ox = -_COUPON_CELL_W / 2 if i % 2 == 0 else _COUPON_CELL_W / 2
        oy = -_COUPON_CELL_L / 2 if i < 2 else _COUPON_CELL_L / 2
        solids += _coupon_bay(ox, oy, clr, i)
    return cq.Workplane("XY").newObject(solids).combine()

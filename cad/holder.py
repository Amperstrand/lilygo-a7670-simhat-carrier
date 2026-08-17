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

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

from cad import parameters as P
from cad.parameters import Measured as M

A7670_STEP = "references/T-A7670X-Board-3D.stp"
SIMHAT_STEP = "references/t-simhat-pcb.stp"


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def a7670_holes_carrier():
    """A7670 mounting hole centers in carrier XY (DXF/STEP derived)."""
    cx = P.a7670_cx()
    x0 = cx - M.a7670_pcb_w / 2
    y0 = -M.a7670_pcb_l / 2
    return [(x0 + hx, y0 + hy) for hx, hy in M.a7670_holes_rel]


def sh_x(u):
    return P.simhat_cx() + u


def sh_y(v):
    return M.simhat_pcb_l / 2 - v


def simhat_pcb_top_z():
    return P.SIMHAT_SUPPORT_H + M.simhat_pcb_t


def place_a7670() -> cq.Shape:
    solid = cq.importers.importStep(A7670_STEP).val()
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

    for y in (-53.5, -28.0, 0.0, 28.0, 53.5):
        solids.append(_rect(x_lo + P.RAIL_W, y - P.RAIL_W / 2,
                            -gap_ch, y + P.RAIL_W / 2, 0, P.BASE_T))
        solids.append(_rect(gap_ch, y - P.RAIL_W / 2,
                            x_hi - P.RAIL_W, y + P.RAIL_W / 2, 0, P.BASE_T))

    return cq.Workplane("XY").newObject(solids).combine()


# ---------------------------------------------------------------------------
# A7670 standoffs (M1.6 into printed pilots)
# ---------------------------------------------------------------------------

def build_standoffs():
    solids = []
    for (hx, hy) in a7670_holes_carrier():
        boss = (cq.Workplane("XY").moveTo(hx, hy)
                .circle(P.A7670_STANDOFF_OD / 2)
                .extrude(P.A7670_STANDOFF_H - P.BASE_T)
                .translate((0, 0, P.BASE_T)).val())
        foot = _rect(hx - 5, hy - 5, hx + 5, hy + 5, 0, P.BASE_T)
        solids.append(boss.fuse(foot))
    return cq.Workplane("XY").newObject(solids).combine()


def cut_screw_pilots(carrier):
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
    v_l0 = clear
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
    g = _clip_geometry(clear, side)
    return [(g["u_out"], g["v_root"]), (g["u_out"], g["v_tip"]),
            (g["u_in"], g["v_tip"]), (g["u_tip"], g["v_tip"]),
            (g["u_tip"], g["v_l0"]), (g["u_in"], g["v_l0"]),
            (g["u_in"], g["v_root"])]


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


def build_simhat_clips(clear=None, deflect=0.0):
    c = P.SIMHAT_PCB_XY_CLEAR if clear is None else clear
    solids = []
    for side in (-1, 1):
        solids.append(_clip_arm(side, c, deflect).fuse(_clip_anchor(side, c)))
    return cq.Workplane("XY").newObject(solids).combine()


def build_simhat_lip():
    c = P.SIMHAT_PCB_XY_CLEAR
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
    c = P.SIMHAT_PCB_XY_CLEAR
    half = M.simhat_pcb_w / 2 + c
    top = P.SIMHAT_SUPPORT_H + P.SIMHAT_FENCE_ENGAGE_H
    x_lo, _, x_hi, _ = _frame_extents()
    gap_ch = P.BOARD_GAP / 2 + 0.4
    solids = []
    for (side, v) in P.SIMHAT_FENCES:
        u = side * (half + P.SIMHAT_FENCE_T / 2)
        wall = _rect(sh_x(u) - P.SIMHAT_FENCE_T / 2, sh_y(v) - 6.0,
                     sh_x(u) + P.SIMHAT_FENCE_T / 2, sh_y(v) + 6.0,
                     P.BASE_T, top - P.BASE_T)
        foot_x1 = -gap_ch if side > 0 else x_lo + P.RAIL_W
        foot = _rect(min(sh_x(u) - P.SIMHAT_FENCE_T / 2, foot_x1),
                     sh_y(v) - 6.0,
                     max(sh_x(u) + P.SIMHAT_FENCE_T / 2, foot_x1),
                     sh_y(v) + 6.0, 0, P.BASE_T)
        solids.append(wall.fuse(foot))
    return cq.Workplane("XY").newObject(solids).combine()


# ---------------------------------------------------------------------------
# Tape pads, cable-tie slots, enclosure ears
# ---------------------------------------------------------------------------

def build_tape_pads():
    solids = [
        _rect(P.a7670_cx() - P.TAPE_PAD_SIZE / 2, -P.TAPE_PAD_SIZE / 2,
              P.a7670_cx() + P.TAPE_PAD_SIZE / 2, P.TAPE_PAD_SIZE / 2,
              0, P.BASE_T),
        _rect(P.simhat_cx() - P.TAPE_PAD_SIZE / 2, -P.TAPE_PAD_SIZE / 2,
              P.simhat_cx() + P.TAPE_PAD_SIZE / 2, P.TAPE_PAD_SIZE / 2,
              0, P.BASE_T),
    ]
    return cq.Workplane("XY").newObject(solids).combine()


def _ear_geometry():
    x_lo, y_lo, x_hi, y_hi = _frame_extents()
    y_half = -y_lo
    out = []
    for name, (sx, sy) in P.EARS.items():
        x_edge = x_hi if sx > 0 else x_lo
        y_c = sy * (y_half - P.EAR_W / 2 + 2.0)
        out.append({
            "name": name, "sx": sx, "x_edge": x_edge, "y_c": y_c,
            "tip_x": x_edge + sx * P.EAR_EXT,
            "slot_x": x_edge + sx * (P.EAR_EXT - 4.0),
        })
    return out


def build_ears():
    solids = []
    for e in _ear_geometry():
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
        carrier = carrier.cut(_slot_cutter(e["slot_x"], e["y_c"],
                                           0 if P.EAR_SLOT_ANGLE == 0 else 90))
    return carrier


def cut_tie_slots(carrier):
    for (x, y) in P.TIE_SLOTS:
        carrier = carrier.cut(_slot_cutter(x, y, 0))
    return carrier


# ---------------------------------------------------------------------------
# Top-level builds
# ---------------------------------------------------------------------------

def build_carrier(clip_deflect=0.0):
    carrier = build_base()
    for part in (build_standoffs(), build_simhat_pads(), build_simhat_lip(),
                 build_simhat_clips(deflect=clip_deflect), build_simhat_fences(),
                 build_tape_pads(), build_ears()):
        carrier = carrier.union(part, tol=1e-4)
    carrier = cut_screw_pilots(carrier)
    carrier = cut_tie_slots(carrier)
    carrier = cut_ear_slots(carrier)
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


# ---------------------------------------------------------------------------
# Snap-fit test coupon: 4 clearance variants in a 2x2 grid, notch-counted
# ---------------------------------------------------------------------------

COUPON_VARIANTS = [0.20, 0.30, 0.40, 0.50]
_COUPON_CELL_W, _COUPON_CELL_L = 52.0, 40.0


def _coupon_bay(ox, oy, clear, index):
    """One bay: pair of corner clips + 2 pads + 2 fences for a board end at
    (ox, oy). Notch count (index+1) marks the clearance variant."""
    solids = []
    half = M.simhat_pcb_w / 2 + clear

    for side in (-1, 1):
        u_out = side * (half + P.SIMHAT_ARM_T)
        u_in = side * half
        u_tip = side * (half - P.SIMHAT_HOOK_ENGAGE)
        u_far = side * (half + P.SIMHAT_ARM_T + 4.0)
        u_fin = side * (half + P.SIMHAT_ARM_T + 1.0)
        v_l0 = clear
        v_tip = clear + P.SIMHAT_HOOK_REACH_V
        v_root = v_tip - P.SIMHAT_ARM_LEN
        z_top = _clip_slab_top()
        z_bot = z_top - P.SIMHAT_ARM_W
        pts = [(u_out, v_root), (u_out, v_tip), (u_in, v_tip),
               (u_tip, v_tip), (u_tip, v_l0), (u_in, v_l0), (u_in, v_root)]
        arm = (cq.Workplane("XY")
               .polyline([(ox + u, oy + v) for u, v in pts]).close()
               .extrude(z_top - z_bot).translate((0, 0, z_bot)).val())
        half_env = M.simhat_pcb_w / 2 + clear
        undercut = cq.Solid.makeBox(
            2 * half_env, 400, simhat_pcb_top_z() + P.SIMHAT_PCB_T_CLEAR + 1,
            cq.Vector(ox - half_env, oy - 200, -1))
        arm = cq.Shape.cast(BRepAlgoAPI_Cut(arm.wrapped, undercut.wrapped).Shape())
        block = _rect(ox + min(u_in, u_far), oy + v_root - 4.0,
                      ox + max(u_in, u_far), oy + v_root + 2.5, 0, z_top)
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
        u = side * (half + P.SIMHAT_FENCE_T / 2)
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

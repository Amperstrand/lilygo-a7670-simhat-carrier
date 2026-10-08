"""Parametric Nucula enclosure shells (bottom + lid + calibration coupon).

Design rules honoured here (see docs/design_spec.md):
  * The routed gap edge (v = 73) is never clamped; two stop ribs locate the
    board against factory-routed edge windows between the remnant zones.
  * Nothing metal anywhere (snap-fit lid, plastic-only construction).
  * The NFC antenna rule areas and the ESP32 antenna zone carry structure
    only where the reference model proves bare laminate.
  * The calibration coupon calls the SAME builders as the production parts
    (lip bite bay, wire-lane slits, pop-out bridge, thickness stairs).
"""

from __future__ import annotations

import cadquery as cq

from . import parameters as P
from .parameters import D, Measured

BT = P.PCB_SUPPORT_H + Measured.board_t          # board top face z
LID_Z0 = D["lid_int_z"]                          # lid interior face
ROOF_TOP = LID_Z0 + P.ROOF_T                     # general lid outer face

# interior cavity (board-local)
INT_U0, INT_U1 = -1.20, 60.35
INT_V0 = -0.35


def end_v(mode: str) -> float:
    """Interior end wall face (v).
    main: routed cut edge + remnant band + wire-drop channel.
    full: factory board edge (v=110) + single-file wire channel (2.0 mm)."""
    if mode == "full":
        return Measured.board_l_full + 2.0
    return D["end_wall_inner_v"]


def outer_rect(mode: str):
    """Exterior XY rectangle of the shell."""
    return (INT_U0 - P.WALL_T, INT_V0 - P.WALL_T,
            INT_U1 + P.WALL_T, end_v(mode) + P.WALL_T)


def _box(x0, y0, x1, y1, z0, z1):
    if x1 <= x0 or y1 <= y0 or z1 <= z0:
        return None
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(x, y, r, z0, z1):
    if r <= 0 or z1 <= z0:
        return None
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(x, y, z0))


def _fuse_all(solids):
    out = None
    for s in solids:
        if s is None:
            continue
        out = s if out is None else out.fuse(s)
    return out


def _cut_all(solid, cutters):
    for c in cutters:
        if c is not None:
            solid = solid.cut(c)
    return solid


# ---------------------------------------------------------------------------
# shared production features (used by shells AND the coupon)
# ---------------------------------------------------------------------------

def snap_tab_solid(side: str, v: float):
    """Wall snap tab (protrudes inward, catches a notch in the lid lip)."""
    if side == "left":
        return _box(INT_U0, v - 3.0, INT_U0 + 0.60, v + 3.0, LID_Z0 - 1.2, LID_Z0 - 0.2)
    return _box(INT_U1 - 0.60, v - 3.0, INT_U1, v + 3.0, LID_Z0 - 1.2, LID_Z0 - 0.2)


def popout_panel(window, z0, t=None, bridges=4):
    """A pop-out panel bridging a rectangular window (u0, v0, u1, v1).

    Printed flat (this face is the bed face when the lid prints
    exterior-down).  Perimeter bridges of SCREEN_BRIDGE_W keep it attached;
    a pick notch (1.6 x 0.9) is cut into one bridge, interior side.
    Shared with the coupon's bridge-feel bay.
    """
    t = t or P.SCREEN_POP_T
    u0, v0, u1, v1 = window
    panel = _box(u0, v0, u1, v1, z0, z0 + t)
    cutters = []
    bw = P.SCREEN_BRIDGE_W
    b = max(2, bridges)
    for i in range(b):
        x = u0 + (u1 - u0) * (i + 1) / (b + 1)
        cutters.append(_box(x - 1, v0, x + 1, v0 + bw, z0 - 1, z0 + t + 1))
        cutters.append(_box(x - 1, v1 - bw, x + 1, v1, z0 - 1, z0 + t + 1))
    for i in range(b):
        y = v0 + (v1 - v0) * (i + 1) / (b + 1)
        cutters.append(_box(u0, y - 1, u0 + bw, y + 1, z0 - 1, z0 + t + 1))
        cutters.append(_box(u1 - bw, y - 1, u1, y + 1, z0 - 1, z0 + t + 1))
    c = 0.8
    for cx in (u0, u1 - c):
        for cy in (v0, v1 - c):
            cutters.append(_box(cx, cy, cx + c, cy + c, z0 - 1, z0 + t + 1))
    mid = (u0 + u1) / 2.0
    cutters.append(_box(mid - 0.8, v1 - bw - 1.6, mid + 0.8, v1, z0 - 1, z0 + t + 1))
    return _cut_all(panel, cutters)


# retention lips: segments per edge (None -> extend to the cavity end)
LEFT_LIP_SEGS = [(INT_V0, 46.5), (69.3, None)]
RIGHT_LIP_SEGS = [(INT_V0, 44.0), (68.5, None)]
STOP_RIBS_U = [(22.0, 26.5), (33.5, 43.5)]
SNAP_TABS = [("left", 15.0), ("left", 30.0), ("right", 15.0), ("right", 38.0)]


# ---------------------------------------------------------------------------
# bottom shell
# ---------------------------------------------------------------------------

def bottom_shell(mode: str):
    end = end_v(mode)
    ox0, oy0, ox1, oy1 = outer_rect(mode)
    cx, cy = (ox0 + ox1) / 2.0, (oy0 + oy1) / 2.0

    # walls only: block from the general floor bottom up, cavity cut through
    walls = (
        cq.Workplane("XY", origin=(cx, cy, -P.FLOOR_T))
        .rect(ox1 - ox0, oy1 - oy0).extrude(LID_Z0 + P.FLOOR_T)
        .edges("|Z").fillet(P.CORNER_R)
    ).val()
    cavity = _box(INT_U0, INT_V0, INT_U1, end, -P.FLOOR_T - 0.01, LID_Z0 + 5)
    solid = walls.cut(cavity)

    # floor slab minus battery pocket
    floor = _box(INT_U0, INT_V0, INT_U1, end, -P.FLOOR_T, 0.0)
    pu0, pu1 = D["pocket_u"]
    pv0, pv1 = D["pocket_v"]
    floor = floor.cut(_box(pu0, pv0, pu1, pv1, D["pocket_z_bot"] - 0.5, 0.5))
    solid = solid.fuse(floor)

    # battery bump under the pocket (2 mm skirt)
    bump = _box(pu0 - 2.0, pv0 - 2.0, pu1 + 2.0, pv1 + 2.0,
                D["case_z_min"], D["pocket_z_bot"] + 0.01)
    solid = solid.fuse(bump)

    # under-board corner support pads (bare-laminate voids)
    pads = []
    if mode == "main":
        cs = [(2.2, 2.2), (57.8, 2.2), (2.2, end - 5.3), (57.8, end - 5.3)]
    else:
        cs = [(2.2, 2.2), (57.8, 2.2),
              (2.2, Measured.board_l_full - 2.2), (57.8, Measured.board_l_full - 2.2)]
    for cx, cy in cs:
        pads.append(_cyl(cx, cy, 2.0, 0.0, P.PCB_SUPPORT_H - 0.15))
    solid = solid.fuse(_fuse_all(pads))

    # retention lips on the three factory edges (never the cut edge)
    lips = []
    lips.append(_box(INT_U0, INT_V0, INT_U1, INT_V0 + P.RAIL_LIP_OVERHANG,
                     BT, BT + P.RAIL_LIP_T))
    for v0, v1 in LEFT_LIP_SEGS:
        v1 = end if v1 is None else v1
        lips.append(_box(INT_U0, v0, P.RAIL_LIP_OVERHANG, v1, BT, BT + P.RAIL_LIP_T))
    for v0, v1 in RIGHT_LIP_SEGS:
        v1 = end if v1 is None else v1
        lips.append(_box(INT_U1 - P.RAIL_LIP_OVERHANG, v0, INT_U1, v1,
                         BT, BT + P.RAIL_LIP_T))
    solid = solid.fuse(_fuse_all(lips))

    # stop ribs: main mode locates the routed cut edge between remnant
    # windows; full mode locates the factory board edge at v=110
    if mode == "main":
        ribs = [_box(u0, Measured.MAIN_V_END + P.STOP_RIB_GAP, u1, end, 0.0, BT + 0.6)
                for u0, u1 in STOP_RIBS_U]
    else:
        ribs = [_box(u0, Measured.board_l_full + P.STOP_RIB_GAP, u1, end, 0.0, BT + 0.6)
                for u0, u1 in [(4.0, 16.0), (45.0, 56.0)]]
    solid = solid.fuse(_fuse_all(ribs))

    # battery pocket locator rim (notched where the wires return under board)
    rim_h = P.PCB_SUPPORT_H - 0.15
    rims = [
        _box(pu0 - 1.2, pv0 - 1.2, pu1 + 1.2, pv0, 0.0, rim_h),
        _box(pu0 - 1.2, pv0, pu0, pv1, 0.0, rim_h),
        _box(pu1, pv0, pu1 + 1.2, pv1, 0.0, rim_h),
        _box(pu0 - 1.2, pv1, 18.0, pv1 + 1.2, 0.0, rim_h),
        _box(21.6, pv1, pu1 + 1.2, pv1 + 1.2, 0.0, rim_h),
    ]
    solid = solid.fuse(_fuse_all(rims))

    # under-board edge locators in the USB / ESP32 zones (bare laminate);
    # the left one stays below the USB plug envelope (z < 1.0)
    solid = solid.fuse(_box(INT_U0, 57.0, -0.15, 66.0, 0.0, 0.85))
    solid = solid.fuse(_box(60.15, 50.0, INT_U1, 64.0, 0.0, rim_h))

    # snap tabs
    solid = solid.fuse(_fuse_all([snap_tab_solid(s, v) for s, v in SNAP_TABS]))

    # openings
    cutters = []
    ov0, ov1 = D["usb_open_v"]
    oz0, oz1 = D["usb_open_z"]
    cutters.append(_box(ox0 - 1, ov0, INT_U0 + 0.6, ov1, oz0, oz1))
    cutters.append(_box(ox0 - 1, ov0 - 0.5, INT_U0 - 0.3, ov1 + 0.5, oz0 - 0.5, oz1 + 0.5))
    sv0, sv1 = D["bat_slot_v"]
    sz0, sz1 = D["bat_slot_z"]
    cutters.append(_box(ox0 - 1, sv0, -0.05, sv1, sz0, sz1))
    # ESP32 antenna window: open slot in the right wall so the module
    # overhang clears and the antenna radiates through air, not plastic
    cutters.append(_box(60.20, 47.00, INT_U1 + P.WALL_T + 0.05, 65.30,
                        P.PCB_SUPPORT_H, 7.00))
    solid = _cut_all(solid, cutters)
    return solid


# ---------------------------------------------------------------------------
# lid
# ---------------------------------------------------------------------------

def screen_window_rect():
    """Window opening + glass rect for the vertical (v-long) glass.

    Glass 29.4 (u) x 57.5 (v), flex edge at v-max, u-centred on the DS1
    socket (u = 30).  Glass upper edge sits 0.4 past the routed cut edge
    INSIDE the lid (above the remnant channel, z 9.5.. - far above remnants).
    """
    gu0, gu1 = 30.0 - P.SCREEN_GLASS_L / 2.0, 30.0 + P.SCREEN_GLASS_L / 2.0
    gv0, gv1 = Measured.MAIN_V_END + 0.4 - P.SCREEN_GLASS_W, Measured.MAIN_V_END + 0.4
    m = 0.10   # glass fit slack: the window admits the whole glass outline
    win = (gu0 - m, gv0 - m, gu1 + m, gv1 + m)
    return win, (gu0, gv0, gu1, gv1)


def lid(variant: str, mode: str, screen_window: bool, led_window: bool = True,
        screen_popped: bool = False):
    end = end_v(mode)
    ox0, oy0, ox1, oy1 = outer_rect(mode)
    cx, cy = (ox0 + ox1) / 2.0, (oy0 + oy1) / 2.0

    roof = (
        cq.Workplane("XY", origin=(cx, cy, LID_Z0))
        .rect(ox1 - ox0, oy1 - oy0).extrude(P.ROOF_T)
        .edges("|Z").fillet(P.CORNER_R)
    ).val()

    # lip dropping inside the walls (shear fit)
    lip_u0, lip_v0 = INT_U0 + P.LID_SHEAR_PLAY, INT_V0 + P.LID_SHEAR_PLAY
    lip_u1, lip_v1 = INT_U1 - P.LID_SHEAR_PLAY, end - P.LID_SHEAR_PLAY
    lip = _box(lip_u0, lip_v0, lip_u1, lip_v1, LID_Z0 - P.LID_LIP_ENGAGE, LID_Z0)
    lip = _cut_all(lip, [_box(lip_u0 + 1.2, lip_v0 + 1.2, lip_u1 - 1.2, lip_v1 - 1.2,
                              LID_Z0 - P.LID_LIP_ENGAGE - 1, LID_Z0 + 1)])
    if mode == "full":
        # open the lip's end wall over the J3 blister zone so a future
        # keypad header can be fitted through the hatch
        lip = _cut_all(lip, [_box(16.0, end - P.LID_LIP_ENGAGE - 0.2, 44.0, end + 1,
                                  LID_Z0 - P.LID_LIP_ENGAGE - 1, LID_Z0 + 1)])
    # break the lip's left run across the battery slot + USB opening so the
    # plug and the J2 service access stay unobstructed (full lip thickness)
    lip = _cut_all(lip, [_box(INT_U0 - 0.05, 46.5, INT_U0 + 1.45,
                              69.3, LID_Z0 - P.LID_LIP_ENGAGE - 1, LID_Z0 + 1)])
    solid = roof.fuse(lip)

    # snap-tab notches in the lip
    notch = []
    for side, v in SNAP_TABS:
        if side == "left":
            notch.append(_box(INT_U0 + 0.15, v - 3.2, INT_U0 + 0.95, v + 3.2,
                              LID_Z0 - P.LID_LIP_ENGAGE - 0.1, LID_Z0 + 1))
        else:
            notch.append(_box(INT_U1 - 0.95, v - 3.2, INT_U1 - 0.15, v + 3.2,
                              LID_Z0 - P.LID_LIP_ENGAGE - 0.1, LID_Z0 + 1))
    solid = _cut_all(solid, notch)

    # button ports (RESET + BOOT): through-hole + molded fixed plunger
    # (plastic plunger, 0.30 above the B3U actuator; recovery use)
    plunger_parts, bcut = [], []
    for cx, cy in (Measured.SW1_C, Measured.SW2_C):
        bcut.append(_cyl(cx, cy, P.BUTTON_HOLE_D / 2.0, LID_Z0 - 0.3, ROOF_TOP + 2))
        rod_top = ROOF_TOP + 1.2
        plunger_parts.append(_cyl(cx, cy, P.BUTTON_PLUNGER_D / 2.0,
                                  BT + P.comp_height("SW1") + P.BUTTON_PLUNGER_GAP,
                                  rod_top))
        # three moulding spokes at the hole rim keep the plunger fixed
        plunger_parts.append(_box(cx - 1.7, cy - 0.25, cx + 1.7, cy + 0.25,
                                  ROOF_TOP - 0.6, ROOF_TOP))
        plunger_parts.append(_box(cx - 0.25, cy - 1.7, cx + 0.25, cy + 1.7,
                                  ROOF_TOP - 0.6, ROOF_TOP))
    solid = _cut_all(solid, bcut)
    solid = solid.fuse(_fuse_all(plunger_parts))

    if led_window:
        solid = solid.cut(_cyl(Measured.D3_C[0], Measured.D3_C[1], P.LED_HOLE_D / 2.0,
                               LID_Z0 - 0.4, ROOF_TOP + 2))

    if screen_window:
        win, _glass = screen_window_rect()
        wu0, wv0, wu1, wv1 = win
        deck_top = LID_Z0 + P.SCREEN_GLASS_T + P.SCREEN_RECESS_CLEAR \
            + P.SCREEN_POP_T + 0.60
        ring_u0, ring_v0 = 13.8, 14.9
        ring_u1, ring_v1 = 46.2, min(end - 0.8, 74.5)
        ring = _box(ring_u0, ring_v0, ring_u1, ring_v1, ROOF_TOP - 0.01, deck_top)
        ring = _cut_all(ring, [_box(wu0, wv0, wu1, wv1, ROOF_TOP - 1, deck_top + 1)])
        solid = solid.fuse(ring)
        solid = solid.cut(_box(wu0, wv0, wu1, wv1, LID_Z0 - 1, ROOF_TOP + 1))
        if not screen_popped:
            panel = popout_panel(window=win, z0=deck_top - P.SCREEN_POP_T,
                                 t=P.SCREEN_POP_T)
            solid = solid.fuse(panel)
        if led_window:
            # the LED sits inside the deck ring: re-cut the light hole
            # through ring + roof so it stays visible in the popout lid
            solid = solid.cut(_cyl(Measured.D3_C[0], Measured.D3_C[1],
                                   P.LED_HOLE_D / 2.0, LID_Z0 - 0.4, deck_top + 2))

    if variant == "kb_blister" and mode == "full":
        bz = D["kb_blister_z"]                       # interior ceiling 12.7
        b_outer = bz + P.KB_BLISTER_WALL             # 13.9
        bu0, bu1 = 15.5, 44.5
        bv0, bv1 = 102.5, end + P.WALL_T + 0.01
        blister = _box(bu0, bv0, bu1, bv1, ROOF_TOP - 0.01, b_outer)
        # hollow the blister interior (walls + roof remain)
        blister = _cut_all(blister, [
            _box(bu0 + 1.2, bv0 + 1.2, bu1 - 1.2, bv1 - 1.2, ROOF_TOP - 0.02, bz + 1)])
        solid = solid.fuse(blister)
        # open the general roof + lip under the blister interior
        solid = _cut_all(solid, [
            _box(bu0 + 1.2, bv0 + 1.2, bu1 - 1.2, bv1 - 1.2, LID_Z0 - 1, ROOF_TOP + 1)])
        # hatch panel in the blister roof (flush with its outer face)
        hatch = popout_panel(window=(17.0, 104.7, 43.0, end - 0.15),
                             z0=b_outer - P.SCREEN_POP_T, t=P.SCREEN_POP_T)
        solid = solid.fuse(hatch)
    return solid


# ---------------------------------------------------------------------------
# calibration coupon (V0) - reuses production builders and parameters
# ---------------------------------------------------------------------------

def coupon():
    H = 3.2
    body = _box(0, 0, 150, 44, 0, H)

    # A: pilot-hole ladder for self-tapping posts (M2 probes)
    for i, d in enumerate(P.COUPON_HOLE_LADDER):
        body = body.cut(_cyl(6 + 6.0 * i, 22, d / 2.0, -1, H + 1))

    # B: board-thickness stairs (tunnels of height t, 2.2 below the top)
    for i, t in enumerate(P.COUPON_THICK_STAIRS):
        body = body.cut(_box(32, 3 + 10 * i, 54, 9 + 10 * i, H - 2.2, H - 2.2 + t))

    # C: lip-bite bay - the production edge relationship (rail face + lip
    # overhang pressing a 1.6 mm board).  Uses RAIL_LIP_OVERHANG / _T.
    wall = _box(88, 8, 90.2, 36, 0, BT + P.RAIL_LIP_T)
    slot = _box(78, 17, 88.01, 17 + Measured.board_t, P.PCB_SUPPORT_H, BT)
    ledge = _box(78, 17, 88.01, 17 + Measured.board_t, 0, P.PCB_SUPPORT_H)
    lip = _box(88 - P.RAIL_LIP_OVERHANG, 12, 90.2, 32, BT, BT + P.RAIL_LIP_T)
    body = body.fuse(wall).fuse(lip)
    body = body.cut(slot)          # board slot (ledge stays below)

    # D: wire-lane clearance slit ladder (0.3..0.6 mm tunnels)
    for i, s in enumerate(P.COUPON_SLIT_LADDER):
        body = body.cut(_box(92 + 7 * i, 10, 96 + 7 * i, 34, 1.0, 1.0 + s))

    # E: pop-out bridge feel bay (same builder as the screen hatch)
    frame = _box(122, 6, 148, 30, 0, 2.6)
    frame = frame.cut(_box(124, 8, 146, 28, -1, 3))
    panel = popout_panel(window=(124, 8, 146, 28), z0=1.6, t=P.SCREEN_POP_T, bridges=3)
    body = body.fuse(frame).fuse(panel)
    return body

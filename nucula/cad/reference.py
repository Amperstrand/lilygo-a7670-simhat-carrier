"""Mechanical reference model of the Nucula board (truth model).

Everything here is built from Measured geometry (KiCad extraction) plus
component height provenance.  The enclosure consumes these solids for
boolean validation; the reference model is never edited by hand.

All solids live in the enclosure coordinate system:
  u, v = board-local mm (KiCad axes preserved, origin at KiCad 50,50)
  z = 0 at the enclosure floor top; PCB bottom face at PCB_SUPPORT_H.
"""

from __future__ import annotations

import os

import cadquery as cq

from . import parameters as P
from .parameters import D, Measured

BOARD_TOP = P.PCB_SUPPORT_H + Measured.board_t   # z of the board top face


# ---------------------------------------------------------------------------
# outline helpers
# ---------------------------------------------------------------------------

def _poly_solid(points, z0, z1):
    w = (
        cq.Workplane("XY", origin=(0, 0, z0))
        .polyline(points).close()
        .extrude(z1 - z0)
    )
    return w.val()


def board_outline(mode: str):
    """Return (outer_pts, [hole_pts, ...]) for 'main' or 'full'."""
    if mode == "main":
        return Measured.main_outline, []
    return Measured.outline, Measured.inner_cutouts


def board_solid(mode: str):
    outer, holes = board_outline(mode)
    w = (
        cq.Workplane("XY", origin=(0, 0, P.PCB_SUPPORT_H))
        .polyline(outer).close()
        .extrude(Measured.board_t)
    )
    for h in holes:
        w = w.cut(
            cq.Workplane("XY", origin=(0, 0, P.PCB_SUPPORT_H - 1))
            .polyline(h).close().extrude(Measured.board_t + 2)
        )
    return w.val()


# ---------------------------------------------------------------------------
# component solids
# ---------------------------------------------------------------------------

def _box(x0, y0, x1, y1, z0, z1):
    if x1 <= x0 or y1 <= y0 or z1 <= z0:
        return None
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _place_esp32():
    """Repo STEP model placed with the KiCad footprint transform.

    Model local (sx, sy, sz) -> enclosure (47.9 + sy, 56.14 + sx, BOARD_TOP + sz).
    (Equivalent to KiCad's Y-mirror convention + rot -90; verified against the
    footprint pad rows and the edge notch: the antenna section overhangs the
    notch at u 54.9..60.6.)
    """
    path = Measured.ESP_STEP
    solid = cq.importers.importStep(path).val()
    solid = solid.mirror("XZ")                      # y -> -y  (KiCad convention)
    solid = solid.rotate((0, 0, 0), (0, 0, 1), 90)  # (x, -y) -> (y, x)
    solid = solid.translate(cq.Vector(47.9, 56.14, BOARD_TOP))
    return solid


def component_solids(mode: str, kb_header_fitted: bool = False) -> dict:
    """Conservative envelope solids for every placed footprint.

    Box = pads+courtyard bbox (extracted) x provenance height.  Overstates
    most parts by design (courtyards include placement margins) which makes
    every downstream clearance check conservative.
    """
    out = {}
    bt = BOARD_TOP
    for ref, fp in Measured.comps.items():
        bb = fp["bbox_local_uv"]
        if not bb:
            continue
        x0, y0, x1, y1 = bb
        if ref in ("MB1", "MB2"):
            continue  # board-only mouse-bite footprints, no body
        if mode == "main" and y0 >= Measured.MAIN_V_END and ref not in ("J4",):
            continue  # keyboard-section parts absent after breakaway
        if ref == "U3":
            out[ref] = _place_esp32()
            continue
        if ref == "A1":
            # the NFC coil is etched copper: a 35 um plate on the board top,
            # at the measured 40x40 copper extent (not the courtyard)
            cx, cy = Measured.COIL_C
            h2 = Measured.COIL_SIZE / 2.0
            out[ref] = _box(cx - h2, cy - h2, cx + h2, cy + h2, bt, bt + 0.035)
            continue
        if ref == "J1":
            # body only; the mating envelope is a separate solid
            # USB4105: 8.94 wide (v) x 7.35 long (u) x 3.31 tall, top mount,
            # mating face ~0.8 mm past the board edge (shell lands overhang).
            out[ref] = _box(-0.80, 56.42, 6.55, 67.36, bt, bt + P.comp_height("J1"))
            continue
        if ref == "J2":
            # JST PH SM4-TB housing: body u 2.39..7.61 x v 46.82..54.98,
            # rear wire-exit tunnel u 7.61..10.0 x v 49.14..52.66 (silk),
            # height 5.6 (JST drawing).  Wires exit +u at ~2.0 above board top.
            body = _box(2.39, 46.82, 10.00, 54.98, bt, bt + P.comp_height("J2"))
            out[ref] = body
            continue
        if ref in ("J3", "J4", "J5"):
            h = P.KB_HEADER_H if (ref == "J3" and kb_header_fitted) else 0.0
            if h <= 0:
                continue  # DNP and unfitted: pads only, nothing above the board
            out[ref] = _box(x0, y0, x1, y1, bt, bt + h)
            continue
        h = P.comp_height(ref)
        out[ref] = _box(x0, y0, x1, y1, bt, bt + h)
    return out


# ---------------------------------------------------------------------------
# keep-outs and service envelopes (solids for boolean validation)
# ---------------------------------------------------------------------------

def nfc_keepout():
    """Everything metal is banned inside the PCB's own antenna rule areas,
    extruded through the full enclosure height."""
    u0, u1, v0, v1 = Measured.NFC_RULE
    return _box(u0, v0, u1, v1, -50, 200)


def esp32_antenna_keepout():
    """Antenna trace zone (u 54.9..60.6, v 47.14..65.14 from the placed STEP)
    plus lateral margin; full height.  Plastic is allowed, metal is not.
    u0 = trace - 2.9 mm; chosen so the placeholder battery clears it."""
    return _box(52.0, 44.0, 61.5, 68.34, -50, 200)


def usb_mating_envelope():
    """Plug + overmold + cable-bend service void, u-negative of the mating
    face.  Zero enclosure material allowed inside (except the floor relief
    channel which is subtracted from the envelope here)."""
    u_face = D["usb_mating_u"]                       # -0.8
    v0, v1 = D["usb_open_v"]
    z0, z1 = D["usb_open_z"]
    env = _box(u_face - P.USB_PLUG_REACH, v0, u_face + 1.0, v1, z0, z1)
    # the floor relief channel under the plug is INTENDED enclosure material
    relief = _box(u_face - P.USB_PLUG_REACH, v0, -P.WALL_T, v1, z0, P.PCB_SUPPORT_H - 0.35)
    if relief is not None:
        env = env.cut(relief)
    return env


def battery_solid():
    u0, u1 = D["battery_u"]
    v0, v1 = D["battery_v"]
    z1 = D["pocket_z_top"]
    z0 = z1 - P.BATTERY_T
    return _box(u0, v0, u1, v1, z0, z1)


def battery_wire_sweep(mode: str = "main"):
    """Swept capsules for the two battery wires (parametric routes).
    main: J2 rear exit -> corridor -> z-7 lane -> drop through the remnant
    channel past the routed cut edge -> under-board -> battery.
    full: same exit and lane, then the full board length at z 7.0, dropping
    through the factory-edge channel at v=110."""
    r = P.WIRE_SWEEP_R
    routes = ((P.WIRE_ROUTE_A, P.WIRE_ROUTE_B) if mode == "main"
              else (P.WIRE_ROUTE_A_FULL, P.WIRE_ROUTE_B_FULL))
    solid = None
    for route in routes:
        for a, b in zip(route[:-1], route[1:]):
            seg = _capsule(a, b, r)
            solid = seg if solid is None else solid.fuse(seg)
    return solid


def _capsule(a, b, r):
    va = cq.Vector(*a)
    vb = cq.Vector(*b)
    seg = vb.sub(va)          # direction a -> b
    L = seg.Length
    if L < 1e-6:
        return cq.Solid.makeSphere(r, va, angleDegrees1=-90, angleDegrees2=90)
    cyl = cq.Solid.makeCylinder(r, L, va, seg.normalized())
    s1 = cq.Solid.makeSphere(r, va, angleDegrees1=-90, angleDegrees2=90)
    s2 = cq.Solid.makeSphere(r, vb, angleDegrees1=-90, angleDegrees2=90)
    return cyl.fuse(s1).fuse(s2)


# ---------------------------------------------------------------------------
# retention-safe laminate analysis
# ---------------------------------------------------------------------------

def bare_laminate_zones(mode: str):
    """Board XY regions where NOTHING sits on the top face and the bottom
    face is bare - candidate support/locator zones.  Returned as list of
    (u0, v0, u1, v1) probe rectangles used by validate.py."""
    zones = {
        # left edge strip under the USB connector (bottom bare, top: J1 only)
        "left_usb_strip": (0.0, 55.0, 2.0, 68.0),
        # right edge strip in the ESP32 zone (bottom bare)
        "right_esp_strip": (58.0, 45.0, 60.0, 67.0),
        # cut-edge strip between remnant zones
        "cut_edge_mid": (16.0, 71.5, 26.5, 73.0),
        "cut_edge_mid2": (33.5, 71.5, 44.0, 73.0),
    }
    return zones

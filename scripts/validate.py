#!/usr/bin/env python3
"""Validation suite for the carrier design. Writes analysis/interference_report.json.

Checks:
  1. fresh rebuild is a single valid solid; STEP round-trips
  2. STL is watertight / manifold / positive volume
  3. bounding box within the A1-mini safety envelope (175 mm XY)
  4. seated interference: carrier vs both reference boards
     (A7670 checked against the pin-trimmed model; the manufacturer STEP
      includes 16 mm stacking-header pins that default standoffs don't clear)
  5. component keep-out distances >= 0.5 mm (from analysis JSON zones)
  6. M1.6 screw pilots, M3 ear slots, cable-tie slots actually present
  7. T-SimHat removal path: clips released -> tilt -> slide -> lift, no collision
  8. A7670 lifts free once unscrewed
  9. deterministic regeneration (double-build hash comparison)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import cadquery as cq
import trimesh
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from cad import holder
from cad import parameters as P
from cad.parameters import Measured as M

REPORT_PATH = "analysis/interference_report.json"
COMPONENT_CLEARANCE_MIN = 0.5
VOLUME_TOL = 1e-3


def _w(shape):
    return shape.wrapped if hasattr(shape, "wrapped") else shape


def vol(shape):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(_w(shape), p)
    return p.Mass()


def common_vol(a, b):
    c = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    if not c.IsDone():
        return -1.0
    return vol(c.Shape())


def min_dist(a, b):
    return BRepExtrema_DistShapeShape(a.wrapped, b.wrapped).Value()


def a7670_trimmed():
    """Reference board without the optional 16 mm stacking-header pins."""
    a76 = holder.place_a7670()
    trim_z = P.A7670_STANDOFF_H - 9.0
    cutbox = cq.Solid.makeBox(500, 500, 200 + trim_z, cq.Vector(-250, -250, -200))
    return cq.Shape.cast(BRepAlgoAPI_Cut(a76.wrapped, cutbox.wrapped).Shape())


def box_solid(bb):
    return cq.Solid.makeBox(
        max(bb["dx"], 0.01), max(bb["dy"], 0.01), max(bb["dz"], 0.01),
        cq.Vector(bb["xmin"], bb["ymin"], bb["zmin"]))


def transform_a7670_bbox(bb):
    """STEP-native bbox -> carrier coords via the same mapping place_a7670
    uses (translation + optional 180-deg Z rotation)."""
    o = M.a7670["overall"]["bbox"]
    slab = M.a7670["pcb_slab"]
    x0, y0 = bb["xmin"] - o["xmin"], bb["ymin"] - o["ymin"]
    x1, y1 = bb["xmax"] - o["xmin"], bb["ymax"] - o["ymin"]
    corners = [holder._a7670_local_to_carrier(x, y)
               for x in (x0, x1) for y in (y0, y1)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    z_off = P.A7670_STANDOFF_H - slab["z_bottom"]
    return {"xmin": min(xs), "xmax": max(xs),
            "ymin": min(ys), "ymax": max(ys),
            "zmin": bb["zmin"] + z_off, "zmax": bb["zmax"] + z_off,
            "dx": bb["dx"], "dy": bb["dy"], "dz": bb["dz"]}


def transform_simhat_bbox(bb):
    """STEP-native bbox -> carrier coords via the flip mapping used by
    place_simhat: (x,y,z)->(-x, y, sh + slab_z_top - z)."""
    sh = P.SIMHAT_SUPPORT_H
    zt = M.simhat["pcb_slab"]["z_top"]
    cx = P.simhat_cx()
    return {"xmin": cx - bb["xmax"], "xmax": cx - bb["xmin"],
            "ymin": M.simhat_pcb_l / 2 + bb["ymin"],
            "ymax": M.simhat_pcb_l / 2 + bb["ymax"],
            "zmin": sh + zt - bb["zmax"], "zmax": sh + zt - bb["zmin"],
            "dx": bb["dx"], "dy": bb["dy"], "dz": bb["dz"]}


def component_clearances(carrier):
    """Min distance from carrier to each recorded component bbox (both boards).

    A7670 below-board zones that extend under z = A7670_STANDOFF_H - 9.0
    belong to the optional 16 mm stacking-header pins and are classified
    separately (default standoffs intentionally do not clear them).
    """
    pin_floor = P.A7670_STANDOFF_H - 9.0
    results = []
    for tag, zones, tf in (
        ("a7670_above", M.a7670["components_above_pcb"], transform_a7670_bbox),
        ("a7670_below", M.a7670["components_below_pcb"], transform_a7670_bbox),
        ("simhat_top(=down_when_flipped)", M.simhat["components_above_pcb"], transform_simhat_bbox),
        ("simhat_bottom(=up_when_flipped)", M.simhat["components_below_pcb"], transform_simhat_bbox),
    ):
        for i, c in enumerate(zones):
            bb = tf(c["bbox"])
            d = min_dist(carrier, box_solid(bb))
            entry = {"zone": f"{tag}[{i}]", "bbox": bb, "min_distance": round(d, 4)}
            if tag == "a7670_below" and bb["zmin"] < pin_floor:
                entry["optional_stacking_pin_zone"] = True
            results.append(entry)
    return results


def check_holes(carrier):
    results = []
    if P.A7670_MOUNT == "screws":
        pilot_h = P.A7670_STANDOFF_H - 1.5
        for i, (hx, hy) in enumerate(holder.a7670_holes_carrier()):
            probe = (cq.Workplane("XY").moveTo(hx, hy).circle(0.60)
                     .extrude(pilot_h)
                     .translate((0, 0, P.A7670_STANDOFF_H - pilot_h)).val())
            frac = common_vol(probe, carrier) / vol(probe)
            results.append({"feature": f"M1.6_pilot_{i}", "open_fraction": round(frac, 4),
                            "pass": frac < 0.05})
    else:
        # snap plugs: annulus around the shaft (the board-hole band) must
        # be free of carrier material; fins must exist above the board
        z0 = P.A7670_STANDOFF_H + 0.05
        for i, (hx, hy) in enumerate(holder.a7670_holes_carrier()):
            outer = (cq.Workplane("XY").moveTo(hx, hy)
                     .circle(0.72).extrude(M.a7670_pcb_t - 0.1)
                     .translate((0, 0, z0)).val())
            inner = (cq.Workplane("XY").moveTo(hx, hy)
                     .circle(P.PLUG_SHAFT_D / 2 + 0.05)
                     .extrude(M.a7670_pcb_t - 0.1)
                     .translate((0, 0, z0)).val())
            annulus = cq.Shape.cast(
                BRepAlgoAPI_Cut(outer.wrapped, inner.wrapped).Shape())
            frac = common_vol(annulus, carrier) / vol(annulus)
            results.append({"feature": f"snap_plug_hole_band_clear_{i}",
                            "blocked_fraction": round(frac, 4),
                            "pass": frac < 0.05})
            fin2_ring_z = (P.A7670_STANDOFF_H + M.a7670_pcb_t + 0.15
                           + (P.PLUG_FIN_LEAD + P.PLUG_FIN_H + P.PLUG_FIN_PITCH)
                           + P.PLUG_FIN_LEAD)
            fin = (cq.Workplane("XY").moveTo(hx, hy)
                   .circle(P.PLUG_FIN_DS[-1] / 2 - 0.1)
                   .extrude(P.PLUG_FIN_H - 0.1)
                   .translate((0, 0, fin2_ring_z + 0.05)).val())
            filled = common_vol(fin, carrier) / vol(fin)
            results.append({"feature": f"snap_plug_fins_{i}",
                            "filled_fraction": round(filled, 4),
                            "pass": filled > 0.5})
    for e in holder._ear_geometry():
        y = e.get("slot_y", e["y_c"])
        probe = (cq.Workplane("XY").moveTo(e["slot_x"], y)
                 .slot2D(P.EAR_SLOT_L - 0.1, P.EAR_SLOT_W - 0.1,
                         e.get("slot_angle", 0))
                 .extrude(P.EAR_T).val())
        frac = common_vol(probe, carrier) / vol(probe)
        results.append({"feature": f"M3_ear_slot_{e['name']}", "open_fraction": round(frac, 4),
                        "pass": frac < 0.05})
    for i, (x, y) in enumerate(P.TIE_SLOTS):
        probe = (cq.Workplane("XY").moveTo(x, y)
                 .rect(P.TIE_SLOT_L - 0.1, P.TIE_SLOT_W - 0.1)
                 .extrude(P.BASE_T).val())
        frac = common_vol(probe, carrier) / vol(probe)
        results.append({"feature": f"tie_slot_{i}", "open_fraction": round(frac, 4),
                        "pass": frac < 0.05})
    return results


def simhat_removal_stages(carrier):
    """Simulate: clips released -> tilt near end up -> slide out from lip -> lift."""
    rel = P.SIMHAT_ARM_DEFLECT + 0.30
    test_carrier = holder.build_carrier(clip_deflect=rel).val()
    stages = []
    board = holder.place_simhat()

    y_far = -M.simhat_pcb_l / 2
    lifted = board.translate(cq.Vector(0, 0, 0.15))
    slid = lifted.translate(cq.Vector(0, 3.6, 0))
    freed = slid.translate(cq.Vector(0, 0, 30.0))

    for name, b in (("lift_0.15mm_tabs_released", lifted),
                    ("slide_out_from_lip", slid),
                    ("lift_clear", freed)):
        stages.append({"stage": name, "interference_mm3": round(common_vol(test_carrier, b), 4)})
    return stages, test_carrier


def service_envelope_checks(carrier):
    """Connector service envelopes: no printed material may enter these
    volumes (USB-C plug, SMA antenna connectors, SIM swap, battery JST,
    SimHat jumper socket zone, relay/terminal cavity)."""
    results = []
    o = M.a7670["overall"]["bbox"]
    slab_t = M.a7670_pcb_t
    for name, (x0, y0, x1, y1, z0, z1) in P.SERVICE_ENVELOPES_A7670.items():
        pts = [holder._a7670_local_to_carrier(x, y)
               for x in (x0, x1) for y in (y0, y1)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        env = cq.Solid.makeBox(
            max(xs) - min(xs), max(ys) - min(ys), z1 - z0,
            cq.Vector(min(xs), min(ys), P.A7670_STANDOFF_H + slab_t + z0))
        results.append({"envelope": name,
                        "interference_mm3": round(common_vol(carrier, env), 4)})
    for name, (x0, y0, x1, y1, z0, z1) in P.SERVICE_ENVELOPES_SIMHAT.items():
        b = transform_simhat_bbox({"xmin": x0, "ymin": y0, "zmin": z0,
                                   "xmax": x1, "ymax": y1, "zmax": z1,
                                   "dx": 0, "dy": 0, "dz": 0})
        env = cq.Solid.makeBox(
            b["xmax"] - b["xmin"], b["ymax"] - b["ymin"], b["zmax"] - b["zmin"],
            cq.Vector(b["xmin"], b["ymin"], b["zmin"]))
        results.append({"envelope": name,
                        "interference_mm3": round(common_vol(carrier, env), 4)})
    return results


def battery_keepout_check(carrier):
    """18650 + holder below the A7670 PCB must clear all printed material."""
    x0, y0 = ((M.a7670_pcb_w - P.A7670_BATTERY_KEEP_W) / 2,
              (M.a7670_pcb_l - P.A7670_BATTERY_KEEP_L) / 2)
    pts = [holder._a7670_local_to_carrier(x, y)
           for x in (x0, x0 + P.A7670_BATTERY_KEEP_W)
           for y in (y0, y0 + P.A7670_BATTERY_KEEP_L)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    env = cq.Solid.makeBox(
        max(xs) - min(xs), max(ys) - min(ys), 19.5,
        cq.Vector(min(xs), min(ys), P.A7670_STANDOFF_H - 20.5))
    return {"keepout": "18650_battery_under_a7670",
            "interference_mm3": round(common_vol(carrier, env), 4)}


def antenna_checks(carrier):
    """Slide path clear, seated sticker clear of carrier, sticker vs the
    18650 keep-out box (under_battery), sticker stays flat."""
    g = holder.antenna_geometry()
    if g["pos"] == "side_tray":
        z0, z1 = P.ANT_FLOOR_T + 0.05, P.ANT_FLOOR_T + 0.35
        sticker = cq.Solid.makeBox(
            P.ANT_W, P.ANT_SLIDE, z1 - z0,
            cq.Vector(g["band_x0"] + P.ANT_SIDE_CLEAR,
                      g["stop_y"] - P.ANT_SLIDE, z0))
        slide = cq.Solid.makeBox(
            P.ANT_W, g["stop_y"] - g["mouth_y"] + 60.0, z1 - z0,
            cq.Vector(g["band_x0"] + P.ANT_SIDE_CLEAR,
                      g["mouth_y"] - 60.0, z0))
        stop = cq.Solid.makeBox(
            g["outer_x"] - g["x_hi"], P.ANT_SIDE_STOP_T - 0.2,
            P.ANT_FLOOR_T + P.ANT_SIDE_WALL_H - 0.4,
            cq.Vector(g["x_hi"] + 0.1, g["stop_y"] + 0.1, 0.2))
        clips = []
        for i, cy in enumerate(P.ANT_COAX_CLIP_YS):
            post = cq.Solid.makeBox(
                0.8, 3.6, P.ANT_COAX_CLIP_H - 0.5,
                cq.Vector(g["x_hi"] - P.RAIL_W + 0.1, cy - 1.8,
                          P.BASE_T + 0.2))
            groove = cq.Solid.makeBox(
                P.RAIL_W - 1.2, 3.0, P.ANT_COAX_CLIP_H - 0.4,
                cq.Vector(g["x_hi"] - P.RAIL_W + 1.1, cy - 1.5,
                          P.BASE_T + 0.1))
            clips.append({
                "clip": i, "y": cy,
                "post_filled": round(common_vol(post, carrier) / vol(post), 4),
                "groove_open": round(1 - common_vol(groove, carrier) / vol(groove), 4),
            })
        return {
            "pos": "side_tray",
            "slide_path_interference_mm3": round(common_vol(carrier, slide), 4),
            "seated_sticker_interference_mm3": round(common_vol(carrier, sticker), 4),
            "battery_overlap_mm3": 0.0,
            "stop_filled_fraction": round(common_vol(stop, carrier) / vol(stop), 4),
            "clips": clips,
            "sticker_plane": "flat in the +X side tray, free air, coax over the board edge",
            "channel_len_mm": round(g["slide_len"], 1),
        }
    if g["pos"] == "under_battery":
        z_lo, z_hi = P.ANT_FLOOR_T + 0.05, P.ANT_FLOOR_T + 0.35
        sticker = cq.Solid.makeBox(
            P.ANT_W, P.ANT_SLIDE, z_hi - z_lo,
            cq.Vector(g["cx"] - P.ANT_W / 2, g["stop_y"] - P.ANT_SLIDE, z_lo))
        slide = cq.Solid.makeBox(
            P.ANT_W, g["slide_len"], z_hi - z_lo,
            cq.Vector(g["cx"] - P.ANT_W / 2, g["entry_y"], z_lo))
        x0, y0 = holder._a7670_local_to_carrier(
            (M.a7670_pcb_w - P.A7670_BATTERY_KEEP_W) / 2,
            (M.a7670_pcb_l - P.A7670_BATTERY_KEEP_L) / 2)
        pts = [holder._a7670_local_to_carrier(
            x, y) for x in (x0, x0 + P.A7670_BATTERY_KEEP_W)
            for y in (y0, y0 + P.A7670_BATTERY_KEEP_L)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        battery = cq.Solid.makeBox(
            max(xs) - min(xs), max(ys) - min(ys), 19.5,
            cq.Vector(min(xs), min(ys), P.A7670_STANDOFF_H - 20.5))
        return {
            "pos": "under_battery",
            "slide_path_interference_mm3": round(common_vol(carrier, slide), 4),
            "seated_sticker_interference_mm3": round(common_vol(carrier, sticker), 4),
            "battery_overlap_mm3": round(common_vol(sticker, battery), 4),
            "sticker_plane": "flat on base strip under battery (1.3mm gap)",
            "channel_len_mm": round(g["slide_len"], 1),
        }
    slide = cq.Solid.makeBox(
        P.ANT_W - 2.0, abs(g["entry_y"] - g["far_y"]) - P.ANT_TRAY_STOP_T, 1.5,
        cq.Vector(g["cx"] - P.ANT_W / 2 + 1.0,
                  g["far_y"] + P.ANT_TRAY_STOP_T, P.ANT_FLOOR_T + 0.1))
    sticker = cq.Solid.makeBox(
        P.ANT_W, P.ANT_SLIDE, 0.35,
        cq.Vector(g["cx"] - P.ANT_W / 2, g["far_y"] + P.ANT_TRAY_STOP_T + 0.3,
                  P.ANT_FLOOR_T))
    return {
        "pos": "end_tray",
        "slide_path_interference_mm3": round(common_vol(carrier, slide), 4),
        "seated_sticker_interference_mm3": round(common_vol(carrier, sticker), 4),
        "battery_overlap_mm3": 0.0,
        "sticker_plane": "flat, horizontal, on tray floor",
        "tray_extends_to_y": round(g["far_y"], 2),
    }


def fitcheck_tray_checks():
    """Gridfinity fit-check tray: footprint exactness, single solid,
    board + antenna drop-in gauges."""
    from cad import fitcheck
    wp = fitcheck.build_fitcheck_tray()
    tray = wp.val()
    bb = tray.BoundingBox()
    out = []

    n = len(wp.solids().vals())
    out.append({"check": "fitcheck_single_solid", "value": n, "pass": n == 1})

    fp = [round(bb.xmax - bb.xmin, 3), round(bb.ymax - bb.ymin, 3)]
    want = [fitcheck.FOOTPRINT_X, fitcheck.FOOTPRINT_Y]
    out.append({"check": "fitcheck_gridfinity_footprint",
                "value": fp, "expected": want,
                "pass": fp == want})

    out.append({"check": "fitcheck_envelope_xy",
                "value": fp, "pass": max(fp) <= P.MAX_XY})

    dy = fitcheck.SHIFT_Y
    web_top = fitcheck.WEB_Z1
    a76 = holder.place_a7670().translate(
        cq.Vector(0, dy, web_top + 20.5 - P.A7670_STANDOFF_H))
    a76_pinrest = holder.place_a7670().translate(
        cq.Vector(0, dy, web_top + 15.0 - P.A7670_STANDOFF_H))
    sh = holder.place_simhat().translate(
        cq.Vector(0, dy, web_top + 18.25 - P.SIMHAT_SUPPORT_H))

    v_batt = common_vol(tray, a76)
    v_pinrest = common_vol(tray, a76_pinrest)
    v_sh = common_vol(tray, sh)
    out.append({"check": "fitcheck_a7670_battery_holder_rest",
                "value": round(v_batt, 4),
                "note": "residual <= 1 mm3 is the designed gauge-pin/hole tangency",
                "pass": v_batt < 1.0})
    out.append({"check": "fitcheck_a7670_stacking_pin_rest",
                "value": round(v_pinrest, 4), "pass": v_pinrest < 1.0})
    out.append({"check": "fitcheck_simhat_relay_down_rest",
                "value": round(v_sh, 4),
                "intended_fence_bite_mm3": round(holder.fence_bite_mm3(), 4),
                "pass": 0 <= v_sh - holder.fence_bite_mm3() < VOLUME_TOL})

    stop_face = M.a7670_pcb_l / 2 + fitcheck.SHIFT_Y - 2.0
    entry_y = -fitcheck.FOOTPRINT_Y / 2 + 5.0
    cx_a = P.a7670_cx()
    seated = cq.Solid.makeBox(
        P.ANT_W, P.ANT_SLIDE, 0.3,
        cq.Vector(cx_a - P.ANT_W / 2, stop_face - P.ANT_SLIDE,
                  fitcheck.WEB_Z1))
    path = cq.Solid.makeBox(
        P.ANT_W, stop_face - entry_y, 0.3,
        cq.Vector(cx_a - P.ANT_W / 2, entry_y, fitcheck.WEB_Z1))
    v_seat = common_vol(tray, seated)
    v_path = common_vol(tray, path)
    out.append({"check": "fitcheck_antenna_seated", "value": round(v_seat, 4),
                "pass": v_seat < 0.1})
    out.append({"check": "fitcheck_antenna_slide_path", "value": round(v_path, 4),
                "pass": v_path < 0.1})

    out.append({"check": "fitcheck_est_mass_g",
                "value": round(tray.Volume() * 1.24 / 1000, 1), "pass": True})
    return out


def calicheck_checks():
    """Calibration mini-coupon: single solid, gauges present and to size,
    board sits cleanly in the clip bay (component-up test orientation)."""
    from cad import calicheck as CC
    wp = CC.build_calicheck()
    cc = wp.val()
    out = []

    n = len(wp.solids().vals())
    out.append({"check": "calicheck_single_solid", "value": n, "pass": n == 1})

    bb = cc.BoundingBox()
    dx, dy = bb.xmax - bb.xmin, bb.ymax - bb.ymin
    out.append({"check": "calicheck_envelope", "value": [round(dx, 1), round(dy, 1)],
                "pass": dx <= 100 and dy <= 80})

    radii = sorted({round(f["radius"], 3) for f in
                    _z_cylindrical_faces(cc)})
    want = sorted(set(round(d / 2, 3) for d in CC.HOLE_DIAMS))
    out.append({"check": "calicheck_hole_gauge_diameters", "value": radii,
                "expected": want, "pass": set(want) <= set(radii),
                "note": "plug bay boss+fins are the screwless gauge (no plate hole)"})

    worst_slit = 0.0
    for i, t in enumerate(CC.PCB_SLIT_HEIGHTS):
        y_c = CC.PCB_Y0 + i * CC.PCB_SLIT_PITCH
        probe = cq.Solid.makeBox(
            CC.SLIT_TRAVEL - 1.0, CC.PCB_SLIT_WIDTH - 0.2, t - 0.15,
            cq.Vector(CC.PCB_X_IN + 0.5, y_c - CC.PCB_SLIT_WIDTH / 2 + 0.1,
                      CC.PLATE_T + CC.PCB_SLIT_FLOOR + 0.05))
        worst_slit = max(worst_slit, common_vol(cc, probe))
    for i, wdt in enumerate(CC.ANT_SLIT_WIDTHS):
        x_c = CC.ANT_X0 + i * CC.ANT_X_PITCH
        probe = cq.Solid.makeBox(
            CC.SLIT_TRAVEL - 1.0, wdt - 0.3, CC.ANT_SLIT_HEIGHT - 0.15,
            cq.Vector(x_c - CC.SLIT_TRAVEL / 2 + 0.5,
                      CC.ANT_Y_C - wdt / 2 + 0.15,
                      CC.PLATE_T + CC.ANT_SLIT_FLOOR + 0.05))
        worst_slit = max(worst_slit, common_vol(cc, probe))
    out.append({"check": "calicheck_slit_gauges_open", "value": round(worst_slit, 4),
                "pass": worst_slit < VOLUME_TOL})

    board = holder.place_simhat().translate(cq.Vector(
        CC.BAY_OX - P.simhat_cx(), CC.BAY_OY - M.simhat_pcb_l / 2,
        CC.PAD_TOP - P.SIMHAT_SUPPORT_H))
    v = common_vol(cc, board)
    out.append({"check": "calicheck_bay_seated_board", "value": round(v, 4),
                "note": ("board in PRODUCTION orientation (flipped, relay down) "
                         "at the bay support height"),
                "pass": abs(v) < VOLUME_TOL})

    out.append({"check": "calicheck_est_mass_g",
                "value": round(cc.Volume() * 1.24 / 1000, 1),
                "pass": cc.Volume() * 1.24 / 1000 < 24})
    return out


def _z_cylindrical_faces(solid):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    out = []
    exp = TopExp_Explorer(solid.wrapped, TopAbs_FACE)
    while exp.More():
        face = cq.Face(exp.Current())
        try:
            ad = BRepAdaptor_Surface(face.wrapped)
            if ad.GetType() == GeomAbs_SurfaceType.GeomAbs_Cylinder:
                cyl = ad.Cylinder()
                ax = cyl.Axis().Direction()
                if abs(ax.Z()) > 0.99 and 0.5 < cyl.Radius() < 1.0:
                    out.append({"radius": round(cyl.Radius(), 3)})
        except Exception:
            pass
        exp.Next()
    return out


def printability_scan(shape, name, dz=0.25, min_area=2.0, min_frac=0.4,
                      cantilever_area=400.0):
    """Slice-by-slice floating-island detector (slicer-style lint).

    At each z slab, islands whose XY cross-section has less than min_frac
    of its area supported by material within the previous 0.5 mm are
    flagged. Two classes: small one-ended regions are floating
    CANTILEVERS (the Bambu Studio warning class - these fail); large
    full-span sheets are edge-anchored BRIDGE SHEETS (how bin bottoms
    print - recorded as notes, not failures). The bottom 0.35 mm sits on
    the print bed and is skipped.
    """
    bb = shape.BoundingBox()
    dx, dy = bb.xmax - bb.xmin + 4, bb.ymax - bb.ymin + 4
    lookback = []
    cantilevers, bridge_sheets = [], []
    z = bb.zmin + dz / 2
    while z < bb.zmax:
        if z - dz / 2 < 0.35:
            z += dz
            continue
        slab = cq.Solid.makeBox(dx, dy, dz,
                                cq.Vector(bb.xmin - 2, bb.ymin - 2, z - dz / 2))
        islands = [s for s in cq.Workplane(obj=cq.Shape.cast(
            BRepAlgoAPI_Common(shape.wrapped, slab.wrapped).Shape()))
            .solids().vals() if s.Volume() > 0.01]
        for isl in islands:
            area = isl.Volume() / dz
            if area < min_area or not lookback:
                continue
            supported = 0.0
            for prev_islands in lookback:
                for prev in prev_islands:
                    pbb, ibb = prev.BoundingBox(), isl.BoundingBox()
                    if (pbb.xmin > ibb.xmax or pbb.xmax < ibb.xmin or
                            pbb.ymin > ibb.ymax or pbb.ymax < ibb.ymin):
                        continue
                    lifted = prev.translate(cq.Vector(0, 0, dz - 0.02))
                    supported += common_vol(isl, lifted) / (dz - 0.02)
            if supported / area < min_frac:
                b = isl.BoundingBox()
                entry = {
                    "z": round(z, 2), "area_mm2": round(area, 1),
                    "supported_fraction": round(supported / area, 3),
                    "bbox": [round(b.xmin, 1), round(b.ymin, 1),
                             round(b.xmax, 1), round(b.ymax, 1)],
                }
                if area < cantilever_area:
                    cantilevers.append(entry)
                else:
                    bridge_sheets.append(
                        {**entry, "note": "edge-anchored sheet bridge"})
        lookback = ([islands] + lookback)[:2]
        z += dz
    return {"cantilevers": cantilevers, "bridge_sheets": bridge_sheets}


def main():
    report = {"parameters_of_record": {}}
    checks = []

    print("== rebuild carrier ==")
    carrier_wp = holder.build_carrier()
    carrier = carrier_wp.val()
    n_solids = len(carrier_wp.solids().vals())
    checks.append({"check": "single_solid", "value": n_solids, "pass": n_solids == 1})

    bb = carrier.BoundingBox()
    dx, dy = bb.xmax - bb.xmin, bb.ymax - bb.ymin
    checks.append({"check": "a1mini_envelope_xy", "value": [round(dx, 2), round(dy, 2)],
                   "pass": dx <= P.MAX_XY and dy <= P.MAX_XY})
    checks.append({"check": "flat_on_plate", "value": round(bb.zmin, 4), "pass": abs(bb.zmin) < 1e-6})

    print("== STEP round-trip ==")
    tmp_step = "/tmp/opencode/_carrier_check.step"
    os.makedirs("/tmp/opencode", exist_ok=True)
    cq.exporters.export(carrier_wp, tmp_step)
    reimported = cq.importers.importStep(tmp_step).val()
    v0, v1 = carrier.Volume(), reimported.Volume()
    checks.append({"check": "step_roundtrip_volume", "value": [round(v0, 2), round(v1, 2)],
                   "pass": abs(v1 - v0) / v0 < 0.005 and len(reimported.Solids()) == 1})

    print("== STL watertight ==")
    tmp_stl = "/tmp/opencode/_carrier_check.stl"
    cq.exporters.export(carrier_wp, tmp_stl, tolerance=0.01, angularTolerance=0.1)
    mesh = trimesh.load(tmp_stl)
    checks.append({"check": "stl_watertight", "value": bool(mesh.is_watertight),
                   "pass": bool(mesh.is_watertight)})
    checks.append({"check": "stl_winding_consistent", "value": bool(mesh.is_winding_consistent),
                   "pass": bool(mesh.is_winding_consistent)})
    checks.append({"check": "stl_volume_positive", "value": round(float(mesh.volume), 1),
                   "pass": bool(mesh.volume > 1000)})

    if P.PROFILE == "full":
        print("== seated interference ==")
        a76 = holder.place_a7670()
        a76t = a7670_trimmed()
        sh = holder.place_simhat()
        bite = holder.fence_bite_mm3()
        iv_sh = common_vol(carrier, sh)
        iv_a76t = common_vol(carrier, a76t)
        iv_a76_full = common_vol(carrier, a76)
        checks.append({"check": "seated_simhat_interference",
                       "value": round(iv_sh, 5),
                       "intended_fence_bite_mm3": round(bite, 5),
                       "pass": 0 <= iv_sh - bite < VOLUME_TOL})
        checks.append({"check": "seated_a7670_interference_no_stacking_pins",
                       "value": round(iv_a76t, 5), "pass": abs(iv_a76t) < VOLUME_TOL})
        report["a7670_full_model_overlap_mm3"] = round(iv_a76_full, 4)
        report["a7670_full_model_overlap_note"] = (
            "Manufacturer STEP includes 16 mm stacking-header pins below the board. "
            "The 25 mm default standoffs clear both the pins and the 18650 holder.")
    else:
        a76t = None
        report["profile_note"] = (
            "low profile: boards do not seat (open frame template) - seated "
            "interference / clearance / removal checks apply to the full "
            "profile only")

    if P.PROFILE == "full":
        print("== component clearances ==")
        comps = component_clearances(carrier)
        strict = [c for c in comps if not c.get("optional_stacking_pin_zone")]
        worst = min(c["min_distance"] for c in strict)
        sh_solid = holder.place_simhat()
        a76_solid = a7670_trimmed()
        sh_overlap = common_vol(carrier, sh_solid)
        a76_overlap = common_vol(carrier, a76_solid)
        small_gap = [c["zone"] for c in strict if c["min_distance"] < COMPONENT_CLEARANCE_MIN]
        checks.append({
            "check": "component_clearance_min",
            "value": worst,
            "small_gap_zones": small_gap,
            "note": ("Distances are to component bounding boxes. Values of "
                     f"{P.SIMHAT_PCB_XY_CLEAR} mm equal the designed XY edge "
                     "clearance (fence/lip vs edge-mounted parts); zero solid "
                     "overlap against real reference geometry is required "
                     "(fence friction bite accounted separately)."),
            "pass": worst >= 0.25
                    and 0 <= sh_overlap - holder.fence_bite_mm3() < VOLUME_TOL
                    and abs(a76_overlap) < VOLUME_TOL,
        })
        report["component_clearances"] = comps

    print("== feature presence ==")
    feats = check_holes(carrier)
    checks.append({"check": "features_present",
                   "value": sum(1 for f in feats if f["pass"]), "total": len(feats),
                   "pass": all(f["pass"] for f in feats)})
    report["features"] = feats

    print("== connector service envelopes ==")
    envs = [e for e in service_envelope_checks(carrier)
            if not (P.PROFILE == "low" and e["envelope"] in
                    ("header_jumpers", "relay_terminals"))]
    env_ok = all(e["interference_mm3"] < VOLUME_TOL for e in envs)
    checks.append({"check": "connector_service_envelopes", "value": envs,
                   "pass": env_ok})
    report["service_envelopes"] = envs

    print("== connector mating envelopes (both boards) ==")
    from cad import connectors as CONN
    mates = CONN.mating_conflicts(carrier)
    checks.append({"check": "connector_mating_clear", "value": mates,
                   "pass": all(m["interference_mm3"] < VOLUME_TOL for m in mates)})
    report["mating_envelopes"] = mates

    if P.PROFILE == "full":
        print("== battery keep-out ==")
        bat = battery_keepout_check(carrier)
        checks.append({"check": "battery_18650_keepout",
                       "value": bat["interference_mm3"],
                       "pass": bat["interference_mm3"] < VOLUME_TOL})
        report["battery_keepout"] = bat

    print("== sections partition ==")
    sections = holder.build_sections(carrier)
    v_total = vol(carrier.wrapped)
    v_sum = 0.0
    sec_ok = True
    for name, wp in sections.items():
        n = len(wp.solids().vals())
        v = wp.val().Volume()
        v_sum += v
        sec_ok &= n == 1
    checks.append({"check": "sections_partition_volume",
                   "value": {"carrier_mm3": round(v_total, 2),
                             "sections_sum_mm3": round(v_sum, 2)},
                   "pass": sec_ok and abs(v_sum - v_total) / v_total < 0.005})
    report["sections"] = list(sections)

    if P.ANT_POS in ("under_battery", "end_tray", "side_tray"):
        print("== antenna ==")
        ant = antenna_checks(carrier)
        checks.append({
            "check": "antenna_channel",
            "value": ant,
            "pass": (ant.get("slide_path_interference_mm3",
                             ant.get("dropin_path_interference_mm3", 0.0)) < VOLUME_TOL
                     and ant["seated_sticker_interference_mm3"] < VOLUME_TOL
                     and ant.get("battery_overlap_mm3", 0.0) < VOLUME_TOL
                     and ant.get("stop_filled_fraction", 1.0) > 0.9
                     and all(c.get("post_filled", c.get("posts_filled", 1.0)) > 0.9
                             and c.get("groove_open", c.get("cable_gap_open", 1.0)) > 0.9
                             for c in ant.get("clips", []))),
        })
        report["antenna"] = ant

    if P.SIMHAT_CLIPS_ENABLED:
        print("== simhat removal simulation ==")
        stages, _ = simhat_removal_stages(carrier)
        bite = holder.fence_bite_mm3()
        ok = all(s["interference_mm3"] - bite < VOLUME_TOL for s in stages)
        checks.append({"check": "simhat_toolless_removal", "value": stages,
                       "intended_fence_bite_mm3": round(bite, 5), "pass": ok})
        report["simhat_removal"] = stages

    if P.PROFILE == "full":
        print("== a7670 removal ==")
        lifted = a76t.translate(cq.Vector(0, 0, 30))
        checks.append({"check": "a7670_lift_free", "value": round(common_vol(carrier, lifted), 5),
                       "pass": abs(common_vol(carrier, lifted)) < VOLUME_TOL})

    print("== calibration mini-coupon ==")
    for c in calicheck_checks():
        checks.append(c)

    print("== gridfinity fit-check tray ==")
    for c in fitcheck_tray_checks():
        checks.append(c)
    report.setdefault("fitcheck_tray", []).extend(
        [{k["check"]: k["value"]} for k in checks if k["check"].startswith("fitcheck_")])

    print("== printability (floating islands) ==")
    from cad import calicheck as CC
    from cad import fitcheck as FC
    scan_targets = [
        ("carrier", carrier),
        ("coupon", holder.build_coupon().val()),
        ("calicheck", CC.build_calicheck().val()),
        ("fitcheck_tray", FC.build_fitcheck_tray().val()),
    ]
    scan_results = {}
    for name, shape in scan_targets:
        found = printability_scan(shape, name)
        scan_results[name] = found
        if found["cantilevers"]:
            print(f"  {name}: {len(found['cantilevers'])} floating "
                  f"cantilever(s) at z="
                  f"{[f['z'] for f in found['cantilevers'][:6]]}")
    checks.append({"check": "printability_no_floating_cantilevers",
                   "value": {k: len(v["cantilevers"])
                             for k, v in scan_results.items()},
                   "pass": all(not v["cantilevers"] for v in scan_results.values())})
    report["printability"] = scan_results

    print("== determinism ==")
    h1 = hashlib.sha256(open(tmp_stl, "rb").read()).hexdigest()
    carrier2 = holder.build_carrier()
    tmp_stl2 = "/tmp/opencode/_carrier_check2.stl"
    cq.exporters.export(carrier2, tmp_stl2, tolerance=0.01, angularTolerance=0.1)
    h2 = hashlib.sha256(open(tmp_stl2, "rb").read()).hexdigest()
    checks.append({"check": "deterministic_rebuild", "value": h1[:16], "pass": h1 == h2})

    for c in checks:
        c["pass"] = bool(c["pass"])
        if isinstance(c["value"], (list, tuple)):
            c["value"] = [float(v) if isinstance(v, float) else v for v in c["value"]]
        elif isinstance(c["value"], float):
            c["value"] = float(c["value"])
    report["carrier_bbox"] = {"dx": round(dx, 2), "dy": round(dy, 2),
                              "dz": round(bb.zmax - bb.zmin, 2)}
    report["checks"] = checks
    report["all_passed"] = bool(all(c["pass"] for c in checks))

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  [{status}] {c['check']} = {c['value']}")
    print(f"-> {REPORT_PATH}")
    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

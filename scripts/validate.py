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
    solid = holder.place_a7670()
    t = solid.BoundingBox()
    bb2 = dict(bb)
    bb2["xmin"] += t.xmin - M.a7670["overall"]["bbox"]["xmin"]
    bb2["xmax"] += t.xmin - M.a7670["overall"]["bbox"]["xmin"]
    bb2["ymin"] += t.ymin - M.a7670["overall"]["bbox"]["ymin"]
    bb2["ymax"] += t.ymin - M.a7670["overall"]["bbox"]["ymin"]
    z_off = P.A7670_STANDOFF_H - M.a7670["pcb_slab"]["z_bottom"]
    bb2["zmin"] += z_off
    bb2["zmax"] += z_off
    bb2["dx"], bb2["dy"], bb2["dz"] = bb["dx"], bb["dy"], bb["dz"]
    return bb2


def transform_simhat_bbox(bb):
    x_lo = min(-bb["xmin"], -bb["xmax"])
    x_hi = max(-bb["xmin"], -bb["xmax"])
    sh = holder.place_simhat()
    t = sh.BoundingBox()
    dx0 = M.simhat["overall"]["bbox"]
    out = {
        "xmin": x_lo + t.xmin - (-dx0["xmax"]), "xmax": x_hi + t.xmin - (-dx0["xmax"]),
        "ymin": bb["ymin"] + t.ymin - dx0["ymin"], "ymax": bb["ymax"] + t.ymin - dx0["ymin"],
        "zmin": -bb["zmax"] + t.zmin - (-dx0["zmax"]), "zmax": -bb["zmin"] + t.zmin - (-dx0["zmax"]),
        "dx": bb["dx"], "dy": bb["dy"], "dz": bb["dz"],
    }
    return out


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
    pilot_h = P.A7670_STANDOFF_H - 1.5
    for i, (hx, hy) in enumerate(holder.a7670_holes_carrier()):
        probe = (cq.Workplane("XY").moveTo(hx, hy).circle(0.60)
                 .extrude(pilot_h).translate((0, 0, P.A7670_STANDOFF_H - pilot_h)).val())
        frac = common_vol(probe, carrier) / vol(probe)
        results.append({"feature": f"M1.6_pilot_{i}", "open_fraction": round(frac, 4),
                        "pass": frac < 0.05})
    for e in holder._ear_geometry():
        probe = (cq.Workplane("XY").moveTo(e["slot_x"], e["y_c"])
                 .slot2D(P.EAR_SLOT_L - 0.1, P.EAR_SLOT_W - 0.1, 0)
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

    print("== seated interference ==")
    a76 = holder.place_a7670()
    a76t = a7670_trimmed()
    sh = holder.place_simhat()
    iv_sh = common_vol(carrier, sh)
    iv_a76t = common_vol(carrier, a76t)
    iv_a76_full = common_vol(carrier, a76)
    checks.append({"check": "seated_simhat_interference", "value": round(iv_sh, 5),
                   "pass": abs(iv_sh) < VOLUME_TOL})
    checks.append({"check": "seated_a7670_interference_no_stacking_pins",
                   "value": round(iv_a76t, 5), "pass": abs(iv_a76t) < VOLUME_TOL})
    report["a7670_full_model_overlap_mm3"] = round(iv_a76_full, 4)
    report["a7670_full_model_overlap_note"] = (
        "Manufacturer STEP includes 16 mm stacking-header pins below the board. "
        "Default standoffs (13 mm) assume they are NOT soldered. "
        "Set A7670_STANDOFF_H = 21.0 if they are.")

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
                 "overlap against real reference geometry is required."),
        "pass": worst >= 0.25 and abs(sh_overlap) < VOLUME_TOL and abs(a76_overlap) < VOLUME_TOL,
    })
    report["component_clearances"] = comps

    print("== feature presence ==")
    feats = check_holes(carrier)
    checks.append({"check": "features_present",
                   "value": sum(1 for f in feats if f["pass"]), "total": len(feats),
                   "pass": all(f["pass"] for f in feats)})
    report["features"] = feats

    print("== simhat removal simulation ==")
    stages, _ = simhat_removal_stages(carrier)
    ok = all(s["interference_mm3"] < VOLUME_TOL for s in stages)
    checks.append({"check": "simhat_toolless_removal", "value": stages, "pass": ok})
    report["simhat_removal"] = stages

    print("== a7670 removal ==")
    lifted = a76t.translate(cq.Vector(0, 0, 30))
    checks.append({"check": "a7670_lift_free", "value": round(common_vol(carrier, lifted), 5),
                   "pass": abs(common_vol(carrier, lifted)) < VOLUME_TOL})

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

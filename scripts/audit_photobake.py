#!/usr/bin/env python3
"""audit_photobake — closed-loop verification of photo-textured renders.

Gate classes (analysis/photobake_audit.json; exit 1 on any hard fail):

  plane_drift   each face's baked plane rectangle must match the TRUE
                plane recomputed from the placed manufacturer STEP solid
                (slab face z, board extent) -- never from hand formulas.
                Hard gate: |dz| <= 0.30 mm, |dcx|,|dcy| <= 0.50 mm.

  fiducial_drift  where a face has unambiguous CAD-truth fiducials
                (simhat: header-socket rails = silver, screw terminal =
                green), the baked texture's landmark centroids must sit
                within FIDUCIAL_TOL of the truth mapped through the same
                (cu, cv) convention the bake used. Hard gate.

  fiducial_mass  a fiducial class used for orientation must have enough
                pixels to be a signal, not noise (rule 29: black PCBs
                starve dark/luminance probes; silver needs >= 20k px on
                a 66x20mm face at our bake resolution).

  advisory      a7670 silver centroids are recorded but not gated:
                which measured parts are silver is a color fact the STEP
                does not carry. Placement IS gated; orientation on that
                board stays a human check until a part-color map exists.

Convention (identical to tools/photobake.py / scripts/orient_photos.py):
  image top = board far end (carrier +Y), left = u min; cv from top,
  cu from left; below-face textures are U-mirrored at bake time, so the
  audit applies the same mirror before comparing.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
sys.path.insert(0, "tools")

import numpy as np
from PIL import Image

from cad import holder
import cad.parameters as P
from cad.parameters import Measured as M
from scripts.orient_photos import landmarks

CACHE = "/tmp/opencode/photobake"
FIDUCIAL_TOL = 0.06
SILVER_MIN_N = 20000
GREEN_MIN_N = 500
PLANE_Z_TOL = 0.30
PLANE_XY_TOL = 0.50


def true_plane(board, face):
    """Plane rect from the PLACED STEP solid: (cx, cy, z, w, h)."""
    off = 0.15
    if board == "simhat":
        solid = holder.place_simhat()
        z_slab_top = M.simhat["pcb_slab"]["z_top"]
        z_slab_bot = M.simhat["pcb_slab"]["z_bottom"]
        z_down = P.SIMHAT_SUPPORT_H + z_slab_top - z_slab_top      # STEP top face
        z_up = P.SIMHAT_SUPPORT_H + z_slab_top - z_slab_bot        # STEP bottom face
        z = (z_down - off) if face == "down" else (z_up + off)
        w, h = M.simhat_pcb_w, M.simhat_pcb_l
    else:
        solid = holder.place_a7670()
        z_slab_top = M.a7670["pcb_slab"]["z_top"]
        z_slab_bot = M.a7670["pcb_slab"]["z_bottom"]
        z_up = P.A7670_STANDOFF_H - z_slab_bot + z_slab_top
        z_down = P.A7670_STANDOFF_H
        z = (z_down - off) if face == "down" else (z_up + off)
        w, h = M.a7670_pcb_w, M.a7670_pcb_l
    bb = solid.BoundingBox()
    return (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, z, w, h


def simhat_fiducial_truth():
    """(cu, cv) centroids of the unambiguous simhat fiducial classes,
    computed from measured component bboxes under the flip mapping
    (u = -x_step, v = -y_step)."""
    half_w, full_l = M.simhat_pcb_w / 2, M.simhat_pcb_l

    def cu_cv(u, v):
        return (u + half_w) / (2 * half_w), (full_l - v) / full_l

    silver_pts = []
    for c in M.simhat["components_below_pcb"]:
        b = c["bbox"]
        u0, u1 = -b["xmax"], -b["xmin"]
        v0, v1 = -b["ymax"], -b["ymin"]
        if (half_w - max(abs(u0), abs(u1)) <= 1.0 and v0 > 50
                and b["dz"] > 5):
            silver_pts.append(((u0 + u1) / 2, (v0 + v1) / 2))
    green_pts = []
    for c in M.simhat["components_above_pcb"]:
        b = c["bbox"]
        u0, u1 = -b["xmax"], -b["xmin"]
        v0, v1 = -b["ymax"], -b["ymin"]
        if (b["dx"] * b["dy"] > 100 and b["dz"] > 10
                and v1 < 20 and u1 < 0):
            green_pts.append(((u0 + u1) / 2, (v0 + v1) / 2))
    out = {}
    if silver_pts:
        us = [p[0] for p in silver_pts]
        vs = [p[1] for p in silver_pts]
        out["silver"] = cu_cv(sum(us) / len(us), sum(vs) / len(vs))
    if green_pts:
        us = [p[0] for p in green_pts]
        vs = [p[1] for p in green_pts]
        out["green"] = cu_cv(sum(us) / len(us), sum(vs) / len(vs))
    return out


def audit_face(face, bake_path, baked_plane):
    result = {"name": face["name"], "gates": [], "advisory": []}
    cx, cy, z, w, h = baked_plane
    tcx, tcy, tz, tw, th = true_plane(face["plane"]["board"],
                                      face["plane"]["face"])
    dz, dcx, dcy = abs(z - tz), abs(cx - tcx), abs(cy - tcy)
    result["gates"].append({
        "gate": "plane_drift", "dz": round(dz, 3), "dcx": round(dcx, 3),
        "dcy": round(dcy, 3), "size_exact": (w, h) == (tw, th),
        "pass": dz <= PLANE_Z_TOL and dcx <= PLANE_XY_TOL
        and dcy <= PLANE_XY_TOL and (w, h) == (tw, th)})

    tex = np.asarray(Image.open(bake_path).convert("RGB")).astype(float)
    lm = landmarks(tex)
    mirror = face["plane"].get("face") == "down"
    board = face["plane"]["board"]
    flat = face["source"].get("style") == "flat_dark"
    # Per-face gating map: only classes that are UNAMBIGUOUS on that face.
    #   simhat up  : socket rails -> single silver truth; no green there.
    #   simhat down: flat_dark style by design (no honest photo exists --
    #                see jobs fiducials_note); placement gated, fiducials
    #                skipped.
    #   a7670      : which parts read silver is a color fact the STEP does
    #                not carry -> advisory (placement still gated).
    gates = {}
    if board == "simhat" and not flat:
        truth = simhat_fiducial_truth()
        if face["plane"]["face"] == "up":
            gates["silver"] = truth.get("silver")
        else:
            gates["green"] = truth.get("green")
    for cls, tc in gates.items():
        if tc is None:
            continue
        tcu, tcv = tc
        m = lm.get(cls)
        if not m:
            result["gates"].append({
                "gate": f"fiducial_{cls}", "error": "class absent in texture",
                "pass": False})
            continue
        cu = 1 - m["cu"] if mirror else m["cu"]
        du, dv = abs(cu - tcu), abs(m["cv"] - tcv)
        min_n = SILVER_MIN_N if cls == "silver" else GREEN_MIN_N
        result["gates"].append({
            "gate": f"fiducial_{cls}",
            "measured_cu_cv": [round(cu, 3), round(m["cv"], 3)],
            "truth_cu_cv": [round(tcu, 3), round(tcv, 3)],
            "du": round(du, 3), "dv": round(dv, 3), "n": m["n"],
            "pass": du <= FIDUCIAL_TOL and dv <= FIDUCIAL_TOL and m["n"] >= min_n})
    if lm.get("silver"):
        result["advisory"].append(
            {"note": "silver centroid (ungated on this board)",
             "cu_cv": [round(lm["silver"]["cu"], 3),
                       round(lm["silver"]["cv"], 3)],
             "n": lm["silver"]["n"]})
    result["pass"] = all(g["pass"] for g in result["gates"])
    return result


def main():
    jobs = json.load(open("tools/photobake_jobs.json"))
    report = {"faces": [], "convention": "top=far(+Y), left=u_min; down faces U-mirrored"}
    ok = True
    for face in jobs["faces"]:
        import os
        bake = os.path.join(CACHE, f"bake_{face['name']}.png")
        if not os.path.exists(bake):
            report["faces"].append({"name": face["name"], "error": "no bake",
                                    "pass": False})
            ok = False
            continue
        from tools.photobake import plane_placement
        plane = plane_placement(face["plane"])
        r = audit_face(face, bake, plane)
        report["faces"].append(r)
        ok &= r["pass"]
        status = "PASS" if r["pass"] else "FAIL"
        print(f"[{status}] {face['name']}")
        for g in r["gates"]:
            if not g["pass"]:
                print(f"    failed: {json.dumps(g)}")
    report["pass"] = ok
    json.dump(report, open("analysis/photobake_audit.json", "w"), indent=1)
    print(f"-> analysis/photobake_audit.json (overall {'PASS' if ok else 'FAIL'})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze LILYGO STEP reference models (fused single-solid assemblies).

Extracts, without guessing:
  - overall bounding box, volume, centroid
  - PCB slab (Z-range, thickness) via cross-section area profiling
  - PCB outline (bbox, area, corner vertices) from a mid-slab section
  - Z-axis cylindrical through-holes in the PCB slab -> mounting hole candidates
  - component envelope solids above/below the PCB (exported as STEP for reuse)
  - area profile table for the Z sweep

Writes a machine-readable JSON report per input file.

Usage:
    python scripts/analyze_step.py <input.stp> <output.json> [--components-dir analysis/parts]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer

SLICE_DZ = 0.02          # thickness of probing slab for area profile
SWEEP_STEP = 0.05        # z sampling step for area profile
SLAB_AREA_RATIO = 0.85   # fraction of max area considered "PCB slab"
CYL_R_MIN, CYL_R_MAX = 0.4, 2.6   # mounting hole radius window [mm]
EPS = 1e-6


def solid_of(shape) -> cq.Solid:
    return shape


def bbox_dict(bb) -> dict:
    xm, ym, zm, xM, yM, zM = bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax
    return {
        "xmin": round(xm, 4), "ymin": round(ym, 4), "zmin": round(zm, 4),
        "xmax": round(xM, 4), "ymax": round(yM, 4), "zmax": round(zM, 4),
        "dx": round(xM - xm, 4), "dy": round(yM - ym, 4), "dz": round(zM - zm, 4),
    }


def area_at_z(solid: cq.Solid, z: float, x0, x1, y0, y1, dz: float = SLICE_DZ) -> float:
    """Cross-section area at height z by intersecting a thin slab with the solid."""
    probe = cq.Solid.makeBox(x1 - x0 + 4, y1 - y0 + 4, dz,
                             cq.Vector(x0 - 2, y0 - 2, z - dz / 2))
    common = BRepAlgoAPI_Common(solid.wrapped, probe.wrapped)
    if not common.IsDone():
        return 0.0
    shp = common.Shape()
    vol = 0.0
    exp = TopExp_Explorer(shp, TopAbs_SOLID)
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    while exp.More():
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(exp.Current(), props)
        vol += props.Mass()
        exp.Next()
    return vol / dz


def pcb_slab_from_profile(profile: list[tuple[float, float]]) -> dict:
    """Find contiguous z-range where area >= SLAB_AREA_RATIO * max area."""
    max_area = max(a for _, a in profile)
    thr = SLAB_AREA_RATIO * max_area
    runs = []
    cur = None
    for z, a in profile:
        if a >= thr:
            if cur is None:
                cur = [z, z]
            else:
                cur[1] = z
        else:
            if cur is not None:
                runs.append(tuple(cur))
                cur = None
    if cur is not None:
        runs.append(tuple(cur))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    best = runs[0]
    return {"z_bottom": best[0] - SLICE_DZ / 2, "z_top": best[1] + SLICE_DZ / 2,
            "thickness": (best[1] - best[0]) + SLICE_DZ,
            "max_area": max_area, "runs": [[round(a, 3), round(b, 3)] for a, b in runs]}


def outline_at_z(solid: cq.Solid, z: float):
    """Mid-slab outline: intersect a thin slab, use the largest island's shape."""
    bball = solid.BoundingBox()
    dx, dy = bball.xmax - bball.xmin, bball.ymax - bball.ymin
    probe = cq.Solid.makeBox(dx + 4, dy + 4, SLICE_DZ,
                             cq.Vector(bball.xmin - 2, bball.ymin - 2, z - SLICE_DZ / 2))
    common = BRepAlgoAPI_Common(solid.wrapped, probe.wrapped)
    shp = cq.Shape.cast(common.Shape())
    solids = cq.Workplane(obj=shp).solids().vals()
    if not solids:
        return None
    isl = max(solids, key=lambda s: s.Volume())
    bb = isl.BoundingBox()
    verts = [(round(v.X, 3), round(v.Y, 3)) for v in isl.Vertices()]
    edges = isl.Edges()
    return {"area": round(isl.Volume() / SLICE_DZ, 3),
            "bbox": bbox_dict(bb), "vertices": verts,
            "n_edges": len(edges)}


def cylindrical_faces(solid: cq.Solid):
    out = []
    exp = TopExp_Explorer(solid.wrapped, TopAbs_FACE)
    while exp.More():
        face = cq.Face(exp.Current())
        try:
            ad = BRepAdaptor_Surface(face.wrapped)
            if ad.GetType() == GeomAbs_SurfaceType.GeomAbs_Cylinder:
                cyl = ad.Cylinder()
                ax = cyl.Axis()
                loc = ax.Location()
                dirv = ax.Direction()
                bb = Bnd_Box()
                BRepBndLib.Add_s(face.wrapped, bb)
                xm, ym, zm, xM, yM, zM = bb.Get()
                out.append({
                    "center_x": round(loc.X(), 4), "center_y": round(loc.Y(), 4),
                    "axis_z_at_origin": round(loc.Z(), 4),
                    "dir": (round(dirv.X(), 4), round(dirv.Y(), 4), round(dirv.Z(), 4)),
                    "radius": round(cyl.Radius(), 4),
                    "face_zmin": round(zm, 4), "face_zmax": round(zM, 4),
                })
        except Exception:
            pass
        exp.Next()
    return out


def planar_faces_z(solid: cq.Solid):
    """Return list of horizontal planar faces: (z, normal_sign, area, bbox)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface as BAS
    from OCP.GeomAbs import GeomAbs_Plane
    out = []
    exp = TopExp_Explorer(solid.wrapped, TopAbs_FACE)
    while exp.More():
        face = cq.Face(exp.Current())
        try:
            ad = BAS(face.wrapped)
            if ad.GetType() == GeomAbs_SurfaceType.GeomAbs_Plane:
                pl = ad.Plane()
                n = pl.Axis().Direction()
                if abs(n.Z()) > 0.99:
                    bb = face.BoundingBox()
                    out.append({"z": round(bb.zmin, 4), "nz": round(n.Z(), 2),
                                "area": round(face.Area(), 2),
                                "bbox": bbox_dict(bb)})
        except Exception:
            pass
        exp.Next()
    return out


def pcb_slab_from_planes(solid: cq.Solid, outline_area: float) -> dict | None:
    """PCB slab = two large coplanar face groups ~1.0-2.0 mm apart."""
    faces = planar_faces_z(solid)
    by_z = {}
    for f in faces:
        key = round(f["z"], 2)
        by_z.setdefault(key, []).append(f)
    levels = [(z, sum(f["area"] for f in fs)) for z, fs in sorted(by_z.items())]
    best = None
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            z0, a0 = levels[i]
            z1, a1 = levels[j]
            t = z1 - z0
            if 1.0 <= t <= 2.0 and a0 > 0.5 * outline_area and a1 > 0.5 * outline_area:
                score = min(a0, a1)
                if best is None or score > best[0]:
                    best = (score, z0, z1, t)
    if best is None:
        return None
    _, z0, z1, t = best
    return {"z_bottom": z0, "z_top": z1, "thickness": t}


def islands_at_z(solid: cq.Solid, z: float, bbx) -> list[dict]:
    """Connected cross-section islands at height z (component map)."""
    dx, dy = bbx.xmax - bbx.xmin, bbx.ymax - bbx.ymin
    probe = cq.Solid.makeBox(dx + 4, dy + 4, SLICE_DZ,
                             cq.Vector(bbx.xmin - 2, bbx.ymin - 2, z - SLICE_DZ / 2))
    common = BRepAlgoAPI_Common(solid.wrapped, probe.wrapped)
    shp = cq.Shape.cast(common.Shape())
    solids = cq.Workplane(obj=shp).solids().vals()
    out = []
    for s in solids:
        b = s.BoundingBox()
        out.append({"z": round(z, 3),
                    "area": round(s.Volume() / SLICE_DZ, 1),
                    "bbox": bbox_dict(b)})
    out.sort(key=lambda d: -d["area"])
    return out


def find_mounting_holes(cyls: list[dict], slab: dict, outline_bbox: dict | None = None) -> list[dict]:
    """Z-axis cylinders spanning the PCB slab, excluding outline corner fillets
    (fillet centers sit within one radius of the outline bbox edges)."""
    holes = []
    zb, zt = slab["z_bottom"], slab["z_top"]
    th = zt - zb
    seen = {}
    for c in cyls:
        d = c["dir"]
        if abs(d[2]) < 0.99:
            continue
        if not (CYL_R_MIN <= c["radius"] <= CYL_R_MAX):
            continue
        span = c["face_zmax"] - c["face_zmin"]
        if span < 0.75 * th:
            continue
        if c["face_zmin"] < zb - 0.05 or c["face_zmax"] > zt + 0.05:
            continue
        if outline_bbox is not None:
            r = c["radius"]
            near = min(
                abs(c["center_x"] - outline_bbox["xmin"]),
                abs(c["center_x"] - outline_bbox["xmax"]),
                abs(c["center_y"] - outline_bbox["ymin"]),
                abs(c["center_y"] - outline_bbox["ymax"]),
            )
            if near < r + 0.25:
                continue
        key = (round(c["center_x"], 2), round(c["center_y"], 2), round(c["radius"], 2))
        if key not in seen or span > seen[key]["span"]:
            seen[key] = {**c, "span": round(span, 4)}
    holes = list(seen.values())
    holes.sort(key=lambda h: (h["center_y"], h["center_x"]))
    return holes


def component_solids(solid: cq.Solid, z_bottom: float, z_top: float):
    """Split fused solid into above-PCB / below-PCB component volumes."""
    bb = solid.BoundingBox()
    big = max(bb.xmax - bb.xmin, bb.ymax - bb.ymin) + 20

    def halfspace(zmin, zmax):
        box = cq.Solid.makeBox(big, big, zmax - zmin,
                               cq.Vector(bb.xmin - 10, bb.ymin - 10, zmin))
        common = BRepAlgoAPI_Common(solid.wrapped, box.wrapped)
        shp = cq.Shape.cast(common.Shape())
        return cq.Workplane(obj=shp).solids().vals()

    top = halfspace(z_top, bb.zmax + 1)
    bottom = halfspace(bb.zmin - 1, z_bottom)
    return top, bottom


def solid_info(s: cq.Solid) -> dict:
    bb = s.BoundingBox()
    c = s.Center()
    return {"bbox": bbox_dict(bb), "volume_mm3": round(s.Volume(), 2),
            "centroid": [round(c.x, 3), round(c.y, 3), round(c.z, 3)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step_file")
    ap.add_argument("out_json")
    ap.add_argument("--components-dir", default=None)
    ap.add_argument("--pretty-slices", type=int, default=None,
                    help="also write per-slice XY bboxes for N z samples above/below PCB")
    args = ap.parse_args()

    wp = cq.importers.importStep(args.step_file)
    solids = wp.solids().vals()
    if len(solids) != 1:
        print(f"NOTE: {len(solids)} solids (expected fused single solid); analyzing first")
    solid = solids[0]

    report: dict = {"source_file": os.path.basename(args.step_file)}
    report["overall"] = solid_info(solid)

    # ---- area profile sweep ----
    bb = solid.BoundingBox()
    profile = []
    z = bb.zmin
    while z <= bb.zmax + EPS:
        a = area_at_z(solid, z, bb.xmin, bb.xmax, bb.ymin, bb.ymax)
        profile.append((round(z, 3), round(a, 2)))
        z += SWEEP_STEP
    report["area_profile"] = profile

    slab = pcb_slab_from_profile(profile)
    approx_area = slab["max_area"]
    plane_slab = pcb_slab_from_planes(solid, approx_area)
    if plane_slab:
        slab.update({"z_bottom": plane_slab["z_bottom"],
                     "z_top": plane_slab["z_top"],
                     "thickness": plane_slab["thickness"]})
        report["pcb_slab_method"] = "planar_faces"
    else:
        report["pcb_slab_method"] = "area_profile"
    report["pcb_slab"] = {k: (round(v, 4) if isinstance(v, float) else v)
                          for k, v in slab.items() if k != "runs"}
    report["pcb_slab"]["runs"] = slab["runs"]

    # ---- outline at mid-slab ----
    mid_z = (slab["z_bottom"] + slab["z_top"]) / 2
    outline = outline_at_z(solid, mid_z)
    if outline:
        report["pcb_outline"] = outline

    # ---- cylindrical holes ----
    cyls = cylindrical_faces(solid)
    report["cylindrical_faces_z_axis"] = [c for c in cyls if abs(c["dir"][2]) > 0.99]
    report["mounting_hole_candidates"] = find_mounting_holes(
        cyls, slab, outline["bbox"] if outline else None)

    # ---- component island map (layout reconnaissance) ----
    comp_map = []
    zb, zt = slab["z_bottom"], slab["z_top"]
    above_span = bb.zmax - zt
    below_span = zb - bb.zmin
    for frac in (0.25, 0.6, 0.9):
        if above_span > 1.0:
            comp_map += islands_at_z(solid, zt + frac * above_span, bb)
        if below_span > 1.0:
            comp_map += islands_at_z(solid, zb - frac * below_span, bb)
    report["component_island_map"] = comp_map

    # ---- component volumes ----
    top, bottom = component_solids(solid, slab["z_bottom"], slab["z_top"])
    report["components_above_pcb"] = [solid_info(s) for s in top]
    report["components_below_pcb"] = [solid_info(s) for s in bottom]

    # ---- optional component slice bboxes (layout mapping) ----
    if args.pretty_slices:
        n = args.pretty_slices
        slices = []
        zs_top = [slab["z_top"] + i * (bb.zmax - slab["z_top"]) / n for i in range(1, n)]
        zs_bot = [slab["z_bottom"] - i * (slab["z_bottom"] - bb.zmin) / n for i in range(1, n)]
        for zz in sorted(zs_top + zs_bot):
            a = area_at_z(solid, zz, bb.xmin, bb.xmax, bb.ymin, bb.ymax)
            slices.append({"z": round(zz, 3), "area": round(a, 2)})
        report["component_layer_slices"] = slices

    # ---- export component solids ----
    if args.components_dir:
        os.makedirs(args.components_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(args.out_json))[0]
        if top:
            cq.exporters.export(cq.Workplane(obj=top[0]),
                                os.path.join(args.components_dir, f"{base}_top_components.step"))
        if bottom:
            cq.exporters.export(cq.Workplane(obj=bottom[0]),
                                os.path.join(args.components_dir, f"{base}_bottom_components.step"))

    with open(args.out_json, "w") as f:
        json.dump(report, f, indent=2)

    # ---- console summary ----
    print(f"== {args.step_file} ==")
    print(f"overall bbox: {report['overall']['bbox']}")
    print(f"PCB slab: z[{slab['z_bottom']:.3f},{slab['z_top']:.3f}] t={slab['thickness']:.3f} mm")
    if outline:
        print(f"outline @z={mid_z:.2f}: area={outline['area']} bbox={outline['bbox']}")
    print(f"mounting hole candidates ({len(report['mounting_hole_candidates'])}):")
    for h in report["mounting_hole_candidates"]:
        print(f"  ({h['center_x']}, {h['center_y']}) r={h['radius']} d={2*h['radius']:.3f} span={h['span']}")
    print(f"above-PCB solids: {len(top)}  below-PCB solids: {len(bottom)}")
    print(f"-> {args.out_json}")


if __name__ == "__main__":
    main()

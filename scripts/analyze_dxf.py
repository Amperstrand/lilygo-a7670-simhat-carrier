#!/usr/bin/env python3
"""Extract authoritative dimensions from LILYGO Altium-style DXF exports.

Reads DIMENSION measurement values, TEXT callouts, and hole geometry,
producing a machine-readable JSON used to cross-check the STEP analysis.

Usage:
    python scripts/analyze_dxf.py <input.dxf> <output.json>
"""

from __future__ import annotations

import argparse
import json
import math
import os

import ezdxf


def circle_polys(msp) -> list[dict]:
    out = []
    for e in msp.query("LWPOLYLINE"):
        if not e.closed:
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) < 8:
            continue
        xs = [p[0] for p in pts[:-1]]
        ys = [p[1] for p in pts[:-1]]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if abs(w - h) > 0.05 or w > 8:
            continue
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        rs = [math.hypot(p[0] - cx, p[1] - cy) for p in pts[:-1]]
        if max(rs) - min(rs) > 0.05:
            continue
        out.append({"center_x": round(cx, 4), "center_y": round(cy, 4),
                    "diameter": round(2 * sum(rs) / len(rs), 4)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf_file")
    ap.add_argument("out_json")
    args = ap.parse_args()

    doc = ezdxf.readfile(args.dxf_file)
    msp = doc.modelspace()

    dims = []
    for d in msp.query("DIMENSION"):
        try:
            p = d.dxf.defpoint
            dims.append({"defpoint": [round(p.x, 3), round(p.y, 3)],
                         "measurement": round(float(d.get_measurement()), 4),
                         "text": d.dxf.text})
        except Exception:
            continue

    texts = [{"text": t.dxf.text,
              "at": [round(t.dxf.insert.x, 2), round(t.dxf.insert.y, 2)]}
             for t in msp.query("TEXT")]

    circles = [{"center_x": round(c.dxf.center.x, 4),
                "center_y": round(c.dxf.center.y, 4),
                "diameter": round(2 * c.dxf.radius, 4)}
               for c in msp.query("CIRCLE")]

    report = {
        "source_file": os.path.basename(args.dxf_file),
        "dimensions": dims,
        "texts": texts,
        "circles": circles,
        "circle_polylines": circle_polys(msp),
        "entity_counts": {t: len(msp.query(t)) for t in
                          ("LINE", "LWPOLYLINE", "CIRCLE", "ARC", "TEXT",
                           "DIMENSION", "INSERT")},
    }

    # mounting-hole consensus: dimensioned features with ~1.4-2.2mm measurement
    hole_dims = [d for d in dims if 1.4 <= d["measurement"] <= 2.2]
    report["mounting_holes_dxf"] = [
        {"center_x": d["defpoint"][0], "center_y": d["defpoint"][1],
         "diameter": d["measurement"]}
        for d in hole_dims]

    with open(args.out_json, "w") as f:
        json.dump(report, f, indent=2)

    print(f"== {args.dxf_file} ==")
    for d in dims:
        print(f"  DIM {d['measurement']:8.3f} @ ({d['defpoint'][0]:.2f}, {d['defpoint'][1]:.2f}) '{d['text']}'")
    print(f"mounting holes (DXF dims): {len(report['mounting_holes_dxf'])}")
    for h in report["mounting_holes_dxf"]:
        print(f"  ({h['center_x']}, {h['center_y']}) d={h['diameter']}")
    print(f"-> {args.out_json}")


if __name__ == "__main__":
    main()

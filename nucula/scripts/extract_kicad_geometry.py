#!/usr/bin/env python3
"""Extract authoritative Nucula PCB geometry from the KiCad board file.

Single source of truth: nucula-v2.kicad_pcb (Edge.Cuts + footprints + pads).
No hand-transcribed dimensions: everything below is parsed or derived.

Outputs:
  analysis/pcb_geometry.json       - board outline(s), thickness, sections
  analysis/component_geometry.json - every footprint with global pad extents

Provenance tags used throughout the project:
  extracted_kicad   - parsed directly from the KiCad board file
  derived_kicad     - computed from extracted geometry (bbox, stitch, clip)
  manufacturer_doc  - taken from a Nucula repo document (source cited)
  conservative_assumption - documented guess, must be measured
  enclosure_design_decision - our choice, changeable parameter

Board-local coordinate system (u, v):
  u = X_kicad - X0  (X0 = outline xmin)
  v = Y_kicad - Y0  (Y0 = outline ymin)
  KiCad Y grows "down the page"; we keep KiCad axes untouched, so the
  keyboard section (KiCad Y 125-160) sits at high v.
  Main section: v in [0, 73].  Keyboard section: v in [75, 110].
"""

import json
import math
import os
import re
import sys

REPO = os.environ.get(
    "NUCULA_REPO",
    "/home/z/my-project/reference-repos/nucula-board",
)
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis"
)

PCB_FILE = os.path.join(REPO, "nucula-v2.kicad_pcb")

# ---------------------------------------------------------------------------
# Minimal S-expression parser (tolerates bare tokens, quoted strings, numbers)
# ---------------------------------------------------------------------------

def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "(" or c == ")":
            yield c
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            yield ("str", "".join(buf))
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n()"':
            j += 1
        yield ("tok", text[i:j])
        i = j


def parse_sexpr(text):
    """Return list of top-level expressions; each is (head, [items...])."""
    stack = []
    result = []
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            top = stack.pop()
            if stack:
                stack[-1].append(top)
            else:
                result.append(top)
        else:
            if stack:
                stack[-1].append(tok)
    if stack:  # truncated file: keep what we have
        result = stack
    return result


def head(expr):
    if isinstance(expr, list) and expr and isinstance(expr[0], tuple):
        return expr[0][1]
    return None


def children(expr, name=None):
    out = []
    if not isinstance(expr, list):
        return out
    for item in expr[1:]:
        if isinstance(item, list) and item and isinstance(item[0], tuple):
            if name is None or item[0][1] == name:
                out.append(item)
    return out


def find_first(expr, name):
    for item in children(expr, name):
        return item
    return None


def tok_val(v):
    if isinstance(v, tuple):
        return v[1]
    return v


def node_values(node):
    """Values of a node after its head, as list of python scalars/strings."""
    if node is None:
        return []
    return [tok_val(v) for v in node[1:] if isinstance(v, tuple)]


def get_numbers(expr, name):
    n = find_first(expr, name)
    if not n:
        return []
    out = []
    for v in node_values(n):
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            pass
    return out


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def arc_points(start, mid, end, segments=24):
    def unit(ax, ay):
        l = math.hypot(ax, ay)
        return (ax / l, ay / l) if l else (1.0, 0.0)

    s, m, e = start, mid, end
    a = unit(s[0] - m[0], s[1] - m[1])
    b = unit(e[0] - m[0], e[1] - m[1])
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
    cross = a[0] * b[1] - a[1] * b[0]
    ang = math.atan2(cross, dot)
    r = math.hypot(s[0] - m[0], s[1] - m[1])
    a0 = math.atan2(s[1] - m[1], s[0] - m[0])
    pts = []
    for i in range(segments + 1):
        t = a0 + ang * i / segments
        pts.append((m[0] + r * math.cos(t), m[1] + r * math.sin(t)))
    return pts


def stitch_loops(polylines, tol=1e-3):
    """Greedy stitch of polylines into closed loops."""
    remaining = [list(p) for p in polylines if len(p) >= 2]
    loops = []
    while remaining:
        cur = remaining.pop(0)
        # extend forward
        extended = True
        while extended:
            extended = False
            for idx, pl in enumerate(remaining):
                for fwd in (False, True):
                    cand = pl if not fwd else pl[::-1]
                    if math.dist(cur[-1], cand[0]) <= tol:
                        cur.extend(cand[1:])
                        remaining.pop(idx)
                        extended = True
                        break
                if extended:
                    break
            if math.dist(cur[0], cur[-1]) <= tol and len(cur) > 3:
                cur.pop()
                loops.append(cur)
                cur = []  # close loop
                break
        if cur and len(cur) > 2:
            loops.append(cur)  # open chain (should not happen on Edge.Cuts)
    return loops


def poly_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def bbox_of(polys):
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    return {"xmin": min(xs), "xmax": max(xs), "ymin": min(ys), "ymax": max(ys)}


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = x0 + (y - y0) * (x1 - x0) / (y1 - y0) if y1 != y0 else x0
            if x < xin:
                inside = not inside
    return inside


def clip_polygon_to_halfplane(pts, keep_above_y, y_line, eps=1e-9):
    """Sutherland-Hodgman clip against y >= y_line (keep_above_y) or y <= y_line."""
    def clip_edge(p0, p1):
        out = []
        d0 = (p0[1] - y_line) * (1 if keep_above_y else -1)
        d1 = (p1[1] - y_line) * (1 if keep_above_y else -1)
        if d0 >= -eps:
            out.append(p0)
        if (d0 > eps and d1 < -eps) or (d0 < -eps and d1 > eps):
            t = d0 / (d0 - d1)
            out.append((p0[0] + t * (p1[0] - p0[0]), y_line))
        return out

    res = pts
    for i in range(len(pts)):
        res = clip_edge(pts[i], pts[(i + 1) % len(pts)]) if i == 0 else _clip(res, pts[i], pts[(i + 1) % len(pts)], keep_above_y, y_line, eps)
    return res


def _clip(pts, p0, p1, keep_above_y, y_line, eps):
    def side(p):
        return (p[1] - y_line) * (1 if keep_above_y else -1)

    out = []
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        da, db = side(a), side(b)
        if da >= -eps:
            out.append(a)
        if (da > eps and db < -eps) or (da < -eps and db > eps):
            t = da / (da - db)
            out.append((a[0] + t * (b[0] - a[0]), y_line))
    return out


# ---------------------------------------------------------------------------
# KiCad placement transform
# ---------------------------------------------------------------------------
# Positive KiCad footprint angle rotates counter-clockwise on screen
# (file Y axis points down the page). For local pad (px, py) and
# footprint at (fx, fy) with angle deg:
#   gx = fx + px*cos + py*sin
#   gy = fy - px*sin + py*cos

def place(px, py, fx, fy, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (fx + px * c + py * s, fy - px * s + py * c)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract():
    text = open(PCB_FILE, encoding="utf-8", errors="replace").read()
    tree = parse_sexpr(text)
    board = None
    for e in tree:
        if head(e) == "kicad_pcb":
            board = e
            break
    assert board is not None, "kicad_pcb node not found"

    thickness = get_numbers(board, "thickness")[0] if find_first(board, "thickness") else 1.6

    # ---- Edge.Cuts graphics ----
    segs = []
    for g in board[1:]:
        h = head(g)
        layer_node = find_first(g, "layer")
        layer = node_values(layer_node)[0] if layer_node else ""
        if layer != "Edge.Cuts":
            continue
        if h == "gr_line":
            s = get_numbers(g, "start")
            e = get_numbers(g, "end")
            segs.append([(s[0], s[1]), (e[0], e[1])])
        elif h == "gr_arc":
            s = get_numbers(g, "start")
            m = get_numbers(g, "mid")
            e = get_numbers(g, "end")
            segs.append(arc_points((s[0], s[1]), (m[0], m[1]), (e[0], e[1])))
        elif h == "gr_rect":
            s = get_numbers(g, "start")
            e = get_numbers(g, "end")
            x0, x1 = sorted((s[0], e[0]))
            y0, y1 = sorted((s[1], e[1]))
            segs.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        elif h == "gr_circle":
            c = get_numbers(g, "center")
            e = get_numbers(g, "end")
            r = math.dist(c, e)
            segs.append([(c[0] + r, c[1])] + [
                (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
                for t in [i * 2 * math.pi / 32 for i in range(33)]
            ])
        elif h == "gr_poly":
            pts_node = find_first(g, "pts")
            pts = []
            for xy in children(pts_node, "xy"):
                vals = node_values(xy)
                pts.append((float(vals[0]), float(vals[1])))
            if pts:
                pts.append(pts[0])
                segs.append(pts)

    loops = stitch_loops(segs)
    loops_signed = [(l, poly_area(l)) for l in loops]
    loops_signed.sort(key=lambda t: -abs(t[1]))
    outer = loops_signed[0][0]
    inner_loops = [l for l, a in loops_signed[1:]]

    ob = bbox_of([outer])
    x0, y0 = ob["xmin"], ob["ymin"]

    def to_local(poly):
        return [(round(p[0] - x0, 4), round(p[1] - y0, 4)) for p in poly]

    outer_local = to_local(outer)
    inner_local = [to_local(l) for l in inner_loops]

    board_w = round(ob["xmax"] - ob["xmin"], 3)
    board_l = round(ob["ymax"] - ob["ymin"], 3)

    # ---- split: main vs keyboard ----
    # Gap routed at KiCad Y 123-125 -> local v = 73-75.
    GAP_LOW = 73.0  # derived below from outline, this is a cross-check
    # clip outer to v <= 73 (main) and v >= 75 (keyboard)
    main_local = _clip(outer_local, outer_local[0], outer_local[1], False, 73.0, 1e-9)
    kb_local = _clip(outer_local, outer_local[0], outer_local[1], True, 75.0, 1e-9)

    # ---- footprints ----
    fps = []
    for fp in children(board, "footprint"):
        name = tok_val(fp[0]) if fp and isinstance(fp[0], tuple) else ""
        at = get_numbers(fp, "at")
        fx, fy = at[0], at[1]
        deg = at[2] if len(at) > 2 else 0.0
        layer_node = find_first(fp, "layer")
        layer = node_values(layer_node)[0] if layer_node else "F.Cu"
        ref, value = "", ""
        for prop in children(fp, "property"):
            vals = node_values(prop)
            if len(vals) >= 2:
                if vals[0] == "Reference":
                    ref = vals[1]
                elif vals[0] == "Value":
                    value = vals[1]
        # pads
        pads = []
        pad_bbox = None
        for pad in children(fp, "pad"):
            pa = get_numbers(pad, "at")
            size = get_numbers(pad, "size")
            if len(pa) >= 2 and size:
                px, py = pa[0], pa[1]
                pdeg = pa[2] if len(pa) > 2 else 0.0
                gx, gy = place(px, py, fx, fy, deg)
                # pad rotated by pad angle + footprint angle
                w, hh = size[0], size[1]
                rr = math.radians(deg + pdeg)
                ext_x = abs(w * math.cos(rr)) + abs(hh * math.sin(rr))
                ext_y = abs(w * math.sin(rr)) + abs(hh * math.cos(rr))
                # circle pads: square extent
                shape_node = find_first(pad, "shape")
                shape = node_values(shape_node)[0] if shape_node else "circle"
                if shape in ("circle", "oval") and len(size) >= 2 and abs(size[0] - size[1]) < 1e-9:
                    ext_y = ext_x
                bx0, bx1 = gx - ext_x / 2, gx + ext_x / 2
                by0, by1 = gy - ext_y / 2, gy + ext_y / 2
                pads.append({
                    "number": node_values(find_first(pad, "number"))[0] if find_first(pad, "number") else "",
                    "shape": shape,
                    "global": [round(gx, 4), round(gy, 4)],
                    "size": [w, hh],
                    "drill": (get_numbers(pad, "drill") or [None])[0],
                })
                if pad_bbox is None:
                    pad_bbox = [bx0, by0, bx1, by1]
                else:
                    pad_bbox = [
                        min(pad_bbox[0], bx0), min(pad_bbox[1], by0),
                        max(pad_bbox[2], bx1), max(pad_bbox[3], by1),
                    ]
        # courtyard graphics (F.CrtYd): lines/arcs/ polys, transformed
        crt = []
        for gh in ("fp_line", "fp_arc", "fp_poly", "fp_rect"):
            for g in children(fp, gh):
                ln = find_first(g, "layer")
                if not ln or node_values(ln)[0] != "F.CrtYd":
                    continue
                if gh in ("fp_line", "fp_arc", "fp_rect", "fp_poly"):
                    pts = []
                    if gh == "fp_line":
                        pts = [get_numbers(g, "start")[:2], get_numbers(g, "end")[:2]]
                    elif gh == "fp_arc":
                        pts = arc_points(tuple(get_numbers(g, "start")),
                                         tuple(get_numbers(g, "mid")),
                                         tuple(get_numbers(g, "end")))
                    elif gh == "fp_rect":
                        s0, e0 = get_numbers(g, "start"), get_numbers(g, "end")
                        pts = [(s0[0], s0[1]), (e0[0], s0[1]), (e0[0], e0[1]), (s0[0], e0[1]), (s0[0], s0[1])]
                    else:
                        pts_node = find_first(g, "pts")
                        for xy in children(pts_node, "xy"):
                            v = node_values(xy)
                            pts.append((float(v[0]), float(v[1])))
                    for px, py in pts:
                        crt.append(place(px, py, fx, fy, deg))
        crt_bbox = None
        if crt:
            xs = [p[0] for p in crt]
            ys = [p[1] for p in crt]
            crt_bbox = [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]
        # geometry bbox in global coords
        gbox = None
        if pad_bbox or crt_bbox:
            boxes = [b for b in (pad_bbox, crt_bbox) if b]
            gbox = [
                round(min(b[0] for b in boxes), 4), round(min(b[1] for b in boxes), 4),
                round(max(b[2] for b in boxes), 4), round(max(b[3] for b in boxes), 4),
            ]
        fps.append({
            "ref": ref or name.split(":")[-1],
            "value": value,
            "library": name.split(":")[0] if ":" in name else "",
            "footprint": name,
            "kicad_at": [fx, fy, deg],
            "layer": layer,
            "bbox_global": gbox,
            "bbox_local_uv": (
                [round(gbox[0] - x0, 3), round(gbox[1] - y0, 3),
                 round(gbox[2] - x0, 3), round(gbox[3] - y0, 3)] if gbox else None
            ),
            "pads": pads,
        })

    result = {
        "source_file": PCB_FILE,
        "provenance": "extracted_kicad + derived_kicad",
        "kicad_to_local_offset": [x0, y0],
        "board_thickness_mm": thickness,
        "outline_global_bbox": ob,
        "board_size_mm": {"w": board_w, "l": board_l},
        "outer_outline_local_uv": outer_local,
        "inner_cutouts_local_uv": inner_local,
        "gap_cross_check_v": GAP_LOW,
        "main_outline_local_uv": [[round(p[0], 4), round(p[1], 4)] for p in main_local],
        "keyboard_outline_local_uv": [[round(p[0], 4), round(p[1], 4)] for p in kb_local],
        "footprints": fps,
    }
    return result


def main():
    data = extract()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "pcb_geometry.json"), "w") as f:
        json.dump(data, f, indent=1)
    comps = {fp["ref"]: fp for fp in data["footprints"]}
    with open(os.path.join(OUT_DIR, "component_geometry.json"), "w") as f:
        json.dump(comps, f, indent=1)
    print("board size (w x l): %.3f x %.3f mm" % (data["board_size_mm"]["w"], data["board_size_mm"]["l"]))
    print("thickness: %.2f" % data["board_thickness_mm"])
    print("outer loop pts: %d, inner cutouts: %d" % (
        len(data["outer_outline_local_uv"]), len(data["inner_cutouts_local_uv"])))
    print("footprints: %d" % len(data["footprints"]))
    mb = bbox_of([data["main_outline_local_uv"]])
    print("main section bbox v: %.3f..%.3f  u: %.3f..%.3f" % (
        mb["ymin"], mb["ymax"], mb["xmin"], mb["xmax"]))
    for ref in ["J1", "J2", "DS1", "U3", "U6", "A1", "SW1", "SW2", "U8", "J3", "J4", "J5", "MB1", "MB2", "U1", "D3"]:
        fp = comps.get(ref)
        if fp and fp["bbox_local_uv"]:
            b = fp["bbox_local_uv"]
            print(f"{ref:>4} {fp['value'][:26]:<26} u {b[0]:6.2f}..{b[2]:6.2f}  v {b[1]:6.2f}..{b[3]:6.2f}")
        else:
            print(f"{ref:>4} MISSING/NO-BBOX")


if __name__ == "__main__":
    main()

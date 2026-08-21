#!/usr/bin/env python3
"""photobake — generic photo-to-CAD texturing pipeline.

Takes a declarative job list (tools/photobake_jobs.json): for each FACE,
crop a photo region (box | largest dark board | half-split), perspective-
rectify it to the true board aspect, pick one of 8 orientations by
fiducial scoring against CAD truth, then bake it as a textured plane at
the part's real position in the carrier assembly. Emits:

  exports/<prefix>_hybrid.glb          photo-on-3D, rotatable
  renders/<prefix>_hybrid_{iso,top,bottom}.png
  exports/<prefix>_turntable.mp4       (local only; gitignored)
  analysis/photobake_report.json       orientation evidence

Texture orientation convention (ALL sources and scorers):
  image top = the board's FAR end in carrier +Y, image left = u negative
  (top-view convention). Planes viewed from BELOW additionally U-mirror
  the texture at bake time — mirroring is applied HERE, never by flipping
  the convention.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import numpy as np
from PIL import Image

from cad import holder
from cad.parameters import Measured as M
from scripts.orient_photos import (TRANSFORMS, apply_transform,
                                   board_corners, find_coeffs,
                                   largest_dark_region_mask, landmarks)

CACHE = "/tmp/opencode/photobake"
REPORT = "analysis/photobake_report.json"


def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        import urllib.request
        urllib.request.urlretrieve(url, path)
    return path


def source_image(spec):
    if "url" in spec:
        return Image.open(fetch(spec["url"], spec["cache"])).convert("RGB")
    return Image.open(os.path.join(CACHE, spec["file"])).convert("RGB")


def crop_region(img, how):
    if how.get("box"):
        return img.crop(tuple(how["box"]))
    if how.get("half") in ("left", "right"):
        w = img.width
        return img.crop((0, 0, w // 2, img.height) if how["half"] == "left"
                        else (w // 2, 0, w, img.height))
    a = np.asarray(img).astype(float)
    lum = a.mean(axis=2)
    mask = largest_dark_region_mask(lum < how.get("thresh", 110))
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    return img.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))


def rectify(img, out_w, out_h, thresh=110):
    """Perspective-rectify using corners of the largest dark region on
    the (possibly cropped) image. If that region already touches >=3
    image edges, corner extremes degenerate to the frame -> fall back to
    an axis-aligned bbox resize."""
    a = np.asarray(img).astype(float)
    lum = a.mean(axis=2)
    mask = largest_dark_region_mask(lum < thresh)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    H, W = lum.shape
    touches = sum(int(v) for v in (rows[0] <= 2, rows[-1] >= H - 3,
                                   cols[0] <= 2, cols[-1] >= W - 3))
    if touches >= 3:
        box = (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)
        return img.crop(box).resize((out_w, out_h), Image.BICUBIC)
    pts = board_corners(mask)
    src = [pts["tl"], pts["tr"], pts["br"], pts["bl"]]
    dst = [(0, 0), (out_w - 1, 0), (out_w - 1, out_h - 1), (0, out_h - 1)]
    coeffs = find_coeffs(dst, src)
    return img.transform((out_w, out_h), Image.PERSPECTIVE, coeffs,
                         resample=Image.BICUBIC)


def fiducial_score(lm, targets):
    """targets: {"silver": (cv, cu, w_v, w_u), "green": (...)?}"""
    s = 0.0
    for key, (tv, tu, wv, wu) in targets.items():
        if lm.get(key):
            s -= abs(lm[key]["cv"] - tv) * wv
            s -= abs(lm[key]["cu"] - tu) * wu
    return s


def bake_face(face):
    if face["source"].get("style") == "flat_dark":
        w, h = face["aspect"]
        tex = Image.new("RGB", (int(w * 20), int(h * 20)), (26, 28, 32))
        out = os.path.join(CACHE, f"bake_{face['name']}.png")
        tex.save(out)
        return {
            "name": face["name"], "transform": "flat_dark", "score": 0.0,
            "landmarks_cu_cv_n": {}, "plane": face["plane"], "texture": out,
            "u_mirror": face["plane"].get("face") == "down",
        }
    img = source_image(face["source"])
    if face["source"].get("box"):
        img = img.crop(tuple(face["source"]["box"]))
    if face.get("rectify", True):
        w, h = face["aspect"]
        img = rectify(img, int(w * 20), int(h * 20))
    best = None
    for t in TRANSFORMS:
        tex = apply_transform(img, t)
        lm = landmarks(np.asarray(tex).astype(float))
        s = fiducial_score(lm, face["fiducials"])
        if best is None or s > best[0]:
            best = (s, t, lm)
    s, t, lm = best
    tex = apply_transform(img, t)
    out = os.path.join(CACHE, f"bake_{face['name']}.png")
    tex.save(out)
    return {
        "name": face["name"], "transform": t, "score": round(s, 3),
        "landmarks_cu_cv_n": {k: (None if v is None else
                                  (round(v["cu"], 2), round(v["cv"], 2), v["n"]))
                              for k, v in lm.items()},
        "plane": face["plane"], "texture": out,
        "u_mirror": face["plane"].get("face") == "down",
    }


def plane_placement(plane):
    """Carrier-frame rectangle + z for each named placement. Planes sit at
    the PCB LAMINATE faces (slab planes), never at whole-part bbox extremes
    - hanging relays/battery holders would put the texture deep inside
    other features."""
    from cad import parameters as P
    off = 0.15
    if plane["board"] == "simhat":
        sh = holder.place_simhat()
        bb = sh.BoundingBox()
        cx, cy = (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2
        w, h = M.simhat_pcb_w, M.simhat_pcb_l
        z = (P.SIMHAT_SUPPORT_H - off if plane["face"] == "down"
             else P.SIMHAT_SUPPORT_H + M.simhat_pcb_t + off)
        return cx, cy, z, w, h
    a = holder.place_a7670()
    bb = a.BoundingBox()
    cx = (bb.xmin + bb.xmax) / 2
    cy = (bb.ymin + bb.ymax) / 2
    w, h = M.a7670_pcb_w, M.a7670_pcb_l
    z = (P.A7670_STANDOFF_H - off if plane["face"] == "down"
         else P.A7670_STANDOFF_H + M.a7670_pcb_t + off)
    return cx, cy, z, w, h


def render(bakes, prefix, video=False):
    import vtk
    from vtk.util import numpy_support

    def tess(shape):
        verts, tris = shape.tessellate(0.08, 0.12)
        pd = vtk.vtkPolyData()
        pts = vtk.vtkPoints()
        for v in verts:
            pts.InsertNextPoint(v.x, v.y, v.z)
        pd.SetPoints(pts)
        arr = vtk.vtkCellArray()
        for t in tris:
            arr.InsertNextCell(3, t)
        pd.SetPolys(arr)
        return pd

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.93, 0.95)
    for shape, rgb in ((holder.build_carrier().val(), (0.72, 0.73, 0.76)),):
        m = vtk.vtkPolyDataMapper()
        m.SetInputData(tess(shape))
        act = vtk.vtkActor()
        act.SetMapper(m)
        act.GetProperty().SetColor(*rgb)
        ren.AddActor(act)

    for b in bakes:
        cx, cy, z, w, h = plane_placement(b["plane"])
        down = b["plane"].get("face") == "down"
        pd = vtk.vtkPolyData()
        pts = vtk.vtkPoints()
        for x, y in ((cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
                     (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)):
            pts.InsertNextPoint(x, y, z)
        pd.SetPoints(pts)
        arr = vtk.vtkCellArray()
        # single-sided planes: down faces wound so the normal points -Z,
        # up faces +Z; with backface culling each photo is visible only
        # from its own side (kills the ghost underside in top views)
        tri = ((0, 2, 1), (0, 3, 2)) if down else ((0, 1, 2), (0, 2, 3))
        for t in tri:
            arr.InsertNextCell(3, t)
        pd.SetPolys(arr)
        tc = vtk.vtkFloatArray()
        tc.SetNumberOfComponents(2)
        u0, u1 = (1.0, 0.0) if b["u_mirror"] else (0.0, 1.0)
        for u, v in ((u0, 0), (u1, 0), (u1, 1), (u0, 1)):
            tc.InsertNextTuple2(u, v)
        pd.GetPointData().SetTCoords(tc)

        img = Image.open(b["texture"]).convert("RGB").transpose(
            Image.FLIP_TOP_BOTTOM)
        a = np.asarray(img, dtype=np.uint8)
        va = numpy_support.numpy_to_vtk(a.reshape(-1, 3), deep=1)
        vi = vtk.vtkImageData()
        vi.SetDimensions(img.width, img.height, 1)
        vi.GetPointData().SetScalars(va)
        tex = vtk.vtkTexture()
        tex.SetInputData(vi)

        m = vtk.vtkPolyDataMapper()
        m.SetInputData(pd)
        act = vtk.vtkActor()
        act.SetMapper(m)
        act.SetTexture(tex)
        act.GetProperty().BackfaceCullingOn()
        ren.AddActor(act)

    bb = holder.build_carrier().val().BoundingBox()
    cx, cy, cz = (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, \
        (bb.zmin + bb.zmax) / 2
    d = max(bb.xmax - bb.xmin, bb.ymax - bb.ymin) * 0.85 + 25
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(1500, 1100)
    win.AddRenderer(ren)
    shot = vtk.vtkWindowToImageFilter()
    shot.SetInput(win)
    views = {"iso": ((1.0, -0.9, 0.55), (0, 0, 1)),
             "top": ((0.3, 0.3, 1.0), (0, 1, 0)),
             "bottom": ((0.3, 0.3, -1.0), (0, 1, 0))}
    for name, (dvec, up) in views.items():
        cam = ren.GetActiveCamera()
        cam.SetPosition(cx + dvec[0] * d, cy + dvec[1] * d, cz + dvec[2] * d)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(*up)
        cam.ParallelProjectionOn()
        ren.ResetCamera()
        win.Render()
        shot.Modified()
        w = vtk.vtkPNGWriter()
        w.SetFileName(f"renders/{prefix}_hybrid_{name}.png")
        w.SetInputConnection(shot.GetOutputPort())
        w.Write()
        print(f"wrote renders/{prefix}_hybrid_{name}.png")

    import trimesh
    scene = trimesh.Scene()
    cv_, cf_ = holder.build_carrier().val().tessellate(0.1, 0.15)
    cm = trimesh.Trimesh(
        vertices=np.array([[p.x, p.y, p.z] for p in cv_]),
        faces=np.array(cf_))
    cm.visual.face_colors = [184, 186, 194, 255]
    scene.add_geometry(cm, node_name="carrier")
    for b in bakes:
        cx, cy, z, w, h = plane_placement(b["plane"])
        down = b["plane"].get("face") == "down"
        v = np.array([[cx - w / 2, cy - h / 2, z], [cx + w / 2, cy - h / 2, z],
                      [cx + w / 2, cy + h / 2, z], [cx - w / 2, cy + h / 2, z]])
        f = np.array([[0, 2, 1], [0, 3, 2]]) if down \
            else np.array([[0, 1, 2], [0, 2, 3]])
        uv = np.array([[1, 0], [0, 0], [0, 1], [1, 1]]) if b["u_mirror"] \
            else np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
        mesh = trimesh.Trimesh(vertices=v, faces=f)
        mesh.visual = trimesh.visual.TextureVisuals(
            uv=uv, image=Image.open(b["texture"]))
        scene.add_geometry(mesh, node_name=b["name"])
    glb = scene.export(file_type="glb")
    with open(f"exports/{prefix}_hybrid.glb", "wb") as fh:
        fh.write(glb)
    print(f"wrote exports/{prefix}_hybrid.glb")

    if video:
        import math
        import shutil
        tmp = "/tmp/opencode/photobake_frames"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        cam = ren.GetActiveCamera()
        cam.ParallelProjectionOn()
        cam.SetFocalPoint(cx, cy, cz)
        for i in range(300):
            ang = 2 * math.pi * i / 300
            elev = 0.35 + 0.25 * math.sin(4 * math.pi * i / 300)
            cam.SetPosition(cx + d * math.cos(ang), cy + d * math.sin(ang),
                            cz + d * elev)
            cam.SetViewUp(0, 0, 1)
            ren.ResetCamera()
            win.Render()
            shot.Modified()
            w = vtk.vtkPNGWriter()
            w.SetFileName(f"{tmp}/f_{i:04d}.png")
            w.SetInputConnection(shot.GetOutputPort())
            w.Write()
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", "30", "-i", f"{tmp}/f_%04d.png",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
             f"exports/{prefix}_turntable.mp4"],
            check=True, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"wrote exports/{prefix}_turntable.mp4")


def main():
    with open("tools/photobake_jobs.json") as f:
        jobs = json.load(f)
    report = {}
    bakes = []
    for face in jobs["faces"]:
        b = bake_face(face)
        bakes.append(b)
        report[b["name"]] = b
        print(f"{b['name']}: {b['transform']} score={b['score']} "
              f"landmarks={b['landmarks_cu_cv_n']}")
    with open(REPORT, "w") as f:
        json.dump({"jobs": jobs, "bakes": report}, f, indent=2)
    render(bakes, jobs.get("prefix", "lilygo"), video="--video" in sys.argv)
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()

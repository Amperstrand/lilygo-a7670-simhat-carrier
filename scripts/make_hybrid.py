#!/usr/bin/env python3
"""Hybrid photo-textured rendering: real product photos mapped onto CAD
geometry so the final assembly can be inspected as it will look.

Outputs:
  exports/lilygo_hybrid_assembly.glb - carrier + photo-textured board planes
        (open in any GLB viewer: photos on 3D, rotatable)
  renders/hybrid_iso.png / hybrid_top.png / hybrid_under.png - VTK stills
        with the same textures
  analysis/hybrid_alignment.json - programmatic alignment evidence
        (photo crop aspect vs measured PCB outline; vision check is done
        separately on the stills)

Alignment method: photos are near-orthographic top/bottom views on light
backgrounds; the PCB region is found as the dark-pixel bounding box,
cropped, and stretched to the STEP-measured outline rectangle placed at
the board's true position/orientation in the carrier. SimHat is FLIPPED
on the carrier, so the 'front' (relay) photo maps to its DOWN face and
the 'back' (socket) photo to its UP face - matching installation.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
from PIL import Image

import cadquery as cq

from cad import holder
from cad import parameters as P
from cad.parameters import Measured as M

PHOTO_DIR = "/tmp/opencode"
OUT_GLB = "exports/lilygo_hybrid_assembly.glb"
STILLS = {"renders/hybrid_iso.png": "iso",
          "renders/hybrid_top.png": "top",
          "renders/hybrid_under.png": "bottom"}


def crop_dark_region(path, dark_thresh=105, pad=0, split_boards=False):
    """Dark-pixel bounding-box crop. split_boards=True for photos showing
    TWO boards side by side: keeps the LEFT board only by cutting at the
    widest empty column gap inside the dark region (marketing photos are
    angled, so aspect never matches the PCB exactly - recorded honestly
    in hybrid_alignment.json)."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im)
    lum = a.mean(axis=2)
    mask = lum < dark_thresh
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    c0, c1 = int(cols[0]), int(cols[-1])
    if split_boards:
        col_occupancy = mask[rows[0]:rows[-1] + 1, c0:c1 + 1].sum(axis=0)
        prof = col_occupancy.astype(float)
        k = 41
        smooth = np.convolve(prof, np.ones(k) / k, mode="same")
        mid_lo, mid_hi = int(len(smooth) * 0.30), int(len(smooth) * 0.70)
        valley = mid_lo + int(np.argmin(smooth[mid_lo:mid_hi]))
        cut = c0 + valley
        sub = mask[:, :cut]
        cols2 = np.where(sub.any(axis=0))[0]
        rows2 = np.where(sub.any(axis=1))[0]
        rows = rows2
        c0, c1 = int(cols2[0]), int(cols2[-1])
    box = (c0 - pad, int(rows[0]) - pad, c1 + 1 + pad, int(rows[-1]) + 1 + pad)
    return im.crop(box), box, im.size


def plane_mesh(w, h, texture_rgba, z, cx, cy, flip_u=False):
    import trimesh
    v = np.array([[cx - w / 2, cy - h / 2, z], [cx + w / 2, cy - h / 2, z],
                  [cx + w / 2, cy + h / 2, z], [cx - w / 2, cy + h / 2, z]],
                 dtype=np.float64)
    f = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    if flip_u:
        uv[:, 0] = 1 - uv[:, 0]
    mesh = trimesh.Trimesh(vertices=v, faces=f)
    if texture_rgba.mode != "RGBA":
        texture_rgba = texture_rgba.convert("RGBA")
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=texture_rgba)
    return mesh


def simhat_faces():
    """Carrier-frame rectangles for the flipped SimHat: relay photo on the
    underside, socket photo on top. Returns (x, y, w, h, z_low_face,
    z_high_face) and the flip flags per face."""
    sh = holder.place_simhat()
    bb = sh.BoundingBox()
    return {
        "cx": (bb.xmin + bb.xmax) / 2,
        "cy": (bb.ymin + bb.ymax) / 2,
        "w": M.simhat_pcb_w,
        "h": M.simhat_pcb_l,
        "z_down": bb.zmin - 0.05,
        "z_up": bb.zmax + 0.05,
    }


def main():
    report = {"photos": {}}

    front, box_f, size_f = crop_dark_region(f"{PHOTO_DIR}/T-SimHat.jpg")
    back, box_b, size_b = crop_dark_region(f"{PHOTO_DIR}/H559_8.jpg",
                                           split_boards=True)
    for name, img, box, full in (("front", front, box_f, size_f),
                                 ("back", back, box_b, size_b)):
        w_px, h_px = img.size
        aspect = w_px / h_px
        report["photos"][name] = {
            "crop_box": list(box), "full_size": list(full),
            "crop_px": [w_px, h_px], "aspect_w_over_h": round(aspect, 4),
        }
    target = M.simhat_pcb_w / M.simhat_pcb_l
    report["target_aspect_w_over_h"] = round(target, 4)
    report["aspect_delta"] = {
        k: round(report["photos"][k]["aspect_w_over_h"] - target, 4)
        for k in report["photos"]}

    f = simhat_faces()

    import trimesh
    scene = trimesh.Scene()

    carrier = holder.build_carrier().val()
    cv, cf = carrier.tessellate(0.1, 0.15)
    verts = np.array([[p.x, p.y, p.z] for p in cv], dtype=np.float64)
    faces = np.array(cf, dtype=np.int64)
    cm = trimesh.Trimesh(vertices=verts, faces=faces)
    cm.visual.face_colors = [184, 186, 194, 255]
    scene.add_geometry(cm, node_name="carrier")

    # Flipped board: relay side DOWN -> front photo on the low face.
    # Product photos have +Y_up board; on the carrier the board is flipped
    # about Y, which mirrors X -> flip_u aligns left/right features.
    low_face = plane_mesh(f["w"], f["h"], front, f["z_down"],
                          f["cx"], f["cy"], flip_u=globals().get("ORIENT_FLIPS",(True,False))[0])
    up_face = plane_mesh(f["w"], f["h"], back, f["z_up"],
                         f["cx"], f["cy"], flip_u=False)
    scene.add_geometry(low_face, node_name="simhat_front_photo")
    scene.add_geometry(up_face, node_name="simhat_back_photo")

    a76 = holder.place_a7670()
    av, af = a76.tessellate(0.08, 0.12)
    am = trimesh.Trimesh(
        vertices=np.array([[p.x, p.y, p.z] for p in av], dtype=np.float64),
        faces=np.array(af, dtype=np.int64))
    am.visual.face_colors = [64, 140, 77, 255]
    scene.add_geometry(am, node_name="T-A7670X_step")

    glb = scene.export(file_type="glb")
    with open(OUT_GLB, "wb") as fh:
        fh.write(glb)
    print(f"wrote {OUT_GLB} ({os.path.getsize(OUT_GLB)} bytes)")

    os.makedirs("renders", exist_ok=True)
    render_stills(low_face, up_face, am, cm)

    os.makedirs("analysis", exist_ok=True)
    with open("analysis/hybrid_alignment.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print("wrote analysis/hybrid_alignment.json")


def build_photo_scene():
    """Shared scene assembly for stills and turntable video."""
    import vtk
    from vtk.util import numpy_support

    def tess_polydata(shape):
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

    def make_texture(pil_img):
        img = pil_img.convert("RGB").transpose(Image.FLIP_TOP_BOTTOM)
        a = np.asarray(img, dtype=np.uint8)
        vtk_arr = numpy_support.numpy_to_vtk(a.reshape(-1, 3), deep=1)
        vtk_img = vtk.vtkImageData()
        vtk_img.SetDimensions(img.width, img.height, 1)
        vtk_img.GetPointData().SetScalars(vtk_arr)
        tex = vtk.vtkTexture()
        tex.SetInputData(vtk_img)
        return tex

    def textured_plane(center_x, center_y, z, w, h, pil_img, flip_u):
        pd = vtk.vtkPolyData()
        pts = vtk.vtkPoints()
        for x, y in ((center_x - w / 2, center_y - h / 2),
                     (center_x + w / 2, center_y - h / 2),
                     (center_x + w / 2, center_y + h / 2),
                     (center_x - w / 2, center_y + h / 2)):
            pts.InsertNextPoint(x, y, z)
        pd.SetPoints(pts)
        arr = vtk.vtkCellArray()
        arr.InsertNextCell(3, (0, 1, 2))
        arr.InsertNextCell(3, (0, 2, 3))
        pd.SetPolys(arr)
        u0 = 1.0 if flip_u else 0.0
        u1 = 0.0 if flip_u else 1.0
        tcoord = vtk.vtkFloatArray()
        tcoord.SetNumberOfComponents(2)
        for u, v in ((u0, 0), (u1, 0), (u1, 1), (u0, 1)):
            tcoord.InsertNextTuple2(u, v)
        pd.GetPointData().SetTCoords(tcoord)
        return pd

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.93, 0.95)

    for shape, rgb in ((holder.build_carrier().val(), (0.72, 0.73, 0.76)),
                       (holder.place_a7670(), (0.25, 0.55, 0.30))):
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(tess_polydata(shape))
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*rgb)
        ren.AddActor(actor)

    f = simhat_faces()
    for z, img, flip in ((f["z_down"], front_img_holder[0],
                         globals().get("ORIENT_FLIPS",(True,False))[0]),
                        (f["z_up"], back_img_holder[0],
                         globals().get("ORIENT_FLIPS",(True,False))[1])):
        pd = textured_plane(f["cx"], f["cy"], z, f["w"], f["h"], img, flip)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(pd)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.SetTexture(make_texture(img))
        ren.AddActor(actor)

    bb = holder.build_carrier().val().BoundingBox()
    return ren, ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2,
                 (bb.zmin + bb.zmax) / 2,
                 max(bb.xmax - bb.xmin, bb.ymax - bb.ymin) * 0.85 + 25)


def render_stills(low_face, up_face, a76_mesh, carrier_mesh):
    import vtk
    ren, (cx, cy, cz, d) = build_photo_scene()
    views = {
        "iso": ((1.0, -0.9, 0.55), (0, 0, 1)),
        "top": ((0.3, 0.3, 1.0), (0, 1, 0)),
        "bottom": ((0.3, 0.3, -1.0), (0, 1, 0)),
    }
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(1500, 1100)
    win.AddRenderer(ren)
    shot = vtk.vtkWindowToImageFilter()
    shot.SetInput(win)
    for path, name in STILLS.items():
        dvec, up = views[name]
        cam = ren.GetActiveCamera()
        cam.SetPosition(cx + dvec[0] * d, cy + dvec[1] * d, cz + dvec[2] * d)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(*up)
        cam.ParallelProjectionOn()
        ren.ResetCamera()
        win.Render()
        shot.Modified()
        w = vtk.vtkPNGWriter()
        w.SetFileName(path)
        w.SetInputConnection(shot.GetOutputPort())
        w.Write()
        print(f"wrote {path}")


def render_turntable(out_path, frames=240, fps=30, size=(1280, 800)):
    """Full-scan orbit video: 360 deg around Z with a slight elevation
    sweep, photo textures live. PNG frames -> system ffmpeg H.264."""
    import glob
    import math
    import shutil
    import subprocess

    import vtk

    tmp = "/tmp/opencode/turntable"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    ren, (cx, cy, cz, d) = build_photo_scene()
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.AddRenderer(ren)
    shot = vtk.vtkWindowToImageFilter()
    shot.SetInput(win)
    cam = ren.GetActiveCamera()
    cam.ParallelProjectionOn()
    cam.SetFocalPoint(cx, cy, cz)
    for i in range(frames):
        a = 2 * math.pi * i / frames
        elev = 0.35 + 0.25 * math.sin(2 * math.pi * 2 * i / frames)
        cam.SetPosition(cx + d * math.cos(a), cy + d * math.sin(a),
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
        ["ffmpeg", "-y", "-framerate", str(fps), "-i", f"{tmp}/f_%04d.png",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out_path],
        check=True, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out_path} ({os.path.getsize(out_path)} bytes, "
          f"{frames} frames @ {fps}fps)")


front_img_holder = []
back_img_holder = []


def _load_face_textures():
    """Prefer fiducial-oriented textures from orient_photos.py; fall back
    to raw crops (documented worse) when the /tmp artifacts are absent."""
    down = "/tmp/opencode/tex_down.png"
    up = "/tmp/opencode/tex_up.png"
    if os.path.exists(down) and os.path.exists(up):
        return Image.open(down), Image.open(up), False, False
    f, _, _ = crop_dark_region(f"{PHOTO_DIR}/T-SimHat.jpg")
    b, _, _ = crop_dark_region(f"{PHOTO_DIR}/H559_8.jpg",
                               split_boards=True)
    return f, b, True, False


if __name__ == "__main__":
    front_img, back_img, flip_d, flip_u = _load_face_textures()
    front_img_holder.append(front_img)
    back_img_holder.append(back_img)
    ORIENT_FLIPS = (flip_d, flip_u)
    main()
    if "--video" in sys.argv:
        render_turntable("exports/hybrid_turntable.mp4", frames=300, fps=30,
                         size=(1440, 900))

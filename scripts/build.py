#!/usr/bin/env python3
"""Rebuild all generated geometry from source: carrier (full + low profile),
coupon, assembly, per-section exports, renders, GLB, validated 3MF.
Deterministic; run from repo root.

Usage:
    python scripts/build.py             full-profile exports (spawns low pass)
    CARRIER_PROFILE=low python scripts/build.py --low-pass   low only
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import cadquery as cq

from cad import calicheck, fitcheck, holder
from cad import parameters as P

EXPORTS = "exports"
RENDERS = "renders"

VIEWS = {
    "top": ((0.3, 0.3, 1.0), (0, 1, 0)),
    "bottom": ((0.3, 0.3, -1.0), (0, 1, 0)),
    "iso": ((1.0, -0.9, 0.8), (0, 0, 1)),
    "iso_back": ((-1.0, 0.9, 0.8), (0, 0, 1)),
    "clip_end": ((0.15, 1.0, 0.35), (0, 0, 1)),
    "tray_end": ((0.15, -1.0, 0.35), (0, 0, 1)),
}

GLB_COLORS = {
    "carrier": (0.72, 0.73, 0.76),
    "board": (0.25, 0.55, 0.30),
    "simhat": (0.90, 0.70, 0.15),
}


def export_step(shape, path):
    cq.exporters.export(shape, path)
    print(f"wrote {path}")


def export_stl(shape, path):
    cq.exporters.export(shape, path, tolerance=0.01, angularTolerance=0.1)
    print(f"wrote {path}")


def render_png(entries, path, view, size=(1500, 1100), zoom=1.0, focus=None):
    """Offscreen VTK render. entries: list of (shape, rgb, tessellation).
    zoom<1 frames tighter; focus=(x,y,z) overrides the framing center."""
    view = VIEWS[view]
    import vtk
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.94, 0.94, 0.96)
    allbb = entries[0][0].BoundingBox()
    for shape, rgb, (tol, atol) in entries:
        verts, tris = shape.tessellate(tol, atol)
        pd = vtk.vtkPolyData()
        pts = vtk.vtkPoints()
        for v in verts:
            pts.InsertNextPoint(v.x, v.y, v.z)
        pd.SetPoints(pts)
        arr = vtk.vtkCellArray()
        for t in tris:
            arr.InsertNextCell(3, t)
        pd.SetPolys(arr)
        norm = vtk.vtkPolyDataNormals()
        norm.SetInputData(pd)
        norm.Update()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(norm.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*rgb)
        actor.GetProperty().SetInterpolationToPhong()
        actor.GetProperty().SetEdgeVisibility(1)
        actor.GetProperty().SetEdgeColor(0.25, 0.25, 0.28)
        actor.GetProperty().SetLineWidth(0.4)
        ren.AddActor(actor)
    cam = ren.GetActiveCamera()
    cx, cy, cz = ((allbb.xmin + allbb.xmax) / 2, (allbb.ymin + allbb.ymax) / 2,
                  (allbb.zmin + allbb.zmax) / 2)
    if focus:
        cx, cy, cz = focus
    dx, dy, dz = view[0]
    d = max(allbb.xmax - allbb.xmin, allbb.ymax - allbb.ymin,
            allbb.zmax - allbb.zmin) * 0.85 * zoom + 25
    cam.SetPosition(cx + dx * d, cy + dy * d, cz + dz * d)
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(*view[1])
    cam.ParallelProjectionOn()
    ren.ResetCamera()
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.AddRenderer(ren)
    win.Render()
    img = vtk.vtkWindowToImageFilter()
    img.SetInput(win)
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(img.GetOutputPort())
    writer.Write()
    print(f"wrote {path}")


def try_3mf(stl_path, out_path):
    if os.path.exists(out_path):
        os.remove(out_path)
    try:
        import trimesh
        mesh = trimesh.load(stl_path)
        trimesh.exchange.export.export_mesh(mesh, out_path, file_type="3mf")
        scene = trimesh.load(out_path)
        geoms = list(scene.geometry.values())
        total = sum(g.volume for g in geoms)
        if (geoms and all(g.is_watertight for g in geoms)
                and abs(total - mesh.volume) / mesh.volume < 0.01):
            print(f"wrote {out_path} (validated round-trip)")
            return True
        os.remove(out_path)
        print("3MF export failed validation; skipped")
    except Exception as e:
        if os.path.exists(out_path):
            os.remove(out_path)
        print(f"3MF skipped: {e}")
    return False


def export_glb(parts, out_path):
    """parts: list of (mesh_name, shape, tessellation)."""
    try:
        import numpy as np
        import trimesh
        scene = trimesh.Scene()
        for name, shape, (tol, atol) in parts:
            verts, tris = shape.tessellate(tol, atol)
            v = np.array([[p.x, p.y, p.z] for p in verts], dtype=np.float64)
            f = np.array(tris, dtype=np.int64)
            mesh = trimesh.Trimesh(vertices=v, faces=f)
            if not mesh.is_watertight:
                mesh.fill_holes()
            rgb = GLB_COLORS[name.split("_ref")[0]]
            mesh.visual.face_colors = [int(255 * c) for c in rgb] + [255]
            scene.add_geometry(mesh, node_name=name)
        data = scene.export(file_type="glb")
        with open(out_path, "wb") as f:
            f.write(data)
        back = trimesh.load(out_path)
        n = len(list(back.geometry.values()))
        print(f"wrote {out_path} ({n} mesh(es), round-trip ok)")
        return True
    except Exception as e:
        print(f"glb skipped: {e}")
        return False


def contact_sheet(paths_labels, out_path, cols=3):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("contact sheet skipped (Pillow unavailable)")
        return False
    imgs = []
    for p, label in paths_labels:
        im = Image.open(p).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([8, 8, 10 * len(label) + 22, 34], fill=(255, 255, 255))
        d.text((15, 14), label, fill=(20, 20, 24))
        imgs.append(im)
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * 12,
                              rows * h + (rows + 1) * 12), (235, 235, 238))
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        sheet.paste(im, (12 + c * (w + 12), 12 + r * (h + 12)))
    sheet.save(out_path)
    print(f"wrote {out_path}")
    return True


def build_profile_exports():
    low = P.PROFILE == "low"
    suffix = "_lowprofile" if low else ""

    if not low:
        print("== building calibration mini-coupon ==")
        cc = calicheck.build_calicheck()
        cc_name = f"{EXPORTS}/lilygo_calicheck_mini"
        export_step(cc, f"{cc_name}.step")
        export_stl(cc, f"{cc_name}.stl")
        try_3mf(f"{cc_name}.stl", f"{cc_name}.3mf")
        render_png([(cc.val(), GLB_COLORS["carrier"], (0.08, 0.12))],
                   f"{RENDERS}/calicheck_mini.png", "iso")

        print("== building gridfinity fit-check tray ==")
        tray = fitcheck.build_fitcheck_tray()
        tray_name = f"{EXPORTS}/lilygo_fitcheck_tray_gridfinity"
        export_step(tray, f"{tray_name}.step")
        export_stl(tray, f"{tray_name}.stl")
        try_3mf(f"{tray_name}.stl", f"{tray_name}.3mf")
        render_png([(tray.val(), GLB_COLORS["carrier"], (0.1, 0.15))],
                   f"{RENDERS}/fitcheck_tray.png", "iso")
        export_glb([("carrier_ref", tray.val(), (0.1, 0.15))],
                   f"{EXPORTS}/lilygo_fitcheck_tray_gridfinity.glb")

    print(f"== building carrier (profile={P.PROFILE}) ==")
    carrier = holder.build_carrier()
    export_step(carrier, f"{EXPORTS}/lilygo_a7670_simhat_carrier{suffix}.step")
    export_stl(carrier, f"{EXPORTS}/lilygo_a7670_simhat_carrier{suffix}.stl")

    if low:
        render_png([(carrier.val(), GLB_COLORS["carrier"], (0.1, 0.15))],
                   f"{RENDERS}/lowprofile.png", "iso")
        return

    print("== building test coupon ==")
    coupon = holder.build_coupon()
    export_step(coupon, f"{EXPORTS}/simhat_clip_test.step")
    export_stl(coupon, f"{EXPORTS}/simhat_clip_test.stl")

    print("== building assembly ==")
    asm, _, a76, sh = holder.build_assembly()
    asm.save(f"{EXPORTS}/lilygo_a7670_simhat_assembly.step")
    print(f"wrote {EXPORTS}/lilygo_a7670_simhat_assembly.step")

    print("== sections ==")
    os.makedirs(f"{EXPORTS}/sections", exist_ok=True)
    for name, wp in holder.build_sections().items():
        export_stl(wp, f"{EXPORTS}/sections/{name}.stl")
        export_step(wp, f"{EXPORTS}/sections/{name}.step")

    print("== renders ==")
    grey = GLB_COLORS["carrier"]
    green, amber = GLB_COLORS["board"], GLB_COLORS["simhat"]
    c = carrier.val()
    fine, coarse = (0.05, 0.1), (0.1, 0.15)
    render_png([(c, grey, coarse)], f"{RENDERS}/top.png", "top")
    render_png([(c, grey, coarse)], f"{RENDERS}/bottom.png", "bottom")
    render_png([(c, grey, coarse)], f"{RENDERS}/isometric.png", "iso")
    render_png([(c, grey, coarse), (a76, green, fine), (sh, amber, fine)],
               f"{RENDERS}/assembly.png", "iso")
    render_png([(c, grey, coarse), (a76, green, fine), (sh, amber, fine)],
               f"{RENDERS}/assembly_back.png", "iso_back")
    render_png([(c, grey, coarse), (a76, green, fine), (sh, amber, fine)],
               f"{RENDERS}/assembly_clip_end.png", "clip_end")
    render_png([(c, grey, coarse)], f"{RENDERS}/carrier_tray_end.png", "tray_end")
    a76_c = (P.a7670_cx(), 0.0, 20.0)
    render_png([(c, grey, coarse), (a76, green, fine), (sh, amber, fine)],
               f"{RENDERS}/a7670_closeup.png", "iso", zoom=0.42, focus=a76_c)
    sh_c = (P.simhat_cx(), 10.0, 18.0)
    render_png([(c, grey, coarse), (a76, green, fine), (sh, amber, fine)],
               f"{RENDERS}/simhat_closeup.png", "iso_back", zoom=0.42, focus=sh_c)

    contact_sheet([
        (f"{RENDERS}/top.png", "top"),
        (f"{RENDERS}/isometric.png", "isometric"),
        (f"{RENDERS}/bottom.png", "bottom"),
        (f"{RENDERS}/assembly.png", "assembly (iso)"),
        (f"{RENDERS}/assembly_back.png", "assembly (rear iso)"),
        (f"{RENDERS}/assembly_clip_end.png", "assembly (clip end)"),
        (f"{RENDERS}/a7670_closeup.png", "T-A7670X close-up"),
        (f"{RENDERS}/simhat_closeup.png", "T-SimHat close-up (headers up)"),
        (f"{RENDERS}/carrier_tray_end.png", "antenna tray end"),
    ], f"{RENDERS}/contact_sheet.png")

    print("== 3MF + GLB ==")
    try_3mf(f"{EXPORTS}/lilygo_a7670_simhat_carrier.stl",
            f"{EXPORTS}/lilygo_a7670_simhat_carrier.3mf")
    export_glb([
        ("carrier_ref", c, coarse),
        ("board_ref", a76, fine),
        ("simhat_ref", sh, fine),
    ], f"{EXPORTS}/lilygo_a7670_simhat_assembly.glb")
    export_glb([("carrier_ref", c, coarse)],
               f"{EXPORTS}/lilygo_a7670_simhat_carrier.glb")


def main():
    os.makedirs(EXPORTS, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)

    if "--low-pass" in sys.argv:
        build_profile_exports()
        return

    build_profile_exports()
    env = dict(os.environ, CARRIER_PROFILE="low")
    r = subprocess.run([sys.executable, __file__, "--low-pass"], env=env)
    if r.returncode != 0:
        sys.exit(r.returncode)
    print("build complete")


if __name__ == "__main__":
    main()

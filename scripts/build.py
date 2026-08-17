#!/usr/bin/env python3
"""Rebuild all generated geometry from source: carrier, coupon, assembly,
renders, and optional 3MF. Deterministic; run from repo root.

Usage: python scripts/build.py   (or ./build.sh)
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import cadquery as cq

from cad import holder

EXPORTS = "exports"
RENDERS = "renders"


def export_step(shape, path):
    cq.exporters.export(shape, path)
    print(f"wrote {path}")


def export_stl(shape, path):
    cq.exporters.export(shape, path, tolerance=0.01, angularTolerance=0.1)
    print(f"wrote {path}")


def render_png(shapes_with_colors, path, view, size=(1400, 1050)):
    """Offscreen VTK render; returns False when unavailable."""
    try:
        import vtk
    except ImportError:
        return False
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.93, 0.95)
    for shape, rgb in shapes_with_colors:
        verts, tris = shape.tessellate(0.15, 0.2)
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
        ren.AddActor(actor)
    cam = ren.GetActiveCamera()
    bb = shapes_with_colors[0][0].BoundingBox()
    cx, cy, cz = (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2
    d = max(bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin) * 0.9 + 20
    views = {
        "top": ((cx, cy + 0.001, cz + d), (0, 1, 0)),
        "bottom": ((cx, cy + 0.001, cz - d), (0, 1, 0)),
        "iso": ((cx + d, cy - d, cz + d), (0, 0, 1)),
    }
    pos, up = views[view]
    cam.SetPosition(*pos)
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(*up)
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
    return True


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


def main():
    os.makedirs(EXPORTS, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)

    print("== building carrier ==")
    carrier = holder.build_carrier()
    export_step(carrier, f"{EXPORTS}/lilygo_a7670_simhat_carrier.step")
    export_stl(carrier, f"{EXPORTS}/lilygo_a7670_simhat_carrier.stl")

    print("== building test coupon ==")
    coupon = holder.build_coupon()
    export_step(coupon, f"{EXPORTS}/simhat_clip_test.step")
    export_stl(coupon, f"{EXPORTS}/simhat_clip_test.stl")

    print("== building assembly ==")
    asm, _, a76, sh = holder.build_assembly()
    asm.save(f"{EXPORTS}/lilygo_a7670_simhat_assembly.step")
    print(f"wrote {EXPORTS}/lilygo_a7670_simhat_assembly.step")

    print("== renders ==")
    grey, green, amber = (0.72, 0.73, 0.76), (0.25, 0.55, 0.30), (0.90, 0.70, 0.15)
    c = carrier.val()
    ok = True
    ok &= render_png([(c, grey)], f"{RENDERS}/top.png", "top")
    ok &= render_png([(c, grey)], f"{RENDERS}/bottom.png", "bottom")
    ok &= render_png([(c, grey)], f"{RENDERS}/isometric.png", "iso")
    ok &= render_png([(c, grey), (a76, green), (sh, amber)],
                     f"{RENDERS}/assembly.png", "iso")
    if not ok:
        for name, shape in [("top", c), ("bottom", c), ("isometric", c)]:
            cq.exporters.export(
                cq.Workplane(obj=shape), f"{RENDERS}/{name}.svg",
                opt={"projectionDir": {"top": (0, 0, 1), "bottom": (0, 0, -1),
                                       "isometric": (1, 1, 1)}[name],
                     "showAxes": False, "strokeWidth": 0.4})
            print(f"wrote {RENDERS}/{name}.svg (VTK unavailable fallback)")

    try_3mf(f"{EXPORTS}/lilygo_a7670_simhat_carrier.stl",
            f"{EXPORTS}/lilygo_a7670_simhat_carrier.3mf")

    print("build complete")


if __name__ == "__main__":
    main()

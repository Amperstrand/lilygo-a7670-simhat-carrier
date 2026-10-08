#!/usr/bin/env python3
"""Render all enclosure variants to PNG contact sheets (three.js + headless
chromium).  Produces per-variant sheets and a combined options overview.

Renders are illustrations, never evidence (AGENTS.md rule 2): the pass gate
is analysis/interference_report.json.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "output", "exports")
OUT = os.path.join(ROOT, "output", "renders")

SCENES = {
    "V0_coupon": [
        ("coupon", "V0_calibration_coupon.stl", 0x7ec8e3),
    ],
    "V1_minimal_closed": [
        ("bottom", "V1_bottom_shell.stl", 0x2f3a45),
        ("board", "reference_main_board.stl", 0x1a6e8a),
        ("battery", None, 0x9b3a3a),
        ("lid", "V1_lid_closed.stl", 0x3c4a57),
    ],
    "V2_screen_popout_closed": [
        ("bottom", "V1_bottom_shell.stl", 0x2f3a45),
        ("board", "reference_main_board.stl", 0x1a6e8a),
        ("battery", None, 0x9b3a3a),
        ("lid", "V2_lid_screen_popout.stl", 0x3c4a57),
    ],
    "V2_screen_popped": [
        ("bottom", "V1_bottom_shell.stl", 0x2f3a45),
        ("board", "reference_main_board.stl", 0x1a6e8a),
        ("battery", None, 0x9b3a3a),
        ("lid_open", "V2_lid_screen_popped.stl", 0x3c4a57),
        ("glass", None, 0x14181c),
    ],
    "V3_full_keyboard": [
        ("bottom", "V3_bottom_shell_full.stl", 0x2f3a45),
        ("board", "reference_full_board.stl", 0x1a6e8a),
        ("battery", None, 0x9b3a3a),
        ("lid", "V3_lid_keyboard_blister.stl", 0x3c4a57),
    ],
}

# extra parametric stand-ins (battery + glass) built by cadquery here
PLACEHOLDERS = {"battery": "battery.stl", "glass": "glass.stl"}


def build_placeholders():
    import cadquery as cq
    from cad import parameters as P
    from cad.parameters import D

    u0, u1 = D["battery_u"]
    v0, v1 = D["battery_v"]
    bat = cq.Workplane(obj=cq.Solid.makeBox(
        u1 - u0, v1 - v0, P.BATTERY_T,
        cq.Vector(u0, v0, D["pocket_z_top"] - P.BATTERY_T)))
    cq.exporters.export(bat, os.path.join(EXP, "battery.stl"), exportType="STL")

    from cad import shell as S
    _, glass = S.screen_window_rect()
    gu0, gv0, gu1, gv1 = glass
    from cad import reference as R
    g = cq.Workplane(obj=cq.Solid.makeBox(
        gu1 - gu0, gv1 - gv0, P.SCREEN_GLASS_T,
        cq.Vector(gu0, gv0, S.LID_Z0)))
    cq.exporters.export(g, os.path.join(EXP, "glass.stl"), exportType="STL")


def build_popped_lid():
    import cadquery as cq
    from cad import shell as S
    lid = S.lid("popout", "main", screen_window=True, led_window=True,
                screen_popped=True)
    cq.exporters.export(cq.Workplane(obj=lid),
                        os.path.join(EXP, "V2_lid_screen_popped.stl"),
                        exportType="STL", tolerance=0.05, angularTolerance=0.2)


PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#101418;color:#cfd8dc;font-family:sans-serif}</style>
</head><body><div id="view"></div>
<script src="file://__ROOT__/reference/three.min.js"></script>
<script src="file://__ROOT__/reference/STLLoader.js"></script>
<script>
const ROOT = "__ROOT__";
const EXP = "__EXP__";
const PARTS = __PARTS__;
const VIEWS = __VIEWS__;
function render() {
  const container = document.getElementById('view');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x101418);
  const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
  renderer.setSize(1600, 1000);
  container.appendChild(renderer.domElement);
  const lights = [
    new THREE.DirectionalLight(0xffffff, 0.9).translateX(80).translateY(120).translateZ(160),
    new THREE.DirectionalLight(0xbfd4dd, 0.45).translateX(-120).translateY(-40).translateZ(60),
    new THREE.AmbientLight(0xffffff, 0.38),
  ];
  lights.forEach(l => scene.add(l));
  let pending = Object.keys(PARTS).length;
  const meshes = {};
  for (const [tag, file, color] of PARTS) {
    const url = file ? EXP + '/' + file : ROOT + '/output/renders/' + tag + '.stl';
    const loader = new THREE.STLLoader();
    loader.load(url, function (geo) {
      geo.computeBoundingBox();
      const mat = new THREE.MeshPhongMaterial({color: color, shininess: 42,
                                               specular: 0x222222});
      const mesh = new THREE.Mesh(geo, mat);
      meshes[tag] = mesh;
      pending--;
      if (pending === 0) shoot();
    }, undefined, function (err) {
      document.title = 'LOAD_ERROR';
      console.error('STL load failed:', url, err);
    });
  }
  function shoot() {
    const box = new THREE.Box3();
    for (const t in meshes) box.expandByObject(meshes[t]);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z);
    for (const t in meshes) scene.add(meshes[t]);
    const cam = new THREE.PerspectiveCamera(32, 1.6, 1, 4000);
    const label = document.createElement('div');
    label.style.cssText = 'position:fixed;left:16px;top:12px;font-size:22px;color:#cfd8dc';
    document.body.appendChild(label);
    let i = 0;
    function shot() {
      if (i >= VIEWS.length) {
        document.title = 'DONE';
        return;
      }
      const v = VIEWS[i];
      const look = v.center ? new THREE.Vector3(v.center[0], v.center[1], v.center[2]) : center;
      const effRadius = v.span ? v.span : radius;
      const az = v.az * Math.PI / 180, el = v.el * Math.PI / 180;
      const d = effRadius * (v.dist || 2.1);
      cam.position.set(look.x + d * Math.cos(el) * Math.sin(az),
                       look.y - d * Math.cos(el) * Math.cos(az),
                       look.z + d * Math.sin(el));
      cam.up.set(0, 0, 1);
      cam.lookAt(look);
      renderer.render(scene, cam);
      label.textContent = v.label;
      const shot_url = v.path;
      window.__shot = shot_url;
      window.__done_marker = 'SHOT_READY_' + i;
      i++;
    }
    window.__next = shot;
    shot();
  }
}
render();
</script></body></html>"""


def parts_json(parts):
    """Parts for the page template: placeholder parts (file=None) resolve to
    the PLACEHOLDERS stl in EXP, where build_placeholders() writes them."""
    return json.dumps(
        [[tag, f if f is not None else PLACEHOLDERS[tag], color]
         for tag, f, color in parts])


def render_scenes():
    os.makedirs(OUT, exist_ok=True)
    build_placeholders()
    build_popped_lid()
    outputs = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1620, "height": 1040})
        for scene_name, parts in SCENES.items():
            views = [
                {"label": "iso", "az": 35, "el": 28, "dist": 2.0,
                 "path": os.path.join(OUT, f"{scene_name}_iso.png")},
                {"label": "USB side", "az": -55, "el": 18, "dist": 2.0,
                 "path": os.path.join(OUT, f"{scene_name}_usb.png")},
                {"label": "top", "az": 0, "el": 88, "dist": 2.0,
                 "path": os.path.join(OUT, f"{scene_name}_top.png")},
            ]
            html = (PAGE.replace("__ROOT__", ROOT)
                        .replace("__EXP__", EXP)
                        .replace("__PARTS__", parts_json(parts))
                        .replace("__VIEWS__", json.dumps(views)))
            tmp = os.path.join(OUT, "_scene.html")
            with open(tmp, "w") as f:
                f.write(html)
            page.goto("file://" + tmp)
            for k, v in enumerate(views):
                if k > 0:
                    page.evaluate("window.__next()")
                page.wait_for_function(
                    f"window.__done_marker === 'SHOT_READY_{k}'", timeout=300000)
                if page.title() == "LOAD_ERROR":
                    raise RuntimeError(
                        f"scene {scene_name}: STL failed to load "
                        f"(browser console has the URL)")
                page.screenshot(path=v["path"])
            outputs[scene_name] = [v["path"] for v in views]
            print("rendered", scene_name)
        browser.close()
    os.unlink(os.path.join(OUT, "_scene.html"))
    with open(os.path.join(OUT, "render_manifest.json"), "w") as f:
        json.dump(outputs, f, indent=1)
    return outputs


def render_closeups():
    """Close-up verification views (AGENTS.md rule 22: features must be
    resolvable; geometry truth still comes from the boolean report)."""
    os.makedirs(OUT, exist_ok=True)
    closeups = {
        "detail_usb_battery_ports": ("V1_bottom_shell.stl", None, 0x2f3a45,
                                     {"label": "USB port + battery service bay",
                                      "center": [-2.0, 57.0, 4.0], "span": 34}),
        "detail_battery_pocket": ("V1_bottom_shell.stl", "battery.stl", None,
                                  {"label": "battery pocket + wire lane (lid removed)",
                                   "center": [28.0, 60.0, -1.0], "span": 52}),
        "detail_popout_window": (None, "V2_lid_screen_popped.stl", 0x3c4a57,
                                 {"label": "screen window popped (glass mounts inside)",
                                  "center": [30.0, 44.0, 10.0], "span": 42}),
        "detail_button_ports": (None, "V1_lid_closed.stl", 0x3c4a57,
                                {"label": "RESET / BOOT plunger ports + charge-LED hole",
                                 "center": [53.0, 34.0, 9.0], "span": 24}),
        "detail_coupon": ("V0_calibration_coupon.stl", None, 0x7ec8e3,
                          {"label": "coupon: pilot ladder / thickness stairs / lip bay / slits / bridges",
                           "center": [45.0, 22.0, 2.0], "span": 85}),
    }
    with sync_playwright() as pw:
        for name, (bottom, second, color, spec) in closeups.items():
            browser = pw.chromium.launch(args=["--allow-file-access-from-files"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            parts = []
            if bottom:
                parts.append(["b", bottom, color])
            if second:
                parts.append(["s", second, 0x8a2f2f if "battery" in name else 0x14181c])
            views = [{"label": spec["label"], "az": -35, "el": 32,
                      "dist": 1.15, "center": spec["center"], "span": spec["span"],
                      "path": os.path.join(OUT, name + ".png")}]
            html = (PAGE.replace("__ROOT__", ROOT).replace("__EXP__", EXP)
                    .replace("__PARTS__", json.dumps(parts))
                    .replace("__VIEWS__", json.dumps(views)))
            tmp = os.path.join(OUT, "_cu.html")
            with open(tmp, "w") as f:
                f.write(html)
            page.goto("file://" + tmp)
            page.wait_for_function("window.__done_marker", timeout=300000)
            if page.title() == "LOAD_ERROR":
                raise RuntimeError(
                    f"closeup {name}: STL failed to load (browser console has the URL)")
            page.screenshot(path=os.path.join(OUT, name + ".png"))
            print("closeup", name)
            browser.close()
    os.unlink(os.path.join(OUT, "_cu.html"))


def contact_sheet():
    """Compose the options overview with PIL."""
    from PIL import Image, ImageDraw, ImageFont
    import glob
    groups = [
        ("V0 - calibration coupon (print FIRST)", "V0_coupon"),
        ("V1 - minimal: no screen, no keyboard, USB + battery access", "V1_minimal_closed"),
        ("V2 - screen-ready: pop-out OLED window (printed closed / popped)", "V2_screen_popout_closed"),
        ("V2b - same print, window popped out", "V2_screen_popped"),
        ("V3 - full length: keyboard breakaway NOT removed", "V3_full_keyboard"),
    ]
    W = 1600
    rows = []
    for title, key in groups:
        imgs = []
        for tag in ("iso", "usb", "top"):
            p = os.path.join(OUT, f"{key}_{tag}.png")
            if os.path.exists(p):
                imgs.append(Image.open(p))
        rows.append((title, imgs))
    TH = 380
    total_h = sum(TH + 46 for _, _ in rows) + 20
    sheet = Image.new("RGB", (W, total_h), (16, 20, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    y = 10
    for title, imgs in rows:
        draw.text((18, y + 4), title, fill=(207, 216, 220), font=font)
        y += 40
        n = len(imgs)
        if n:
            tw = (W - 30) // n
            for k, im in enumerate(imgs):
                im = im.resize((tw - 8, TH))
                sheet.paste(im, (15 + k * tw, y))
        y += TH + 6
    out = os.path.join(OUT, "OPTIONS_overview.png")
    sheet.save(out)
    print("contact sheet:", out)


if __name__ == "__main__":
    render_scenes()
    render_closeups()
    contact_sheet()

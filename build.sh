#!/usr/bin/env bash
# Rebuild everything: analysis (if missing), geometry, exports, renders.
# Validation runs afterwards; a non-zero exit means a check failed.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PY:-.venv/bin/python}"
if [ ! -x "$PY" ]; then
    echo "no venv at .venv — see README for setup" >&2
    exit 1
fi

if [ ! -f analysis/a7670_geometry.json ]; then
    "$PY" scripts/analyze_step.py references/T-A7670X-Board-3D.stp analysis/a7670_geometry.json --components-dir analysis/parts
    "$PY" scripts/analyze_step.py references/t-simhat-pcb.stp analysis/simhat_geometry.json --components-dir analysis/parts
    "$PY" scripts/analyze_dxf.py references/T-A7670X-ESP32.dxf analysis/a7670_dxf.json
fi

"$PY" scripts/build.py
"$PY" scripts/validate.py

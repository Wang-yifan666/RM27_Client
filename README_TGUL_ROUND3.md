# TGUL 2027 Round 3 — 2D battlefield map adapter

## Prerequisites

- WSL2 Ubuntu 24.04; the RM27_Client clone already passed round 2 tests
- Local official 2027 STEP files: 3v3 and/or 1v1, **not included in this archive**
- Map PNG must be prepared from those CAD models, with the actual playfield
  cropped to its inner court rectangle and correctly oriented

## Install

In `/home/wangyifan/RM27_Client`:

    # Save a Git checkpoint first; install from your own working branch.
    git status --short
    python3 -m zipfile -e tgul_round3.zip .
    source sim/.venv/bin/activate
    python apply_tgul_round3.py
    python -m unittest discover -s sim/tests -t sim -p 'test_*.py' -v
    node --test sim/tests/test_tgul_map_geometry.js
    node --test sim/tests/test_map_geometry.js
    git diff --check

The installer checks exact source anchors before writing any modified
source. It assumes round 2's `sim/server/tgul2027_simulation.py` is present.
It is designed to leave original legacy mode untouched.

## Export field PNG from STEP

1. Open the ORIGINAL STEP model in FreeCAD or a CAD tool.
2. Switch to an **orthographic top view**, not a perspective/isometric view.
3. Identify the true court inner boundary (do not include operation tables
   or a surrounding viewport border in the playable rectangle).
4. Export or capture a sharp PNG and crop its image frame to the exact
   rectangular playable field. Keep north/blue/red orientation consistent
   with the simulation's bottom-left origin and x-right, y-up axes.
5. Copy PNG files to the simulator's statically served directory:

    sim/server/static/tgul_maps/tgul_3v3.png
    sim/server/static/tgul_maps/tgul_infantry.png

   The source STEP files are not renamed or modified.

6. Confirm image dimensions match the court width/height aspect ratio.
   For example, use `file sim/server/static/tgul_maps/tgul_3v3.png`.
   If a screenshot contains extra image margins, set normalized
   `[left,top,right,bottom]` in the JSON `crop` property.
   The cropped region's aspect ratio must match the court.
7. Check `sim/server/static/tgul_maps/tgul_3v3.json`.
   Initial width=12, height=8 is a provisional geometry reference, NOT
   proof that the official 2027 inner court/calibration matches it.
   Check physical dimensions and coordinate orientation against STEP,
   official rulebook, and, ultimately, actual field.
8. For 1v1, `tgul_infantry.json` intentionally starts with null width and
   height. MEASURE the true dimensions before entering them. The web map
   remains visibly "unconfigured" until both values are supplied.
9. Set `calibrated` to true only after validating dimensional correspondence
   and image orientation. The application shows "not calibrated" until then.

## Run

3v3:

    bash sim/run_sim.sh --no-video --mqtt-host 127.0.0.1 \
      --mqtt-port 3333 --tgul-mode tgul_3v3 --current-robot-id 1

Infantry duel (after configuring field size):

    bash sim/run_sim.sh --no-video --mqtt-host 127.0.0.1 \
      --mqtt-port 3333 --tgul-mode tgul_infantry --current-robot-id 3

Visit http://localhost:8000 from Windows. Use Ctrl+Shift+R after changing
static PNGs or JS. Restart the server after editing map geometry JSON
so that demonstration robot starting positions are refreshed.

## What changes

- TGUL map dimensions and starting positions supplied by new metadata module
- Source-of-truth 2D conversion functions with letterboxing and inverted Y
- Map images rendered within the exact world canvas viewport (no distortion)
- Web robot dragging and path-planning coordinates use the same transform
- Inactive or reserve robots hidden on TGUL minimap
- Invalid/out-of-field coordinates rejected by TGUL state manager
- TGUL Web dragging does NOT publish legacy RadarInfoToClient
- Original RM26 mode keeps its prior map and behavior

## Out of scope

The STEP itself is not parsed by this patch. CAD-to-PNG calibration is a
manual operation. No official field-zone polygons, collision geometry,
navigation surfaces, or TGUL MQTT/Protobuf message compliance are claimed.
Current Web controls may still show some old-season panels.

For external official or community 2027 assets, check redistribution and
attribution/license terms before adding derived PNGs to a public repository.

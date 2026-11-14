"""TGUL battlefield map metadata for the simulator Web console.

Image calibration and court dimensions are deliberately separate from the
match rules. The STEP assets remain on the user's machine.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MAP_DIR = Path(__file__).resolve().parent / "static" / "tgul_maps"
VALID_MODES = {
    "tgul_3v3": ("tgul_3v3.json", "tgul_3v3.png"),
    "tgul_infantry": ("tgul_infantry.json", "tgul_infantry.png"),
}


def get_tgul_map(mode: str) -> dict:
    """Return JSON-safe map metadata; unconfigured maps remain explicitly blank."""
    key = str(getattr(mode, "value", mode))
    if key not in VALID_MODES:
        raise ValueError(f"Unknown TGUL map mode: {key}")
    config_file, image_file = VALID_MODES[key]
    data = json.loads((MAP_DIR / config_file).read_text(encoding="utf-8"))
    raw_width, raw_height = data.get("width_m"), data.get("height_m")
    configured = raw_width is not None and raw_height is not None
    width = height = None
    if configured:
        width, height = float(raw_width), float(raw_height)
        if not (math.isfinite(width) and math.isfinite(height)) or min(width, height) <= 0:
            raise ValueError(f"Invalid TGUL map dimensions in {config_file}")
    elif raw_width is not None or raw_height is not None:
        raise ValueError(f"Set both width_m and height_m in {config_file}")

    crop = data.get("crop", [0, 0, 1, 1])
    if (
        not isinstance(crop, list) or len(crop) != 4
        or any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in crop)
        or not (0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1)
    ):
        raise ValueError(f"Invalid crop [left,top,right,bottom] in {config_file}")
    image_ready = (MAP_DIR / image_file).is_file()
    return {
        "mode": key,
        "width_m": width,
        "height_m": height,
        "configured": configured,
        "calibrated": bool(data.get("calibrated", False)) and configured and image_ready,
        "image_ready": image_ready,
        "image_url": f"/tgul_maps/{image_file}" if image_ready else None,
        "crop": list(crop),
        "source": str(data.get("source", "")),
    }


def initial_demo_positions(mode: str, robot_ids: list[int]) -> list[dict]:
    """Sample positions inside a CONFIGURED field, not official robot spawn points."""
    config = get_tgul_map(mode)
    # Preserve existing positions in unconfigured 1v1 until dimensions are known.
    if not config["configured"]:
        return []
    w, h = config["width_m"], config["height_m"]
    if config["mode"] == "tgul_3v3":
        coords = {
            1: (.16, .24, 0), 3: (.18, .51, 0),
            4: (.18, .77, 0), 7: (.29, .51, 0),
            101: (.84, .76, 180), 103: (.82, .49, 180),
            104: (.82, .23, 180), 107: (.71, .49, 180),
        }
    else:
        coords = {
            3: (.22, .5, 0),
            103: (.78, .5, 180),
        }
    return [
        {
            "x": round(w * coords.get(rid, (.5, .5, 0))[0], 4),
            "y": round(h * coords.get(rid, (.5, .5, 0))[1], 4),
            "angle": float(coords.get(rid, (.5, .5, 0))[2]),
        }
        for rid in robot_ids
    ]

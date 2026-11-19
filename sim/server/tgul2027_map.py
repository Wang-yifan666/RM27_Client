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


def _resolve_image_styles(data: dict, mode_key: str, image_file: str) -> tuple[list[dict], str]:
    """Return the switchable background styles and the default one.

    A config without an ``image_styles`` table keeps the original single-image
    behaviour, so a not-yet-calibrated map needs no extra fields.
    """
    raw = data.get("image_styles")
    if raw is None:
        return (
            [{"id": "default", "label": "默认底图", "file": image_file, "note": ""}],
            "default",
        )
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"image_styles must be a non-empty list in {mode_key}.json")
    styles: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid image_styles entry in {mode_key}.json")
        style_id = str(item.get("id") or "").strip()
        file_name = str(item.get("file") or "").strip()
        if not style_id or not file_name:
            raise ValueError(f"image_styles entry needs both id and file in {mode_key}.json")
        if "/" in file_name or "\\" in file_name or file_name.startswith("."):
            raise ValueError(
                f"image_styles file must be a bare filename in {mode_key}.json: {file_name}"
            )
        styles.append(
            {
                "id": style_id,
                "label": str(item.get("label") or style_id),
                "file": file_name,
                "note": str(item.get("note") or ""),
            }
        )
    if len({style["id"] for style in styles}) != len(styles):
        raise ValueError(f"Duplicate image_styles id in {mode_key}.json")
    default_style = str(data.get("default_image_style") or styles[0]["id"])
    if default_style not in {style["id"] for style in styles}:
        raise ValueError(
            f"default_image_style {default_style} is not declared in {mode_key}.json"
        )
    return styles, default_style


def _public_style(style: dict) -> dict:
    """Describe one style for the Web console; a missing file stays explicitly unavailable."""
    available = (MAP_DIR / style["file"]).is_file()
    return {
        "id": style["id"],
        "label": style["label"],
        "note": style["note"],
        "available": available,
        "url": f"/tgul_maps/{style['file']}" if available else None,
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

    styles, default_style = _resolve_image_styles(data, key, image_file)
    image_styles = [_public_style(style) for style in styles]
    default_entry = next(s for s in image_styles if s["id"] == default_style)
    image_ready = default_entry["available"]
    return {
        "mode": key,
        "width_m": width,
        "height_m": height,
        "configured": configured,
        "calibrated": bool(data.get("calibrated", False)) and configured and image_ready,
        "image_ready": image_ready,
        "image_url": default_entry["url"],
        "image_style": default_style,
        "image_styles": image_styles,
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

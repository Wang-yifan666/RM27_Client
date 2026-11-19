"""TGUL 2027 zone data: playable frame, obstacles and passable terrain.

Zone shapes come from the official STEP file (planar faces only), never from the
delivered map images. A zone whose outline has not been extracted yet stays
``aabb_only``; such a zone must not be used to forbid a position, because its
bounding box overstates the real footprint.

Task T1 scope: load and validate the data file. Geometry queries
(point-in-polygon, validity, enter/leave events) belong to later tasks.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from server.tgul2027_map import get_tgul_map

MAP_DIR = Path(__file__).resolve().parent / "static" / "tgul_maps"
ZONE_FILES = {"tgul_3v3": "tgul_3v3_zones.json"}
VALID_KINDS = frozenset(
    {
        "playable_frame",
        "obstacle",
        "passable",
        "control_zone",
        "terrain",
        "base_marking",
    }
)
VALID_STATUS = frozenset({"measured", "aabb_only", "pending"})
ZONE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _as_number(value, field: str) -> float:
    _require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value),
        f"{field} 必须是有限数值",
    )
    return float(value)


def _as_rect(value, field: str) -> tuple[float, float, float, float]:
    _require(
        isinstance(value, list) and len(value) == 4,
        f"{field} 必须是 [x0, y0, x1, y1]",
    )
    x0, y0, x1, y1 = (_as_number(item, field) for item in value)
    _require(x0 < x1 and y0 < y1, f"{field} 必须满足 x0 < x1 且 y0 < y1")
    return (x0, y0, x1, y1)


def _as_ring(value, field: str, bounds, *, ccw: bool = True):
    """闭合环：至少 3 点、首尾不重复、落在 validation_bounds 内。"""
    _require(
        isinstance(value, list) and len(value) >= 3,
        f"{field} 至少需要 3 个顶点",
    )
    points = []
    for index, point in enumerate(value):
        _require(
            isinstance(point, list) and len(point) == 2,
            f"{field}[{index}] 必须是 [x, y]",
        )
        x = _as_number(point[0], f"{field}[{index}]")
        y = _as_number(point[1], f"{field}[{index}]")
        _require(
            bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3],
            f"{field}[{index}] 超出 validation_bounds",
        )
        points.append((x, y))

    _require(
        points[0] != points[-1],
        f"{field} 首尾不能重复（环不需要闭合点）",
    )
    if len({point for point in points}) != len(points):
        raise ValueError(f"{field} 存在重复顶点")

    twice_area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        twice_area += x1 * y2 - x2 * y1
    twice_area /= 2.0
    _require(abs(twice_area) > 1e-9, f"{field} 面积不能为 0")
    if ccw:
        _require(twice_area > 0, f"{field} 必须是逆时针（有向面积 > 0）")
    return tuple(points)


def _validate_zone(raw, index: int, bounds) -> dict:
    field = f"zones[{index}]"
    _require(isinstance(raw, dict), f"{field} 必须是对象")

    zone_id = raw.get("id")
    _require(
        isinstance(zone_id, str) and ZONE_ID_PATTERN.match(zone_id) is not None,
        f"{field}.id 必须是「域.名称」形式的小写标识",
    )
    kind = raw.get("kind")
    _require(kind in VALID_KINDS, f"{field}.kind 非法：{kind!r}")
    label = raw.get("label")
    _require(isinstance(label, str) and label.strip(), f"{field}.label 不能为空")
    status = raw.get("status")
    _require(status in VALID_STATUS, f"{field}.status 非法：{status!r}")

    blocks_motion = raw.get("blocks_motion")
    _require(
        blocks_motion is None or isinstance(blocks_motion, bool),
        f"{field}.blocks_motion 必须是 true / false / null",
    )
    # 只有拿到真实轮廓才允许据此禁止位置。
    _require(
        not (blocks_motion is True and status != "measured"),
        f"{field} 的 blocks_motion 为 true 时 status 必须是 measured",
    )

    evidence = raw.get("evidence")
    _require(
        isinstance(evidence, str) and evidence.strip(),
        f"{field}.evidence 不能为空",
    )

    polygon = raw.get("polygon")
    holes = raw.get("holes")
    aabb = raw.get("aabb")

    if status == "measured":
        _require(
            polygon is not None,
            f"{field} 的 status 为 measured 时必须提供 polygon",
        )
    if status == "aabb_only":
        _require(
            aabb is not None,
            f"{field} 的 status 为 aabb_only 时必须提供 aabb",
        )
        _require(
            polygon is None,
            f"{field} 的 aabb_only 不应同时提供 polygon（轮廓未提取）",
        )

    parsed_polygon = None
    if polygon is not None:
        parsed_polygon = _as_ring(polygon, f"{field}.polygon", bounds)
    parsed_holes = ()
    if holes is not None:
        _require(
            isinstance(holes, list) and holes,
            f"{field}.holes 必须是非空数组",
        )
        _require(
            parsed_polygon is not None,
            f"{field}.holes 只能与 polygon 一起出现",
        )
        parsed_holes = tuple(
            _as_ring(hole, f"{field}.holes[{hole_index}]", bounds, ccw=False)
            for hole_index, hole in enumerate(holes)
        )

    parsed_aabb = None
    if aabb is not None:
        parsed_aabb = _as_rect(aabb, f"{field}.aabb")

    z_mm = raw.get("z_mm")
    if z_mm is not None:
        z_mm = _as_number(z_mm, f"{field}.z_mm")
    clearance_mm = raw.get("clearance_mm")
    if clearance_mm is not None:
        clearance_mm = _as_number(clearance_mm, f"{field}.clearance_mm")

    return {
        "id": zone_id,
        "kind": kind,
        "label": label.strip(),
        "status": status,
        "blocks_motion": blocks_motion,
        "z_mm": z_mm,
        "clearance_mm": clearance_mm,
        "polygon": parsed_polygon,
        "holes": parsed_holes,
        "aabb": parsed_aabb,
        "confirmed_by": raw.get("confirmed_by"),
        "evidence": evidence.strip(),
    }


def load_zones(mode: str) -> dict:
    """Load and validate the zone table for ``mode``; unknown modes raise."""
    key = str(getattr(mode, "value", mode))
    if key not in ZONE_FILES:
        raise ValueError(f"Unknown TGUL zone mode: {key}")

    path = MAP_DIR / ZONE_FILES[key]
    data = json.loads(path.read_text(encoding="utf-8"))

    _require(data.get("schema_version") == 1, f"{path.name} 的 schema_version 必须为 1")
    _require(data.get("map") == key, f"{path.name} 的 map 必须是 {key}")

    system = data.get("coordinate_system")
    _require(isinstance(system, dict), f"{path.name} 缺少 coordinate_system")
    _require(system.get("unit") == "m", f"{path.name} 的坐标单位必须是米")
    frame = _as_rect(system.get("frame"), f"{path.name}.coordinate_system.frame")
    bounds = _as_rect(
        system.get("validation_bounds"),
        f"{path.name}.coordinate_system.validation_bounds",
    )
    _require(
        bounds[0] <= frame[0] and bounds[1] <= frame[1]
        and frame[2] <= bounds[2] and frame[3] <= bounds[3],
        f"{path.name} 的 frame 必须落在 validation_bounds 内",
    )

    # 与地图配置的尺寸保持一致，避免两处真值漂移。
    map_info = get_tgul_map(key)
    _require(
        map_info["configured"],
        f"{key} 的地图尺寸未配置，区域数据无法校验",
    )
    _require(
        abs(frame[0]) < 1e-9 and abs(frame[1]) < 1e-9
        and abs(frame[2] - float(map_info["width_m"])) < 1e-9
        and abs(frame[3] - float(map_info["height_m"])) < 1e-9,
        f"{path.name} 的 frame 与 {key} 地图尺寸不一致",
    )

    source = data.get("source")
    _require(isinstance(source, dict), f"{path.name} 缺少 source")
    _require(
        isinstance(source.get("file"), str) and source["file"].strip(),
        f"{path.name}.source.file 不能为空",
    )
    _require(
        isinstance(source.get("sha256"), str)
        and SHA256_PATTERN.match(source["sha256"]) is not None,
        f"{path.name}.source.sha256 必须是 64 位小写十六进制",
    )

    raw_zones = data.get("zones")
    _require(
        isinstance(raw_zones, list) and raw_zones,
        f"{path.name} 的 zones 必须是非空数组",
    )
    zones = [
        _validate_zone(raw_zone, index, bounds)
        for index, raw_zone in enumerate(raw_zones)
    ]
    ids = [zone["id"] for zone in zones]
    duplicates = sorted({zone_id for zone_id in ids if ids.count(zone_id) > 1})
    _require(not duplicates, f"{path.name} 存在重复 id：{duplicates}")

    return {
        "mode": key,
        "frame": frame,
        "validation_bounds": bounds,
        "source": source,
        "zones": zones,
    }


_EDGE_EPSILON = 1e-9


def _on_segment(x: float, y: float, start, end) -> bool:
    ax, ay = start
    bx, by = end
    length = math.hypot(bx - ax, by - ay)
    if length <= _EDGE_EPSILON:
        return abs(x - ax) <= _EDGE_EPSILON and abs(y - ay) <= _EDGE_EPSILON
    cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    if abs(cross) > _EDGE_EPSILON * length:
        return False
    return (
        min(ax, bx) - _EDGE_EPSILON <= x <= max(ax, bx) + _EDGE_EPSILON
        and min(ay, by) - _EDGE_EPSILON <= y <= max(ay, by) + _EDGE_EPSILON
    )


def point_in_ring(x: float, y: float, ring) -> bool:
    """射线法判定点是否在单个环内；**落在环上的点算命中**。

    边界算内是刻意选择：位置校验时「正好压在区域边上」比「漏判」更安全，
    洞的边界同理算作洞内，于是紧贴内场边缘的点不会被判成在围墙里。
    """
    _require(
        isinstance(ring, (list, tuple)) and len(ring) >= 3,
        "ring 至少需要 3 个顶点",
    )
    px = _as_number(x, "point.x")
    py = _as_number(y, "point.y")

    count = len(ring)
    for index in range(count):
        if _on_segment(px, py, ring[index], ring[(index + 1) % count]):
            return True

    inside = False
    for index in range(count):
        ax, ay = ring[index]
        bx, by = ring[(index + 1) % count]
        if (ay > py) != (by > py):
            crossing = ax + (py - ay) * (bx - ax) / (by - ay)
            if px < crossing:
                inside = not inside
    return inside


def point_in_polygon(x: float, y: float, polygon, holes=()) -> bool:
    """实心区域判定：在外环内，且不在任何一个洞里。"""
    if not point_in_ring(x, y, polygon):
        return False
    return not any(point_in_ring(x, y, hole) for hole in holes)


def zones_at(x: float, y: float, table: dict) -> list[str]:
    """返回包含该点的 measured 区域 id。

    只查有真实轮廓（polygon）的区域；``aabb_only`` 的包围盒高估了实际占地，
    不能用来回答「这个点属于哪个区域」。
    """
    hits: list[str] = []
    for zone in table["zones"]:
        ring = zone["polygon"]
        if ring is None:
            continue
        if point_in_polygon(x, y, ring, zone["holes"]):
            hits.append(zone["id"])
    return hits


_ZONE_CACHE: dict[str, dict] = {}


def load_zones_cached(mode: str) -> dict:
    """进程内只读一次。

    区域表是随源码发布的静态数据，运行期不会变；缓存避免每次拖拽都读盘。
    需要按环境重新读取时调用 ``load_zones()``。
    """
    key = str(getattr(mode, "value", mode))
    if key not in _ZONE_CACHE:
        _ZONE_CACHE[key] = load_zones(key)
    return _ZONE_CACHE[key]


def classify_position(x: float, y: float, table: dict) -> dict:
    """判定一个坐标是否可用。

    规则（与 docs/architecture/tgul-3v3-zones.md 第 4 节一致）：
    - 只有 ``blocks_motion is True`` 的区域才会拒绝位置；
    - ``aabb_only`` / ``pending`` 区域一律不拒绝，只进 ``unverified_zones`` 供上层提示；
    - 场地矩形的边界算作场内。
    """
    result = {
        "valid": True,
        "reasons": [],
        "blocking_zones": [],
        "zones": [],
        "unverified_zones": [],
    }
    try:
        px = _as_number(x, "x")
        py = _as_number(y, "y")
    except ValueError:
        result["valid"] = False
        result["reasons"].append(
            {"code": "not_finite", "detail": "坐标不是有限数值"}
        )
        return result

    frame = table["frame"]
    if not (
        frame[0] - _EDGE_EPSILON <= px <= frame[2] + _EDGE_EPSILON
        and frame[1] - _EDGE_EPSILON <= py <= frame[3] + _EDGE_EPSILON
    ):
        result["valid"] = False
        result["reasons"].append(
            {
                "code": "out_of_frame",
                "detail": f"({px}, {py}) 超出场地 {frame}",
            }
        )

    for zone in table["zones"]:
        ring = zone["polygon"]
        if ring is not None:
            if point_in_polygon(px, py, ring, zone["holes"]):
                result["zones"].append(zone["id"])
                if zone["blocks_motion"] is True:
                    result["blocking_zones"].append(zone["id"])
            continue
        box = zone["aabb"]
        if box is not None:
            # 仅用于提示：包围盒高估实际占地，不参与有效/无效判定。
            if box[0] <= px <= box[2] and box[1] <= py <= box[3]:
                result["unverified_zones"].append(zone["id"])

    if result["blocking_zones"]:
        result["valid"] = False
        result["reasons"].append(
            {
                "code": "blocked",
                "detail": "落在障碍物 " + "、".join(result["blocking_zones"]),
            }
        )
    return result


def zone_by_id(table: dict, zone_id: str) -> dict | None:
    for zone in table["zones"]:
        if zone["id"] == zone_id:
            return zone
    return None

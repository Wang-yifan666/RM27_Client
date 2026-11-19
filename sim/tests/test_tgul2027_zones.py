import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import tgul2027_zones as zones

FIXED_MAP = {"configured": True, "width_m": 12.0, "height_m": 8.0}

BASE = {
    "schema_version": 1,
    "map": "tgul_3v3",
    "coordinate_system": {
        "unit": "m",
        "frame": [0.0, 0.0, 12.0, 8.0],
        "validation_bounds": [-0.5, -0.5, 12.5, 8.5],
    },
    "source": {
        "file": "RMUL2027_3V3_V1.0.0.stp",
        "sha256": "7d47c1b6a6a0253a732e46cb122bb84410b11d5134bcb5658104299db4a48ca4",
    },
    "zones": [
        {
            "id": "field.inner",
            "kind": "playable_frame",
            "label": "内场可行驶区",
            "status": "measured",
            "blocks_motion": False,
            "polygon": [[0.0, 0.0], [12.0, 0.0], [12.0, 8.0], [0.0, 8.0]],
            "evidence": "unit-test fixture",
        }
    ],
}


class RealZoneTableTest(unittest.TestCase):
    """真实数据文件的契约。"""

    def test_3v3_zone_table_loads_and_is_consistent(self):
        table = zones.load_zones("tgul_3v3")
        self.assertEqual(table["frame"], (0.0, 0.0, 12.0, 8.0))
        self.assertEqual(len(table["zones"]), 12)

        by_status = {}
        for zone in table["zones"]:
            by_status[zone["status"]] = by_status.get(zone["status"], 0) + 1
        self.assertEqual(
            by_status, {"measured": 5, "aabb_only": 6, "pending": 1}
        )

        ids = [zone["id"] for zone in table["zones"]]
        self.assertEqual(len(ids), len(set(ids)))

        for zone in table["zones"]:
            # 只有 measured 区域才允许声明阻挡
            if zone["blocks_motion"] is True:
                self.assertEqual(zone["status"], "measured", zone["id"])
            if zone["status"] == "measured":
                self.assertIsNotNone(zone["polygon"], zone["id"])
                self.assertIsNone(zone["aabb"], zone["id"])
            if zone["status"] == "aabb_only":
                self.assertIsNotNone(zone["aabb"], zone["id"])
                self.assertIsNone(zone["polygon"], zone["id"])
                self.assertIs(zone["blocks_motion"], False, zone["id"])
            self.assertTrue(zone["evidence"], zone["id"])

    def test_wall_ring_carries_the_inner_field_as_hole(self):
        table = zones.load_zones("tgul_3v3")
        wall = zones.zone_by_id(table, "obstacle.perimeter_wall")
        self.assertIsNotNone(wall)
        self.assertTrue(wall["blocks_motion"])
        self.assertEqual(wall["z_mm"], 420.0)
        self.assertEqual(len(wall["holes"]), 1)
        hole = wall["holes"][0]
        self.assertEqual(
            set(hole),
            {(0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)},
        )

    def test_highlands_are_passable_but_not_yet_outlined(self):
        table = zones.load_zones("tgul_3v3")
        for zone_id in ("terrain.highland_se", "terrain.highland_nw"):
            zone = zones.zone_by_id(table, zone_id)
            self.assertIsNotNone(zone, zone_id)
            self.assertEqual(zone["status"], "aabb_only", zone_id)
            self.assertIs(zone["blocks_motion"], False, zone_id)
            self.assertEqual(zone["z_mm"], 200.0, zone_id)
            self.assertEqual(zone["confirmed_by"], "维护者确认允许上高地")

    def test_spawn_formations_stays_pending(self):
        table = zones.load_zones("tgul_3v3")
        zone = zones.zone_by_id(table, "spawn.formations")
        self.assertIsNotNone(zone)
        self.assertEqual(zone["status"], "pending")
        self.assertIsNone(zone["blocks_motion"])
        self.assertIsNone(zone["polygon"])
        self.assertIsNone(zone["aabb"])

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            zones.load_zones("tgul_infantry")


class ZoneValidationTest(unittest.TestCase):
    """schema 校验必须能挡住脏数据。"""

    def _load(self, folder, document, *, map_info=None):
        (folder / "tgul_3v3_zones.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
        with patch.object(zones, "MAP_DIR", folder), patch.object(
            zones, "get_tgul_map", return_value=map_info or FIXED_MAP
        ):
            return zones.load_zones("tgul_3v3")

    def _assert_rejected(self, mutate, *, message="", map_info=None):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            document = copy.deepcopy(BASE)
            mutate(document)
            with self.assertRaises(ValueError, msg=message):
                self._load(folder, document, map_info=map_info)

    def test_base_document_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            table = self._load(Path(directory), copy.deepcopy(BASE))
            self.assertEqual(len(table["zones"]), 1)
            self.assertEqual(table["zones"][0]["polygon"][0], (0.0, 0.0))

    def test_document_level_rejections(self):
        cases = {
            "schema_version": lambda d: d.update(schema_version=2),
            "map": lambda d: d.update(map="tgul_infantry"),
            "unit": lambda d: d["coordinate_system"].update(unit="mm"),
            "frame_order": lambda d: d["coordinate_system"].update(
                frame=[12.0, 8.0, 0.0, 0.0]
            ),
            "frame_outside_bounds": lambda d: d["coordinate_system"].update(
                frame=[0.0, 0.0, 20.0, 8.0]
            ),
            "source_sha": lambda d: d["source"].update(sha256="XYZ"),
            "empty_zones": lambda d: d.update(zones=[]),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self._assert_rejected(mutate, message=name)

    def test_frame_must_match_map_dimensions(self):
        self._assert_rejected(
            lambda d: None,
            message="frame 与地图尺寸不一致",
            map_info={"configured": True, "width_m": 10.0, "height_m": 8.0},
        )
        self._assert_rejected(
            lambda d: None,
            message="地图未配置",
            map_info={"configured": False, "width_m": None, "height_m": None},
        )

    def test_zone_level_rejections(self):
        def zone(document):
            return document["zones"][0]

        cases = {
            "id_format": lambda d: zone(d).update(id="FieldInner"),
            "id_no_domain": lambda d: zone(d).update(id="fieldinner"),
            "kind": lambda d: zone(d).update(kind="nonsense"),
            "status": lambda d: zone(d).update(status="guessed"),
            "label_empty": lambda d: zone(d).update(label="  "),
            "evidence_empty": lambda d: zone(d).update(evidence=""),
            "blocks_motion_type": lambda d: zone(d).update(blocks_motion="yes"),
            "blocks_on_unmeasured": lambda d: (
                zone(d).update(status="aabb_only", aabb=[0, 0, 1, 1],
                               blocks_motion=True)
            ),
            "measured_without_polygon": lambda d: zone(d).pop("polygon"),
            "aabb_only_without_aabb": lambda d: zone(d).update(status="aabb_only"),
            "aabb_only_with_polygon": lambda d: zone(d).update(
                status="aabb_only", aabb=[0, 0, 1, 1]
            ),
            "polygon_clockwise": lambda d: zone(d).update(
                polygon=[[0.0, 8.0], [12.0, 8.0], [12.0, 0.0], [0.0, 0.0]]
            ),
            "polygon_too_few": lambda d: zone(d).update(
                polygon=[[0.0, 0.0], [1.0, 1.0]]
            ),
            "polygon_closed": lambda d: zone(d).update(
                polygon=[[0.0, 0.0], [12.0, 0.0], [12.0, 8.0], [0.0, 0.0]]
            ),
            "polygon_duplicate_vertex": lambda d: zone(d).update(
                polygon=[[0.0, 0.0], [12.0, 0.0], [12.0, 0.0], [0.0, 8.0]]
            ),
            "polygon_zero_area": lambda d: zone(d).update(
                polygon=[[0.0, 0.0], [6.0, 4.0], [12.0, 8.0]]
            ),
            "polygon_out_of_bounds": lambda d: zone(d).update(
                polygon=[[0.0, 0.0], [12.0, 0.0], [12.0, 9.0], [0.0, 9.0]]
            ),
            "polygon_nan": lambda d: zone(d).update(
                polygon=[[float("nan"), 0.0], [12.0, 0.0], [12.0, 8.0]]
            ),
            "holes_without_polygon": lambda d: zone(d).update(
                polygon=None, holes=[[[0, 0], [1, 0], [1, 1]]]
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self._assert_rejected(mutate, message=name)

    def test_duplicate_zone_ids_are_rejected(self):
        def mutate(document):
            document["zones"].append(copy.deepcopy(document["zones"][0]))

        self._assert_rejected(mutate, message="重复 id")


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "tgul_zone_point_cases.json"


class PointInPolygonTest(unittest.TestCase):
    """与 JS 端共用同一份用例，保证两处语义一致。"""

    def setUp(self):
        self.data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.shapes = {
            key: value for key, value in self.data.items()
            if isinstance(value, list)
        }

    def test_shared_cases_match_expected(self):
        cases = self.data["cases"]
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            with self.subTest(case=case["name"]):
                x, y = case["point"]
                if case["shape"] == "wall":
                    inside = zones.point_in_polygon(
                        x, y,
                        self.shapes["wall_outer"],
                        [self.shapes["wall_hole"]],
                    )
                else:
                    inside = zones.point_in_polygon(
                        x, y, self.shapes[case["shape"]]
                    )
                self.assertEqual(inside, case["inside"])

    def test_degenerate_inputs_raise(self):
        with self.assertRaises(ValueError):
            zones.point_in_polygon(1.0, 1.0, [[0.0, 0.0], [1.0, 1.0]])
        with self.assertRaises(ValueError):
            zones.point_in_polygon(
                float("nan"), 1.0, self.shapes["square"]
            )
        with self.assertRaises(ValueError):
            zones.point_in_polygon(
                1.0, float("inf"), self.shapes["square"]
            )

    def test_zones_at_only_uses_outlined_zones(self):
        table = zones.load_zones("tgul_3v3")
        self.assertEqual(
            zones.zones_at(6.0, 4.0, table),
            ["field.inner", "control.central"],
        )
        # 高地在 (8.5, 3.0) 的包围盒内，但只有 aabb 没有轮廓，不得命中
        self.assertEqual(zones.zones_at(8.5, 3.0, table), ["field.inner"])
        # 隧道薄面有真实轮廓，应该命中
        self.assertEqual(
            zones.zones_at(8.5, 0.5, table),
            ["field.inner", "terrain.tunnel_se"],
        )
        # 围墙上：在内场之外，只命中围墙
        self.assertEqual(
            zones.zones_at(-0.15, 4.0, table),
            ["obstacle.perimeter_wall"],
        )
        self.assertEqual(zones.zones_at(-1.0, 4.0, table), [])


if __name__ == "__main__":
    unittest.main()

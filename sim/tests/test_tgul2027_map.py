import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import tgul2027_map as maps


class TGULMapTests(unittest.TestCase):
    def test_3v3_configured_with_step_measured_field(self):
        m = maps.get_tgul_map("tgul_3v3")
        self.assertEqual((m["width_m"], m["height_m"]), (12, 8))
        self.assertTrue(m["configured"])
        # calibrated 表示"人眼在浏览器确认过"，CAD 实测通过不等于人眼确认。
        self.assertFalse(m["calibrated"])
        self.assertTrue(m["image_ready"])
        self.assertEqual(m["image_url"], "/tgul_maps/tgul_3v3.png")
        self.assertEqual(m["image_style"], "official")
        self.assertEqual(m["crop"], [0, 0, 1, 1])
        ids = [1, 3, 4, 7, 101, 103, 104, 107]
        poses = maps.initial_demo_positions("tgul_3v3", ids)
        self.assertEqual(len(poses), len(ids))
        for pose in poses:
            self.assertGreaterEqual(pose["x"], 0)
            self.assertGreaterEqual(pose["y"], 0)
            self.assertLessEqual(pose["x"], 12)
            self.assertLessEqual(pose["y"], 8)

    def test_3v3_exposes_two_image_styles(self):
        m = maps.get_tgul_map("tgul_3v3")
        styles = {style["id"]: style for style in m["image_styles"]}
        self.assertEqual(set(styles), {"official", "cad"})
        self.assertEqual(styles["official"]["label"], "官方纹理")
        self.assertEqual(styles["cad"]["label"], "CAD 配色")
        for style in styles.values():
            self.assertTrue(style["available"])
            self.assertTrue(style["url"].startswith("/tgul_maps/"))
        self.assertEqual(styles["official"]["url"], "/tgul_maps/tgul_3v3.png")
        self.assertEqual(styles["cad"]["url"], "/tgul_maps/tgul_3v3_cad.png")

    def test_infantry_not_falsely_calibrated(self):
        m = maps.get_tgul_map("tgul_infantry")
        self.assertFalse(m["configured"])
        self.assertIsNone(m["width_m"])
        # 没有 image_styles 表的旧配置回退成单一默认底图，行为不变。
        self.assertEqual([style["id"] for style in m["image_styles"]], ["default"])
        self.assertFalse(m["image_ready"])
        self.assertEqual(maps.initial_demo_positions("tgul_infantry", [3, 103]), [])

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            maps.get_tgul_map("rmul_3v3")

    def test_config_validation_and_image_readiness(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            config = folder / "tgul_infantry.json"
            def write(obj):
                config.write_text(json.dumps(obj), encoding="utf-8")
            with patch.object(maps, "MAP_DIR", folder):
                write({"width_m": 6, "height_m": 4, "calibrated": True})
                m = maps.get_tgul_map("tgul_infantry")
                self.assertTrue(m["configured"])
                self.assertFalse(m["image_ready"])
                self.assertFalse(m["calibrated"])
                self.assertEqual(m["image_url"], None)
                (folder / "tgul_infantry.png").write_bytes(b"fake-image")
                m = maps.get_tgul_map("tgul_infantry")
                self.assertTrue(m["image_ready"])
                self.assertTrue(m["calibrated"])
                self.assertEqual(len(maps.initial_demo_positions("tgul_infantry", [3,103])), 2)

                for bad in [
                    {"width_m": 12, "height_m": -3},
                    {"width_m": 0, "height_m": 8},
                    {"width_m": 12, "height_m": None},
                    {"width_m": "NaN", "height_m": 8},
                    {"width_m": 12, "height_m": 8, "crop": [0,0,0,1]},
                    {"width_m": 12, "height_m": 8, "crop": [0,0,2,1]},
                    {"width_m": 12, "height_m": 8, "crop": [True,0,1,1]},
                ]:
                    with self.subTest(bad=bad):
                        write(bad)
                        with self.assertRaises(ValueError):
                            maps.get_tgul_map("tgul_infantry")

    def test_image_style_validation_and_missing_files(self):
        base = {"width_m": 12, "height_m": 8}
        two_styles = {
            "default_image_style": "official",
            "image_styles": [
                {"id": "official", "label": "官方纹理", "file": "tgul_3v3.png"},
                {"id": "cad", "label": "CAD 配色", "file": "tgul_3v3_cad.png"},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            config = folder / "tgul_3v3.json"
            def write(obj):
                config.write_text(json.dumps(obj), encoding="utf-8")
            with patch.object(maps, "MAP_DIR", folder):
                write({**base, **two_styles, "crop": [0, 0, 1, 1]})
                m = maps.get_tgul_map("tgul_3v3")
                styles = {style["id"]: style for style in m["image_styles"]}
                # 两张图都不存在时，风格仍要列出来，但明确标为不可用。
                self.assertFalse(styles["official"]["available"])
                self.assertIsNone(styles["official"]["url"])
                self.assertFalse(m["image_ready"])
                self.assertIsNone(m["image_url"])

                # 只补齐备选图，默认项依旧缺失 -> 默认图仍未就绪。
                (folder / "tgul_3v3_cad.png").write_bytes(b"x")
                m = maps.get_tgul_map("tgul_3v3")
                styles = {style["id"]: style for style in m["image_styles"]}
                self.assertFalse(styles["official"]["available"])
                self.assertTrue(styles["cad"]["available"])
                self.assertFalse(m["image_ready"])
                self.assertIsNone(m["image_url"])
                self.assertFalse(m["calibrated"])

                for bad in [
                    {"image_styles": "tgul_3v3.png"},
                    {"image_styles": []},
                    {"image_styles": [{"id": "a"}]},
                    {"image_styles": [{"id": "a", "file": "../escape.png"}]},
                    {"image_styles": [{"id": "a", "file": ".hidden.png"}]},
                    {"image_styles": [{"id": "a", "file": "a.png"},
                                      {"id": "a", "file": "b.png"}]},
                    {"image_styles": [{"id": "a", "file": "a.png"}],
                     "default_image_style": "zzz"},
                ]:
                    with self.subTest(bad=bad):
                        write({**base, **bad})
                        with self.assertRaises(ValueError):
                            maps.get_tgul_map("tgul_3v3")


if __name__ == "__main__":
    unittest.main()

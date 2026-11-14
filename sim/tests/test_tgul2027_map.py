import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import tgul2027_map as maps


class TGULMapTests(unittest.TestCase):
    def test_3v3_provisional_and_positions(self):
        m = maps.get_tgul_map("tgul_3v3")
        self.assertEqual((m["width_m"], m["height_m"]), (12, 8))
        self.assertTrue(m["configured"])
        self.assertFalse(m["calibrated"])
        ids = [1, 3, 4, 7, 101, 103, 104, 107]
        poses = maps.initial_demo_positions("tgul_3v3", ids)
        self.assertEqual(len(poses), len(ids))
        for pose in poses:
            self.assertGreaterEqual(pose["x"], 0)
            self.assertGreaterEqual(pose["y"], 0)
            self.assertLessEqual(pose["x"], 12)
            self.assertLessEqual(pose["y"], 8)

    def test_infantry_not_falsely_calibrated(self):
        m = maps.get_tgul_map("tgul_infantry")
        self.assertFalse(m["configured"])
        self.assertIsNone(m["width_m"])
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


if __name__ == "__main__":
    unittest.main()

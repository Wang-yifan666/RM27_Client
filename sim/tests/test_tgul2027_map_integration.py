import math
import unittest

from server.tgul2027_simulation import TGULStateManager


class TGULMapIntegrationTest(unittest.TestCase):
    def test_map_metadata_initial_points_and_drag_validation(self):
        manager = TGULStateManager("tgul_3v3")
        state = manager.get_state()
        spec = state["tgulMap"]
        self.assertTrue(spec["configured"])
        self.assertEqual((spec["width_m"], spec["height_m"]), (12, 8))
        for index, rid in enumerate(state["robotIds"]):
            if rid not in state["tgulActiveRobotIds"]:
                continue
            pose = state["positions"][index]
            self.assertTrue(0 <= pose["x"] <= 12)
            self.assertTrue(0 <= pose["y"] <= 8)

        index = manager.robot_ids.index(3)
        self.assertTrue(manager.set_robot_position(index, 12, 8, 90))
        self.assertEqual(manager.positions[index]["x"], 12)
        self.assertEqual(manager.positions[index]["y"], 8)
        for invalid in ((12.01, 5), (-0.01, 1), (math.nan, 5), (1, math.inf)):
            with self.subTest(invalid=invalid):
                self.assertFalse(manager.set_robot_position(index, *invalid))
                self.assertEqual(manager.positions[index]["x"], 12)
        reserve = manager.robot_ids.index(4)
        self.assertFalse(manager.set_robot_position(reserve, 1, 1))

        duel = TGULStateManager("tgul_infantry")
        self.assertFalse(duel.get_state()["tgulMap"]["configured"])
        self.assertFalse(duel.set_robot_position(duel.robot_ids.index(3), 0.5, 0.5))

    def test_reset_keeps_every_active_robot_inside_the_map(self):
        """重置比赛后位置必须仍是 12x8 m 米制坐标，否则蓝方会被前端丢弃。"""
        manager = TGULStateManager("tgul_3v3")
        manager.reset_match_simulation()
        state = manager.get_state()
        active = set(state["tgulActiveRobotIds"])
        self.assertEqual(sorted(active), [1, 3, 7, 101, 103, 107])
        for index, rid in enumerate(state["robotIds"]):
            if rid not in active:
                continue
            pose = state["positions"][index]
            with self.subTest(robot=rid):
                self.assertGreaterEqual(pose["x"], 0)
                self.assertLessEqual(pose["x"], 12)
                self.assertGreaterEqual(pose["y"], 0)
                self.assertLessEqual(pose["y"], 8)


if __name__ == "__main__":
    unittest.main()

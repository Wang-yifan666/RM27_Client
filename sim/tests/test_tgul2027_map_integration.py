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


if __name__ == "__main__":
    unittest.main()

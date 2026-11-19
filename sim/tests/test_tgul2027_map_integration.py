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

    def test_simulation_frame_clamps_to_real_field_size(self):
        """演示帧位置按 12x8 钳制；父类仍保持 28x15 旧行为。"""
        from server.state_manager import StateManager

        manager = TGULStateManager("tgul_3v3")
        positions = [dict(pose) for pose in manager.positions]
        positions[0] = {"x": 20.0, "y": 30.0, "angle": 0.0}
        manager.apply_match_simulation_frame(
            positions=positions,
            robot_health=None,
            current_stage=0,
            stage_countdown_sec=0,
            stage_elapsed_sec=0,
            simulation_status=None,
        )
        self.assertEqual(manager.positions[0]["x"], 12.0)
        self.assertEqual(manager.positions[0]["y"], 8.0)

        legacy = StateManager()
        legacy_positions = [dict(pose) for pose in legacy.positions]
        legacy_positions[0] = {"x": 20.0, "y": 30.0, "angle": 0.0}
        legacy.apply_match_simulation_frame(
            positions=legacy_positions,
            robot_health=None,
            current_stage=0,
            stage_countdown_sec=0,
            stage_elapsed_sec=0,
            simulation_status=None,
        )
        self.assertEqual(legacy.positions[0]["x"], 20.0)
        self.assertEqual(legacy.positions[0]["y"], 15.0)


if __name__ == "__main__":
    unittest.main()

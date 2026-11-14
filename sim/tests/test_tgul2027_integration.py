import unittest

from server.tgul2027_rules import MatchMode, MatchStage
from server.tgul2027_simulation import (
    TGULMatchSimulationEngine, TGULStateManager
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def set(self, seconds):
        self.value = float(seconds)


class NoRadarPublisher:
    def __init__(self):
        self.calls = 0

    def publish_radar_info_to_client(self, **kwargs):
        self.calls += 1
        raise AssertionError("TGUL mode must not fabricate radar data")


class TGUL2027IntegrationTest(unittest.TestCase):
    def test_3v3_initialization_and_current_robot(self):
        manager = TGULStateManager("tgul_3v3")
        state = manager.get_state()
        self.assertEqual(state["tgulMode"], "tgul_3v3")
        self.assertEqual(
            state["robotIds"], [1, 3, 4, 7, 101, 103, 104, 107]
        )
        unit = state["globalUnitStatus"]
        self.assertEqual(
            unit["robot_max_hp"],
            [100, 350, 0, 400, 100, 350, 0, 400]
        )
        self.assertEqual(unit["robot_health"], unit["robot_max_hp"])
        self.assertEqual(
            unit["robot_bullets"], [0, 0, 0, 750, 0, 0, 0, 750]
        )
        self.assertEqual(state["tgulControlPoints"], {"red": 600, "blue": 600})
        self.assertEqual(state["globalLogisticsStatus"]["red_economy"], 200)

        self.assertEqual(
            state["tgulActiveRobotIds"], [1, 3, 7, 101, 103, 107]
        )
        manager.current_robot_id = 104
        with self.assertRaises(ValueError):
            manager.sync_current_robot_view()
        manager.current_robot_id = 103
        manager.sync_current_robot_view()
        state = manager.get_state()
        self.assertEqual(state["robotStaticStatus"]["robot_id"], 103)
        self.assertEqual(state["robotStaticStatus"]["max_health"], 350)
        self.assertEqual(state["robotStaticStatus"]["max_heat"], 88)

    def test_infantry_has_only_two_active_slots(self):
        manager = TGULStateManager(MatchMode.INFANTRY_DUEL)
        state = manager.get_state()
        self.assertEqual(state["tgulActiveRobotIds"], [3, 103])
        self.assertEqual(
            state["globalUnitStatus"]["robot_max_hp"],
            [0, 200, 0, 0, 0, 200, 0, 0]
        )
        self.assertEqual(
            state["globalUnitStatus"]["robot_bullets"],
            [0, 200, 0, 0, 0, 200, 0, 0]
        )
        self.assertEqual(state["tgulControlPoints"], {"red": 0, "blue": 0})
        self.assertEqual(state["globalLogisticsStatus"]["blue_economy"], 0)
        manager.current_robot_id = 1
        with self.assertRaises(ValueError):
            manager.sync_current_robot_view()
        manager.current_robot_id = 103
        manager.sync_current_robot_view()
        self.assertEqual(manager.get_state()["robotStaticStatus"]["max_health"], 200)

    def test_full_timeline_every_boundary_and_selfcheck(self):
        for mode, boundaries in (
            ("tgul_3v3", (180, 195, 200, 500)),
            ("tgul_infantry", (120, 135, 140, 260)),
        ):
            with self.subTest(mode=mode):
                clock = FakeClock()
                manager = TGULStateManager(mode)
                engine = TGULMatchSimulationEngine(manager, clock=clock)
                status = engine.control("start", mode="full")
                self.assertEqual(status["current_stage"], MatchStage.PREPARATION)
                self.assertEqual(status["duration_sec"], boundaries[-1])

                active_index = 1
                manager.global_unit_status["robot_health"][active_index] = 5
                for timestamp, expected_stage in (
                    (boundaries[0] - 0.001, MatchStage.PREPARATION),
                    (boundaries[0], MatchStage.SELF_CHECK),
                    (boundaries[1], MatchStage.COUNTDOWN),
                    (boundaries[2], MatchStage.BATTLE),
                    (boundaries[3], MatchStage.SETTLEMENT),
                ):
                    clock.set(timestamp)
                    frame = engine.tick()
                    self.assertEqual(frame["current_stage"], expected_stage)
                    self.assertEqual(
                        manager.get_state()["gameStatus"]["current_stage"],
                        expected_stage
                    )
                self.assertEqual(
                    manager.global_unit_status["robot_health"][active_index],
                    350 if mode == "tgul_3v3" else 200
                )
                self.assertEqual(engine.get_status()["status"], "completed")
                self.assertEqual(manager.get_events(), [])

    def test_quick_is_compressed_timeline_and_no_radar(self):
        manager = TGULStateManager()
        clock = FakeClock()
        radar = NoRadarPublisher()
        engine = TGULMatchSimulationEngine(
            manager, mqtt_publisher=radar, clock=clock
        )
        self.assertEqual(engine.control("start")["duration_sec"], 90)
        clock.set(36)  # 36/90 of 500 = 200, battle begins
        frame = engine.tick()
        self.assertEqual(frame["current_stage"], MatchStage.BATTLE)
        self.assertEqual(radar.calls, 0)
        self.assertEqual(manager.get_events(), [])
        self.assertEqual(frame["robots"][0]["robot_id"], 1)
        clock.set(90)
        self.assertEqual(engine.tick()["current_stage"], MatchStage.SETTLEMENT)

    def test_pause_resume_reset_and_manual_hp(self):
        manager = TGULStateManager()
        clock = FakeClock()
        engine = TGULMatchSimulationEngine(manager, clock=clock)
        engine.control("start", mode="full")
        clock.set(40)
        engine.tick()
        engine.control("pause")
        clock.set(300)
        self.assertIsNone(engine.tick())
        self.assertEqual(engine.get_status()["elapsed_sec"], 40)
        engine.control("resume")
        clock.set(310)
        engine.tick()
        self.assertEqual(engine.get_status()["elapsed_sec"], 50)
        manager.global_unit_status["robot_health"][1] = 123
        engine.control("reset")
        self.assertEqual(manager.get_state()["globalUnitStatus"]["robot_health"][1], 350)
        self.assertEqual(manager.get_state()["gameStatus"]["current_stage"], 0)


if __name__ == "__main__":
    unittest.main()

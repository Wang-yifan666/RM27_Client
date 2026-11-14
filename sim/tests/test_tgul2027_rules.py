import math
import unittest
from dataclasses import FrozenInstanceError

from server.tgul2027_rules import (
    ChassisChoice,
    MatchMode,
    MatchStage,
    RobotRole,
    ShooterChoice,
    THREE_V_THREE_ROBOT_IDS,
    get_match_rules,
    get_robot_specs,
    stage_at,
)

class tgul2027RulesTest(unittest.TestCase):

    def test_match_durations_and_starting_resources(self):
        a = get_match_rules(MatchMode.THREE_V_THREE)
        b = get_match_rules(MatchMode.INFANTRY_DUEL)

        self.assertEqual(
            (
                a.preparation_sec,
                a.self_check_sec,
                a.countdown_sec,
                a.battle_sec,
                a.total_sec,
            ),
            (180, 15, 5, 300, 500),
        )
        self.assertEqual(
            (b.preparation_sec, b.battle_sec, b.total_sec),
            (120, 120, 260),
        )
        self.assertEqual(
            (a.initial_control_points, a.initial_coins),
            (600, 200),
        )
        self.assertIsNone(b.initial_control_points)
        self.assertEqual(
            THREE_V_THREE_ROBOT_IDS,
            (1, 3, 4, 7, 101, 103, 104, 107),
        )

    def test_all_stage_boundaries(self):
        for mode in MatchMode:
            rules = get_match_rules(mode)
            boundaries = [
                rules.preparation_sec,
                rules.preparation_sec + rules.self_check_sec,
                rules.preparation_sec + rules.self_check_sec
                + rules.countdown_sec,
                rules.total_sec,
            ]
            stages = [
                MatchStage.PREPARATION,
                MatchStage.SELF_CHECK,
                MatchStage.COUNTDOWN,
                MatchStage.BATTLE,
                MatchStage.SETTLEMENT,
            ]

            self.assertEqual(
                stage_at(mode, 0).stage, stages[0]
            )

            for index, boundary in enumerate(boundaries):
                self.assertEqual(
                    stage_at(mode, boundary - 0.001).stage,
                    stages[index],
                )
                self.assertEqual(
                    stage_at(mode, boundary).stage,
                    stages[index + 1],
                )
                self.assertEqual(
                    stage_at(mode, boundary - 0.001).countdown_sec,
                    1,
                )

            self.assertEqual(
                stage_at(mode, rules.total_sec + 10).stage,
                MatchStage.SETTLEMENT,
            )
            self.assertFalse(
                stage_at(mode, boundaries[1]).accepts_robot_control
            )
            self.assertTrue(
                stage_at(mode, boundaries[2]).accepts_robot_control
            )

    def test_stage_elapsed_and_invalid_time(self):
        snapshot = stage_at("tgul_3v3", 181.3)
        self.assertEqual(snapshot.elapsed_sec, 1)
        self.assertEqual(snapshot.countdown_sec, 14)

        for invalid in (
            -0.01, math.nan, math.inf,
            -math.inf, None, "invalid", True
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    stage_at("tgul_3v3", invalid)

        with self.assertRaises(ValueError):
            get_match_rules("invalid")

    def test_robot_profiles(self):
        heavy = get_robot_specs("tgul_3v3", "heavy")
        active = get_robot_specs(
            "tgul_3v3", "heavy", heavy_activated=True
        )
        sentry = get_robot_specs("tgul_3v3", "sentry")
        duel = get_robot_specs("tgul_infantry", "infantry")

        self.assertEqual(
            (heavy.max_hp, heavy.max_power_w, heavy.max_heat),
            (100, 50, None),
        )
        self.assertEqual(
            (active.max_hp, active.max_heat,
             active.cooling_per_sec),
            (450, 250, 66),
        )
        self.assertEqual(
            (sentry.max_hp, sentry.initial_allowed_ammo),
            (400, 750),
        )
        self.assertFalse(sentry.allows_custom_terminal)
        self.assertEqual(
            (duel.max_hp, duel.max_power_w,
             duel.max_heat, duel.cooling_per_sec,
             duel.initial_allowed_ammo),
            (200, 120, 80, 12, 200),
        )

        with self.assertRaises(ValueError):
            get_robot_specs("tgul_infantry", "sentry")

    def test_infantry_performance_matrix_and_enum_validation(self):
        expected = {
            (ChassisChoice.HEALTH, ShooterChoice.COOLING):
                (350, 75, 88, 24),
            (ChassisChoice.HEALTH, ShooterChoice.BURST):
                (350, 75, 230, 14),
            (ChassisChoice.POWER, ShooterChoice.COOLING):
                (300, 90, 88, 24),
            (ChassisChoice.POWER, ShooterChoice.BURST):
                (300, 90, 230, 14),
        }

        for (chassis, shooter), values in expected.items():
            with self.subTest(chassis=chassis, shooter=shooter):
                spec = get_robot_specs(
                    MatchMode.THREE_V_THREE,
                    RobotRole.INFANTRY,
                    chassis=chassis,
                    shooter=shooter,
                )
                self.assertEqual(
                    (spec.max_hp, spec.max_power_w,
                     spec.max_heat, spec.cooling_per_sec),
                    values,
                )

        with self.assertRaises(ValueError):
            get_robot_specs(
                "tgul_3v3", "infantry", chassis=9
            )

        with self.assertRaises(ValueError):
            get_robot_specs("tgul_3v3", "unknown")

    def test_rules_are_immutable(self):
        rules = get_match_rules("tgul_3v3")
        with self.assertRaises(FrozenInstanceError):
            rules.battle_sec = 123

if __name__ == "__main__":
    unittest.main()
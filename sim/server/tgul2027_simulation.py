"""TGUL 2027 opt-in state and timeline adapter for the RM26 simulator.

This is a Web-side integration milestone, NOT an official TGUL MQTT implementation.
The older application keeps eight display slots; infantry duel uses only 3/103.
"""
import threading

from server.match_simulation_engine import MatchSimulationEngine
from server.state_manager import StateManager
from server.tgul2027_map import get_tgul_map, initial_demo_positions
from server.tgul2027_rules import (
    MatchMode, MatchStage, RobotRole, THREE_V_THREE_ROBOT_IDS,
    get_match_rules, get_robot_specs, stage_at,
)


class TGULStateManager(StateManager):
    """Preserve legacy Web structure while populating TGUL state."""

    def __init__(self, mode=MatchMode.THREE_V_THREE):
        self.tgul_mode = MatchMode(mode)
        self._tgul_self_check_applied = False
        super().__init__()
        # The superclass uses a regular Lock; TGUL needs atomic nested updates.
        self.lock = threading.RLock()
        with self.lock:
            self._apply_tgul_profile_locked()

    @property
    def active_robot_ids(self):
        if self.tgul_mode == MatchMode.INFANTRY_DUEL:
            return (3, 103)
        # Three robots take the field per team; 4/104 remain registered spares.
        return (1, 3, 7, 101, 103, 107)

    @staticmethod
    def _role_for(robot_id):
        return {
            1: RobotRole.HEAVY,
            3: RobotRole.INFANTRY,
            4: RobotRole.INFANTRY,
            7: RobotRole.SENTRY,
        }[int(robot_id) % 100]

    def _spec_for(self, robot_id):
        return get_robot_specs(
            self.tgul_mode, self._role_for(robot_id)
        )

    def _stage_default_countdown(self, stage):
        rules = get_match_rules(self.tgul_mode)
        return {
            0: 0,
            1: rules.preparation_sec,
            2: rules.self_check_sec,
            3: rules.countdown_sec,
            4: rules.battle_sec,
            5: 0,
        }.get(int(stage), 0)

    def _apply_tgul_profile_locked(self):
        """Caller must hold self.lock, except during the superclass reset."""
        ids = list(THREE_V_THREE_ROBOT_IDS)
        active = set(self.active_robot_ids)
        self.robot_ids = ids
        demo_positions = initial_demo_positions(self.tgul_mode, ids)
        if demo_positions:
            self.positions = demo_positions

        # Keep the eight Web display slots; inactive slots are deliberately zero.
        specs = {
            rid: self._spec_for(rid)
            for rid in ids if rid in active
        }
        hp_max = [specs[rid].max_hp if rid in active else 0 for rid in ids]
        ammo = [
            specs[rid].initial_allowed_ammo if rid in active else 0
            for rid in ids
        ]
        unit = self.global_unit_status
        unit["robot_max_hp"] = list(hp_max)
        unit["robot_health"] = list(hp_max)
        unit["robot_bullets"] = list(ammo)
        for key in (
            "robot_heat", "robot_fire_rate", "robot_power",
        ):
            unit[key] = [0] * len(ids)
        for key in (
            "robot_heat_manual_hold", "robot_speed_over_limit",
            "robot_power_over_limit",
        ):
            unit[key] = [False] * len(ids)

        initial_cp = get_match_rules(self.tgul_mode).initial_control_points or 0
        unit["total_CP_red"] = initial_cp
        unit["total_CP_blue"] = initial_cp
        if self.game_status["current_stage"] == MatchStage.NOT_STARTED:
            self.game_status["stage_countdown_sec"] = 0
        initial_coins = get_match_rules(self.tgul_mode).initial_coins or 0
        for team in ("red", "blue"):
            self.global_logistics_status[f"{team}_economy"] = initial_coins
            self.global_logistics_status[
                f"{team}_total_economy_obtained"
            ] = initial_coins

        template = dict(next(iter(self.respawn_info.values()), {}))
        self.respawn_info = {rid: dict(template) for rid in ids}
        self.robot_injury_stats = {
            rid: self._empty_robot_injury_stat() for rid in ids
        }
        self.last_yellow_ts = {rid: 0.0 for rid in ids}
        self.yellow_streak = {rid: 0 for rid in ids}
        self.yellow_count = {rid: 0 for rid in ids}

        # During initialization, choose a valid view; CLI selection overrides it.
        if self.current_robot_id not in active:
            self.current_robot_id = self.active_robot_ids[0]
        self._sync_current_robot_view_locked()

    def _sync_current_robot_view_locked(self):
        rid = int(self.current_robot_id)
        if rid not in self.active_robot_ids:
            raise ValueError(
                f"robot ID {rid} is not active in {self.tgul_mode.value}; "
                f"choose one of {self.active_robot_ids}"
            )
        spec = self._spec_for(rid)
        index = self.robot_ids.index(rid)
        self.robot_static_status.update({
            "robot_id": rid,
            "robot_type": rid % 100,
            "max_health": spec.max_hp,
            "max_heat": spec.max_heat or 0,
            "heat_cooldown_rate": spec.cooling_per_sec or 0.0,
            "max_power": spec.max_power_w,
            "performance_system_shooter": 1,
            "performance_system_chassis": 1,
        })
        self.robot_dynamic_status.update({
            "current_health": self.global_unit_status["robot_health"][index],
            "current_heat": self.global_unit_status["robot_heat"][index],
            "remaining_ammo": self.global_unit_status["robot_bullets"][index],
            "current_buffer_energy": 60,
        })

    def sync_current_robot_view(self):
        """Call after main.py sets current_robot_id."""
        with self.lock:
            self._sync_current_robot_view_locked()

    def _get_robot_fire_rate_limit(self, robot_id):
        if robot_id not in self.active_robot_ids:
            return 0.0
        return float(self._spec_for(robot_id).max_muzzle_speed_mps or 0)

    def _get_robot_power_limit(self, robot_id):
        if robot_id not in self.active_robot_ids:
            return 0.0
        return float(self._spec_for(robot_id).max_power_w)

    def _reset_game_state(self, reset_series_score=True):
        super()._reset_game_state(reset_series_score=reset_series_score)
        self._tgul_self_check_applied = False
        self._apply_tgul_profile_locked()

    def reset_all(self):
        super().reset_all()
        with self.lock:
            self.game_status["stage_countdown_sec"] = (
                self._stage_default_countdown(0)
            )

    def skip_to_battle(self):
        with self.lock:
            self.game_status.update({
                "current_stage": int(MatchStage.BATTLE),
                "stage_countdown_sec": get_match_rules(
                    self.tgul_mode
                ).battle_sec,
                "stage_elapsed_sec": 0,
                "is_paused": False,
            })

    def set_match_stage(self, stage, countdown_sec=None):
        super().set_match_stage(stage, countdown_sec)
        with self.lock:
            if self.game_status["current_stage"] == MatchStage.BATTLE:
                duration = get_match_rules(self.tgul_mode).battle_sec
                self.game_status["stage_elapsed_sec"] = max(
                    0, duration - self.game_status["stage_countdown_sec"]
                )

    def apply_match_simulation_frame(self, **kwargs):
        with self.lock:
            stage = int(kwargs["current_stage"])
            if stage >= MatchStage.SELF_CHECK and not self._tgul_self_check_applied:
                # Referee-system self-check restores each active robot's HP.
                self.global_unit_status["robot_health"] = list(
                    self.global_unit_status["robot_max_hp"]
                )
                self._sync_current_robot_view_locked()
                self._tgul_self_check_applied = True
            return super().apply_match_simulation_frame(**kwargs)

    # TGUL_MAP_ROUND3: reject invalid coordinates and inactive robots.
    def set_robot_position(self, robot_index, x, y, angle=None):
        import math
        try:
            idx, px, py = int(robot_index), float(x), float(y)
            angle_num = None if angle is None else float(angle)
        except (ValueError, TypeError, OverflowError):
            return False
        cfg = get_tgul_map(self.tgul_mode)
        if not cfg["configured"] or not (0 <= idx < len(self.robot_ids)):
            return False
        if self.robot_ids[idx] not in self.active_robot_ids:
            return False
        if not math.isfinite(px) or not math.isfinite(py):
            return False
        if angle_num is not None and not math.isfinite(angle_num):
            return False
        if not (0 <= px <= cfg["width_m"] and 0 <= py <= cfg["height_m"]):
            return False
        super().set_robot_position(idx, px, py, angle_num)
        return True

    def get_state(self):
        snapshot = super().get_state()
        snapshot["tgulMode"] = self.tgul_mode.value
        snapshot["tgulActiveRobotIds"] = list(self.active_robot_ids)
        snapshot["tgulMap"] = get_tgul_map(self.tgul_mode)
        snapshot["tgulControlPoints"] = {
            "red": snapshot["globalUnitStatus"]["total_CP_red"],
            "blue": snapshot["globalUnitStatus"]["total_CP_blue"],
        }
        return snapshot


class TGULMatchSimulationEngine(MatchSimulationEngine):
    """Reuse transport/tick/control, replace only the legacy demo timeline."""

    PHASE_NAMES = {
        MatchStage.NOT_STARTED: "idle",
        MatchStage.PREPARATION: "preparation",
        MatchStage.SELF_CHECK: "self_check",
        MatchStage.COUNTDOWN: "countdown",
        MatchStage.BATTLE: "battle",
        MatchStage.SETTLEMENT: "settlement",
    }

    def __init__(self, state_manager, mqtt_publisher=None, clock=None, seed=2027):
        if not isinstance(state_manager, TGULStateManager):
            raise TypeError("TGULMatchSimulationEngine requires TGULStateManager")
        rules = get_match_rules(state_manager.tgul_mode)
        self.FULL_DURATION_SEC = float(rules.total_sec)
        # quick is a compressed full-stage preview, NOT a competition type.
        self.QUICK_DURATION_SEC = 90.0
        super().__init__(
            state_manager, mqtt_publisher=mqtt_publisher,
            clock=clock, seed=seed,
        )

    def _timeline_state(self):
        if self._status == "idle" or (
            self._status == "stopped" and self._elapsed_sec <= 0
        ):
            return 0, 0, 0, "idle", 0.0

        rules = get_match_rules(self.state_manager.tgul_mode)
        # When quick mode is selected, compress the entire official timeline.
        official_time = min(
            float(rules.total_sec),
            self._elapsed_sec * rules.total_sec
            / max(self._duration_sec, 0.001),
        )
        snapshot = stage_at(self.state_manager.tgul_mode, official_time)
        before_battle = (
            rules.preparation_sec + rules.self_check_sec
            + rules.countdown_sec
        )
        battle_progress = min(
            1.0, max(
                0.0, (official_time - before_battle) / rules.battle_sec
            )
        )
        return (
            int(snapshot.stage),
            snapshot.countdown_sec,
            snapshot.elapsed_sec,
            self.PHASE_NAMES[snapshot.stage],
            battle_progress,
        )

    def _apply_current_frame(self, publish_radar):
        # Do not fabricate legacy hero/dart/outpost events, HP or radar data.
        stage, countdown, elapsed, _, _ = self._timeline_state()
        status = self.get_status()
        self.state_manager.apply_match_simulation_frame(
            positions=None,
            robot_health=None,
            current_stage=stage,
            stage_countdown_sec=countdown,
            stage_elapsed_sec=elapsed,
            events=None,
            structure_health=None,
            simulation_status=status,
        )
        snapshot = self.state_manager.get_state()
        positions = snapshot["positions"]
        health = snapshot["globalUnitStatus"]["robot_health"]
        robots = self._build_robot_payload(positions, health)
        for item in robots:
            item["team"] = "blue" if item["robot_id"] >= 100 else "red"

        frame = dict(status)
        frame["robots"] = robots
        frame["recent_events"] = []
        frame["sequence_time"] = round(self._elapsed_sec, 3)
        self._last_stage = stage
        return frame

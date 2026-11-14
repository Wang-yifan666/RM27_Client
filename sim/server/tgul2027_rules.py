from dataclasses import dataclass
from enum import Enum, IntEnum
from math import ceil, isfinite

class MatchMode(str, Enum):
    THREE_V_THREE = "tgul_3v3"
    INFANTRY_DUEL = "tgul_infantry"

class RobotRole(str, Enum):
    HEAVY = "heavy"        # 英雄
    INFANTRY = "infantry"  # 步兵
    SENTRY = "sentry"      # 烧饼

class ChassisChoice(IntEnum):
    HEALTH = 1  
    POWER = 2 

class ShooterChoice(IntEnum):
    COOLING = 1
    BURST = 2

class MatchStage(IntEnum):
    NOT_STARTED = 0  # 未开始
    PREPARATION = 1  # 准备阶段
    SELF_CHECK = 2   # 自检阶段
    COUNTDOWN = 3    # 倒计时阶段
    BATTLE = 4       # 战斗阶段
    SETTLEMENT = 5   # 结算阶段

THREE_V_THREE_ROBOT_IDS = (
    1, 3, 4, 7, 101, 103, 104, 107
)

@dataclass(frozen=True, slots=True)
class MatchRules:
    preparation_sec: int               # 准备阶段秒数       
    self_check_sec: int                # 自检阶段秒数
    countdown_sec: int                 # 倒计时阶段秒数
    battle_sec: int                    # 战斗阶段秒数
    initial_control_points: int | None # 初始控制点，可能为 None
    initial_coins: int | None          # 初始金币，可能为 None

    @property
    def total_sec(self) -> int:
        return (
            self.preparation_sec
            + self.self_check_sec
            + self.countdown_sec
            + self.battle_sec
        )

@dataclass(frozen=True, slots=True)
class RobotSpecs:
    max_hp: int                         # 最大血量
    max_power_w: int                    # 最大功率，单位 W
    max_heat: int | None                # 最大热量，可能为 None
    cooling_per_sec: float | None       # 每秒冷却，可能为 None
    max_muzzle_speed_mps: float | None  # 最大枪口速度，米/秒，可能为 None
    initial_allowed_ammo: int           # 初始允许弹药量
    allows_custom_terminal: bool        # 是否允许自定义终端

@dataclass(frozen=True, slots=True)
class StageSnapshot:
    stage: MatchStage                   # 当前阶段
    countdown_sec: int                  # 当前阶段剩余秒数
    elapsed_sec: int                    # 当前阶段已经过的秒数
    accepts_robot_control: bool         # 当前阶段是否接受机器人控制

_MATCH_RULES = {
    MatchMode.THREE_V_THREE: MatchRules(
        180, 15, 5, 300, 600, 200
    ),
    MatchMode.INFANTRY_DUEL: MatchRules(
        120, 15, 5, 120, None, None
    ),
}

def get_match_rules(mode: MatchMode | str) -> MatchRules:
    return _MATCH_RULES[MatchMode(mode)]

def get_robot_specs(
    mode: MatchMode | str,
    role: RobotRole | str,
    *,
    chassis: ChassisChoice = ChassisChoice.HEALTH,
    shooter: ShooterChoice = ShooterChoice.COOLING,
    heavy_activated: bool = False,
) -> RobotSpecs:
    # 只返回规则上限
    mode = MatchMode(mode)
    role = RobotRole(role)
    chassis = ChassisChoice(chassis)
    shooter = ShooterChoice(shooter)

    if mode == MatchMode.INFANTRY_DUEL:
        if role != RobotRole.INFANTRY:
            raise ValueError(
                "Infantry duel only permits infantry robots"
            )
        return RobotSpecs(
            200, 120, 80, 12.0, 25.0, 200, True
        )

    if role == RobotRole.HEAVY:
        if heavy_activated:
            return RobotSpecs(
                450, 50, 250, 66.0, 16.5, 0, True
            )
        return RobotSpecs(
            100, 50, None, None, None, 0, True
        )

    if role == RobotRole.SENTRY:
        return RobotSpecs(
            400, 100, 260, 30.0, 25.0, 750, False
        )

    hp, power = (
        (350, 75)
        if chassis == ChassisChoice.HEALTH
        else (300, 90)
    )

    max_heat, cooldown = (
        (88, 24.0)
        if shooter == ShooterChoice.COOLING
        else (230, 14.0)
    )

    return RobotSpecs(
        hp, power, max_heat, cooldown, 25.0, 0, True
    )

def stage_at(
    mode: MatchMode | str,
    elapsed_sec: float,
) -> StageSnapshot:
    # 从准备阶段开始算的比赛模拟时间，并非准确时间
    rules = get_match_rules(mode)

    if isinstance(elapsed_sec, bool):
        raise ValueError("Invalid elapsed_sec")

    try:
        elapsed = float(elapsed_sec)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid elapsed_sec") from exc

    if not isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid elapsed_sec")

    stages = (
        (MatchStage.PREPARATION, rules.preparation_sec),
        (MatchStage.SELF_CHECK, rules.self_check_sec),
        (MatchStage.COUNTDOWN, rules.countdown_sec),
        (MatchStage.BATTLE, rules.battle_sec),
    )

    for stage, duration in stages:
        if elapsed < duration:
            return StageSnapshot(
                stage=stage,
                countdown_sec=ceil(duration - elapsed),
                elapsed_sec=int(elapsed),
                accepts_robot_control=(
                    stage == MatchStage.BATTLE
                ),
            )
        elapsed -= duration

    return StageSnapshot(
        MatchStage.SETTLEMENT, 0, 0, False
    )
"""
V2.5.2 阻断问题回归测试。

覆盖：目标被完全封死时（blocked.cell = None），巡检决策不能崩，
clear 要明确拒绝，skip / stop 必须清掉 blocked 并继续。
"""

import pytest

from app.services.simulation_engine import SimulationEngine


def walled_engine() -> SimulationEngine:
    """构造一个目标四周被固定屏障封死的引擎。"""
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 12,
            "height": 8,
            "grid": [[0] * 12 for _ in range(8)],
            "start": [1, 1],
            "goals": [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    x, y = engine.map.goals[0]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        engine.map.grid[y + dy][x + dx] = 2
    engine.start_patrol()
    assert engine.blocked is not None
    assert engine.blocked["cell"] is None
    return engine


def test_clear_on_walled_goal_is_rejected_without_crash():
    """cell 为 None 时点“清除”不能抛异常，blocked 保持。"""
    engine = walled_engine()
    engine.patrol_decision("clear")
    assert engine.blocked is not None
    assert engine.blocked["cell"] is None


def test_skip_on_walled_goal_clears_blocked():
    """cell 为 None 时“跳过”必须清掉 blocked，且不写入待清障。"""
    engine = walled_engine()
    engine.patrol_decision("skip")
    assert engine.blocked is None
    assert engine.paused is False
    assert engine.pending == []


def test_stop_on_walled_goal_clears_blocked():
    """cell 为 None 时“停止”必须结束巡检并清掉 blocked。"""
    engine = walled_engine()
    engine.patrol_decision("stop")
    assert engine.blocked is None
    assert engine.mode == "manual"


@pytest.mark.parametrize("action", ["clear", "skip", "stop"])
def test_decisions_do_not_raise(action):
    """三个按钮都不允许抛异常——这是 V2.5.1 卡死弹窗的直接原因。"""
    engine = walled_engine()
    engine.patrol_decision(action)

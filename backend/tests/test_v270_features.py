"""
V2.7.0 测试：低电量返航预算 + 定时巡检。
"""

from datetime import datetime

from app.services.simulation_engine import SimulationEngine


def blank_engine(goals=None) -> SimulationEngine:
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 12,
            "height": 8,
            "grid": [[0] * 12 for _ in range(8)],
            "start": [1, 1],
            "goals": goals or [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def test_charge_blocked_reports_budget():
    engine = blank_engine()
    engine.map.grid[5][1] = 1  # (1,5)
    engine.map.grid[6][2] = 1  # (2,6)
    engine.battery = 4.0
    engine.tick()
    assert engine.blocked is not None
    assert engine.blocked["reason"] == "charge_unreachable"
    assert engine.blocked["clear_cost"] > 0
    assert engine.blocked["return_cost"] >= 0
    assert engine.blocked["can_clear_and_return"] is False
    engine.clear_and_charge()
    assert engine.battery == 4.0, "预算不够时不能扣电清障"


def test_add_schedule_and_trigger():
    engine = blank_engine(goals=[[9, 6]])
    engine.add_schedule("09:30", [[9, 6]], 99)
    assert len(engine.schedules) == 1
    schedule = engine.schedules[0]
    assert 1 <= schedule["rounds"] <= schedule["max_rounds"]

    engine.schedules[0]["time"] = datetime.now().strftime("%H:%M")
    engine.mode = "manual"
    engine.tick()
    assert engine.mode == "patrol"
    assert engine.patrol.total == schedule["rounds"]


def test_schedule_rejects_bad_time():
    engine = blank_engine()
    engine.add_schedule("25:99", [[9, 6]], 1)
    assert engine.schedules == []

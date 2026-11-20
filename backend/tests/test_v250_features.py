"""
V2.5 功能测试模块。

覆盖：最省电路径、手动排障按材质扣电、巡检不可达暂停、动态障碍投放、
返航不可达人工搬回、云端 LLM 无 Key/失败降级。
"""

import pytest

from app.core import config
from app.services import agent as agent_module
from app.services.planner import build_plan
from app.services.simulation_engine import SimulationEngine


def blank_engine(width: int = 12, height: int = 8) -> SimulationEngine:
    """构造一张空白地图的引擎（只保留边界墙）。"""
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": width,
            "height": height,
            "grid": [[0] * width for _ in range(height)],
            "start": [1, 1],
            "goals": [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def test_energy_mode_avoids_expensive_material():
    """最省电模式应绕开 20% 的金刚石，而不是走最短直线。"""
    grid = [[0] * 7 for _ in range(7)]
    grid[3][3] = 4  # 直线上放金刚石
    energy = build_plan(
        grid, (1, 3), (5, 3), 100.0, 0.2, 5.0, config.settings.material_costs, "energy"
    )
    distance = build_plan(
        grid, (1, 3), (5, 3), 100.0, 0.2, 5.0, config.settings.material_costs, "distance"
    )
    assert energy["obstacles"] == [], "最省电模式不该穿过金刚石"
    assert energy["total_cost"] < 2.0
    assert distance["obstacles"] == [[3, 3]], "最短模式仍会走直线"
    assert distance["clear_cost"] == pytest.approx(20.0)


def test_energy_mode_is_never_more_expensive_than_distance():
    """同一张地图上，最省电的总耗电不应高于最短路线。"""
    grid = [[0] * 8 for _ in range(8)]
    grid[4][4] = 4
    grid[4][3] = 3
    energy = build_plan(grid, (1, 4), (6, 4), 100.0, 0.2, 5.0, config.settings.material_costs, "energy")
    distance = build_plan(grid, (1, 4), (6, 4), 100.0, 0.2, 5.0, config.settings.material_costs, "distance")
    assert energy["total_cost"] <= distance["total_cost"] + 1e-9


def test_resolve_fault_rejects_when_battery_low():
    """电量不足时手动排障必须失败：不清格、不扣电、给出原因。"""
    engine = blank_engine()
    engine.mode = "blocked"
    engine.theta = 0.0
    engine.x, engine.y = 3, 3
    engine.map.grid[3][4] = 4  # 正前方金刚石，需 20%
    engine.battery = 5.0
    result = engine.resolve_fault()
    assert engine.map.grid[3][4] == 4, "电量不足不应清除障碍"
    assert engine.battery == pytest.approx(5.0)
    assert "电量不足" in result["data"]["message"]
    assert result["data"]["ok"] is False


def test_resolve_fault_charges_material_cost():
    """手动排障成功时按材质扣电。"""
    engine = blank_engine()
    engine.mode = "blocked"
    engine.theta = 0.0
    engine.x, engine.y = 3, 3
    engine.map.grid[3][4] = 3  # 沙子 2%
    engine.battery = 50.0
    result = engine.resolve_fault()
    assert engine.map.grid[3][4] == 0
    assert engine.battery == pytest.approx(48.0)
    assert result["data"]["ok"] is True


def test_start_patrol_pauses_when_goal_is_walled():
    """目标四周被屏障封死时，巡检应立即暂停并记录 blocked，而不是静默跳过。"""
    engine = blank_engine()
    x, y = engine.map.goals[0]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        engine.map.grid[y + dy][x + dx] = 2
    engine.start_patrol()
    assert engine.paused is True
    assert engine.blocked is not None
    assert engine.blocked["reason"] == "unreachable"


def test_drop_obstacle_ahead():
    """动态障碍：在正前方投放一格石头，并广播地图。"""
    engine = blank_engine()
    engine.x, engine.y = 3, 3
    engine.theta = 0.0
    engine.drop_obstacle_ahead()
    assert engine.map.grid[3][4] == 1


def test_carry_home_allows_charge_unreachable():
    """返航路线被封死时，允许人工搬回并恢复满电。"""
    engine = blank_engine()
    engine.blocked = {"cell": None, "reason": "charge_unreachable", "goal": [1, 6]}
    engine.battery = 3.0
    engine.carry_home()
    assert engine.battery == pytest.approx(100.0)
    assert engine.blocked is None


def test_llm_without_key_falls_back_to_rule(monkeypatch):
    """没有开启大模型（也没有 Key）时直接走规则，不发起任何外部请求。"""
    monkeypatch.setattr(config.settings, "agent_llm_enabled", False)
    monkeypatch.setattr(config.settings, "agent_llm_api_key", "")
    engine = blank_engine()
    agent = agent_module.AgentService(engine)
    parsed, source = __import__("asyncio").run(agent._understand("现在状态怎么样"))
    assert source == "rule"
    assert parsed["tool"] == "status"


def test_llm_failure_falls_back_to_rule(monkeypatch):
    """云端报错时自动降级为规则解析，不阻塞指令。"""
    monkeypatch.setattr(config.settings, "agent_llm_enabled", True)
    monkeypatch.setattr(config.settings, "agent_llm_api_key", "fake-key")

    def boom(*_args, **_kwargs):
        raise TimeoutError("boom")

    monkeypatch.setattr(agent_module, "_call_openai", boom)
    engine = blank_engine()
    agent = agent_module.AgentService(engine)
    parsed, source = __import__("asyncio").run(agent._understand("现在状态怎么样"))
    assert source == "rule-fallback"
    assert parsed["tool"] == "status"

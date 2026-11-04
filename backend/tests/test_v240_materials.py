"""
V2.4.0 障碍材质测试模块。

模块功能：验证"石头 / 沙子 / 金刚石"三种材质在规划预算、清障扣电、
地图校验三条链路上都按材质计价，且前后端口径一致。
作者：智能巡检机器人二维仿真系统 V2.4.0 开发组
日期：2026-11-04
版本：V2.4.0
"""

import pytest

from app.core import config
from app.models.map import GridMap
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


def test_material_costs_configured():
    """共享规则里的材质价格应被后端读取：石头 5% / 沙子 2% / 金刚石 20%。"""
    assert config.settings.material_costs == {1: 5.0, 3: 2.0, 4: 20.0}
    # 兜底单价仍是 5%，老地图（只有 1）不受影响
    assert config.settings.clear_obstacle_cost == 5.0


def test_build_plan_sums_material_costs():
    """规划预算按"每格材质"累加，而不是按障碍个数统一计价。"""
    grid = [[0] * 7 for _ in range(7)]
    grid[3][2] = 3  # 沙子 2%
    grid[3][4] = 4  # 金刚石 20%
    plan = build_plan(
        grid,
        (1, 3),
        (5, 3),
        battery=100.0,
        move_cost=0.2,
        clear_cost=5.0,
        material_costs=config.settings.material_costs,
    )
    assert plan["path"], "7x7 空白地图应当可达"
    assert plan["obstacles"] == [[2, 3], [4, 3]]
    # 4 步 × 0.2 = 0.8；清障 2 + 20 = 22
    assert plan["move_cost"] == pytest.approx(0.8)
    assert plan["clear_cost"] == pytest.approx(22.0)
    assert plan["total_cost"] == pytest.approx(22.8)
    assert plan["enough"] is True


def test_plan_budget_truncates_by_material_price():
    """电量只够移动 + 清沙子时，金刚石不应被纳入 clearable。"""
    grid = [[0] * 7 for _ in range(7)]
    grid[3][2] = 3  # 沙子 2%
    grid[3][4] = 4  # 金刚石 20%
    plan = build_plan(
        grid,
        (1, 3),
        (5, 3),
        battery=3.6,  # 移动 0.8 + 沙子 2 = 2.8，再清金刚石要 22.8
        move_cost=0.2,
        clear_cost=5.0,
        material_costs=config.settings.material_costs,
    )
    assert plan["reachable"] is True
    assert plan["enough"] is False
    assert plan["clearable"] == [[2, 3]]
    assert plan["clear_cost"] == pytest.approx(2.0)


def test_clear_sand_and_diamond_use_their_own_price():
    """手动清障按材质扣电：沙子 2%、金刚石 20%。"""
    engine = blank_engine()
    engine.map.grid[3][3] = 3  # 坐标 (3, 3)
    engine.map.grid[5][3] = 4  # 坐标 (3, 5)
    engine.battery = 100.0

    engine.clear_obstacle_at([3, 3])
    assert engine.map.grid[3][3] == 0
    assert engine.battery == pytest.approx(98.0)

    engine.clear_obstacle_at([3, 5])
    assert engine.map.grid[5][3] == 0
    assert engine.battery == pytest.approx(78.0)


def test_clear_diamond_rejected_when_battery_low():
    """电量不足 20% 时清不动金刚石，格子必须保持原样。"""
    engine = blank_engine()
    engine.map.grid[3][3] = 4
    engine.battery = 10.0
    engine.clear_obstacle_at([3, 3])
    assert engine.map.grid[3][3] == 4
    assert engine.battery == pytest.approx(10.0)


def test_set_cell_accepts_material_values():
    """编辑格子允许写入 3（沙子）和 4（金刚石），且同步到地图。"""
    engine = blank_engine()
    engine.set_cell(4, 4, 3)
    assert engine.map.grid[4][4] == 3
    engine.set_cell(4, 4, 4)
    assert engine.map.grid[4][4] == 4
    engine.set_cell(4, 4, 0)
    assert engine.map.grid[4][4] == 0


def test_map_validation_accepts_materials_and_rejects_unknown():
    """地图校验：0~4 合法，5 非法。"""
    base = {
        "width": 6,
        "height": 6,
        "grid": [[0] * 6 for _ in range(6)],
        "start": [1, 1],
        "goals": [[4, 4]],
        "charge_point": [1, 4],
    }
    base["grid"][2][2] = 3
    assert GridMap(**base).grid[2][2] == 3
    base["grid"][2][2] = 4
    assert GridMap(**base).grid[2][2] == 4
    base["grid"][2][2] = 5
    with pytest.raises(ValueError):
        GridMap(**base)

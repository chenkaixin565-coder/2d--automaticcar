"""
V2.5.4 回归测试。

覆盖：目标被“多层可清障碍”挡住时的批量清除、重新开始清空尾迹、
以及斜穿墙角仍然被禁止（这次问题的根因）。
"""

import pytest

from app.algorithms.astar import astar
from app.services.simulation_engine import SimulationEngine


def blank_engine(width: int = 12, height: int = 8) -> SimulationEngine:
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": width,
            "height": height,
            "grid": [[0] * width for _ in range(height)],
            "start": [1, 1],
            "goals": [[10, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def two_walls_engine() -> tuple[SimulationEngine, list[list[int]]]:
    """在机器人到目标之间竖两道石头墙：单独拆一处仍然过不去。"""
    engine = blank_engine()
    cells = []
    for x in (4, 7):
        for y in range(1, 7):
            engine.map.grid[y][x] = 1
            cells.append([x, y])
    return engine, cells


def test_multilayer_wall_offers_batch_clear():
    """两道墙 => 单格拆除救不了，应给出‘清除 N 处’的批量方案。"""
    engine, _ = two_walls_engine()
    engine.start_patrol()
    assert engine.blocked is not None
    cells = engine.blocked.get("cells") or []
    assert len(cells) >= 2
    assert engine.blocked["clear_cost"] == pytest.approx(len(cells) * 5.0)


def test_batch_clear_clears_all_and_resumes():
    """点“全部清除”后，路线上的石头都该消失、电量按处扣减，并重新规划。"""
    engine, _ = two_walls_engine()
    engine.start_patrol()
    cells = [list(c) for c in (engine.blocked.get("cells") or [])]
    engine.battery = 100.0
    engine.patrol_decision("clear")
    for cx, cy in cells:
        assert engine.map.grid[cy][cx] == 0
    assert engine.battery == pytest.approx(100.0 - len(cells) * 5.0)
    assert engine.blocked is None
    assert engine.paused is False


def test_batch_clear_rejected_when_battery_low():
    """电量不足时，批量清除必须整体拒绝，一格都不清。"""
    engine, _ = two_walls_engine()
    engine.start_patrol()
    cells = [list(c) for c in (engine.blocked.get("cells") or [])]
    engine.battery = 5.0
    engine.patrol_decision("clear")
    assert engine.battery == pytest.approx(5.0)
    assert engine.blocked is not None
    for cx, cy in cells:
        assert engine.map.grid[cy][cx] == 1


def test_restart_clears_trail():
    """“重新开始”应该把尾迹清空，只留起点。"""
    engine = blank_engine()
    engine.visited_trail = [[1, 1], [2, 1], [3, 1]]
    engine.reset(keep_trail=False)
    assert engine.visited_trail == [[1, 1]]


def test_astar_refuses_diagonal_corner_cut():
    """斜穿墙角仍然禁止：右侧和正下方是障碍时，不能斜着走。"""
    grid = [[0] * 5 for _ in range(5)]
    grid[1][2] = 1  # (2, 1)
    grid[2][1] = 1  # (1, 2)
    result = astar(grid, (1, 1), (2, 2))
    # 不能一步斜穿过去，只能绕路或不可达
    assert len(result["path"]) != 2

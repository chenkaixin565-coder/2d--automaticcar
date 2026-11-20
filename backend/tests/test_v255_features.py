"""
V2.5.5 一致性测试：规划与执行使用同一套“禁止斜穿墙角”口径。

场景：起点 (1,1)、终点 (3,3)，(2,1) 和 (1,2) 各有一块石头。
- 规划如果想走 (1,1) → (2,2) 的斜线，必须把两块石头都清掉；
- 只清一块，执行时的 astar 仍然不能斜穿。
"""

from app.algorithms.astar import astar
from app.services.planner import build_plan


def corner_grid():
    grid = [[0] * 5 for _ in range(5)]
    grid[1][2] = 1  # (2, 1)
    grid[2][1] = 1  # (1, 2)
    return grid


def test_planner_includes_both_corner_cells():
    plan = build_plan(corner_grid(), (1, 1), (3, 3), 100.0, 0.2, 5.0, {1: 5.0}, "distance")
    obstacles = [tuple(c) for c in plan["obstacles"]]
    assert (2, 1) in obstacles
    assert (1, 2) in obstacles
    assert plan["clear_cost"] == 10.0


def test_clearing_planned_cells_makes_path_executable():
    """把规划列出的待清障清掉后，执行用的 astar 必须能走通。"""
    grid = corner_grid()
    plan = build_plan(grid, (1, 1), (3, 3), 100.0, 0.2, 5.0, {1: 5.0}, "distance")
    for x, y in plan["obstacles"]:
        grid[y][x] = 0
    result = astar(grid, (1, 1), (3, 3))
    assert result["path"], "清完规划里的格子后，执行路径不应再被斜角挡住"


def test_clearing_only_one_corner_still_blocked_by_astar():
    """反证：只清一块，执行路径仍然不合法（说明必须两块都算进规划）。"""
    grid = corner_grid()
    grid[1][2] = 0  # 只清 (2,1)
    result = astar(grid, (1, 1), (2, 2))
    # 斜穿 (1,1)->(2,2) 需要 (2,1) 与 (1,2) 都为空，(1,2) 仍是石头
    assert all(
        not (path == [[1, 1], [2, 2]]) for path in [result["path"]]
    )

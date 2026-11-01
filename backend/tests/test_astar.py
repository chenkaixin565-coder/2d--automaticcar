"""
A* 算法单元测试模块。

模块功能：验证 Python 版 A* 的路径正确性、避障性、八邻域几何口径与返回
结构一致性。V2.3.0 新增：斜向代价 √2、禁止斜穿墙角、失败原因码。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import math

from app.algorithms.astar import astar, octile


def test_straight_line_path():
    """空旷地图上应返回直线路径，代价等于曼哈顿距离。"""
    grid = [[0] * 5 for _ in range(5)]
    result = astar(grid, (0, 0), (4, 0))
    assert result["path"][0] == [0, 0]
    assert result["path"][-1] == [4, 0]
    assert result["cost"] == 4
    assert len(result["path"]) == 5
    assert result["reachable"] is True
    assert result["error"] is None


def test_diagonal_shortcut_uses_octile_cost():
    """八邻域下对角目标应走斜线，代价为 2√2（而不是绕直角走 4 步）。"""
    grid = [[0] * 3 for _ in range(3)]
    result = astar(grid, (0, 0), (2, 2))
    assert result["path"] == [[0, 0], [1, 1], [2, 2]]
    assert math.isclose(result["cost"], 2 * math.sqrt(2), rel_tol=1e-9)


def test_four_neighbor_mode_keeps_manhattan_cost():
    """diagonal=False 时必须退化为四邻域直角路径，与旧版行为一致。"""
    grid = [[0] * 3 for _ in range(3)]
    result = astar(grid, (0, 0), (2, 2), diagonal=False)
    assert len(result["path"]) == 5
    assert result["cost"] == 4


def test_no_corner_cutting():
    """两个障碍呈对角夹缝时，不允许从缝隙"斜穿"过去。"""
    grid = [
        [0, 1, 0],
        [1, 0, 0],
        [0, 0, 0],
    ]
    # (0,0) 的正交邻居 (1,0)、(0,1) 都是障碍，只剩对角 (1,1)；
    # 允许斜穿墙角的实现会"挤"出去，禁止斜穿时该点实际被封死。
    result = astar(grid, (0, 0), (2, 2))
    assert result["path"] == []
    assert result["error"] == "unreachable"


def test_obstacle_avoidance():
    """中间有墙时应绕行且不穿过障碍。"""
    grid = [[0] * 3 for _ in range(3)]
    grid[0][1] = 1  # 在 (1,0) 放障碍，迫使绕行。
    result = astar(grid, (0, 0), (2, 0))
    assert result["path"], "应能找到绕行路径"
    for x, y in result["path"]:
        assert grid[y][x] == 0, "路径不得穿过障碍物"


def test_unreachable_returns_empty():
    """目标被墙完全包围时应返回空路径与 unreachable 原因码。"""
    grid = [[0] * 5 for _ in range(5)]
    grid[1][1] = 1
    grid[1][2] = 1
    grid[1][3] = 1
    grid[2][1] = 1
    grid[2][3] = 1
    grid[3][1] = 1
    grid[3][2] = 1
    grid[3][3] = 1
    result = astar(grid, (0, 0), (2, 2))
    assert result["path"] == []
    assert result["reachable"] is False
    assert result["error"] == "unreachable"


def test_start_or_goal_blocked():
    """起点或目标是障碍时应返回空路径并给出对应原因码。"""
    grid = [[0, 1], [0, 0]]
    blocked_goal = astar(grid, (0, 0), (1, 0))
    assert blocked_goal["path"] == []
    assert blocked_goal["error"] == "goal_blocked"
    blocked_start = astar(grid, (1, 0), (0, 0))
    assert blocked_start["path"] == []
    assert blocked_start["error"] == "start_blocked"


def test_out_of_bounds_reports_error():
    """越界坐标应返回 out_of_bounds，而不是抛 IndexError。"""
    grid = [[0] * 3 for _ in range(3)]
    assert astar(grid, (-1, 0), (2, 2))["error"] == "out_of_bounds"
    assert astar(grid, (0, 0), (3, 3))["error"] == "out_of_bounds"


def test_result_structure_matches_contract():
    """返回结构必须包含 path/visited_count/cost/reachable/error 五个字段。"""
    grid = [[0] * 4 for _ in range(4)]
    result = astar(grid, (0, 0), (3, 3))
    assert set(result.keys()) == {"path", "visited_count", "cost", "reachable", "error"}


def test_octile_is_admissible_on_empty_grid():
    """octile 距离应恰好等于空旷八邻域地图上的最优代价（既是下界也取得到）。"""
    grid = [[0] * 8 for _ in range(8)]
    for goal in ((7, 3), (2, 6), (5, 5)):
        result = astar(grid, (0, 0), goal)
        assert math.isclose(result["cost"], octile((0, 0), goal), rel_tol=1e-9)

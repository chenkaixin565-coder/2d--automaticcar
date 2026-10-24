"""
A* 算法单元测试模块。

模块功能：验证 Python 版 A* 的路径正确性、避障性与返回结构一致性。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from app.algorithms.astar import astar


def test_straight_line_path():
    """空旷地图上应返回直线路径，代价等于曼哈顿距离。"""
    grid = [[0] * 5 for _ in range(5)]
    result = astar(grid, (0, 0), (4, 0))
    assert result["path"][0] == [0, 0]
    assert result["path"][-1] == [4, 0]
    assert result["cost"] == 4
    assert len(result["path"]) == 5


def test_obstacle_avoidance():
    """中间有墙时应绕行且不穿过障碍。"""
    grid = [[0] * 3 for _ in range(3)]
    grid[0][1] = 1  # 在 (1,0) 放障碍，迫使绕行。
    result = astar(grid, (0, 0), (2, 0))
    assert result["path"], "应能找到绕行路径"
    for x, y in result["path"]:
        assert grid[y][x] == 0, "路径不得穿过障碍物"


def test_unreachable_returns_empty():
    """目标被墙完全包围时应返回空路径。"""
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


def test_start_or_goal_blocked():
    """起点或目标是障碍时应返回空路径。"""
    grid = [[0, 1], [0, 0]]
    assert astar(grid, (1, 0), (0, 0))["path"] == []
    assert astar(grid, (0, 0), (1, 0))["path"] == []


def test_result_structure_matches_contract():
    """返回结构必须包含 path/visited_count/cost 三个字段。"""
    grid = [[0] * 4 for _ in range(4)]
    result = astar(grid, (0, 0), (3, 3))
    assert set(result.keys()) == {"path", "visited_count", "cost"}

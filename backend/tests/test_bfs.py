"""
BFS 对照实现测试。

模块功能：验证 BFS 与 A* 在同一地图上的最优代价一致，并覆盖不可达、
起终点相同、障碍起点等边界。BFS 的价值是给 A* 提供独立基准，因此这里
重点断言"两者代价相等"，而不是比较实现细节。

作者：智能巡检机器人二维仿真系统 V2.2.1 开发组
日期：2026-10-27
版本：V2.2.1
"""

from app.algorithms.astar import astar
from app.algorithms.bfs import bfs


def _open_grid(size: int = 10) -> list[list[int]]:
    return [[0] * size for _ in range(size)]


def test_bfs_matches_astar_on_open_map():
    """空地：A* 与 BFS 代价一致，路径长度 = 代价 + 1。"""
    grid = _open_grid(10)
    a = astar(grid, (1, 1), (8, 8))
    b = bfs(grid, (1, 1), (8, 8))
    assert a["cost"] == b["cost"] == 14
    assert len(a["path"]) == len(b["path"]) == 15
    assert a["path"][0] == [1, 1] and a["path"][-1] == [8, 8]


def test_bfs_and_astar_agree_when_wall_forces_detour():
    """中间一堵墙只留一个缺口：两者都要绕行，代价一致；A* 扩展更少。"""
    grid = _open_grid(10)
    for y in range(1, 9):
        grid[y][5] = 1
    grid[5][5] = 0  # 缺口

    a = astar(grid, (1, 5), (8, 5))
    b = bfs(grid, (1, 5), (8, 5))
    assert a["cost"] == b["cost"] == 7
    assert a["path"] == b["path"]
    assert a["visited_count"] < b["visited_count"]


def test_bfs_unreachable_returns_empty():
    """目标被墙完全封死：两者都返回空路径。"""
    grid = _open_grid(8)
    # 加四周边界墙，再用一整列墙把右侧完全封死
    for i in range(8):
        grid[0][i] = grid[7][i] = 1
        grid[i][0] = grid[i][7] = 1
    for y in range(1, 7):
        grid[y][4] = 1
    assert astar(grid, (1, 1), (6, 6))["path"] == []
    assert bfs(grid, (1, 1), (6, 6))["path"] == []


def test_bfs_start_equals_goal():
    """起点即终点：单格路径、代价 0。"""
    result = bfs(_open_grid(5), (2, 2), (2, 2))
    assert result["path"] == [[2, 2]]
    assert result["cost"] == 0


def test_bfs_rejects_blocked_start_or_goal():
    """起点或终点落在障碍上：返回空路径，不抛异常。"""
    grid = _open_grid(5)
    grid[2][2] = 1
    assert bfs(grid, (2, 2), (3, 3))["path"] == []
    assert bfs(grid, (1, 1), (2, 2))["path"] == []

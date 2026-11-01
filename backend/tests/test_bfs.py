"""
BFS 对照实现单元测试模块。

模块功能：验证 BFS 与 A* 在同一张无权地图上的最优代价一致，同时确认
A* 的扩展节点数显著更少——这正是"启发式搜索比盲目搜索省"的实验依据。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import random

from app.algorithms.astar import astar
from app.algorithms.bfs import bfs


def test_bfs_straight_line():
    """空旷地图上 BFS 应返回与曼哈顿距离一致的步数。"""
    grid = [[0] * 6 for _ in range(4)]
    result = bfs(grid, (0, 0), (5, 0))
    assert result["path"][0] == [0, 0]
    assert result["path"][-1] == [5, 0]
    assert result["cost"] == 5
    assert result["reachable"] is True


def test_bfs_detours_around_wall():
    """遇到整列墙体时 BFS 应绕行且不穿墙。"""
    grid = [[0] * 5 for _ in range(5)]
    for y in range(4):
        grid[y][2] = 1
    result = bfs(grid, (0, 0), (4, 0))
    assert result["path"]
    for x, y in result["path"]:
        assert grid[y][x] == 0


def test_bfs_unreachable():
    """目标被完全围死时返回 unreachable。"""
    grid = [[0] * 5 for _ in range(5)]
    for y in range(1, 4):
        grid[y][1] = 1
        grid[y][3] = 1
    for x in range(1, 4):
        grid[1][x] = 1
        grid[3][x] = 1
    result = bfs(grid, (0, 0), (2, 2))
    assert result["path"] == []
    assert result["error"] == "unreachable"


def test_bfs_blocked_endpoints():
    """起点/终点为障碍时给出与 A* 相同的原因码。"""
    grid = [[0, 1], [0, 0]]
    assert bfs(grid, (0, 0), (1, 0))["error"] == "goal_blocked"
    assert bfs(grid, (1, 0), (0, 0))["error"] == "start_blocked"


def test_astar_expands_fewer_nodes_with_same_cost():
    """
    随机 40×40、20% 障碍地图上：
      - 可达样本里 A*（四邻域）与 BFS 的最优代价必须完全一致；
      - A* 的平均扩展节点数应明显少于 BFS。
    """
    rng = random.Random(20261030)
    grid = [[0] * 40 for _ in range(40)]
    for y in range(1, 39):
        for x in range(1, 39):
            if rng.random() < 0.2:
                grid[y][x] = 1

    astar_nodes = 0
    bfs_nodes = 0
    samples = 0
    for _ in range(20):
        start = (rng.randrange(1, 39), rng.randrange(1, 39))
        goal = (rng.randrange(1, 39), rng.randrange(1, 39))
        if grid[start[1]][start[0]] or grid[goal[1]][goal[0]]:
            continue
        a = astar(grid, start, goal, diagonal=False)
        b = bfs(grid, start, goal)
        if not a["path"] or not b["path"]:
            continue
        assert a["cost"] == b["cost"], "四邻域 A* 与 BFS 的最优代价必须一致"
        astar_nodes += a["visited_count"]
        bfs_nodes += b["visited_count"]
        samples += 1

    assert samples >= 10, "随机样本太少，说明地图或种子异常"
    assert astar_nodes < bfs_nodes, "A* 的扩展节点数应少于 BFS"

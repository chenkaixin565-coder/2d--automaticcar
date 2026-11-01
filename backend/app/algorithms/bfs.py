"""
BFS 宽度优先搜索模块（教学对照与测试基准）。

模块功能：在无权栅格图上按层扩展求最短步数路径，作为 A* 的对照实现，
用于课程中的"启发式搜索 vs 盲目搜索"实验，并作为 A* 最优性的断言基准。

与 A* 的区别：
  - BFS 没有启发函数，按"离起点远近"逐层铺开，四邻域均匀扩展；
  - 在单位步长图上 BFS 与 A* 的最优代价一致，但 A* 展开的节点通常少得多；
  - 本实现固定四邻域（图是无权图，斜向代价 √2 会破坏"无权"前提，
    因此不做八邻域版本，需要斜向时请用 astar(diagonal=True)）。

返回结构与 astar 完全一致：{path, visited_count, cost, reachable, error}。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

from collections import deque

from app.algorithms.astar import (
    ERROR_EMPTY_MAP,
    ERROR_GOAL_BLOCKED,
    ERROR_OUT_OF_BOUNDS,
    ERROR_START_BLOCKED,
    ERROR_UNREACHABLE,
    _result,
)

# 四邻域移动方向（dx, dy）。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def bfs(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    BFS 最短步数搜索。

    :param grid: 二维栅格数组，0=可通行，非 0=障碍。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: {path, visited_count, cost, reachable, error}。
    """
    height = len(grid)
    if height == 0 or not grid[0]:
        return _result([], 0, 0.0, ERROR_EMPTY_MAP)
    width = len(grid[0])

    if not (0 <= start[0] < width and 0 <= start[1] < height):
        return _result([], 0, 0.0, ERROR_OUT_OF_BOUNDS)
    if not (0 <= goal[0] < width and 0 <= goal[1] < height):
        return _result([], 0, 0.0, ERROR_OUT_OF_BOUNDS)

    def is_free(x: int, y: int) -> bool:
        """判断坐标是否在地图内且可通行。"""
        return 0 <= x < width and 0 <= y < height and grid[y][x] == 0

    if not is_free(*start):
        return _result([], 0, 0.0, ERROR_START_BLOCKED)
    if not is_free(*goal):
        return _result([], 0, 0.0, ERROR_GOAL_BLOCKED)

    queue: deque = deque([start])
    visited: set = {start}
    came_from: dict = {}
    visited_count = 0

    while queue:
        current = queue.popleft()
        visited_count += 1

        if current == goal:
            path = [list(current)]
            while current in came_from:
                current = came_from[current]
                path.append(list(current))
            path.reverse()
            return _result(path, visited_count, float(len(path) - 1), None)

        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in visited or not is_free(*neighbor):
                continue
            visited.add(neighbor)
            came_from[neighbor] = current
            queue.append(neighbor)

    return _result([], visited_count, 0.0, ERROR_UNREACHABLE)

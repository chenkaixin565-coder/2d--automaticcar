"""
BFS 路径规划对照实现。

模块功能：在二维栅格地图上用广度优先搜索求最短路径，作为 A* 的对照基线。
两者函数签名与返回结构完全一致（path / visited_count / cost），便于在同一批
随机地图上做"扩展节点数、最优代价、耗时"的对比实验。

为什么需要它：
  - A* 的正确性需要独立参照物。BFS 在无权图上保证最短步数，可直接校验 A* 的 cost；
  - 课程与答辩考点是"启发式搜索相对盲目搜索省了多少扩展"，没有 BFS 就没有对照；
  - 文档 docs/algorithm.md 的对比表由 tools/benchmark_paths.py 实测生成，不手填。

作者：智能巡检机器人二维仿真系统 V2.2.1 开发组
日期：2026-10-27
版本：V2.2.1
"""

from collections import deque

# 四邻域移动方向（dx, dy），与 A* 实现保持一致，避免对角穿墙。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def bfs(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    广度优先搜索（无权图最短路）。

    :param grid: 二维栅格数组，0=可通行，非 0=障碍（与 A* 的判定一致）。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: {'path': [[x, y], ...], 'visited_count': int, 'cost': int}
             cost 为步数；不可达时 path 为空、cost 为 0。
    """
    height = len(grid)
    if height == 0:
        return {"path": [], "visited_count": 0, "cost": 0}
    width = len(grid[0])

    def is_free(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and grid[y][x] == 0

    if not is_free(*start) or not is_free(*goal):
        return {"path": [], "visited_count": 0, "cost": 0}

    if start == goal:
        return {"path": [list(start)], "visited_count": 1, "cost": 0}

    queue: deque[tuple[int, int]] = deque([start])
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    seen = {start}
    visited_count = 0

    while queue:
        current = queue.popleft()
        visited_count += 1

        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in seen or not is_free(*neighbor):
                continue
            seen.add(neighbor)
            came_from[neighbor] = current

            if neighbor == goal:
                path = [list(neighbor)]
                node = neighbor
                while node in came_from:
                    node = came_from[node]
                    path.append(list(node))
                path.reverse()
                return {"path": path, "visited_count": visited_count, "cost": len(path) - 1}

            queue.append(neighbor)

    # 队列耗尽仍未到达：不可达。
    return {"path": [], "visited_count": visited_count, "cost": 0}

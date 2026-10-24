"""
A* 路径规划算法模块（Python 实现）。

模块功能：在二维栅格地图上，使用 A* 算法从起点搜索到目标点的最短
无障碍路径。采用曼哈顿距离作为启发函数，四邻域移动，避免对角穿墙。
函数签名与返回结构与前端临时实现（src/services/astar.js）保持一致，
便于下一阶段平滑迁移、前后端互验。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import heapq

# 四邻域移动方向（dx, dy）。禁止对角移动，避免“斜穿障碍缝隙”的几何问题。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """
    曼哈顿距离启发函数。

    :param a: 起点坐标 (x, y)。
    :param b: 目标坐标 (x, y)。
    :return: 两坐标的曼哈顿距离。
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _reconstruct_path(
    came_from: dict,
    current: tuple[int, int],
    start: tuple[int, int],
) -> list[list[int]]:
    """
    从搜索结果回溯出完整路径。

    :param came_from: 节点前驱映射表。
    :param current: 终点坐标。
    :param start: 起点坐标。
    :return: 从起点到终点的坐标列表 [[x, y], ...]。
    """
    path = [list(current)]
    while current in came_from:
        current = came_from[current]
        path.append(list(current))
    path.reverse()  # 回溯得到的是终点→起点，反转成起点→终点。
    return path


def astar(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    A* 路径搜索主函数。

    参数与返回结构刻意与前端 astar.js 保持一致：
    返回 {path: [[x,y],...], visited_count: int, cost: int}。

    :param grid: 二维栅格数组，0=可通行，1=障碍物。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: 包含路径、访问节点数与路径代价的字典。
    """
    height = len(grid)
    if height == 0:
        return {"path": [], "visited_count": 0, "cost": 0}
    width = len(grid[0])

    # 边界与障碍校验：起点、终点必须可通行。
    def is_free(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and grid[y][x] == 0

    if not is_free(*start) or not is_free(*goal):
        return {"path": [], "visited_count": 0, "cost": 0}

    # open_set 用最小堆维护 (f_score, 计数, 节点)，计数用于稳定排序避免 tie-breaking 报错。
    open_heap: list = []
    counter = 0
    heapq.heappush(open_heap, (0, counter, start))

    came_from: dict = {}
    g_score: dict = {start: 0}
    visited_count = 0

    while open_heap:
        _f, _c, current = heapq.heappop(open_heap)
        visited_count += 1

        # 到达目标，回溯路径。
        if current == goal:
            return {
                "path": _reconstruct_path(came_from, current, start),
                "visited_count": visited_count,
                "cost": g_score[current],
            }

        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if not is_free(*neighbor):
                continue
            tentative_g = g_score[current] + 1
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + _manhattan(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (f_score, counter, neighbor))

    # 堆耗尽仍未到达目标，说明目标不可达。
    return {"path": [], "visited_count": visited_count, "cost": 0}

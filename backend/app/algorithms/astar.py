"""
A* 路径规划算法模块（Python 实现）。

模块功能：在二维栅格地图上，使用 A* 算法从起点搜索到目标点的最短路
径。V2.3.0 起支持四邻域与八邻域两种移动模式：
  - 四邻域：曼哈顿距离启发，一步代价 1；
  - 八邻域：octile 距离启发，直行一步代价 1、斜行一步代价 √2，
    并禁止"斜穿墙角"（斜向移动要求两个相邻正交格都可通行），
    因此路径仍是可被机器人逐格执行的合法路径。
两种模式都用 heapq 维护开放列表，并以 h 值做 tie-breaking，使同代价
路径优先朝目标方向展开，路径更直、更自然。

函数签名与返回结构与前端实现（src/services/astar.js）保持一致：
{path, visited_count, cost, reachable, error}。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import heapq
import math

# 四邻域移动方向（dx, dy）。
_NEIGHBORS_4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]

# 八邻域：四方向 + 四个对角方向。
_NEIGHBORS_8 = _NEIGHBORS_4 + [(-1, -1), (1, -1), (-1, 1), (1, 1)]

# 斜向一步的几何长度（欧氏距离）。直行记 1，斜行记 √2，与路径长度单位一致。
SQRT2 = math.sqrt(2)

# 错误码：供前端与上层调用方区分失败原因，避免只拿到一个空列表。
ERROR_START_BLOCKED = "start_blocked"
ERROR_GOAL_BLOCKED = "goal_blocked"
ERROR_OUT_OF_BOUNDS = "out_of_bounds"
ERROR_EMPTY_MAP = "empty_map"
ERROR_UNREACHABLE = "unreachable"


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> float:
    """
    曼哈顿距离启发函数（四邻域使用）。

    :param a: 起点坐标 (x, y)。
    :param b: 目标坐标 (x, y)。
    :return: 两坐标的曼哈顿距离。
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def octile(a: tuple[int, int], b: tuple[int, int]) -> float:
    """
    octile（对角）距离启发函数（八邻域使用）。

    公式：h = max(dx, dy) + (√2 - 1) · min(dx, dy)。
    含义是"先沿对角走到只剩一个坐标差，再沿直线走完"的最短几何长度，
    与八邻域的真实代价完全相等，因此既不高估（可采纳），也满足一致性。

    :param a: 起点坐标 (x, y)。
    :param b: 目标坐标 (x, y)。
    :return: 两坐标的 octile 距离。
    """
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return (dx + dy) + (SQRT2 - 2) * min(dx, dy)


def _result(path: list[list[int]], visited_count: int, cost: float, error: str | None) -> dict:
    """
    统一构造返回字典，保证前端拿到的字段永远齐全。

    :param path: 路径坐标列表（失败时为空列表）。
    :param visited_count: 展开节点数。
    :param cost: 路径总代价（失败时为 0）。
    :param error: 失败原因码，成功时为 None。
    :return: 结果字典。
    """
    return {
        "path": path,
        "visited_count": visited_count,
        "cost": float(cost),
        "reachable": error is None,
        "error": error,
    }


def _reconstruct_path(
    came_from: dict,
    current: tuple[int, int],
) -> list[list[int]]:
    """
    从搜索结果回溯出完整路径。

    :param came_from: 节点前驱映射表。
    :param current: 终点坐标。
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
    diagonal: bool = True,
) -> dict:
    """
    A* 路径搜索主函数。

    :param grid: 二维栅格数组，0=可通行，非 0=障碍。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :param diagonal: True 使用八邻域 + octile 启发，False 使用四邻域 + 曼哈顿启发。
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

    # 选择邻居集合与启发函数。
    neighbors = _NEIGHBORS_8 if diagonal else _NEIGHBORS_4
    heuristic = octile if diagonal else manhattan

    # 开放列表元素：(f, h, 自增计数, x, y)。
    # 第二键 h 即 tie-breaking：f 相同时优先展开离目标更近的节点，路径更直。
    open_heap: list = []
    counter = 0

    start_h = heuristic(start, goal)
    heapq.heappush(open_heap, (start_h, start_h, counter, start[0], start[1]))

    came_from: dict = {}
    g_score: dict = {start: 0.0}
    closed: set = set()
    visited_count = 0

    while open_heap:
        _f, _h, _c, cx, cy = heapq.heappop(open_heap)
        current = (cx, cy)
        if current in closed:
            continue
        closed.add(current)
        visited_count += 1

        # 到达目标，回溯路径。
        if current == goal:
            return _result(_reconstruct_path(came_from, current), visited_count, g_score[current], None)

        for dx, dy in neighbors:
            neighbor = (current[0] + dx, current[1] + dy)
            if not is_free(*neighbor) or neighbor in closed:
                continue
            if dx != 0 and dy != 0:
                # 禁止斜穿墙角：斜向移动要求两个相邻正交格都可通行，
                # 否则机器人会被想象成从两个障碍的缝隙里"挤"过去。
                if not is_free(current[0] + dx, current[1]) or not is_free(current[0], current[1] + dy):
                    continue
                step_cost = SQRT2
            else:
                step_cost = 1.0

            tentative_g = g_score[current] + step_cost
            if neighbor in g_score and tentative_g >= g_score[neighbor] - 1e-12:
                continue
            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            h = heuristic(neighbor, goal)
            counter += 1
            heapq.heappush(open_heap, (tentative_g + h, h, counter, neighbor[0], neighbor[1]))

    # 堆耗尽仍未到达目标，说明目标不可达。
    return _result([], visited_count, 0.0, ERROR_UNREACHABLE)

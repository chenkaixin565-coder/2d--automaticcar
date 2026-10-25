"""
路线规划模块。

模块功能：为“一键规划路线”提供穿障 A* 与电力预算计算。与普通 A*
（app.algorithms.astar）的区别：规划出的路线是理论最短路径——普通障碍
格视为“可通行但需要清除”，只有最外环边界墙不可穿越；随后按移动耗电与
清障耗电（每处障碍）计算总预算，在电量不足时截断为“可清除前 k 个”。
作者：智能巡检机器人二维仿真系统 V1.2 开发组
日期：2026-10-25
版本：V1.2
"""

import heapq

from app.core.constants import CELL_OBSTACLE

# 四邻域移动方向（dx, dy），与 astar 保持一致。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """曼哈顿距离启发函数。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def plan_route(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    计算起点到目标点的“理论最短路径”（可穿越普通障碍，边界墙不可穿越）。

    :param grid: 二维栅格数组，0=可通行，1=障碍物。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: {'path': [[x, y], ...], 'obstacles_on_path': [[x, y], ...]}，
             路径不可规划时 path 为空列表。
    """
    height = len(grid)
    width = len(grid[0]) if height else 0

    # 边界墙不可穿越；内部格（含普通障碍）均可通行。
    def passable(x: int, y: int) -> bool:
        return 0 < x < width - 1 and 0 < y < height - 1

    if not passable(*start) or not passable(*goal):
        return {"path": [], "obstacles_on_path": []}

    open_heap: list = []
    counter = 0
    heapq.heappush(open_heap, (0, counter, start))
    came_from: dict = {}
    g_score: dict = {start: 0}

    while open_heap:
        _f, _c, current = heapq.heappop(open_heap)
        if current == goal:
            path = [list(current)]
            while current in came_from:
                current = came_from[current]
                path.append(list(current))
            path.reverse()
            obstacles = [cell for cell in path if grid[cell[1]][cell[0]] == CELL_OBSTACLE]
            return {"path": path, "obstacles_on_path": obstacles}
        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if not passable(*neighbor):
                continue
            tentative_g = g_score[current] + 1
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                counter += 1
                heapq.heappush(open_heap, (tentative_g + _manhattan(neighbor, goal), counter, neighbor))

    # 内部区域被完全封死（理论上不会发生，边界墙保证连通）。
    return {"path": [], "obstacles_on_path": []}


def build_plan(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    battery: float,
    move_cost: float,
    clear_cost: float,
) -> dict:
    """
    规划路线并按电力预算决定可清除的障碍个数。

    预算模型：总耗电 = 移动格数 × move_cost + 待清障数 × clear_cost。
    电量充足时全部纳入；仅够移动时按剩余电量截断为前 k 个；连移动都不够时
    标记为不可到达。

    :param grid: 二维栅格数组。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :param battery: 当前电量百分比。
    :param move_cost: 每移动一格耗电百分比。
    :param clear_cost: 每清除一处障碍耗电百分比。
    :return: 路线规划字典（字段与前端 routePlanner.js 逐字段一致）。
    """
    result = plan_route(grid, start, goal)
    base = {
        "goal": list(goal),
        "path": [],
        "obstacles": [],
        "clearable": [],
        "move_cost": 0.0,
        "clear_cost": 0.0,
        "total_cost": 0.0,
        "battery": battery,
        "clear_unit_cost": clear_cost,
        "reachable": False,
        "enough": False,
        "message": "无法规划路线：目标不可达",
    }
    if not result["path"]:
        return base

    path = result["path"]
    obstacles = result["obstacles_on_path"]
    move_cost_total = round((len(path) - 1) * move_cost, 2)
    total_cost = round(move_cost_total + len(obstacles) * clear_cost, 2)

    if battery + 1e-9 >= total_cost:
        clearable = list(obstacles)
        enough = True
        reachable = True
    elif battery + 1e-9 >= move_cost_total:
        affordable = int((battery - move_cost_total + 1e-9) // clear_cost) if clear_cost > 0 else len(obstacles)
        clearable = obstacles[:affordable]
        enough = False
        reachable = True
    else:
        clearable = []
        enough = False
        reachable = False

    return {
        "goal": list(goal),
        "path": path,
        "obstacles": obstacles,
        "clearable": clearable,
        "move_cost": move_cost_total,
        "clear_cost": round(len(clearable) * clear_cost, 2),
        "total_cost": total_cost,
        "battery": battery,
        "clear_unit_cost": clear_cost,
        "reachable": reachable,
        "enough": enough,
        "message": "",
    }

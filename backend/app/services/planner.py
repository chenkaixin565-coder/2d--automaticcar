"""
路线规划模块。

模块功能：为"一键规划路线"提供穿障 A* 与电力预算计算。与普通 A*
（app.algorithms.astar）的区别：规划出的路线是理论最短路径——普通障碍
格视为"可通行但需要清除"，只有最外环边界墙不可穿越；随后按移动耗电与
清障耗电（每处障碍）计算总预算，在电量不足时截断为"可清除前 k 个"。

V2.3.0 变更：与主 A* 同步升级为八邻域（octile 启发、斜向代价 √2、禁止
斜穿墙角），使"规划预览"与"实际执行"使用同一套几何口径。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import heapq

from app.algorithms.astar import SQRT2, octile
from app.core.constants import CELL_BARRIER, CELL_OBSTACLE

# 八邻域移动方向（dx, dy），与 astar 保持一致。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]


def plan_route(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    计算起点到目标点的"理论最短路径"（可穿越普通障碍，边界墙不可穿越）。

    :param grid: 二维栅格数组，0=可通行，1=障碍物，2=固定屏障。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: {'path': [[x, y], ...], 'obstacles_on_path': [[x, y], ...], 'cost': float}，
             路径不可规划时 path 为空列表。
    """
    height = len(grid)
    width = len(grid[0]) if height else 0

    # 边界墙与固定屏障不可穿越；普通障碍视为"可通行但需清除"。
    def passable(x: int, y: int) -> bool:
        if not (0 < x < width - 1 and 0 < y < height - 1):
            return False
        return grid[y][x] != CELL_BARRIER

    if not passable(*start) or not passable(*goal):
        return {"path": [], "obstacles_on_path": [], "cost": 0.0}

    open_heap: list = []
    counter = 0
    start_h = octile(start, goal)
    heapq.heappush(open_heap, (start_h, start_h, counter, start[0], start[1]))
    came_from: dict = {}
    g_score: dict = {start: 0.0}
    closed: set = set()

    while open_heap:
        _f, _h, _c, cx, cy = heapq.heappop(open_heap)
        current = (cx, cy)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path = [list(current)]
            while current in came_from:
                current = came_from[current]
                path.append(list(current))
            path.reverse()
            obstacles = [cell for cell in path if grid[cell[1]][cell[0]] == CELL_OBSTACLE]
            return {"path": path, "obstacles_on_path": obstacles, "cost": round(g_score[goal], 4)}
        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if not passable(*neighbor) or neighbor in closed:
                continue
            if dx != 0 and dy != 0:
                # 与 astar 同规则：不允许斜穿墙角（两侧正交格必须都可通行）。
                if not passable(current[0] + dx, current[1]) or not passable(current[0], current[1] + dy):
                    continue
                step_cost = SQRT2
            else:
                step_cost = 1.0
            tentative_g = g_score[current] + step_cost
            if neighbor in g_score and tentative_g >= g_score[neighbor] - 1e-12:
                continue
            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            h = octile(neighbor, goal)
            counter += 1
            heapq.heappush(open_heap, (tentative_g + h, h, counter, neighbor[0], neighbor[1]))

    # 内部区域被完全封死（理论上不会发生，边界墙保证连通）。
    return {"path": [], "obstacles_on_path": [], "cost": 0.0}


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

    预算模型：总耗电 = 路径几何长度 × move_cost + 待清障数 × clear_cost。
    其中几何长度直行计 1、斜行计 √2，与仿真引擎的逐步扣电口径一致。
    电量充足时全部纳入；仅够移动时按剩余电量截断为前 k 个；连移动都不够时
    标记为不可到达。

    :param grid: 二维栅格数组。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :param battery: 当前电量百分比。
    :param move_cost: 每移动一格耗电百分比（斜向按 √2 格折算）。
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
    move_cost_total = round(result["cost"] * move_cost, 2)
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

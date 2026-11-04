"""
路线规划模块。

模块功能：为"一键规划路线"提供穿障 A* 与电力预算计算。与普通 A*
（app.algorithms.astar）的区别：规划出的路线是理论最短路径——可清除的
障碍格（石头/沙子/金刚石）视为"可通行但需要清除"，只有最外环边界墙与
固定屏障不可穿越；随后按移动耗电与各材质清障耗电计算总预算，电量不足
时按路径顺序截断。

V2.3.0 变更：与主 A* 同步升级为八邻域（octile 启发、斜向代价 √2、禁止
斜穿墙角），使"规划预览"与"实际执行"使用同一套几何口径。
V2.4.0 变更：障碍引入材质（1=石头 5%、3=沙子 2%、4=金刚石 20%），
预算按每格材质累加，不再"所有障碍一个价"。
作者：智能巡检机器人二维仿真系统 V2.4.0 开发组
日期：2026-11-04
版本：V2.4.0
"""

import heapq

from app.algorithms.astar import SQRT2, octile
from app.core.constants import CELL_BARRIER, CLEARABLE_CELLS

# 八邻域移动方向（dx, dy），与 astar 保持一致。
_NEIGHBORS = [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]


def plan_route(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> dict:
    """
    计算起点到目标点的"理论最短路径"（可穿越可清除障碍，边界墙/屏障不可穿越）。

    :param grid: 二维栅格数组，0=可通行，1/3/4=可清除障碍，2=固定屏障。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :return: {'path': [[x, y], ...], 'obstacles_on_path': [[x, y], ...], 'cost': float}，
             路径不可规划时 path 为空列表。
    """
    height = len(grid)
    width = len(grid[0]) if height else 0

    # 边界墙与固定屏障不可穿越；石头/沙子/金刚石视为"可通行但需清除"。
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
            obstacles = [cell for cell in path if grid[cell[1]][cell[0]] in CLEARABLE_CELLS]
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
    material_costs: dict | None = None,
) -> dict:
    """
    规划路线并按电力预算决定可清除的障碍。

    预算模型：总耗电 = 路径几何长度 × move_cost + Σ 每格材质的清障耗电。
    材质成本来自 `shared/simulation-rules.json`，缺省时退回统一的 clear_cost。
    电量充足时全部纳入；仅够移动时按路径顺序尽量多清；连移动都不够时不可到达。

    :param grid: 二维栅格数组。
    :param start: 起点坐标 (x, y)。
    :param goal: 目标坐标 (x, y)。
    :param battery: 当前电量百分比。
    :param move_cost: 每移动一格耗电百分比（斜向按 √2 格折算）。
    :param clear_cost: 未登记材质的兜底清障耗电。
    :param material_costs: {格子值: 单处耗电}，例如 {1: 5.0, 3: 2.0, 4: 20.0}。
    :return: 路线规划字典（字段与前端 routePlanner.js 逐字段一致）。
    """
    costs = material_costs or {}
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
        # V2.3.1：不可达时由 engine 填入"拆这一格能通"的建议坐标。
        "suggestion": None,
    }
    if not result["path"]:
        return base

    path = result["path"]
    obstacles = result["obstacles_on_path"]
    # 每格按材质计价
    per_cell = [float(costs.get(grid[y][x], clear_cost)) for x, y in obstacles]
    move_cost_total = round(result["cost"] * move_cost, 2)
    full_clear_cost = round(sum(per_cell), 2)
    total_cost = round(move_cost_total + full_clear_cost, 2)

    if battery + 1e-9 >= total_cost:
        clearable = list(obstacles)
        clearable_cost = full_clear_cost
        enough = True
        reachable = True
    elif battery + 1e-9 >= move_cost_total:
        # 按路径顺序累加，直到预算不够为止
        budget = battery - move_cost_total
        clearable = []
        clearable_cost = 0.0
        for cell, cost in zip(obstacles, per_cell):
            if clearable_cost + cost > budget + 1e-9:
                break
            clearable.append(cell)
            clearable_cost += cost
        clearable_cost = round(clearable_cost, 2)
        enough = False
        reachable = True
    else:
        clearable = []
        clearable_cost = 0.0
        enough = False
        reachable = False

    return {
        "goal": list(goal),
        "path": path,
        "obstacles": obstacles,
        "clearable": clearable,
        "move_cost": move_cost_total,
        "clear_cost": clearable_cost,
        "total_cost": total_cost,
        "battery": battery,
        "clear_unit_cost": clear_cost,
        "reachable": reachable,
        "enough": enough,
        "message": "",
    }

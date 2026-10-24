"""
巡检任务管理模块。

模块功能：管理多巡检点自动巡检任务。采用最近邻贪心算法对巡检点排序，
逐段调用 A* 生成路径；当某个巡检点不可达时记录告警并跳过，同时支持
"排除最小障碍"重试策略（配合前端的一键排障功能）。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from app.algorithms.astar import astar
from app.core.constants import CELL_OBSTACLE


def order_goals_by_nearest(
    start: tuple[int, int],
    goals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """
    最近邻贪心排序：每次从剩余巡检点中选取离当前位置最近的点。

    :param start: 起始位置 (x, y)。
    :param goals: 巡检点列表。
    :return: 排序后的巡检点列表。
    """
    remaining = list(goals)
    ordered: list[tuple[int, int]] = []
    current = start
    while remaining:
        nearest = min(
            remaining,
            key=lambda goal: abs(goal[0] - current[0]) + abs(goal[1] - current[1]),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest
    return ordered


def find_min_obstacle_to_remove(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> tuple[int, int] | None:
    """
    在起点到目标点之间寻找"最小代价"的可拆除障碍物。

    策略：对所有障碍格子逐一试拆，拆掉后运行 A*，选择使路径代价最小的
    障碍格；若无任何单格拆除可使目标可达，返回 None。

    :param grid: 当前栅格地图。
    :param start: 起点坐标。
    :param goal: 目标巡检点坐标。
    :return: 建议拆除的障碍坐标 (x, y)，无解时为 None。
    """
    height = len(grid)
    width = len(grid[0]) if height else 0
    best_cell: tuple[int, int] | None = None
    best_cost = float("inf")

    for y in range(height):
        for x in range(width):
            if grid[y][x] != CELL_OBSTACLE:
                continue
            # 真正的边界：最外环边界墙不可拆除，直接跳过
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                continue
            # 临时拆除该障碍并试算路径。
            grid[y][x] = 0
            result = astar(grid, start, goal)
            grid[y][x] = CELL_OBSTACLE  # 还原，试拆不改原图。
            if result["path"] and result["cost"] < best_cost:
                best_cost = result["cost"]
                best_cell = (x, y)
    return best_cell


class PatrolManager:
    """巡检任务状态机。"""

    def __init__(self) -> None:
        """初始化为空闲状态。"""
        self.running: bool = False
        self.goals: list[tuple[int, int]] = []
        self.current_index: int = 0
        self.completed: int = 0
        self.path_remain: int = 0

    def start(self, goals: list[tuple[int, int]]) -> None:
        """
        启动巡检任务。

        :param goals: 已排序的巡检点列表。
        """
        self.running = True
        self.goals = goals
        self.current_index = 0
        self.completed = 0
        self.path_remain = 0

    def stop(self) -> None:
        """停止巡检任务并清空状态。"""
        self.running = False
        self.goals = []
        self.current_index = 0
        self.completed = 0
        self.path_remain = 0

    def current_goal(self) -> tuple[int, int] | None:
        """
        获取当前目标巡检点。

        :return: 目标坐标，任务已完成时为 None。
        """
        if not self.running or self.current_index >= len(self.goals):
            return None
        return self.goals[self.current_index]

    def advance(self) -> None:
        """完成当前巡检点，推进到下一个。"""
        self.completed += 1
        self.current_index += 1
        self.path_remain = 0

    @property
    def progress(self) -> float:
        """巡检完成进度（0~1）。"""
        if not self.goals:
            return 0.0
        return round(self.completed / len(self.goals), 2)

    def status_dict(self) -> dict:
        """
        导出与公共契约一致的巡检状态字典。

        :return: {'running', 'current_goal', 'progress', 'path_remain'}
        """
        goal = self.current_goal()
        return {
            "running": self.running,
            "current_goal": list(goal) if goal else None,
            "progress": self.progress,
            "path_remain": self.path_remain,
        }

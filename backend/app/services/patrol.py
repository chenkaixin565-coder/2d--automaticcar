"""
巡检任务管理模块。

模块功能：管理多巡检点自动巡检任务。采用最近邻贪心算法对巡检点排序，
逐段调用 A* 生成路径；当某个巡检点不可达或遇阻时记录告警并跳过/暂停，
配合引擎的"清障后继续"与"待清障记录"逻辑。

V2.0 变更：
  - progress 统一为 0~1 比例（原先后端 0~1、前端 0~100，接后端时进度条永远 ~0%）；
  - 新增 finish()：巡检自然结束时保留 completed/total，不再把进度清零；
  - 新增 pause/resume 与 pending 记录所需的辅助状态。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
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
            # 临时拆除该障碍并试算路径；异常时确保原图被还原。
            grid[y][x] = 0
            try:
                result = astar(grid, start, goal)
            finally:
                grid[y][x] = CELL_OBSTACLE
            if result["path"] and result["cost"] < best_cost:
                best_cost = result["cost"]
                best_cell = (x, y)
    return best_cell


class PatrolManager:
    """巡检任务状态机。"""

    def __init__(self) -> None:
        """初始化为空闲状态。"""
        self.running: bool = False
        self.paused: bool = False
        self.goals: list[tuple[int, int]] = []
        self.current_index: int = 0
        self.completed: int = 0
        self.total: int = 0
        self.path_remain: int = 0
        # 巡检受阻且无法绕行时，前方待清障障碍格 [x, y]；无阻碍为 None。
        self.blocked_by: list[int] | None = None

    def start(self, goals: list[tuple[int, int]]) -> None:
        """
        启动巡检任务。

        :param goals: 已排序的巡检点列表。
        """
        self.running = True
        self.paused = False
        self.goals = list(goals)
        self.current_index = 0
        self.completed = 0
        self.total = len(goals)
        self.path_remain = 0
        self.blocked_by = None

    def stop(self) -> None:
        """停止巡检任务并清空全部状态（用于"停止巡检"与新建地图）。"""
        self.running = False
        self.paused = False
        self.goals = []
        self.current_index = 0
        self.completed = 0
        self.total = 0
        self.path_remain = 0
        self.blocked_by = None

    def finish(self) -> None:
        """
        巡检自然结束：停止任务但保留 completed/total，使进度停在 100%。

        V2.0 新增。原实现直接 stop() 会把 completed 清零，用户刚跑完就看到
        进度从 100% 掉回 0%，与直觉相反。
        """
        self.running = False
        self.paused = False
        self.completed = self.total
        self.path_remain = 0
        self.blocked_by = None

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
        """巡检完成进度（0~1，与前端展示层约定一致）。"""
        if self.total <= 0:
            return 0.0
        return round(min(1.0, self.completed / self.total), 3)

    def status_dict(self) -> dict:
        """
        导出与公共契约一致的巡检状态字典。

        :return: {'running', 'paused', 'current_goal', 'progress',
                  'completed', 'total', 'path_remain', 'blocked_by'}
        """
        goal = self.current_goal()
        return {
            "running": self.running,
            "paused": self.paused,
            "current_goal": list(goal) if goal else None,
            "progress": self.progress,
            "completed": self.completed,
            "total": self.total,
            "path_remain": self.path_remain,
            "blocked_by": list(self.blocked_by) if self.blocked_by else None,
        }

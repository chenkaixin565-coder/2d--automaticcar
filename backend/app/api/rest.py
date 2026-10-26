"""
REST 路由模块。

模块功能：实现公共契约规定的全部 REST 接口。路由只做参数解析与响应
封装，业务逻辑一律委托给仿真引擎，保证职责单一。

V2.0 变更：
  - 路由表改为每次调用新建，避免多次 create_rest_router 时重复注册；
  - GET /path 改用正则校验坐标参数，非法输入返回 422 而不是 500；
  - 新增新建地图、巡检遇阻决策、待清障记录、重新开始（保留尾迹）等接口。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.models.map import GridMap
from app.models.robot import (
    ClearObstacleCommand,
    MoveCommand,
    NewMapCommand,
    PatrolDecisionCommand,
    PatrolStartCommand,
    PlanGoalCommand,
)
from app.services.simulation_engine import SimulationEngine

logger = logging.getLogger("api.rest")


def create_rest_router(engine: SimulationEngine) -> APIRouter:
    """
    构建并返回挂载了仿真引擎的 REST 路由。

    :param engine: 全局仿真引擎实例。
    :return: 配置完成的 APIRouter。
    """
    router = APIRouter(prefix="/api/v1")

    @router.get("/map", summary="获取当前地图")
    async def get_map() -> dict:
        """返回当前栅格地图，字段与契约一致。"""
        return engine.get_map()

    @router.put("/map", summary="更新地图")
    async def put_map(new_map: GridMap) -> dict:
        """
        接收前端编辑后的地图并保存（尺寸与坐标非法时返回 422）。

        :param new_map: 新地图数据。
        :return: 保存后的地图字典。
        """
        return engine.update_map(new_map)

    @router.post("/map/new", summary="新建空白地图")
    async def post_new_map(command: NewMapCommand) -> dict:
        """
        新建一张空白地图（仅保留四周边界墙）。

        :param command: {'width': int, 'height': int}。
        :return: 新地图字典。
        """
        return engine.new_map(command.width, command.height)

    @router.post("/robot/move", summary="手动控制机器人移动")
    async def robot_move(command: MoveCommand) -> dict:
        """
        单步移动机器人（会中断自动巡检）。

        :param command: {'dx': -1/0/1, 'dy': -1/0/1}
        :return: 移动后的 state 帧数据。
        """
        return engine.move(command.dx, command.dy)

    @router.post("/robot/reset", summary="机器人复位（可选保留尾迹）")
    async def robot_reset(keep_trail: bool = Query(False, description="true=重新开始并保留尾迹")) -> dict:
        """
        复位机器人到起点。

        :param keep_trail: True 时保留已走过的尾迹（"重新开始"）。
        :return: 通知帧。
        """
        engine.reset(keep_trail=keep_trail)
        message = "机器人已重新开始，保留历史尾迹" if keep_trail else "机器人已复位到起点"
        return {"type": "notice", "data": {"message": message}}

    @router.post("/robot/resolve", summary="一键排障")
    async def robot_resolve() -> dict:
        """机器人被障碍卡住时，清除前方障碍并恢复正常控制。"""
        return engine.resolve_fault()

    @router.get("/path", summary="A* 寻路调试接口")
    async def compute_path(
        start: str = Query(..., pattern=r"^-?\d+,-?\d+$", description="起点坐标，格式 x,y"),
        goal: str = Query(..., pattern=r"^-?\d+,-?\d+$", description="目标坐标，格式 x,y"),
    ) -> dict:
        """
        计算起点到目标点的 A* 路径。

        :param start: 'x,y' 字符串。
        :param goal: 'x,y' 字符串。
        :return: {'path', 'visited_count', 'cost'}
        """
        start_xy = [int(v) for v in start.split(",")]
        goal_xy = [int(v) for v in goal.split(",")]
        return engine.compute_path(start_xy, goal_xy)

    @router.post("/patrol/start", summary="开始自动巡检")
    async def patrol_start(command: Optional[PatrolStartCommand] = None) -> dict:
        """
        启动巡检任务，goals 缺省时使用地图巡检点。

        :param command: {'goals': [[x, y], ...] | null}
        :return: 巡检状态字典。
        """
        goals = command.goals if command else None
        return engine.start_patrol(goals)

    @router.post("/patrol/stop", summary="停止自动巡检")
    async def patrol_stop() -> dict:
        """停止巡检任务。"""
        return engine.stop_patrol()

    @router.post("/patrol/decision", summary="巡检遇阻决策")
    async def patrol_decision(command: PatrolDecisionCommand) -> dict:
        """
        巡检停在障碍前一格后，对当前阻碍做出决策。

        :param command: {'action': 'clear' | 'skip' | 'stop'}
        :return: state 数据 + 权威地图。
        """
        return engine.patrol_decision(command.action)

    @router.get("/patrol/status", summary="查询巡检状态")
    async def patrol_status() -> dict:
        """返回巡检进度信息。"""
        return engine.get_patrol_status()

    @router.get("/sensors/latest", summary="获取最新传感器数据")
    async def sensors_latest() -> dict:
        """返回三向测距与温度读数。"""
        return engine.get_sensors()

    @router.get("/events/anomalies", summary="获取历史异常事件")
    async def events_anomalies() -> list[dict]:
        """返回异常事件列表，字段与契约一致。"""
        return engine.get_anomalies()

    @router.delete("/events/anomalies", summary="清空异常事件")
    async def clear_anomalies() -> dict:
        """清空历史异常事件列表。"""
        engine.clear_anomalies()
        return {"message": "异常事件已清空"}

    @router.post("/map/suggest-removal", summary="建议拆除的最小障碍（不执行）")
    async def suggest_removal(goal: list[int]) -> dict:
        """
        寻找并建议拆除使目标可达的最小代价障碍格（仅建议，不执行拆除）。

        :param goal: 目标巡检点 [x, y]。
        :return: {'remove': [x, y] | null, 'message': str}
        """
        return engine.find_min_obstacle(goal)

    @router.post("/map/remove-obstacle", summary="（兼容旧版）建议拆除的最小障碍")
    async def remove_obstacle_legacy(goal: list[int]) -> dict:
        """旧路径兼容：等价于 /map/suggest-removal。"""
        return engine.find_min_obstacle(goal)

    @router.post("/plan", summary="一键规划路线（预览：穿障最短路径 + 电力预算）")
    async def plan_route(command: PlanGoalCommand) -> dict:
        """
        规划从机器人到目标巡检点的路线：理论最短路径（穿障），
        路径上的障碍按电力预算标记为待清障目标。仅预览，不移动机器人。

        :param command: {'goal': [x, y]}。
        :return: 路线规划字典（path/obstacles/clearable/电力预算等）。
        """
        return engine.plan_route(command.goal)

    @router.post("/plan/cancel", summary="取消当前路线规划")
    async def plan_cancel() -> dict:
        """取消当前路线规划预览。"""
        return engine.cancel_plan()

    @router.post("/plan/execute", summary="按当前规划批量清障")
    async def plan_execute() -> dict:
        """清除当前路线规划中电力预算内的全部障碍（逐处扣电，不足即停）。"""
        return engine.execute_plan_clear()

    @router.post("/robot/clear-obstacle", summary="手动清除指定障碍格")
    async def robot_clear_obstacle(command: ClearObstacleCommand) -> dict:
        """
        手动清障：清除指定障碍格并扣减清障电量（边界墙/电量不足拒绝）。

        :param command: {'cell': [x, y]}。
        :return: state 帧数据 + 权威地图。
        """
        return engine.clear_obstacle_at(command.cell)

    @router.post("/robot/clear-nearest-pending", summary="一键清除最近的待清障障碍")
    async def clear_nearest_pending() -> dict:
        """从待清障记录中选出离机器人最近的一处并清除。"""
        return engine.clear_nearest_pending()

    @router.get("/robot/pending", summary="获取待清障记录")
    async def get_pending() -> dict:
        """返回巡检过程中记录下来的待清障障碍格列表。"""
        return {"pending": [list(c) for c in engine.pending]}

    @router.post("/robot/carry-home", summary="空电后将机器人搬回起点")
    async def robot_carry_home() -> dict:
        """电量耗尽后把机器人搬回初始点并恢复满电。"""
        return engine.carry_home()

    @router.get("/robot/trail", summary="获取机器人轨迹")
    async def robot_trail() -> dict:
        """返回已访问轨迹，供前端绘制与回放。"""
        return {"trail": engine.get_trail()}

    logger.info("REST 路由注册完成")
    return router

"""
REST 路由模块。

模块功能：实现公共契约规定的全部 REST 接口。路由只做参数解析与响应
封装，业务逻辑一律委托给仿真引擎，保证职责单一。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import logging

from fastapi import APIRouter, Query

from app.models.map import GridMap
from app.models.robot import MoveCommand, PatrolStartCommand
from app.services.simulation_engine import SimulationEngine

logger = logging.getLogger("api.rest")

router = APIRouter(prefix="/api/v1")


def create_rest_router(engine: SimulationEngine) -> APIRouter:
    """
    构建并返回挂载了仿真引擎的 REST 路由。

    :param engine: 全局仿真引擎实例。
    :return: 配置完成的 APIRouter。
    """

    @router.get("/map", summary="获取当前地图")
    async def get_map() -> dict:
        """返回当前栅格地图，字段与契约一致。"""
        return engine.get_map()

    @router.put("/map", summary="更新地图")
    async def put_map(new_map: GridMap) -> dict:
        """
        接收前端编辑后的地图并保存。

        :param new_map: 新地图数据。
        :return: 保存后的地图字典。
        """
        return engine.update_map(new_map)

    @router.post("/robot/move", summary="手动控制机器人移动")
    async def robot_move(command: MoveCommand) -> dict:
        """
        单步移动机器人。

        :param command: {'dx': -1/0/1, 'dy': -1/0/1}
        :return: 移动后的 state 帧数据。
        """
        return engine.move(command.dx, command.dy)

    @router.post("/robot/reset", summary="机器人复位")
    async def robot_reset() -> dict:
        """复位机器人到起点，返回通知帧。"""
        engine.reset()
        return {"type": "notice", "data": {"message": "机器人已复位到起点"}}

    @router.post("/robot/resolve", summary="一键排障")
    async def robot_resolve() -> dict:
        """机器人被障碍卡住时，清除前方障碍并恢复正常控制。"""
        return engine.resolve_fault()

    @router.get("/path", summary="A* 寻路调试接口")
    async def compute_path(
        start: str = Query(..., description="起点坐标，格式 x,y"),
        goal: str = Query(..., description="目标坐标，格式 x,y"),
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
    async def patrol_start(command: PatrolStartCommand) -> dict:
        """
        启动巡检任务，goals 缺省时使用地图巡检点。

        :param command: {'goals': [[x, y], ...] | null}
        :return: 巡检状态字典。
        """
        return engine.start_patrol(command.goals)

    @router.post("/patrol/stop", summary="停止自动巡检")
    async def patrol_stop() -> dict:
        """停止巡检任务。"""
        return engine.stop_patrol()

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

    @router.post("/map/remove-obstacle", summary="一键排除最小障碍")
    async def remove_obstacle(goal: list[int]) -> dict:
        """
        寻找并拆除使目标可达的最小代价障碍格。

        :param goal: 目标巡检点 [x, y]。
        :return: {'remove': [x, y] | null, 'message': str}
        """
        return engine.find_min_obstacle(goal)

    @router.get("/robot/trail", summary="获取机器人轨迹")
    async def robot_trail() -> dict:
        """返回已访问轨迹，供前端绘制与回放。"""
        return {"trail": engine.get_trail()}

    logger.info("REST 路由注册完成")
    return router

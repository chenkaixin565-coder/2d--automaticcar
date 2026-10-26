"""
WebSocket 实时通道模块。

模块功能：维护 /api/v1/ws 连接。服务端每 tick_interval_ms（默认 200ms）
推送 state 帧，异常/通知事件即时推送；接收客户端 command 下行帧并分发
到仿真引擎。支持多客户端同时在线。

V2.0 变更（重要）：原先每个连接都会启动一个"广播给所有人"的推送循环，
N 个客户端时每个客户端每秒会收到 5N 帧（N² 放大）。现在推送循环全进程
只有一份，由应用生命周期启动，连接只负责收指令。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.simulation_engine import SimulationEngine

logger = logging.getLogger("api.websocket")

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器（支持多客户端广播）。"""

    def __init__(self) -> None:
        """初始化空连接集合。"""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """
        接受并登记新连接。

        :param websocket: FastAPI WebSocket 实例。
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket 客户端接入，当前连接数 %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """
        移除断开的连接。

        :param websocket: 已断开的 WebSocket 实例。
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket 客户端断开，剩余连接数 %d", len(self.active_connections))

    async def broadcast(self, frame: dict) -> None:
        """
        向所有在线客户端广播一帧 JSON。

        :param frame: 与协议一致的帧字典。
        """
        if not self.active_connections:
            return
        text = json.dumps(frame, ensure_ascii=False)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text)
            except Exception:  # noqa: BLE001 - 单个客户端发送失败不影响其它客户端。
                self.disconnect(connection)


# 全局唯一连接管理器：推送循环与事件回调共用。
manager = ConnectionManager()


async def push_state_loop(engine: SimulationEngine, tick_interval_ms: int) -> None:
    """
    全局唯一的 state 帧推送循环（每 tick 广播一次，与客户端数量无关）。

    :param engine: 仿真引擎实例。
    :param tick_interval_ms: 推送间隔（毫秒）。
    """
    while True:
        await asyncio.sleep(tick_interval_ms / 1000)
        try:
            await manager.broadcast(engine.state_dict())
        except Exception:  # noqa: BLE001 - 推送失败不能让循环退出。
            logger.exception("state 帧推送失败")


def bind_engine_events(engine: SimulationEngine) -> None:
    """
    把引擎产生的事件帧桥接到 WebSocket 广播。

    引擎回调是同步函数，运行在事件循环线程内，直接 create_task 即可。

    :param engine: 仿真引擎实例。
    """

    def _on_engine_event(frame: dict) -> None:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast(frame))
        else:  # pragma: no cover - 仅在测试的同步上下文中出现
            logger.debug("事件循环未运行，丢弃事件帧: %s", frame.get("type"))

    engine.add_event_listener(_on_engine_event)


def create_ws_router(engine: SimulationEngine) -> APIRouter:
    """
    构建 WebSocket 路由。

    :param engine: 全局仿真引擎实例。
    :return: 配置完成的 APIRouter。
    """

    @router.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket 主处理协程：只负责接收并分发下行指令。"""
        await manager.connect(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("收到非法 JSON 帧: %s", raw[:100])
                    continue
                if message.get("type") != "command":
                    continue
                action = message.get("action")
                payload = message.get("payload") or {}
                logger.info("收到客户端指令: %s %s", action, payload)
                try:
                    _dispatch(engine, action, payload)
                except Exception:  # noqa: BLE001 - 单条指令异常不应断开连接。
                    logger.exception("指令执行失败: %s", action)
                    await manager.broadcast(
                        {"type": "notice", "data": {"message": f"指令执行失败：{action}"}}
                    )
        except WebSocketDisconnect:
            logger.info("客户端正常断开")
        finally:
            manager.disconnect(websocket)

    return router


def _dispatch(engine: SimulationEngine, action: str, payload: dict) -> None:
    """
    把客户端指令分发到引擎。

    :param engine: 仿真引擎实例。
    :param action: 指令名。
    :param payload: 指令参数。
    """
    if action == "move":
        engine.move(int(payload.get("dx", 0)), int(payload.get("dy", 0)))
    elif action == "patrol_start":
        engine.start_patrol(payload.get("goals"))
    elif action == "patrol_stop":
        engine.stop_patrol()
    elif action == "patrol_decision":
        engine.patrol_decision(payload.get("action", ""))
    elif action == "reset":
        engine.reset(keep_trail=bool(payload.get("keep_trail", False)))
    elif action == "restart":
        engine.reset(keep_trail=True)
    elif action == "resolve_fault":
        engine.resolve_fault()
    elif action == "plan":
        engine.plan_route(payload.get("goal") or [1, 1])
    elif action == "cancel_plan":
        engine.cancel_plan()
    elif action == "clear_obstacle":
        engine.clear_obstacle_at(payload.get("cell") or [0, 0])
    elif action == "clear_nearest_pending":
        engine.clear_nearest_pending()
    elif action == "execute_plan_clear":
        engine.execute_plan_clear()
    elif action == "carry_home":
        engine.carry_home()
    elif action == "set_cell":
        engine.set_cell(int(payload.get("x", 0)), int(payload.get("y", 0)), int(payload.get("value", 0)))
    elif action == "new_map":
        engine.new_map(int(payload.get("width", 30)), int(payload.get("height", 20)))
    else:
        logger.warning("未知指令: %s", action)

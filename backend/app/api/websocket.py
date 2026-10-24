"""
WebSocket 实时通道模块。

模块功能：维护 /api/v1/ws 连接。服务端每 tick_interval_ms（默认 200ms）
推送 state 帧，异常/通知事件即时推送；接收客户端 command 下行帧并分发
到仿真引擎。支持多客户端同时在线。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
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
        text = json.dumps(frame, ensure_ascii=False)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text)
            except Exception:  # noqa: BLE001 - 单个客户端发送失败不影响其它客户端。
                self.disconnect(connection)


def create_ws_router(engine: SimulationEngine, tick_interval_ms: int) -> APIRouter:
    """
    构建 WebSocket 路由。

    :param engine: 全局仿真引擎实例。
    :param tick_interval_ms: state 帧推送间隔（毫秒）。
    :return: 配置完成的 APIRouter。
    """

    @router.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """
        WebSocket 主处理协程。

        并发运行两个任务：定时推送 state 帧 / 接收客户端 command 帧。
        """
        await manager.connect(websocket)
        _register_broadcast_loop()  # 捕获运行循环并注册引擎事件广播。

        async def push_state_loop() -> None:
            """周期性向本连接推送 state 帧（引擎 tick 由主循环统一推进）。"""
            while True:
                await asyncio.sleep(tick_interval_ms / 1000)
                await manager.broadcast(engine.state_dict())

        async def command_loop() -> None:
            """接收并分发客户端指令的后台任务。"""
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
                if action == "move":
                    engine.move(payload.get("dx", 0), payload.get("dy", 0))
                elif action == "patrol_start":
                    engine.start_patrol(payload.get("goals"))
                elif action == "patrol_stop":
                    engine.stop_patrol()
                elif action == "reset":
                    engine.reset()
                elif action == "resolve_fault":
                    engine.resolve_fault()
                else:
                    logger.warning("未知指令: %s", action)

        state_task = asyncio.create_task(push_state_loop())
        command_task = asyncio.create_task(command_loop())
        try:
            done, pending = await asyncio.wait(
                {state_task, command_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()  # 抛出真实异常便于日志定位。
        except WebSocketDisconnect:
            logger.info("客户端正常断开")
        finally:
            manager.disconnect(websocket)

    # 广播器：引擎事件 -> WebSocket 群发。引擎回调是同步函数，
    # 通过事件循环线程安全地调度异步广播。
    manager = ConnectionManager()
    _broadcast_loop: dict = {"loop": None}
    _listener_registered = {"flag": False}

    def _register_broadcast_loop() -> None:
        """在首个连接建立时捕获运行中的事件循环并注册引擎监听器。"""
        _broadcast_loop["loop"] = asyncio.get_running_loop()
        if not _listener_registered["flag"]:
            engine.add_event_listener(_on_engine_event)
            _listener_registered["flag"] = True

    def _on_engine_event(frame: dict) -> None:
        """把引擎产生的帧线程安全地投递到事件循环广播。"""
        loop = _broadcast_loop["loop"]
        if loop is not None:
            asyncio.run_coroutine_threadsafe(manager.broadcast(frame), loop)

    return router

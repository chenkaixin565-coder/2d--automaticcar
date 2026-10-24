"""
仿真引擎模块。

模块功能：系统核心。持有地图与机器人状态，按固定周期（默认 200ms）
推进仿真：电量消耗、巡检路径跟随、传感器刷新、规则异常检测。对外提供
与 REST/WebSocket 契约一致的操作方法，并通过回调把 state/anomaly 帧
推送给接口层。业务规则与前端 SimulatedService 逐条对应。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import logging
import math
from datetime import datetime, timezone

from app.algorithms.astar import astar
from app.core import config
from app.core.constants import (
    ANOMALY_OBSTACLE,
    CELL_OBSTACLE,
    MODE_BLOCKED,
    MODE_CHARGING,
    MODE_MANUAL,
    MODE_PATROL,
)
from app.models.map import GridMap
from app.services.anomaly import create_detector
from app.services.patrol import PatrolManager, find_min_obstacle_to_remove, order_goals_by_nearest
from app.services.sensors import SensorSimulator

logger = logging.getLogger("simulation.engine")


def _default_map(width: int, height: int) -> GridMap:
    """
    生成默认地图：空旷场地 + 少量固定障碍，用于开箱即用的演示。

    :param width: 地图宽度。
    :param height: 地图高度。
    :return: GridMap 实例。
    """
    grid = [[0] * width for _ in range(height)]
    # 预置几段障碍墙体，保证默认地图就有寻路与避障的演示效果。
    walls = [
        (3, 2), (3, 3), (3, 4),
        (8, 5), (9, 5), (10, 5), (11, 5),
        (5, 8), (6, 8), (7, 8), (8, 8),
        (12, 2), (12, 3), (13, 7),
    ]
    for x, y in walls:
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = CELL_OBSTACLE
    # 真正的边界：最外环由 GridMap 校验器强制为墙，起点/充电点/巡检点一律放内侧
    return GridMap(
        width=width,
        height=height,
        grid=grid,
        start=(1, 1),
        goals=[[width - 2, height - 2], [width // 2, height // 2]],
        charge_point=(1, height - 2),
    )


class SimulationEngine:
    """机器人二维仿真引擎（单例，由应用生命周期持有）。"""

    def __init__(self) -> None:
        """初始化引擎：默认地图、初始状态、各服务组件。"""
        self.map = _default_map(config.settings.default_width, config.settings.default_height)
        self.sensor_sim = SensorSimulator(self.map.grid)
        self.anomaly_detector = create_detector()
        self.patrol = PatrolManager()

        # 机器人运动状态。
        self.x, self.y = self.map.start
        self.theta = 0.0
        self.battery = 100.0
        self.speed = 1.0
        self.mode = MODE_MANUAL
        self.path: list[list[int]] = []
        self.visited_trail: list[list[int]] = [[self.x, self.y]]

        # 传感器最新读数缓存。
        self.sensors: dict = {
            "front": None,
            "left": None,
            "right": None,
            "temperature": config.settings.base_temperature,
        }
        # 事件回调集合（WebSocket 广播器注册进来）。
        self._event_listeners: list = []
        logger.info("仿真引擎初始化完成：地图 %dx%d，起点 %s", self.map.width, self.map.height, self.map.start)

    # ---------- 事件推送 ----------

    def add_event_listener(self, callback) -> None:
        """
        注册事件监听器（接口层的 WebSocket 广播函数）。

        :param callback: 接收帧字典的回调函数。
        """
        self._event_listeners.append(callback)

    def _emit(self, frame: dict) -> None:
        """
        向所有监听器广播一帧数据。

        :param frame: 与 WebSocket 协议一致的帧字典。
        """
        for callback in self._event_listeners:
            try:
                callback(frame)
            except Exception:  # noqa: BLE001 - 单个客户端异常不能影响仿真循环。
                logger.exception("事件监听器执行失败")

    def _emit_anomaly(self, event: dict) -> None:
        """广播异常事件帧并写入日志。"""
        logger.warning("异常事件: %s - %s @ %s", event["type"], event["message"], event["position"])
        self._emit({"type": "anomaly", "data": event})

    def _emit_notice(self, message: str) -> None:
        """广播通知帧并写入日志。"""
        logger.info("通知: %s", message)
        self._emit({"type": "notice", "data": {"message": message}})

    # ---------- 地图 ----------

    def get_map(self) -> dict:
        """
        获取当前地图（REST GET /map 响应体）。

        :return: 与契约字段一致的地图字典。
        """
        return self.map.model_dump()

    def update_map(self, new_map: GridMap | dict) -> dict:
        """
        更新地图（REST PUT /map 请求体）。

        机器人位置非法时自动回退到起点。

        :param new_map: 新地图模型或可校验的字典。
        :return: 保存后的地图字典。
        """
        if isinstance(new_map, dict):
            new_map = GridMap.model_validate(new_map)
        self.map = new_map
        self.sensor_sim.set_grid(new_map.grid)
        if not new_map.is_free(self.x, self.y):
            logger.warning("机器人当前位置 (%d, %d) 变为障碍，回退起点", self.x, self.y)
            self.x, self.y = new_map.start
            self.visited_trail.append([self.x, self.y])
        logger.info("地图已更新: %dx%d", new_map.width, new_map.height)
        return self.map.model_dump()

    # ---------- 手动控制 ----------

    def move(self, dx: int, dy: int) -> dict:
        """
        手动单步移动（REST POST /robot/move）。

        碰撞障碍或越界时不动并将 mode 置为 blocked。

        :param dx: 水平步长 -1/0/1。
        :param dy: 垂直步长 -1/0/1。
        :return: 移动后的状态字典。
        """
        if dx == 0 and dy == 0:
            return self.state_dict()["data"]
        target = (self.x + dx, self.y + dy)
        if self.map.is_free(*target):
            self.x, self.y = target
            self.theta = math.atan2(dy, dx)
            self.visited_trail.append([self.x, self.y])
            # 移动一格即时扣除电量（与契约一致：移动 0.2%/格）。
            self.battery = max(0.0, self.battery - config.settings.battery_move_cost)
            if self.mode not in (MODE_PATROL, MODE_CHARGING):
                self.mode = MODE_MANUAL
            logger.debug("移动到 (%d, %d)", self.x, self.y)
        else:
            self.mode = MODE_BLOCKED
            logger.info("移动被阻挡于 (%d, %d)", *target)
        return self.state_dict()["data"]

    def reset(self) -> None:
        """复位机器人到起点并停止巡检（REST POST /robot/reset）。"""
        self.patrol.stop()
        self.x, self.y = self.map.start
        self.theta = 0.0
        self.battery = 100.0
        self.mode = MODE_MANUAL
        self.path = []
        self.visited_trail = [[self.x, self.y]]
        logger.info("机器人已复位到起点 %s", self.map.start)
        self._emit_notice("机器人已复位到起点")

    # ---------- 路径规划 ----------

    def compute_path(self, start: list[int], goal: list[int]) -> dict:
        """
        A* 调试接口（REST GET /path）。

        :param start: 起点坐标 [x, y]。
        :param goal: 目标坐标 [x, y]。
        :return: {'path', 'visited_count', 'cost'} 与前端 astar.js 一致。
        """
        result = astar(self.map.grid, tuple(start), tuple(goal))
        logger.info("寻路 %s -> %s：路径长 %d，访问 %d 节点", start, goal, len(result["path"]), result["visited_count"])
        return result

    def find_min_obstacle(self, goal: list[int]) -> dict:
        """
        一键排障：寻找使目标可达的最小代价障碍格（配合前端功能 11）。

        :param goal: 目标巡检点坐标 [x, y]。
        :return: {'remove': [x, y] | None, 'message': str}
        """
        cell = find_min_obstacle_to_remove(self.map.grid, (self.x, self.y), tuple(goal))
        if cell is None:
            logger.info("一键排障：无单格拆除方案可使 %s 可达", goal)
            return {"remove": None, "message": "拆除单个障碍无法到达目标"}
        logger.info("一键排障：建议拆除障碍 %s", cell)
        return {"remove": list(cell), "message": f"建议拆除障碍 [{cell[0]}, {cell[1]}]"}

    def remove_obstacle(self, cell: list[int]) -> dict:
        """
        拆除指定障碍格并重算当前巡检路径。

        真正的边界：最外环边界墙不可拆除，拒绝后原样返回地图。

        :param cell: 障碍坐标 [x, y]。
        :return: 更新后的地图字典。
        """
        cell_x, cell_y = cell
        if self.map.in_bounds(cell_x, cell_y):
            if self.map.is_boundary(cell_x, cell_y):
                logger.info("障碍 (%d, %d) 是边界墙，拒绝拆除", cell_x, cell_y)
                return self.map.model_dump()
            self.map.grid[cell_y][cell_x] = 0
            logger.info("障碍 (%d, %d) 已拆除", cell_x, cell_y)
        return self.map.model_dump()

    def resolve_fault(self) -> dict:
        """
        一键排障：机器人被障碍卡住（mode=blocked）时，清除正前方障碍格
        并恢复正常控制；无阻塞时仅返回提示。正前方朝向由 theta 近似为
        四方向步长（与前端 SimulatedService._thetaToDirection 一致）。

        :return: 通知帧 {'type': 'notice', 'data': {'message': str}}。
        """
        if self.mode != MODE_BLOCKED:
            message = "当前无阻塞故障，无需排障"
            logger.info("一键排障：%s", message)
            self._emit_notice(message)
            return {"type": "notice", "data": {"message": message}}

        dx, dy = self._theta_to_step(self.theta)
        target = (self.x + dx, self.y + dy)
        if self.map.in_bounds(*target) and self.map.grid[target[1]][target[0]] == CELL_OBSTACLE:
            if self.map.is_boundary(*target):
                # 边界墙不可清除：仅恢复控制权，提示用户转向脱离
                message = "前方是固定边界墙，无法清除；请向其他方向移动脱离"
                logger.info("一键排障：前方为边界墙 (%d, %d)，不清除", *target)
                self.mode = MODE_MANUAL
                self.path = []
                self._emit_notice(message)
                return {"type": "notice", "data": {"message": message}}
            self.map.grid[target[1]][target[0]] = 0
            logger.info("一键排障：拆除前方障碍 (%d, %d)", *target)
        self.mode = MODE_MANUAL
        self.path = []
        message = "已排除前方障碍，恢复正常控制"
        self._emit_notice(message)
        return {"type": "notice", "data": {"message": message}}

    @staticmethod
    def _theta_to_step(theta: float) -> tuple[int, int]:
        """
        把朝向角近似为四方向步长。

        :param theta: 朝向角（弧度）。
        :return: (dx, dy) 单位步长。
        """
        normalized = (theta % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
        half = math.pi / 4
        if normalized < half or normalized >= 7 * half:
            return (1, 0)
        if normalized < 3 * half:
            return (0, 1)
        if normalized < 5 * half:
            return (-1, 0)
        return (0, -1)

    # ---------- 巡检 ----------

    def start_patrol(self, goals: list[list[int]] | None = None) -> dict:
        """
        启动自动巡检（REST POST /patrol/start）。

        goals 缺省时使用地图巡检点；先最近邻贪心排序，再逐段 A*。

        :param goals: 巡检点列表（可选）。
        :return: 与契约一致的巡检状态字典。
        """
        goal_list = [tuple(g) for g in (goals if goals else self.map.goals)]
        ordered = order_goals_by_nearest((self.x, self.y), goal_list)
        self.patrol.start(ordered)
        self.mode = MODE_PATROL
        self._plan_current_segment()
        logger.info("巡检启动，共 %d 个巡检点：%s", len(ordered), ordered)
        self._emit_notice(f"自动巡检已启动，共 {len(ordered)} 个巡检点")
        return self.patrol.status_dict()

    def stop_patrol(self) -> dict:
        """停止巡检（REST POST /patrol/stop）。"""
        self.patrol.stop()
        self.mode = MODE_MANUAL
        self.path = []
        logger.info("巡检已停止")
        self._emit_notice("自动巡检已停止")
        return self.patrol.status_dict()

    def get_patrol_status(self) -> dict:
        """获取巡检状态（REST GET /patrol/status）。"""
        return self.patrol.status_dict()

    def _plan_current_segment(self) -> None:
        """为当前巡检点规划路径；不可达时告警并跳过。"""
        goal = self.patrol.current_goal()
        if goal is None:
            return
        result = astar(self.map.grid, (self.x, self.y), goal)
        if result["path"]:
            self.path = result["path"]
            self.patrol.path_remain = max(0, len(result["path"]) - 1)
        else:
            self._emit_anomaly(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": ANOMALY_OBSTACLE,
                    "message": f"无法到达巡检点 [{goal[0]}, {goal[1]}]，已跳过",
                    "position": [self.x, self.y],
                }
            )
            self.patrol.advance()

    # ---------- 传感器与异常 ----------

    def get_sensors(self) -> dict:
        """获取最新传感器读数（REST GET /sensors/latest）。"""
        return dict(self.sensors)

    def get_anomalies(self) -> list[dict]:
        """获取历史异常事件（REST GET /events/anomalies）。"""
        return self.anomaly_detector.get_history()

    def clear_anomalies(self) -> None:
        """清空历史异常事件。"""
        self.anomaly_detector.clear()
        logger.info("异常事件列表已清空")

    # ---------- 仿真主循环 ----------

    def state_dict(self) -> dict:
        """
        导出与 WebSocket state 帧完全一致的帧字典。

        :return: {'type': 'state', 'data': {...}}
        """
        data = {
            "x": self.x,
            "y": self.y,
            "theta": round(self.theta, 3),
            "battery": round(self.battery, 1),
            "speed": self.speed,
            "mode": self.mode,
            "path": self.path,
            "sensors": dict(self.sensors),
            "patrol": self.patrol.status_dict(),
        }
        return {"type": "state", "data": data}

    def tick(self) -> None:
        """
        仿真主循环单步：由后台定时任务每 tick_interval_ms 调用一次。

        步骤：巡检路径跟随 → 电量消耗 → 传感器刷新 → 异常检测 → 低电量返航。
        """
        moving = False

        # 步骤 1：巡检模式按路径前进。
        if self.mode == MODE_PATROL and len(self.path) > 1:
            next_cell = self.path[1]
            self.x, self.y = next_cell
            self.theta = math.atan2(next_cell[1] - self.path[0][1], next_cell[0] - self.path[0][0])
            self.visited_trail.append([self.x, self.y])
            self.path = self.path[1:]
            self.patrol.path_remain = max(0, len(self.path) - 1)
            moving = True
            # 到达当前巡检点，推进任务。
            if len(self.path) <= 1:
                goal = self.patrol.current_goal()
                if goal and (self.x, self.y) == goal:
                    logger.info("到达巡检点 (%d, %d)，进度 %d/%d", self.x, self.y, self.patrol.completed + 1, len(self.patrol.goals))
                    self.patrol.advance()
                    self._plan_current_segment()
                    if self.patrol.current_goal() is None:
                        self.mode = MODE_MANUAL
                        self.patrol.stop()
                        self._emit_notice("巡检任务全部完成")
        # 步骤 1b：充电模式沿路径返航。
        elif self.mode == MODE_CHARGING and len(self.path) > 1:
            next_cell = self.path[1]
            self.x, self.y = next_cell
            self.visited_trail.append([self.x, self.y])
            self.path = self.path[1:]
            moving = True
            if len(self.path) <= 1:
                logger.info("已到达充电点，开始充电")
                self._emit_notice("已到达充电点，开始充电")

        # 步骤 2：电量结算（移动/静止/充电三种速率）。
        if self.mode == MODE_CHARGING and not moving:
            self.battery = min(100.0, self.battery + config.settings.charge_rate)
            if self.battery >= 100.0:
                self.mode = MODE_MANUAL
                self._emit_notice("充电完成，电量 100%")
        else:
            cost = config.settings.battery_move_cost if moving else config.settings.battery_idle_cost
            self.battery = max(0.0, self.battery - cost)

        # 步骤 3：刷新传感器读数（整合电量/位置，统一喂给异常检测器）。
        reading = self.sensor_sim.read_all(self.x, self.y, self.theta, self.battery, moving)
        self.sensors = {
            "front": reading["front"],
            "left": reading["left"],
            "right": reading["right"],
            "temperature": reading["temperature"],
        }
        reading["mode"] = self.mode

        # 步骤 4：异常检测（规则基线 / 机器学习，按 ANOMALY_STRATEGY 切换）。
        events = self.anomaly_detector.update(reading)
        for event in events:
            self._emit_anomaly(event)

        # 步骤 5：低电量自动返航（一次性触发）。
        if (
            self.battery < config.settings.low_battery_threshold
            and self.mode not in (MODE_CHARGING,)
        ):
            self.mode = MODE_CHARGING
            charge = tuple(self.map.charge_point)
            result = astar(self.map.grid, (self.x, self.y), charge)
            self.path = result["path"]
            logger.warning("低电量触发自动返航充电")

    def get_trail(self) -> list[list[int]]:
        """
        获取已访问轨迹（供前端绘制与回放）。

        :return: 轨迹坐标列表。
        """
        return list(self.visited_trail)

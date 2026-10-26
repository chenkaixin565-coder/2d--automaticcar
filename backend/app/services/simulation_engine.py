"""
仿真引擎模块。

模块功能：系统核心。持有地图与机器人状态，按固定周期（默认 200ms）
推进仿真：电量消耗、巡检路径跟随、传感器刷新、规则异常检测。对外提供
与 REST/WebSocket 契约一致的操作方法，并通过回调把 state/anomaly 帧
推送给接口层。业务规则与前端 SimulatedService 逐条对应。

V2.0 变更（对应验收清单）：
  1. move() 会中断巡检并清空路径（原先后端手动移动后下一 tick 会瞬移）；
  2. 充电只认"是否在充电点上"，离开即取消（原先后端随处可充电）；
  3. 清障前校验电量，批量清障逐处判断余额（原先可以 1% 电量拆一排墙）；
  4. 新增巡检遇阻暂停 + 三选一决策（清除 / 跳过记录 / 停止）；
  5. 新增待清障记录与"一键清最近"；
  6. 新增 restart（保留尾迹）与 new_map（新建空白地图）；
  7. 低电量自动返航充电，充满后自动继续原巡检任务；
  8. 温度改为累积模型，过热告警可真实触发。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import logging
import math
from datetime import datetime, timezone

from app.algorithms.astar import astar
from app.core import config
from app.core.constants import (
    ANOMALY_LOW_BATTERY,
    ANOMALY_OBSTACLE,
    CELL_OBSTACLE,
    MODE_BLOCKED,
    MODE_CHARGING,
    MODE_EMPTY,
    MODE_MANUAL,
    MODE_PATROL,
)
from app.models.map import GridMap
from app.services.anomaly import create_detector
from app.services.patrol import PatrolManager, find_min_obstacle_to_remove, order_goals_by_nearest
from app.services.planner import build_plan
from app.services.sensors import SensorSimulator

logger = logging.getLogger("simulation.engine")


def _default_map(width: int, height: int) -> GridMap:
    """
    生成默认地图："默认厂房"预设，与前端 mapPresets.factory 保持一致。

    V2.0 起前后端使用同一张默认地图（30x20 / 23 处墙体），避免同一系统
    两个入口（GitHub Pages 离线版、Render 全栈版）画面完全不同。

    :param width: 地图宽度。
    :param height: 地图高度。
    :return: GridMap 实例。
    """
    grid = [[0] * width for _ in range(height)]
    # 与 frontend/src/services/mapPresets.js 的 factory 预设保持一致。
    walls = [
        (5, 3), (6, 3), (7, 3), (8, 3),
        (12, 5), (12, 6), (12, 7),
        (18, 4), (19, 4), (20, 4),
        (4, 12), (5, 12), (6, 12),
        (15, 13), (16, 13), (17, 13), (18, 13),
        (22, 10), (22, 11), (22, 12),
        (10, 16), (11, 16), (12, 16),
    ]
    for x, y in walls:
        if 0 < x < width - 1 and 0 < y < height - 1:
            grid[y][x] = CELL_OBSTACLE
    goals = [[5, 5], [15, 8], [25, 5], [10, 15], [20, 16]]
    goals = [[x, y] for x, y in goals if 0 < x < width - 1 and 0 < y < height - 1]
    return GridMap(
        width=width,
        height=height,
        grid=grid,
        start=(1, 1),
        goals=goals,
        charge_point=(width - 2, height - 2),
    )


def _blank_map(width: int, height: int) -> GridMap:
    """
    生成一张空白地图（只有四周边界墙），供"新建地图"功能使用。

    :param width: 地图宽度。
    :param height: 地图高度。
    :return: GridMap 实例。
    """
    grid = [[0] * width for _ in range(height)]
    return GridMap(
        width=width,
        height=height,
        grid=grid,
        start=(1, 1),
        goals=[],
        charge_point=(width - 2, height - 2),
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
        self.speed = 0.0
        self.mode = MODE_MANUAL
        self.path: list[list[int]] = []
        self.visited_trail: list[list[int]] = [[self.x, self.y]]

        # 巡检遇阻暂停与待清障记录（V2.0）。
        self.paused: bool = False
        self.blocked: dict | None = None
        self.pending: list[list[int]] = []

        # 传感器最新读数缓存。
        self.sensors: dict = {
            "front": None,
            "left": None,
            "right": None,
            "temperature": config.settings.base_temperature,
        }
        # 事件回调集合（WebSocket 广播器注册进来）。
        self._event_listeners: list = []
        # 一键路线规划结果（含电力预算），未规划时为 None，随 state 帧下发。
        self.plan: dict | None = None
        # 低电量且充电点不可达的告警去重标记。
        self._charge_unreachable_notified = False
        # 充电前是否正在巡检：充满后自动继续（V2.0）。
        self._resume_patrol_after_charge = False
        # 最近一次"到达巡检点"提示的时间戳，避免重复刷屏。
        self._last_arrive_at = 0.0
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

    def _emit_blocked(self, message: str) -> None:
        """广播"巡检遇阻"帧：前端据此弹窗询问是否清障（V2.0）。"""
        cell = self.blocked["cell"] if self.blocked else None
        logger.info("巡检遇阻，等待决策：%s", message)
        self._emit(
            {
                "type": "blocked",
                "data": {
                    "cell": cell,
                    "message": message,
                    "battery": round(self.battery, 1),
                    "clear_cost": config.settings.clear_obstacle_cost,
                },
            }
        )

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

        地图变更会中断巡检、作废规划、清除遇阻状态；机器人当前位置非法时
        回退到起点。

        :param new_map: 新地图模型或可校验的字典。
        :return: 保存后的地图字典。
        """
        if isinstance(new_map, dict):
            new_map = GridMap.model_validate(new_map)
        self.map = new_map
        self.sensor_sim.set_grid(new_map.grid)
        self._reset_task_state()
        if not new_map.is_free(self.x, self.y) or not new_map.in_bounds(self.x, self.y):
            logger.warning("机器人当前位置 (%s, %s) 非法，回退起点", self.x, self.y)
            self.x, self.y = new_map.start
            self.visited_trail.append([self.x, self.y])
        # 待清障记录里已经被新地图清除的格子直接剔除。
        self.pending = [c for c in self.pending if new_map.in_bounds(*c) and new_map.grid[c[1]][c[0]] == CELL_OBSTACLE]
        logger.info("地图已更新: %dx%d", new_map.width, new_map.height)
        return self.map.model_dump()

    def new_map(self, width: int, height: int) -> dict:
        """
        新建一张空白地图（只保留四周边界墙），机器人复位到新起点。

        :param width: 地图宽度（列数）。
        :param height: 地图高度（行数）。
        :return: 新地图字典。
        """
        width = max(config.settings.min_map_size, min(config.settings.max_map_size, int(width)))
        height = max(config.settings.min_map_size, min(config.settings.max_map_size, int(height)))
        blank = _blank_map(width, height)
        self.pending = []
        self.visited_trail = []
        self.update_map(blank)
        self.x, self.y = blank.start
        self.visited_trail = [[self.x, self.y]]
        self.battery = 100.0
        self.sensor_sim.reset_temperature()
        self._emit_notice(f"已新建 {width}×{height} 空白地图，可直接绘制障碍与巡检点")
        return self.map.model_dump()

    def _reset_task_state(self) -> None:
        """中断巡检、作废规划、清空遇阻状态（地图/新任务切换时调用）。"""
        self.patrol.stop()
        self.paused = False
        self.blocked = None
        self.path = []
        self.plan = None
        self.mode = MODE_MANUAL if self.mode != MODE_EMPTY else MODE_EMPTY
        self._resume_patrol_after_charge = False

    # ---------- 手动控制 ----------

    def move(self, dx: int, dy: int) -> dict:
        """
        手动单步移动（REST POST /robot/move）。

        V2.0：手动操作会立即中断自动巡检并清空路径，与前端行为保持一致
        （原先后端不动巡检状态，下一 tick 机器人会沿旧路径瞬移）。

        :param dx: 水平步长 -1/0/1。
        :param dy: 垂直步长 -1/0/1。
        :return: 移动后的状态字典。
        """
        if self.mode == MODE_EMPTY:
            self._emit_notice("电量耗尽，无法移动；请将机器人搬回初始点")
            return self.state_dict()["data"]
        if dx == 0 and dy == 0:
            return self.state_dict()["data"]

        # 手动接管：巡检中断、遇阻状态清除、充电中断。
        if self.patrol.running or self.mode in (MODE_PATROL, MODE_CHARGING):
            was_patrol = self.patrol.running
            self.patrol.stop()
            self.paused = False
            self.blocked = None
            self.path = []
            self.mode = MODE_MANUAL
            self._resume_patrol_after_charge = False
            if was_patrol:
                self._emit_notice("手动控制已中断自动巡检")

        target = (self.x + dx, self.y + dy)
        if self.map.is_free(*target):
            # 若离开充电点，充电状态立即取消（不再"随处回血"）。
            if self.mode == MODE_CHARGING:
                self.mode = MODE_MANUAL
            self.x, self.y = target
            self.theta = math.atan2(dy, dx)
            self.visited_trail.append([self.x, self.y])
            self.battery = max(0.0, self.battery - config.settings.battery_move_cost)
            self.sensor_sim.note_move()  # 手动移动同样产生温升（供过热检测）
            self.speed = 1.0
            if self.mode != MODE_CHARGING:
                self.mode = MODE_MANUAL
            logger.debug("移动到 (%d, %d)", self.x, self.y)
        else:
            self.mode = MODE_BLOCKED
            self.speed = 0.0
            logger.info("移动被阻挡于 (%s, %s)", *target)
            self._emit_notice("前方有障碍，机器人已停止；可点击「一键排障」清除或转向")
        return self.state_dict()["data"]

    def reset(self, keep_trail: bool = False) -> None:
        """
        复位机器人到起点。

        :param keep_trail: True 表示"重新开始"：保留已走过的尾迹；
                           False 表示"复位"：尾迹一并清空。
        """
        self.patrol.stop()
        self.x, self.y = self.map.start
        self.theta = 0.0
        self.battery = 100.0
        self.mode = MODE_MANUAL
        self.path = []
        self.plan = None
        self.paused = False
        self.blocked = None
        self._charge_unreachable_notified = False
        self._resume_patrol_after_charge = False
        self.sensor_sim.reset_temperature()
        if keep_trail:
            self.visited_trail.append([self.x, self.y])
        else:
            self.visited_trail = [[self.x, self.y]]
        logger.info("机器人已复位到起点 %s（keep_trail=%s）", self.map.start, keep_trail)
        self._emit_notice("机器人已重新开始，保留历史尾迹" if keep_trail else "机器人已复位到起点")

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
        建议拆除：寻找使目标可达的最小代价障碍格（不执行拆除）。

        :param goal: 目标巡检点坐标 [x, y]。
        :return: {'remove': [x, y] | None, 'message': str}
        """
        cell = find_min_obstacle_to_remove(self.map.grid, (self.x, self.y), tuple(goal))
        if cell is None:
            logger.info("建议拆除：无单格拆除方案可使 %s 可达", goal)
            return {"remove": None, "message": "拆除单个障碍无法到达目标"}
        logger.info("建议拆除：障碍 %s", cell)
        return {"remove": list(cell), "message": f"建议拆除障碍 [{cell[0]}, {cell[1]}]"}

    # ---------- 一键路线规划与清障 ----------

    def plan_route(self, goal: list[int]) -> dict:
        """
        一键规划路线：理论最短路径（穿障）+ 电力预算内的待清障目标。

        V2.0 语义：这是"预览"，不移动机器人；点"开始巡检"才真正执行。

        :param goal: 目标巡检点坐标 [x, y]。
        :return: 路线规划字典（字段与前端 routePlanner.js 一致）。
        """
        plan = build_plan(
            self.map.grid,
            (self.x, self.y),
            (goal[0], goal[1]),
            self.battery,
            config.settings.battery_move_cost,
            config.settings.clear_obstacle_cost,
        )
        if not plan["path"]:
            self.plan = None
            logger.info("路线规划失败：目标 %s 不可达", goal)
            self._emit_notice(plan.get("message") or "无法规划路线：目标不可达")
            return plan
        self.plan = plan
        logger.info(
            "路线已规划（预览）：全程 %d 格，待清障 %d 个，预计耗电 %.1f%%",
            len(plan["path"]) - 1,
            len(plan["obstacles"]),
            plan["total_cost"],
        )
        self._emit_notice(
            f"路线已规划：全程 {len(plan['path']) - 1} 格，"
            f"待清障 {len(plan['obstacles'])} 个，预计耗电 {plan['total_cost']:.1f}%"
        )
        return plan

    def cancel_plan(self) -> dict:
        """
        取消当前路线规划预览。

        :return: 控制类统一响应体（state 数据 + map）。
        """
        self.plan = None
        logger.info("路线规划已取消")
        self._emit_notice("路线规划已取消")
        return self._command_payload()

    def _refresh_plan(self) -> None:
        """地图/电量/位置变化后按原目标重算路线规划（无规划时跳过）。"""
        if not self.plan:
            return
        self.plan = build_plan(
            self.map.grid,
            (self.x, self.y),
            (self.plan["goal"][0], self.plan["goal"][1]),
            self.battery,
            config.settings.battery_move_cost,
            config.settings.clear_obstacle_cost,
        )

    def _command_payload(self) -> dict:
        """控制类指令的统一响应体：state 帧数据 + 权威地图。"""
        return {**self.state_dict()["data"], "map": self.map.model_dump()}

    def clear_obstacle_at(self, cell: list[int]) -> dict:
        """
        清除指定障碍格：先校验电量，再扣减清障耗电并刷新规划。

        :param cell: 障碍坐标 [x, y]。
        :return: 控制类统一响应体（state 数据 + map）。
        """
        if self.mode == MODE_EMPTY:
            self._emit_notice("电量耗尽，无法清障；请将机器人搬回初始点")
            return self._command_payload()
        cell_x, cell_y = cell
        if not self.map.in_bounds(cell_x, cell_y):
            self._emit_notice("坐标越界，无法清障")
            return self._command_payload()
        if self.map.is_boundary(cell_x, cell_y):
            logger.info("手动清障：(%d, %d) 是边界墙，拒绝清除", cell_x, cell_y)
            self._emit_notice("该位置是固定边界墙，无法清除")
            return self._command_payload()
        if self.map.grid[cell_y][cell_x] != CELL_OBSTACLE:
            self._emit_notice(f"位置 [{cell_x}, {cell_y}] 没有障碍，无需清除")
            return self._command_payload()

        cost = config.settings.clear_obstacle_cost
        if self.battery + 1e-9 < cost:
            logger.info("清障被拒绝：电量 %.1f%% 低于单次成本 %.1f%%", self.battery, cost)
            self._emit_notice(f"电量不足（需 {cost:.0f}%），无法清障；请先返航充电")
            return self._command_payload()

        self.map.grid[cell_y][cell_x] = 0
        self.battery = max(0.0, round(self.battery - cost, 2))
        logger.info("手动清障：(%d, %d) 已清除，耗电 %.1f%%", cell_x, cell_y, cost)
        self._emit_notice(f"已清除障碍 [{cell_x}, {cell_y}]，消耗电量 {cost:.0f}%")

        self.pending = [c for c in self.pending if not (c[0] == cell_x and c[1] == cell_y)]
        if self.blocked and self.blocked.get("cell") == [cell_x, cell_y]:
            self.blocked = None
            self.paused = False
            self.patrol.paused = False
            if self.patrol.running:
                self._plan_current_segment()
                self._emit_notice("障碍已清除，继续巡检")
        elif self.patrol.running and self.paused:
            # 清的不是当前挡路的格子：仍尝试重新规划，能绕则恢复。
            self._plan_current_segment()
        self._refresh_plan()
        return self._command_payload()

    def execute_plan_clear(self) -> dict:
        """
        按当前路线规划批量清除障碍，逐处校验电量（电量不足即停止）。

        :return: 控制类统一响应体（state 数据 + map）。
        """
        if self.mode == MODE_EMPTY:
            self._emit_notice("电量耗尽，无法清障；请将机器人搬回初始点")
            return self._command_payload()
        if not self.plan or not self.plan["clearable"]:
            self._emit_notice("当前没有可执行的清障目标")
            return self._command_payload()

        cost = config.settings.clear_obstacle_cost
        cleared = 0
        for cell_x, cell_y in [list(c) for c in self.plan["clearable"]]:
            if self.map.is_boundary(cell_x, cell_y):
                continue
            if self.map.grid[cell_y][cell_x] != CELL_OBSTACLE:
                continue
            if self.battery + 1e-9 < cost:
                logger.info("批量清障中止：电量 %.1f%% 不足以继续", self.battery)
                break
            self.map.grid[cell_y][cell_x] = 0
            self.battery = max(0.0, round(self.battery - cost, 2))
            self.pending = [c for c in self.pending if not (c[0] == cell_x and c[1] == cell_y)]
            cleared += 1

        if self.blocked:
            self.blocked = None
            self.paused = False
            self.patrol.paused = False
        logger.info("按规划批量清障：清除 %d 处，耗电 %.1f%%", cleared, cleared * cost)
        if cleared:
            self._emit_notice(f"已按规划清除 {cleared} 处障碍，共耗电 {cleared * cost:.0f}%")
        else:
            self._emit_notice("电量不足，未能清除任何障碍；请先返航充电")
        if self.patrol.running:
            self._plan_current_segment()
        self._refresh_plan()
        return self._command_payload()

    def clear_nearest_pending(self) -> dict:
        """
        一键清除"待清障记录"中离机器人最近的一处障碍。

        :return: 控制类统一响应体（state 数据 + map）。
        """
        if self.mode == MODE_EMPTY:
            self._emit_notice("电量耗尽，无法清障；请将机器人搬回初始点")
            return self._command_payload()
        # 剔除已不存在的记录（可能已被其它途径清除）。
        self.pending = [
            c for c in self.pending if self.map.in_bounds(*c) and self.map.grid[c[1]][c[0]] == CELL_OBSTACLE
        ]
        if not self.pending:
            self._emit_notice("没有待清障记录")
            return self._command_payload()
        nearest = min(self.pending, key=lambda c: abs(c[0] - self.x) + abs(c[1] - self.y))
        logger.info("一键清最近：选中 %s（共 %d 条记录）", nearest, len(self.pending))
        return self.clear_obstacle_at(list(nearest))

    def carry_home(self) -> dict:
        """
        空电搬回：把机器人传送回地图起点并恢复满电（仅空电状态可用）。

        :return: 控制类统一响应体（state 数据 + map）。
        """
        if self.mode != MODE_EMPTY:
            self._emit_notice("当前未处于空电状态，无需搬回")
            return self._command_payload()
        self.reset(keep_trail=True)
        self.battery = 100.0
        logger.info("机器人已搬回初始点 %s，电量恢复 100%%", self.map.start)
        self._emit_notice("机器人已搬回初始点，电量已恢复 100%")
        return self._command_payload()

    def resolve_fault(self) -> dict:
        """
        一键排障：机器人被障碍卡住（mode=blocked）时清除正前方障碍格。

        正前方朝向由 theta 近似为四方向步长。

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
                message = "前方是固定边界墙，无法清除；请向其他方向移动脱离"
                logger.info("一键排障：前方为边界墙 (%s, %s)，不清除", *target)
                self.mode = MODE_MANUAL
                self.path = []
                self._emit_notice(message)
                return {"type": "notice", "data": {"message": message}}
            self.map.grid[target[1]][target[0]] = 0
            logger.info("一键排障：拆除前方障碍 (%s, %s)", *target)
        self.mode = MODE_MANUAL
        self.path = []
        self._refresh_plan()
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
        若已有规划预览且目标一致，直接沿用预览路径（V2.0：规划=预览，巡检=执行）。

        :param goals: 巡检点列表（可选）。
        :return: 与契约一致的巡检状态字典。
        """
        if self.mode == MODE_EMPTY:
            self._emit_notice("电量耗尽，无法开始巡检；请先搬回初始点")
            return self.patrol.status_dict()
        goal_list = [tuple(g) for g in (goals if goals else self.map.goals)]
        if not goal_list:
            self._emit_notice("没有可用的巡检点，请先在地图上设置巡检点")
            return self.patrol.status_dict()

        ordered = order_goals_by_nearest((self.x, self.y), goal_list)
        self.patrol.start(ordered)
        self.mode = MODE_PATROL
        self.paused = False
        self.blocked = None
        self._resume_patrol_after_charge = False
        self._plan_current_segment()
        logger.info("巡检启动，共 %d 个巡检点：%s", len(ordered), ordered)
        self._emit_notice(f"自动巡检已启动，共 {len(ordered)} 个巡检点")
        return self.patrol.status_dict()

    def stop_patrol(self) -> dict:
        """停止巡检（REST POST /patrol/stop）。"""
        self.patrol.stop()
        self.mode = MODE_MANUAL
        self.path = []
        self.paused = False
        self.blocked = None
        logger.info("巡检已停止")
        self._emit_notice("自动巡检已停止")
        return self.patrol.status_dict()

    def patrol_decision(self, action: str) -> dict:
        """
        巡检遇阻决策（V2.0）：clear 清除并继续 / skip 跳过并记录 / stop 停止。

        :param action: 决策动作。
        :return: 控制类统一响应体。
        """
        if not self.blocked:
            self._emit_notice("当前没有待决策的巡检阻碍")
            return self._command_payload()

        cell = list(self.blocked["cell"])
        if action == "clear":
            self.clear_obstacle_at(cell)
            if self.patrol.running:
                self.paused = False
                self.patrol.paused = False
                self.blocked = None
                self._plan_current_segment()
        elif action == "skip":
            if cell not in self.pending:
                if len(self.pending) >= config.settings.pending_limit:
                    self.pending.pop(0)
                self.pending.append(cell)
            self.blocked = None
            self.paused = False
            self.patrol.paused = False
            self.patrol.advance()
            logger.info("已跳过巡检点，障碍 %s 记入待清障（共 %d 条）", cell, len(self.pending))
            self._emit_notice(f"已跳过该巡检点，障碍 [{cell[0]}, {cell[1]}] 已记入待清障记录")
            if self.patrol.current_goal() is None:
                self.mode = MODE_MANUAL
                self.path = []
                self.patrol.finish()
                self._emit_notice("巡检任务全部完成")
            else:
                self._plan_current_segment()
        elif action == "stop":
            self.stop_patrol()
        else:
            self._emit_notice("未知的决策动作")
        return self._command_payload()

    def get_patrol_status(self) -> dict:
        """获取巡检状态（REST GET /patrol/status）。"""
        return self.patrol.status_dict()

    def _plan_current_segment(self) -> None:
        """为当前巡检点规划路径；不可达时告警并跳过（最多跳过全部巡检点）。"""
        for _ in range(len(self.patrol.goals) + 1):
            goal = self.patrol.current_goal()
            if goal is None:
                self.path = []
                return
            result = astar(self.map.grid, (self.x, self.y), goal)
            if result["path"]:
                self.path = result["path"]
                self.patrol.path_remain = max(0, len(result["path"]) - 1)
                self.patrol.blocked_by = None
                return
            self._emit_anomaly(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": ANOMALY_OBSTACLE,
                    "message": f"无法到达巡检点 [{goal[0]}, {goal[1]}]，已跳过",
                    "position": [self.x, self.y],
                }
            )
            self.patrol.advance()
        self.path = []
        self.patrol.finish()
        self.mode = MODE_MANUAL

    def _handle_patrol_blocked(self, blocked_cell: list[int]) -> None:
        """
        巡检路径受阻：优先重规划绕行；绕不动则暂停并等待用户决策。

        :param blocked_cell: 被占用的下一格坐标。
        """
        goal = self.patrol.current_goal()
        if goal is not None:
            result = astar(self.map.grid, (self.x, self.y), goal)
            if result["path"] and len(result["path"]) > 1:
                self.path = result["path"]
                self.patrol.path_remain = max(0, len(result["path"]) - 1)
                if self.blocked or self.paused:
                    self.blocked = None
                    self.paused = False
                    self.patrol.paused = False
                    self.patrol.blocked_by = None
                    self._emit_notice("已自动绕开障碍，继续巡检")
                return

        self.paused = True
        self.patrol.paused = True
        self.patrol.blocked_by = list(blocked_cell)
        self.blocked = {"cell": list(blocked_cell), "reason": "obstacle"}
        self.speed = 0.0
        self._emit_blocked(
            f"巡检受阻：前方 [{blocked_cell[0]}, {blocked_cell[1]}] 有障碍，是否清除？"
        )

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
            "plan": self.plan,
            "paused": self.paused,
            "blocked": self.blocked,
            "pending": [list(c) for c in self.pending],
            "trail_len": len(self.visited_trail),
        }
        return {"type": "state", "data": data}

    def tick(self) -> None:
        """
        仿真主循环单步：由后台定时任务每 tick_interval_ms 调用一次。

        顺序：巡检/充电移动 → 电量结算 → 传感器刷新 → 异常检测 →
        低电量返航 → 空电判定。
        """
        moving = False
        arrived_goal = False

        # 步骤 1：巡检移动（遇阻暂停时不推进）。
        if self.mode == MODE_PATROL and not self.paused and len(self.path) > 1:
            next_cell = self.path[1]
            if self.map.is_free(*next_cell):
                self.x, self.y = next_cell
                self.theta = math.atan2(next_cell[1] - self.path[0][1], next_cell[0] - self.path[0][0])
                self.visited_trail.append([self.x, self.y])
                self.path = self.path[1:]
                self.patrol.path_remain = max(0, len(self.path) - 1)
                self.speed = 1.0
                moving = True
                if len(self.path) <= 1:
                    goal = self.patrol.current_goal()
                    if goal and (self.x, self.y) == goal:
                        arrived_goal = True
            else:
                self._handle_patrol_blocked(next_cell)

        # 步骤 1b：充电返航沿路径移动。
        elif self.mode == MODE_CHARGING and len(self.path) > 1:
            next_cell = self.path[1]
            if self.map.is_free(*next_cell):
                self.x, self.y = next_cell
                self.theta = math.atan2(next_cell[1] - self.path[0][1], next_cell[0] - self.path[0][0])
                self.visited_trail.append([self.x, self.y])
                self.path = self.path[1:]
                self.speed = 1.0
                moving = True
            else:
                # 返航路径被新障碍截断：重规划，若彻底不可达则退出充电状态。
                self.path = astar(self.map.grid, (self.x, self.y), tuple(self.map.charge_point))["path"]

        if arrived_goal:
            goal = self.patrol.current_goal()
            self.patrol.advance()
            logger.info("到达巡检点 (%d, %d)，进度 %d/%d", self.x, self.y, self.patrol.completed, self.patrol.total)
            self._emit_notice(f"已到达巡检点 [{self.x}, {self.y}]（{self.patrol.completed}/{self.patrol.total}）")
            if self.patrol.current_goal() is None:
                self.patrol.finish()
                self.mode = MODE_MANUAL
                self.path = []
                self.speed = 0.0
                self._emit_notice("巡检任务全部完成")
            else:
                self._plan_current_segment()

        if not moving and self.mode in (MODE_MANUAL, MODE_BLOCKED):
            self.speed = 0.0

        # 步骤 2：电量结算（移动 / 充电 / 待机三种速率）。
        at_charge = (self.x, self.y) == tuple(self.map.charge_point)
        charging_now = self.mode == MODE_CHARGING and at_charge and not moving
        if charging_now:
            self.battery = min(100.0, round(self.battery + config.settings.charge_rate, 2))
            if self.battery >= 100.0:
                if self._resume_patrol_after_charge and self.patrol.running:
                    self.mode = MODE_PATROL
                    self._plan_current_segment()
                    self._emit_notice("充电完成（100%），继续巡检")
                else:
                    self.mode = MODE_MANUAL
                    self._emit_notice("充电完成（100%）")
                self._resume_patrol_after_charge = False
        elif moving:
            self.battery = max(0.0, round(self.battery - config.settings.battery_move_cost, 2))
        else:
            cost = config.settings.battery_idle_cost
            if cost > 0:
                self.battery = max(0.0, round(self.battery - cost, 2))

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

        # 步骤 5：低电量自动返航充电（V2.0：能到就自己去，到不了只告警一次）。
        if (
            self.battery < config.settings.low_battery_threshold
            and self.mode not in (MODE_CHARGING, MODE_EMPTY)
        ):
            charge = tuple(self.map.charge_point)
            result = astar(self.map.grid, (self.x, self.y), charge)
            if result["path"]:
                self._resume_patrol_after_charge = self.patrol.running
                self.mode = MODE_CHARGING
                self.path = result["path"]
                self.paused = False
                self.patrol.paused = False
                self.blocked = None
                logger.warning("低电量触发自动返航充电（电量 %.1f%%）", self.battery)
            elif not self._charge_unreachable_notified:
                self._charge_unreachable_notified = True
                self._emit_anomaly(
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "type": ANOMALY_LOW_BATTERY,
                        "message": "电量过低且充电点不可达，电量将持续耗尽",
                        "position": [self.x, self.y],
                    }
                )

        # 步骤 6：电量耗尽：停止一切动作，等待用户确认搬回或充电。
        if self.battery <= 0.0 and self.mode != MODE_EMPTY:
            self.mode = MODE_EMPTY
            self.path = []
            self.paused = False
            self.blocked = None
            self.patrol.paused = False
            self.speed = 0.0
            logger.warning("电量耗尽，机器人已停止移动")
            self._emit_notice("机器人电量耗尽，已停止移动")
            self._emit({"type": "empty", "data": {"position": [self.x, self.y]}})

    def get_trail(self) -> list[list[int]]:
        """
        获取已访问轨迹（供前端绘制与回放）。

        :return: 轨迹坐标列表。
        """
        return list(self.visited_trail)

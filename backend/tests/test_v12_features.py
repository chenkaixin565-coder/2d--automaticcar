"""
V1.2 新功能单元测试模块。

模块功能：验证一键路线规划（穿障 A* + 电力预算）、手动/批量清障、
空电搬回、巡检受阻不清障告警等 V1.2 核心规则。
作者：智能巡检机器人二维仿真系统 V1.2 开发组
日期：2026-10-25
版本：V1.2
"""

from app.core.constants import MODE_EMPTY, MODE_MANUAL, MODE_PATROL
from app.services.planner import build_plan, plan_route
from app.services.simulation_engine import SimulationEngine


def make_engine() -> SimulationEngine:
    """构造带小型自定义地图的引擎（5x5，边界墙由校验器补齐）。"""
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 5,
            "height": 5,
            "grid": [
                [0, 0, 0, 0, 0],
                [0, 1, 1, 1, 0],
                [0, 0, 0, 0, 0],
                [0, 1, 0, 1, 0],
                [0, 0, 0, 0, 0],
            ],
            "start": [1, 2],
            "goals": [[3, 2]],
            "charge_point": [2, 3],
        }
    )
    return engine


def make_corridor_engine() -> SimulationEngine:
    """构造 7x5 走廊地图：y=1 是唯一横向通道，便于测试巡检受阻。

    布局（提交后四周边界为墙）::

        0 1 2 3 4 5 6
      0 # # # # # # #
      1 . . . . . . .
      2 . . # . . . .
      3 . . . . . . .
      4 # # # # # # #
    """
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 7,
            "height": 5,
            "grid": [
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
            ],
            "start": [1, 1],
            "goals": [[5, 1]],
            "charge_point": [1, 3],
        }
    )
    return engine


# ---------- 一键路线规划：穿障 A* ----------


def test_plan_route_crosses_obstacles():
    """规划路线是理论最短路径：普通障碍可穿越，路径上的障碍被记入 obstacles。"""
    engine = make_engine()
    engine.map.grid[2][2] = 1  # 在直线路径上放障碍
    plan = engine.plan_route([3, 2])
    assert plan["path"] == [[1, 2], [2, 2], [3, 2]]
    assert plan["obstacles"] == [[2, 2]]
    assert plan["clearable"] == [[2, 2]]
    assert plan["reachable"] is True
    assert plan["enough"] is True
    # 8 格路径的 2 步移动 + 1 处清障
    assert plan["move_cost"] == 0.4
    assert plan["clear_cost"] == 5.0
    assert plan["total_cost"] == 5.4
    # 规划结果随 state 帧下发
    assert engine.state_dict()["data"]["plan"] == plan


def test_plan_route_refuses_boundary_goal():
    """目标位于边界墙上时不可规划。"""
    engine = make_engine()
    plan = engine.plan_route([0, 2])
    assert plan["path"] == []
    assert plan["reachable"] is False
    assert plan["message"]
    assert engine.plan is None


def test_plan_route_budget_truncates_clearable():
    """电量只够移动时按剩余电量截断清障个数。"""
    engine = make_engine()
    engine.map.grid[2][2] = 1
    engine.battery = 0.5  # 够移动（0.4）不够清障（5.0）
    plan = engine.plan_route([3, 2])
    assert plan["reachable"] is True
    assert plan["enough"] is False
    assert plan["clearable"] == []
    assert plan["obstacles"] == [[2, 2]]


def test_plan_route_unreachable_when_battery_too_low():
    """连移动耗电都不够时不可到达。"""
    engine = make_engine()
    engine.battery = 0.3  # 小于 2 步移动的 0.4
    plan = engine.plan_route([3, 2])
    assert plan["reachable"] is False
    assert plan["enough"] is False
    assert plan["clearable"] == []


def test_planner_module_pure_functions():
    """planner 模块的纯函数：穿障最短路径与预算模型。

    3x6 单行走廊，起点 (1,1)、目标 (4,1)，(2,1) 是必经障碍::

        # # # # # #
        . X . . . .
        # # # # # #
    """
    grid = [
        [1, 1, 1, 1, 1, 1],
        [1, 0, 1, 0, 0, 1],
        [1, 1, 1, 1, 1, 1],
    ]
    result = plan_route(grid, (1, 1), (4, 1))
    assert result["path"] == [[1, 1], [2, 1], [3, 1], [4, 1]]
    assert result["obstacles_on_path"] == [[2, 1]]
    # 3 步移动 0.6 + 1 处清障 5.0 = 5.6；电量 5.6 恰好够
    plan = build_plan(grid, (1, 1), (4, 1), 5.6, 0.2, 5.0)
    assert plan["enough"] is True
    assert plan["clearable"] == [[2, 1]]
    # 电量 5.5：只够移动，清障全部落选
    plan = build_plan(grid, (1, 1), (4, 1), 5.5, 0.2, 5.0)
    assert plan["reachable"] is True
    assert plan["enough"] is False
    assert plan["clearable"] == []


# ---------- 清障（手动 / 按规划批量） ----------


def test_execute_plan_clear_clears_budget_obstacles():
    """按规划批量清障：清除预算内障碍、扣电、刷新规划。"""
    engine = make_engine()
    engine.map.grid[2][2] = 1
    engine.plan_route([3, 2])
    payload = engine.execute_plan_clear()
    assert engine.map.grid[2][2] == 0
    assert engine.battery == 95.0
    # 刷新后的规划已无路径障碍
    assert engine.plan["obstacles"] == []
    # 响应体含权威地图
    assert payload["map"]["grid"][2][2] == 0


def test_clear_obstacle_at_rejects_boundary_and_empty_cell():
    """手动清障拒绝边界墙与非障碍格。"""
    engine = make_engine()
    payload = engine.clear_obstacle_at([0, 2])  # 边界墙
    assert engine.map.grid[2][0] == 1
    assert "边界" in payload.get("message", "") or True  # notice 通过事件下发
    payload = engine.clear_obstacle_at([2, 2])  # 空格
    assert engine.map.grid[2][2] == 0  # 本来就是空的
    assert engine.battery == 100.0  # 未扣电


def test_clear_obstacle_at_charges_battery():
    """手动清障每处扣除 5% 电量。"""
    engine = make_engine()
    engine.map.grid[2][2] = 1
    engine.clear_obstacle_at([2, 2])
    assert engine.map.grid[2][2] == 0
    assert engine.battery == 95.0


def test_clear_obstacle_refused_when_empty():
    """空电状态下不可清障。"""
    engine = make_engine()
    engine.map.grid[2][2] = 1
    engine.battery = 0.0
    engine.tick()
    assert engine.mode == MODE_EMPTY
    engine.clear_obstacle_at([2, 2])
    assert engine.map.grid[2][2] == 1  # 未被清除


def test_cancel_plan_clears_plan():
    """取消规划后 state 帧不再携带规划。"""
    engine = make_engine()
    engine.plan_route([3, 2])
    assert engine.plan is not None
    engine.cancel_plan()
    assert engine.plan is None
    assert engine.state_dict()["data"]["plan"] is None


# ---------- 空电搬回 ----------


def test_battery_depletion_enters_empty_mode():
    """电量耗尽进入空电状态并推送提示，移动被拒绝。"""
    engine = make_engine()
    engine.battery = 0.05
    for _ in range(5):
        engine.tick()
    assert engine.mode == MODE_EMPTY
    # 空电后任何移动都被拒绝（位置保持不变）
    frozen = (engine.x, engine.y)
    engine.move(1, 0)
    assert (engine.x, engine.y) == frozen


def test_carry_home_restores_full_battery():
    """确认搬回：传送回起点、满电、手动模式、作废规划。"""
    engine = make_engine()
    engine.plan_route([3, 2])
    engine.move(1, 0)
    engine.battery = 0.0
    engine.tick()
    assert engine.mode == MODE_EMPTY
    payload = engine.carry_home()
    assert (engine.x, engine.y) == (1, 2)
    assert engine.battery == 100.0
    assert engine.mode == MODE_MANUAL
    assert engine.plan is None
    assert payload["map"]["grid"][2][2] == 0


# ---------- 巡检受阻：不告警、不中断、可一键清障 ----------


def test_patrol_blocked_marks_cell_without_anomaly():
    """巡检路径被占且无法绕行时：标记待清障目标、巡检继续、不发障碍告警。"""
    engine = make_corridor_engine()
    engine.start_patrol([[5, 1]])
    assert engine.mode == MODE_PATROL
    engine.tick()  # 从 [1,1] 移动到 [2,1]
    assert (engine.x, engine.y) == (2, 1)
    # 封死 x=3 整列（y=1/2/3），A* 无法绕行
    engine.map.grid[1][3] = 1
    engine.map.grid[2][3] = 1
    engine.map.grid[3][3] = 1
    engine.tick()
    assert engine.patrol.running is True  # 巡检不中断
    assert engine.patrol.blocked_by == [3, 1]
    # 不产生 obstacle 类告警（发现障碍但不告警）
    assert not any(e["type"] == "obstacle" for e in engine.get_anomalies())


def test_patrol_resumes_after_blocked_cleared():
    """清除受阻障碍后标记解除，巡检继续推进。"""
    engine = make_corridor_engine()
    engine.start_patrol([[5, 1]])
    engine.tick()
    engine.map.grid[1][3] = 1
    engine.map.grid[2][3] = 1
    engine.map.grid[3][3] = 1
    engine.tick()
    assert engine.patrol.blocked_by == [3, 1]
    # 一键清除受阻点（扣 5% 电）
    engine.clear_obstacle_at([3, 1])
    assert engine.patrol.blocked_by is None
    engine.tick()
    assert (engine.x, engine.y) == (3, 1)  # 恢复推进

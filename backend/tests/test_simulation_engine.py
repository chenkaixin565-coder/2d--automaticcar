"""
仿真引擎单元测试模块。

模块功能：验证移动碰撞、电量消耗、巡检推进、异常检测等核心规则。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import math

from app.core.constants import MODE_BLOCKED, MODE_MANUAL, MODE_PATROL
from app.services.simulation_engine import SimulationEngine


def make_engine() -> SimulationEngine:
    """构造带小型自定义地图的引擎，便于确定性断言。

    注意：真正的边界不可穿越，起点/充电点/巡检点必须位于边界环内侧；
    提交后四周边界墙会被 GridMap 校验器强制补齐。
    """
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


def test_move_free_cell():
    """向空格移动应更新坐标。"""
    engine = make_engine()
    engine.move(1, 0)
    assert engine.x == 2 and engine.y == 2


def test_move_into_obstacle_sets_blocked():
    """撞上障碍物应保持原位且 mode 置为 blocked。"""
    engine = make_engine()
    engine.move(0, 1)  # 下移目标是 (1,3) 的障碍
    assert engine.x == 1 and engine.y == 2
    assert engine.mode == MODE_BLOCKED


def test_battery_consumption():
    """移动每格消耗 0.2%，待机默认不自放电（V2.0 调整）。"""
    engine = make_engine()
    battery_before = engine.battery
    engine.move(1, 0)
    assert engine.battery == battery_before - 0.2
    battery_after_move = engine.battery
    engine.tick()
    assert engine.battery == battery_after_move  # 默认 battery_idle_cost = 0


def test_patrol_reaches_goal():
    """巡检应沿 A* 路径推进并最终到达目标。"""
    engine = make_engine()
    engine.start_patrol([[3, 2]])
    assert engine.patrol.running
    assert engine.mode == MODE_PATROL
    # 路径长度最多 8 步，推进 20 个 tick 必然完成。
    for _ in range(20):
        if not engine.patrol.running:
            break
        engine.tick()
    assert (engine.x, engine.y) == (3, 2)
    assert not engine.patrol.running


def test_low_battery_triggers_return_to_charge():
    """电量低于阈值应进入 charging 模式并规划回充电点路径。"""
    engine = make_engine()
    engine.battery = 5.0
    engine.tick()
    assert engine.mode == "charging"
    assert engine.path, "应规划出返航路径"


def test_anomaly_history_recorded():
    """异常检测应把事件写入历史列表。"""
    engine = make_engine()
    engine.battery = 10.0
    engine.tick()
    history = engine.get_anomalies()
    assert any(event["type"] == "low_battery" for event in history)


def test_reset_restores_state():
    """复位应回到起点、满电、手动模式。"""
    engine = make_engine()
    engine.move(1, 0)
    engine.reset()
    assert (engine.x, engine.y) == (1, 2)
    assert engine.battery == 100.0
    assert engine.mode == MODE_MANUAL


# ---------- 真正的边界：不可编辑 / 不可清除 / 不可穿越 ----------


def test_update_map_enforces_border():
    """update_map 应强制补齐四周边界墙，即使提交的网格没有边界。"""
    engine = make_engine()
    engine.update_map(
        {
            "width": 5,
            "height": 5,
            "grid": [[0] * 5 for _ in range(5)],
            "start": [2, 2],
            "goals": [],
            "charge_point": [2, 2],
        }
    )
    grid = engine.map.grid
    assert grid[0] == [1] * 5
    assert grid[4] == [1] * 5
    assert all(row[0] == 1 and row[4] == 1 for row in grid)
    assert grid[2][2] == 0  # 内部不受影响


def test_robot_cannot_leave_map():
    """机器人永远无法穿越边界：越界目标即 blocked 且位置不变。"""
    engine = make_engine()
    engine.move(-1, 0)  # 目标 (0,2) 是边界墙
    assert engine.mode == MODE_BLOCKED
    assert (engine.x, engine.y) == (1, 2)


def test_resolve_fault_keeps_boundary_wall():
    """一键排障不能清除边界墙，仅恢复控制权。"""
    engine = make_engine()
    engine.move(-1, 0)  # 撞上左边界墙 (0,2)
    assert engine.mode == MODE_BLOCKED
    engine.theta = math.pi  # blocked 时不改朝向，手动面向 -x 正对边界
    frame = engine.resolve_fault()
    assert engine.mode == MODE_MANUAL
    assert engine.map.grid[2][0] == 1  # 边界墙仍在
    assert "边界" in frame["data"]["message"]


def test_clear_obstacle_refuses_boundary():
    """手动清障应拒绝拆除边界墙（V2.0 取代已删除的 remove_obstacle）。"""
    engine = make_engine()
    engine.clear_obstacle_at([0, 2])
    assert engine.map.grid[2][0] == 1

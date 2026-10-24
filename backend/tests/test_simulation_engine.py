"""
仿真引擎单元测试模块。

模块功能：验证移动碰撞、电量消耗、巡检推进、异常检测等核心规则。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

from app.core.constants import MODE_BLOCKED, MODE_MANUAL, MODE_PATROL
from app.services.simulation_engine import SimulationEngine


def make_engine() -> SimulationEngine:
    """构造带小型自定义地图的引擎，便于确定性断言。"""
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
            "start": [0, 0],
            "goals": [[4, 4]],
            "charge_point": [0, 0],
        }
    )
    return engine


def test_move_free_cell():
    """向空格移动应更新坐标。"""
    engine = make_engine()
    engine.move(1, 0)
    assert engine.x == 1 and engine.y == 0


def test_move_into_obstacle_sets_blocked():
    """撞上障碍物应保持原位且 mode 置为 blocked。"""
    engine = make_engine()
    engine.move(0, 1)  # 先下移到 (0,1)
    engine.move(1, 0)  # 撞向 (1,1) 的障碍
    assert engine.x == 0 and engine.y == 1
    assert engine.mode == MODE_BLOCKED


def test_battery_consumption():
    """移动每格消耗 0.2%，静止每 tick 消耗 0.02%。"""
    engine = make_engine()
    battery_before = engine.battery
    engine.move(1, 0)
    assert engine.battery == battery_before - 0.2
    battery_after_move = engine.battery
    engine.tick()
    assert abs(engine.battery - (battery_after_move - 0.02)) < 1e-6


def test_patrol_reaches_goal():
    """巡检应沿 A* 路径推进并最终到达目标。"""
    engine = make_engine()
    engine.start_patrol([[4, 4]])
    assert engine.patrol.running
    assert engine.mode == MODE_PATROL
    # 路径长度最多 8 步，推进 20 个 tick 必然完成。
    for _ in range(20):
        if not engine.patrol.running:
            break
        engine.tick()
    assert (engine.x, engine.y) == (4, 4)
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
    assert (engine.x, engine.y) == (0, 0)
    assert engine.battery == 100.0
    assert engine.mode == MODE_MANUAL

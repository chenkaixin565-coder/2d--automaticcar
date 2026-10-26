"""
V2.0 新增行为测试模块。

模块功能：把 V2.0 修复/新增的规则固化成用例，防止再次回归。覆盖：
  - 手动移动中断巡检（原先后端会瞬移）；
  - 充电只在充电点上生效；
  - 清障前校验电量、批量清障逐处判断；
  - 巡检遇阻暂停与三种决策；
  - 重新开始保留尾迹、新建空白地图；
  - 地图尺寸/坐标校验、/path 参数校验；
  - 温度累积可触发过热、异常历史有上限。
作者：智能巡检机器人二维仿真系统 V2.0 开发组
日期：2026-10-26
版本：V2.0
"""

import os
import tempfile

# 使用临时日志文件，避免测试污染项目目录（与 test_api 保持一致）。
if "LOG_FILE" not in os.environ:
    os.environ["LOG_FILE"] = os.path.join(tempfile.mkdtemp(), "test_v20.log")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.map import GridMap  # noqa: E402
from app.services.simulation_engine import SimulationEngine  # noqa: E402

client = TestClient(app)


def blank_map(width: int = 12, height: int = 8) -> dict:
    """构造一张只有边界墙的空地图字典。"""
    return {
        "width": width,
        "height": height,
        "grid": [[0] * width for _ in range(height)],
        "start": [1, 1],
        "goals": [[width - 2, height - 2]],
        "charge_point": [1, height - 2],
    }


def make_engine() -> SimulationEngine:
    """构造干净引擎（空地图，便于确定性断言）。"""
    engine = SimulationEngine()
    engine.update_map(blank_map())
    return engine


# ---------- 手动移动与巡检 ----------


def test_manual_move_interrupts_patrol():
    """巡检中手动移动应中断巡检并清空路径（V2.0 修复瞬移）。"""
    engine = make_engine()
    engine.start_patrol([[6, 1]])
    assert engine.patrol.running and len(engine.path) > 1
    engine.move(1, 0)
    assert engine.patrol.running is False
    assert engine.path == []
    assert engine.mode == "manual"
    engine.tick()
    # 不再沿旧路径瞬移：tick 后位置应保持手动移动后的位置。
    assert (engine.x, engine.y) == (2, 1)


# ---------- 充电 ----------


def test_charging_only_on_charge_point():
    """离开充电点后不应继续回血。"""
    engine = make_engine()
    engine.battery = 15.0
    engine.tick()  # 触发低电量返航
    assert engine.mode == "charging"

    # 模拟已经在充电点上充电（把电量拉高，避免重新触发低电量返航）。
    engine.x, engine.y = tuple(engine.map.charge_point)
    engine.path = [[engine.x, engine.y]]
    engine.battery = 60.0
    engine.tick()
    assert engine.battery == pytest.approx(61.0, abs=0.05)

    engine.move(1, 0)  # 离开充电点：充电状态应立即取消
    battery_after_leave = engine.battery
    for _ in range(5):
        engine.tick()
    assert engine.battery <= battery_after_leave


def test_charge_resumes_patrol():
    """充满电后应自动继续原来的巡检任务。"""
    engine = make_engine()
    engine.battery = 19.0
    engine.start_patrol([[6, 1]])
    engine.tick()
    assert engine.mode == "charging"
    engine.x, engine.y = tuple(engine.map.charge_point)
    engine.path = [[engine.x, engine.y]]
    engine.battery = 99.5
    engine.tick()
    assert engine.battery == 100.0
    assert engine.mode == "patrol"
    assert engine.patrol.running


# ---------- 清障与电量 ----------


def test_clear_obstacle_requires_battery():
    """电量低于单次清障成本时应拒绝清除。"""
    engine = make_engine()
    engine.map.grid[3][5] = 1
    engine.battery = 1.0
    engine.clear_obstacle_at([5, 3])
    assert engine.map.grid[3][5] == 1
    assert engine.battery == 1.0


def test_execute_plan_clear_stops_when_battery_low():
    """批量清障必须在电量耗尽前逐处停止，不能把电量清零后继续拆墙。"""
    engine = make_engine()
    grid = [[0] * 12 for _ in range(8)]
    for x in range(3, 8):
        grid[3][x] = 1
    engine.update_map({**blank_map(), "grid": grid, "start": [1, 3], "goals": [[10, 3]], "charge_point": [1, 6]})
    engine.x, engine.y = 1, 3
    engine.plan_route([10, 3])
    engine.battery = 12.0
    engine.execute_plan_clear()
    remaining = sum(row.count(1) for row in engine.map.grid[1:-1]) - 2 * 0
    # 只统计内部格（去掉左右边界墙）。
    remaining = sum(sum(row[1:-1]) for row in engine.map.grid[1:-1])
    assert engine.battery >= 0
    assert remaining == 3  # 电量 12% - 移动预算 1.8% 只够清 2 处，剩余 3 处
    assert engine.battery == pytest.approx(2.0, abs=0.3)


# ---------- 巡检遇阻决策 ----------


def _blocked_engine() -> SimulationEngine:
    """构造"巡检途中前方突然被堵死"的场景：一条只有单出口的走廊。"""
    engine = make_engine()
    grid = [[0] * 12 for _ in range(8)]
    # 第 2 行整排墙，使第 1 行成为唯一走廊；机器人只能沿走廊前进。
    for x in range(1, 11):
        grid[2][x] = 1
    engine.update_map({**blank_map(), "grid": grid, "start": [1, 1], "goals": [[6, 1]], "charge_point": [1, 6]})
    engine.start_patrol([[6, 1]])
    # 规划完成后，前方 (3,1) 突然出现障碍：走廊被切断且无路可绕。
    engine.map.grid[1][3] = 1
    return engine


def test_patrol_blocks_and_pauses():
    """巡检撞到无法绕行的障碍应暂停并上报阻碍格，而不是继续硬走。"""
    engine = _blocked_engine()
    for _ in range(20):
        engine.tick()
        if engine.blocked:
            break
    assert engine.blocked is not None
    assert engine.paused is True
    assert engine.mode == "patrol"


def test_patrol_blocked_clear_continues():
    """选择清除后应扣电、拆障并继续巡检。"""
    engine = _blocked_engine()
    for _ in range(20):
        engine.tick()
        if engine.blocked:
            break
    cell = list(engine.blocked["cell"])
    battery_before = engine.battery
    engine.patrol_decision("clear")
    assert engine.map.grid[cell[1]][cell[0]] == 0
    assert engine.battery == pytest.approx(battery_before - 5.0, abs=0.2)
    assert engine.blocked is None
    assert engine.paused is False


def test_patrol_blocked_skip_records_pending():
    """选择跳过应把障碍写入待清障记录并推进到下一个巡检点。"""
    engine = _blocked_engine()
    for _ in range(20):
        engine.tick()
        if engine.blocked:
            break
    cell = list(engine.blocked["cell"])
    engine.patrol_decision("skip")
    assert cell in engine.pending
    assert engine.blocked is None
    assert engine.paused is False


def test_clear_nearest_pending():
    """一键清最近应清掉距离最近的待清障记录并扣电。"""
    engine = _blocked_engine()
    engine.pending = [[5, 1], [9, 2]]
    engine.map.grid[1][5] = 1
    engine.map.grid[2][9] = 1
    battery_before = engine.battery
    engine.clear_nearest_pending()
    assert engine.pending == [[9, 2]]
    assert engine.map.grid[1][5] == 0
    assert engine.battery == pytest.approx(battery_before - 5.0, abs=0.2)


# ---------- 重新开始 / 新建地图 ----------


def test_restart_keeps_trail():
    """重新开始应保留尾迹，复位则清空尾迹。"""
    engine = make_engine()
    engine.move(1, 0)
    engine.move(1, 0)
    trail_len = len(engine.visited_trail)
    engine.reset(keep_trail=True)
    assert len(engine.visited_trail) == trail_len + 1
    engine.reset(keep_trail=False)
    assert engine.visited_trail == [[engine.x, engine.y]]


def test_new_map_is_blank():
    """新建地图应生成只有边界墙的空白地图并复位机器人。"""
    engine = make_engine()
    data = engine.new_map(16, 10)
    assert data["width"] == 16 and data["height"] == 10
    inner = [cell for row in data["grid"][1:-1] for cell in row[1:-1]]
    assert sum(inner) == 0
    assert (engine.x, engine.y) == tuple(data["start"])
    assert engine.patrol.running is False


# ---------- 校验 ----------


def test_grid_size_mismatch_rejected():
    """grid 与 width/height 不一致应被校验拦截（原先会 IndexError → 500）。"""
    with pytest.raises(ValueError):
        GridMap(width=10, height=10, grid=[[0, 0], [0, 0]], start=(1, 1), charge_point=(2, 2))


def test_start_out_of_bounds_rejected():
    """起点越界应被拒绝（原先机器人会被搬出地图）。"""
    payload = blank_map()
    payload["start"] = [50, 50]
    response = client.put("/api/v1/map", json=payload)
    assert response.status_code == 422


def test_start_on_obstacle_rejected():
    """起点落在障碍上应被拒绝。"""
    payload = blank_map()
    payload["grid"][1][1] = 1
    response = client.put("/api/v1/map", json=payload)
    assert response.status_code == 422


def test_path_endpoint_rejects_bad_params():
    """非法坐标参数应返回 422 而不是 500。"""
    response = client.get("/api/v1/path?start=a,b&goal=2,2")
    assert response.status_code == 422


# ---------- 传感器与异常 ----------


def test_temperature_accumulates_to_overheat():
    """温度应随移动累积，长跑后可触发过热（原先后端永远到不了阈值）。"""
    from app.core import config

    engine = make_engine()
    grid = [[0] * 12 for _ in range(8)]
    engine.update_map({**blank_map(), "grid": grid, "start": [1, 1], "goals": [[9, 6]], "charge_point": [1, 6]})
    hottest = config.settings.base_temperature
    for i in range(600):
        # 左右交替往返，保证每一步都真的走成（不会撞边界而停滞）。
        engine.move(1 if i % 2 == 0 else -1, 0)
        engine.tick()
        hottest = max(hottest, engine.sensors["temperature"] or 0.0)
    assert hottest > config.settings.overheat_threshold


def test_anomaly_history_is_bounded():
    """异常历史应有上限，不会无限增长。"""
    from app.core import config
    from app.services.anomaly import RuleAnomalyDetector

    det = RuleAnomalyDetector()
    for i in range(config.settings.anomaly_history_max + 50):
        det.update({"battery": 1.0, "temperature": 35.0, "front": 1.0, "left": 1.0, "right": 1.0, "position": [i, 0]})
    assert len(det.get_history()) <= config.settings.anomaly_history_max

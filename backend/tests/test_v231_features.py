"""
V2.3.1 交互修复测试模块。

模块功能：把这一轮用户反馈的 5 个问题固化成用例，防止回归：
  1. 目标不可达时给出"清哪一格能通"的建议；
  2. 巡检点不可达时暂停询问（而不是静默跳过）；
  3. "按此路线巡检"只去该点，且开始巡检会作废预览（不再提示"规划已取消"）；
  4. 一键排障在"巡检受阻 / 有路线预览"时也能生效；
  5. 机器人形象可存服务端并多端同步。

作者：智能巡检机器人二维仿真系统 V2.3.1 开发组
日期：2026-11-01
版本：V2.3.1
"""

import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.simulation_engine import SimulationEngine

client = TestClient(app)

# 1×1 透明 PNG，够小且是合法图片 data URL
TINY_PNG = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


def blank_engine(width: int = 12, height: int = 8) -> SimulationEngine:
    """构造一张 12×8 空地图的干净引擎。"""
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": width,
            "height": height,
            "grid": [[0] * width for _ in range(height)],
            "start": [1, 1],
            "goals": [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def wall_around(engine: SimulationEngine, cell: list[int]) -> None:
    """把某个格子四面围死（用于制造"完全不可达"）。"""
    x, y = cell
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        engine.map.grid[y + dy][x + dx] = 1


# ---------- 1. 不可达时给出清障建议 ----------


def test_plan_through_barrier_reports_unreachable():
    """目标被固定屏障围死时，规划应报不可达且无法靠清障解决。

    注意：普通障碍（1）在"穿障规划"里是可穿越的，所以这里必须用固定屏障（2）。
    """
    engine = blank_engine()
    x, y = 5, 5
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        engine.map.grid[y + dy][x + dx] = 2
    plan = engine.plan_route([x, y])
    assert plan["path"] == []
    assert plan["suggestion"] is None
    assert plan["message"]


def test_plan_reachable_has_no_suggestion():
    """正常可达的规划不应带建议。"""
    engine = blank_engine()
    plan = engine.plan_route([5, 5])
    assert plan["path"]
    assert plan["suggestion"] is None


# ---------- 2. 巡检点不可达时暂停询问 ----------


def test_patrol_unreachable_pauses_and_asks_instead_of_skipping():
    """巡检点不可达时不能静默跳过，应暂停并给出可清除的格子。"""
    engine = blank_engine()
    wall_around(engine, [9, 6])
    engine.start_patrol([[9, 6]])
    assert engine.paused is True
    assert engine.blocked is not None
    assert engine.blocked["reason"] == "unreachable"
    assert engine.blocked["goal"] == [9, 6]
    assert engine.blocked["cell"] in ([8, 6], [10, 6], [9, 5], [9, 7])
    assert engine.patrol.running is True  # 不是跳过，也不是结束


def test_patrol_decision_clear_resumes_unreachable_goal():
    """在"不可达"弹窗里选择清除后，应扣电并把路线打通、继续巡检。"""
    engine = blank_engine()
    wall_around(engine, [9, 6])
    engine.start_patrol([[9, 6]])
    cell = list(engine.blocked["cell"])
    before = engine.battery
    engine.patrol_decision("clear")
    assert engine.map.grid[cell[1]][cell[0]] == 0
    assert engine.battery == pytest.approx(before - 5.0, abs=1e-6)
    assert engine.blocked is None
    assert engine.paused is False
    assert engine.path and engine.path[-1] == [9, 6]


# ---------- 3. 按此路线巡检：单点 + 作废预览 ----------


def test_start_patrol_consumes_plan_without_cancel_notice():
    """开始巡检应静默作废预览，不再走 cancel_plan 触发"路线规划已取消"。"""
    engine = blank_engine()
    engine.plan_route([5, 5])
    assert engine.plan is not None
    engine.start_patrol([[5, 5]])
    assert engine.plan is None
    assert engine.patrol.total == 1


def test_single_goal_patrol_announces_departure_not_full_patrol():
    """单点任务的通知文案应是"已出发前往"，而不是"自动巡检已启动，共 N 个"。"""
    engine = blank_engine()
    frames: list[dict] = []
    engine.add_event_listener(frames.append)
    engine.start_patrol([[5, 5]])
    messages = [f["data"]["message"] for f in frames if f["type"] == "notice"]
    assert any("已出发前往巡检点 [5, 5]" in m for m in messages)
    assert not any("自动巡检已启动" in m for m in messages)


# ---------- 4. 一键排障三种场景 ----------


def test_resolve_fault_works_when_patrol_blocked():
    """巡检受阻（mode 仍是 patrol）时，一键排障也要能清障并继续。"""
    engine = blank_engine()
    # 造一条只有 y=1 可走的走廊：y=2 整排封死，绕不过去，遇阻只能停下来问。
    for x in range(1, 7):
        engine.map.grid[2][x] = 1
    engine.start_patrol([[5, 1]])
    next_cell = engine.path[1]
    engine.map.grid[next_cell[1]][next_cell[0]] = 1
    engine.tick()
    assert engine.blocked is not None
    assert engine.paused is True
    before = engine.battery
    engine.resolve_fault()
    assert engine.blocked is None
    assert engine.map.grid[next_cell[1]][next_cell[0]] == 0
    assert engine.battery < before  # 巡检清障按 5% 计费


def test_resolve_fault_clears_planned_obstacles():
    """有路线预览时，一键排障应直接执行规划里的清障。"""
    engine = blank_engine()
    # 在直线路径上放一处障碍，规划会把它标成待清障
    engine.map.grid[3][3] = 1
    plan = engine.plan_route([5, 3])
    assert plan["clearable"] == [[3, 3]]
    engine.resolve_fault()
    assert engine.map.grid[3][3] == 0
    assert engine.battery == pytest.approx(95.0, abs=1e-6)


# ---------- 5. 形象多端同步 ----------


def test_avatar_roundtrip_and_version_bump():
    """PUT 后 GET 能拿到同一张图，且版本号递增。"""
    engine = blank_engine()
    before = engine.avatar_version
    result = engine.set_avatar(TINY_PNG)
    assert result["data_url"] == TINY_PNG
    assert result["version"] == before + 1
    assert engine.get_avatar()["data_url"] == TINY_PNG
    engine.set_avatar(None)
    assert engine.get_avatar()["data_url"] is None
    assert engine.avatar_version == before + 2


def test_avatar_rejects_non_image_payload():
    """非图片 data URL 应被拒绝。"""
    engine = blank_engine()
    with pytest.raises(ValueError):
        engine.set_avatar("javascript:alert(1)")


def test_avatar_rest_endpoints():
    """REST：PUT 上传、GET 读取、DELETE 清除，非法内容 422。"""
    put = client.put("/api/v1/robot/avatar", json={"data_url": TINY_PNG})
    assert put.status_code == 200
    assert put.json()["data_url"] == TINY_PNG
    got = client.get("/api/v1/robot/avatar")
    assert got.status_code == 200
    assert got.json()["data_url"] == TINY_PNG
    bad = client.put("/api/v1/robot/avatar", json={"data_url": "not-an-image"})
    assert bad.status_code == 422
    deleted = client.delete("/api/v1/robot/avatar")
    assert deleted.status_code == 200
    assert client.get("/api/v1/robot/avatar").json()["data_url"] is None


# ---------- 6. "去第 N 号巡检点" ----------


def test_agent_understands_goal_index():
    """「去 2 号巡检点」应只去第 2 个巡检点，而不是全图巡检。"""
    # 其他用例会改全局地图，这里先放一张确定的 12×8 地图（两个巡检点）。
    client.put(
        "/api/v1/map",
        json={
            "width": 12,
            "height": 8,
            "grid": [[0] * 12 for _ in range(8)],
            "start": [1, 1],
            "goals": [[9, 6], [4, 3]],
            "charge_point": [1, 6],
        },
    )
    goals = client.get("/api/v1/map").json()["goals"]
    assert len(goals) >= 2
    response = client.post("/api/v1/agent/command", json={"text": "去 2 号巡检点"})
    assert response.status_code == 200
    data = response.json()
    assert data["tool"] == "start_patrol"
    assert data["executed"] is True
    assert data["args"]["goals"] == [goals[1]]


def test_agent_rejects_out_of_range_goal_index():
    """序号越界应返回可读提示，且不执行。"""
    response = client.post("/api/v1/agent/command", json={"text": "去 99 号巡检点"})
    data = response.json()
    assert data["understood"] is True
    assert data["executed"] is False
    assert "没有第 99 号巡检点" in data["message"]

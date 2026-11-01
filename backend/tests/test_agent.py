"""
Agent 指令层单元测试模块。

模块功能：验证"自然语言 → 白名单工具 → 校验 → 执行"这条链路：
  - 常见中文说法的意图识别；
  - 越界 / 屏障 / 电量不足 / 非法工具等参数拦截；
  - 破坏性操作的二次确认（未确认时状态不得改变）；
  - REST 接口返回结构与工具清单。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.agent import AgentError, AgentService, parse_rules, validate_call
from app.services.simulation_engine import SimulationEngine

client = TestClient(app)


def blank_engine() -> SimulationEngine:
    """构造一张 12×8 空地图的干净引擎（起点 1,1，充电点 1,6）。"""
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 12,
            "height": 8,
            "grid": [[0] * 12 for _ in range(8)],
            "start": [1, 1],
            "goals": [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def run(coro):
    """在同步用例里跑协程。"""
    return asyncio.run(coro)


# ---------- 规则解析 ----------


@pytest.mark.parametrize(
    ("text", "tool"),
    [
        ("去 5,5 巡检", "start_patrol"),
        ("开始巡检", "start_patrol"),
        ("停止巡检", "stop_patrol"),
        ("规划到 8,4 的路线", "plan_route"),
        ("去 6,2 怎么走", "plan_route"),
        ("现在状态怎么样", "status"),
        ("回充电点", "go_charge"),
        ("把 3,4 的障碍清掉", "clear_obstacle"),
        ("把 5,5 设成屏障", "set_cell"),
        ("复位", "reset"),
        ("向右移动一格", "move"),
    ],
)
def test_parse_rules_recognizes_intents(text, tool):
    """常见说法应落到正确的工具上。"""
    assert parse_rules(text)["tool"] == tool


def test_parse_rules_extracts_coordinates():
    """坐标应从中文标点里正确提取。"""
    parsed = parse_rules("去 (6，3) 巡检")
    assert parsed["tool"] == "start_patrol"
    assert parsed["args"]["goals"] == [[6, 3]]


def test_parse_rules_unknown_text():
    """听不懂的句子不应瞎猜动作。"""
    assert parse_rules("今天天气不错")["tool"] is None


def test_parse_forward_uses_current_heading():
    """「前进」按机器人当前朝向解释。"""
    assert parse_rules("前进一步", heading=(-1, 0))["args"] == {"dx": -1, "dy": 0}


# ---------- 参数校验 ----------


def test_validate_rejects_unknown_tool():
    """白名单之外的工具一律拒绝。"""
    with pytest.raises(AgentError):
        validate_call("exec_shell", {}, blank_engine())


def test_validate_rejects_out_of_bounds_goal():
    """越界目标应在执行前被拦下。"""
    with pytest.raises(AgentError, match="地图之外"):
        validate_call("plan_route", {"goal": [999, 999]}, blank_engine())


def test_validate_rejects_barrier_goal():
    """固定屏障不能作为规划目标。"""
    engine = blank_engine()
    engine.set_cell(5, 5, 2)
    with pytest.raises(AgentError, match="固定屏障"):
        validate_call("plan_route", {"goal": [5, 5]}, engine)


def test_validate_rejects_clear_when_not_obstacle():
    """目标格不是障碍时不应白扣电量。"""
    with pytest.raises(AgentError, match="不是障碍物"):
        validate_call("clear_obstacle", {"cell": [4, 4]}, blank_engine())


def test_validate_rejects_move_into_wall():
    """撞墙的移动指令提前拒绝。"""
    engine = blank_engine()
    with pytest.raises(AgentError, match="障碍或屏障"):
        validate_call("move", {"dx": -1, "dy": 0}, engine)


def test_validate_rejects_boundary_edit():
    """最外环边界不可编辑。"""
    with pytest.raises(AgentError, match="边界"):
        validate_call("set_cell", {"x": 0, "y": 0, "value": 1}, blank_engine())


# ---------- 执行与二次确认 ----------


def test_status_reports_position_and_battery():
    """状态查询应给出坐标、电量与模式。"""
    service = AgentService(blank_engine())
    result = run(service.handle("现在状态怎么样"))
    assert result["understood"] and result["executed"] and result["ok"]
    assert "电量" in result["message"] and "模式" in result["message"]


def test_plan_route_executes_and_reports_steps():
    """规划指令应生成预览路线，且不移动机器人。"""
    engine = blank_engine()
    service = AgentService(engine)
    result = run(service.handle("规划到 9,6 的路线"))
    assert result["tool"] == "plan_route"
    assert result["executed"] and result["ok"]
    assert engine.plan and engine.plan["path"]
    assert (engine.x, engine.y) == (1, 1), "预览不应移动机器人"


def test_destructive_tool_requires_confirmation():
    """清障第一次只返回待确认，地图与电量都不能变。"""
    engine = blank_engine()
    engine.set_cell(4, 4, 1)
    service = AgentService(engine)
    first = run(service.handle("把 4,4 的障碍清掉"))
    assert first["need_confirm"] and not first["executed"]
    assert engine.map.grid[4][4] == 1 and engine.battery == 100.0

    second = run(service.handle("把 4,4 的障碍清掉", confirm=True))
    assert second["executed"] and second["ok"]
    assert engine.map.grid[4][4] == 0
    assert engine.battery == 95.0


def test_go_charge_starts_returning():
    """「回充电点」应让机器人进入 charging 模式并规划路径。"""
    engine = blank_engine()
    service = AgentService(engine)
    result = run(service.handle("回充电点"))
    assert result["executed"] and result["ok"]
    assert engine.mode == "charging"
    assert engine.path[0] == [1, 1] and engine.path[-1] == [1, 6]


def test_start_patrol_with_coordinates():
    """「去 5,5 巡检」应只巡这个点。"""
    engine = blank_engine()
    service = AgentService(engine)
    result = run(service.handle("去 5,5 巡检"))
    assert result["executed"] and result["ok"]
    assert engine.patrol.running
    assert [tuple(g) for g in engine.patrol.goals] == [(5, 5)]


def test_invalid_command_returns_message_not_exception():
    """越界指令应返回可读错误，而不是 500。"""
    service = AgentService(blank_engine())
    result = run(service.handle("去 999,999 巡检"))
    assert result["understood"] and not result["executed"] and not result["ok"]
    assert "地图之外" in result["message"]


def test_empty_text_is_rejected():
    """空指令直接拒绝。"""
    service = AgentService(blank_engine())
    result = run(service.handle("   "))
    assert not result["understood"] and not result["executed"]


# ---------- REST 接口 ----------


def test_agent_command_endpoint_contract():
    """POST /agent/command 应返回完整字段。"""
    response = client.post("/api/v1/agent/command", json={"text": "现在状态怎么样"})
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {
        "text",
        "understood",
        "tool",
        "args",
        "source",
        "executed",
        "need_confirm",
        "ok",
        "message",
        "result",
        "latency_ms",
    }
    assert data["tool"] == "status"
    assert data["source"] == "rule"


def test_agent_tools_endpoint_lists_whitelist():
    """GET /agent/tools 应列出白名单工具。"""
    response = client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"plan_route", "start_patrol", "clear_obstacle", "status"} <= names


def test_agent_command_rejects_empty_text():
    """Pydantic 层应拦住空指令（422）。"""
    response = client.post("/api/v1/agent/command", json={"text": ""})
    assert response.status_code == 422

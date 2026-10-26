"""
V2.2.0 访问控制、限流、指标与共享规则测试。

模块功能：验证
  1. 配置 OPERATOR_KEY 后，写接口必须带正确密钥；
  2. READONLY_MODE 下写接口一律 403；
  3. 令牌桶达到上限后返回 429 且带 Retry-After；
  4. /metrics 输出 Prometheus 文本并随请求增长；
  5. 后端默认地图 / 电量规则与 shared/*.json 完全一致（防止再次漂移）。

作者：智能巡检机器人二维仿真系统 V2.2.0 开发组
日期：2026-10-26
版本：V2.2.0
"""

import os
import tempfile

import pytest

_tempdir = tempfile.mkdtemp()
os.environ["LOG_FILE"] = os.path.join(_tempdir, "test_v22.log")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.metrics import metrics  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.core.shared import load_default_map, load_rules  # noqa: E402
from app.main import app  # noqa: E402
from app.services.simulation_engine import SimulationEngine  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """每个用例前后恢复配置与计数器，避免互相污染。"""
    monkeypatch.setattr(settings, "operator_key", "", raising=False)
    monkeypatch.setattr(settings, "readonly_mode", False, raising=False)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 240, raising=False)
    monkeypatch.setattr(settings, "rate_limit_burst", 80, raising=False)
    limiter.reset()
    metrics.reset()
    yield
    limiter.reset()
    metrics.reset()


def test_write_requires_operator_key(monkeypatch):
    """配置密钥后：读放行，写无密钥 401，带正确密钥 200。"""
    monkeypatch.setattr(settings, "operator_key", "s3cret", raising=False)

    assert client.get("/api/v1/map").status_code == 200
    denied = client.post("/api/v1/robot/move", json={"dx": 1, "dy": 0})
    assert denied.status_code == 401
    assert "ApiKey" in denied.headers.get("www-authenticate", "")

    allowed = client.post(
        "/api/v1/robot/move", json={"dx": 1, "dy": 0}, headers={"X-API-Key": "s3cret"}
    )
    assert allowed.status_code == 200

    wrong = client.post(
        "/api/v1/robot/move", json={"dx": 0, "dy": 0}, headers={"X-API-Key": "nope"}
    )
    assert wrong.status_code == 401


def test_readonly_mode_blocks_writes(monkeypatch):
    """只读模式：即使没有配置密钥，写操作也返回 403。"""
    monkeypatch.setattr(settings, "readonly_mode", True, raising=False)
    denied = client.post("/api/v1/robot/move", json={"dx": 1, "dy": 0})
    assert denied.status_code == 403
    assert "只读" in denied.json()["detail"]
    assert client.get("/api/v1/map").status_code == 200


def test_rate_limit_returns_429(monkeypatch):
    """令牌桶耗尽后返回 429，并带 Retry-After；健康检查不受限。"""
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2, raising=False)
    monkeypatch.setattr(settings, "rate_limit_burst", 2, raising=False)
    limiter.reset()

    assert client.get("/api/v1/map").status_code == 200
    assert client.get("/api/v1/map").status_code == 200
    limited = client.get("/api/v1/map")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1

    # 健康探针在豁免名单内，始终可用
    assert client.get("/api/v1/health").status_code == 200


def test_metrics_exposes_counters():
    """/metrics 输出 Prometheus 文本，请求计数随调用增长。"""
    before = metrics.snapshot().get(
        'http_requests_total{method="GET",status="200"}', 0
    )
    client.get("/api/v1/map")
    text = client.get("/metrics").text
    after = metrics.snapshot().get('http_requests_total{method="GET",status="200"}', 0)

    assert "irm_uptime_seconds" in text
    assert "irm_engine_battery_percent" in text
    assert "irm_ws_clients" in text
    assert after > before
    assert 'http_requests_total{method="GET",status="200"}' in text


def test_shared_rules_are_single_source():
    """后端配置与默认地图必须与 shared/*.json 完全一致。"""
    rules = load_rules()
    assert settings.battery_move_cost == rules["battery"]["move_cost"]
    assert settings.clear_obstacle_cost == rules["battery"]["clear_cost"]
    assert settings.low_battery_threshold == rules["battery"]["low_threshold"]
    assert settings.overheat_threshold == rules["temperature"]["overheat_threshold"]
    assert settings.sensor_fault_delta == rules["sensor"]["fault_delta"]

    shared_map = load_default_map()
    engine = SimulationEngine()
    assert engine.map.width == shared_map["width"]
    assert engine.map.height == shared_map["height"]
    assert [list(row) for row in engine.map.grid] == shared_map["grid"]
    assert [list(g) for g in engine.map.goals] == shared_map["goals"]
    assert list(engine.map.start) == shared_map["start"]
    assert list(engine.map.charge_point) == shared_map["charge_point"]


def test_ws_readonly_can_watch_but_not_control(monkeypatch):
    """未带密钥的连接仍能收到状态，但下发指令会被拒绝并回 auth_required。"""
    monkeypatch.setattr(settings, "operator_key", "s3cret", raising=False)
    with client.websocket_connect("/api/v1/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "auth_state"
        assert first["data"]["can_control"] is False

        ws.send_json({"type": "command", "action": "move", "payload": {"dx": 1, "dy": 0}})
        denied = None
        for _ in range(10):
            message = ws.receive_json()
            if message["type"] == "auth_required":
                denied = message
                break
        assert denied is not None
        assert denied["data"]["code"] == 4401


def test_ws_with_key_can_control(monkeypatch):
    """带正确密钥的连接 auth_state.can_control 为 True，并真的能移动。"""
    monkeypatch.setattr(settings, "operator_key", "s3cret", raising=False)
    with client.websocket_connect("/api/v1/ws?api_key=s3cret") as ws:
        first = ws.receive_json()
        assert first["type"] == "auth_state"
        assert first["data"]["can_control"] is True

    # 同一密钥走 HTTP 写接口应被放行（副作用由 WS 推送，测试环境无推送循环）
    moved = client.post(
        "/api/v1/robot/move", json={"dx": 1, "dy": 0}, headers={"X-API-Key": "s3cret"}
    )
    assert moved.status_code == 200

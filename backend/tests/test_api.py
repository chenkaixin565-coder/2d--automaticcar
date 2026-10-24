"""
REST 接口集成测试模块。

模块功能：使用 FastAPI TestClient 验证全部契约接口的请求/响应结构。
作者：智能巡检机器人二维仿真系统 V1.0 开发组
日期：2026-10-24
版本：V1.0
"""

import os
import tempfile

# 使用临时日志文件，避免测试污染项目目录。
_tempdir = tempfile.mkdtemp()
os.environ["LOG_FILE"] = os.path.join(_tempdir, "test.log")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_endpoint():
    """健康检查接口应返回 ok。"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_map_contract():
    """GET /map 应返回契约要求的全部字段。"""
    response = client.get("/api/v1/map")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"width", "height", "grid", "start", "goals", "charge_point"}


def test_put_map_roundtrip():
    """PUT /map 提交后应能 GET 到相同数据。"""
    new_map = {
        "width": 4,
        "height": 4,
        "grid": [[0] * 4 for _ in range(4)],
        "start": [0, 0],
        "goals": [[3, 3]],
        "charge_point": [0, 0],
    }
    put = client.put("/api/v1/map", json=new_map)
    assert put.status_code == 200
    got = client.get("/api/v1/map").json()
    assert got["width"] == 4
    assert got["grid"] == new_map["grid"]


def test_move_endpoint():
    """POST /robot/move 应返回 state 帧结构。"""
    response = client.post("/api/v1/robot/move", json={"dx": 1, "dy": 0})
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"x", "y", "theta", "battery", "speed", "mode", "path", "sensors"}
    assert set(data["sensors"].keys()) == {"front", "left", "right", "temperature"}


def test_path_endpoint():
    """GET /path 应返回 A* 结果三元组。"""
    response = client.get("/api/v1/path", params={"start": "0,0", "goal": "3,3"})
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"path", "visited_count", "cost"}
    assert data["path"][0] == [0, 0]
    assert data["path"][-1] == [3, 3]


def test_patrol_lifecycle():
    """巡检启动/查询/停止全流程。"""
    start = client.post("/api/v1/patrol/start", json={"goals": [[3, 3]]})
    assert start.status_code == 200
    assert start.json()["running"] is True

    status = client.get("/api/v1/patrol/status").json()
    assert status["running"] is True
    assert status["current_goal"] == [3, 3]

    stop = client.post("/api/v1/patrol/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False


def test_sensors_and_anomalies():
    """传感器与异常接口应可访问。"""
    sensors = client.get("/api/v1/sensors/latest")
    assert sensors.status_code == 200
    anomalies = client.get("/api/v1/events/anomalies")
    assert anomalies.status_code == 200
    assert isinstance(anomalies.json(), list)


def test_remove_obstacle_endpoint():
    """一键排障接口应能找到建议拆除的障碍。"""
    # 构造被单格障碍阻断的地图。
    grid = [[0] * 3 for _ in range(3)]
    grid[0][1] = 1
    grid[1][1] = 1
    grid[2][1] = 1
    client.put(
        "/api/v1/map",
        json={"width": 3, "height": 3, "grid": grid, "start": [0, 0], "goals": [], "charge_point": [0, 0]},
    )
    response = client.post("/api/v1/map/remove-obstacle", json=[2, 0])
    assert response.status_code == 200
    data = response.json()
    assert data["remove"] is not None
    assert data["remove"][0] == 1  # 应建议拆除中间那列障碍之一。

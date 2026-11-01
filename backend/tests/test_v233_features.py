"""
V2.3.3 地图同步测试模块。

模块功能：验证"地图被修改后必须广播权威地图"这一约定。

背景：正常操作走 WebSocket，而地图此前只放在 HTTP 响应体里，客户端拿不到
新地图，于是出现"障碍已经清掉、画面还显示障碍，机器人却从上面穿过去"。
现在引擎在每次地图变更后广播 `map` 帧，前端直接覆盖本地地图。

作者：智能巡检机器人二维仿真系统 V2.3.3 开发组
日期：2026-11-01
版本：V2.3.3
"""

from app.services.simulation_engine import SimulationEngine


def blank_engine() -> SimulationEngine:
    """构造一张 12×8 空地图的干净引擎。"""
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


def map_frames(frames: list[dict]) -> list[dict]:
    """取出所有 map 帧。"""
    return [frame for frame in frames if frame.get("type") == "map"]


def test_clear_obstacle_broadcasts_map_frame():
    """清障后应广播 map 帧，且帧里的格子已经变成可通行。"""
    engine = blank_engine()
    frames: list[dict] = []
    engine.add_event_listener(frames.append)
    engine.map.grid[5][6] = 1
    engine.clear_obstacle_at([6, 5])
    maps = map_frames(frames)
    assert maps, "清障后应至少广播一帧 map"
    assert maps[-1]["data"]["grid"][5][6] == 0


def test_set_cell_broadcasts_map_frame():
    """编辑格子后应广播 map 帧（多端地图保持一致）。"""
    engine = blank_engine()
    frames: list[dict] = []
    engine.add_event_listener(frames.append)
    engine.set_cell(4, 4, 1)
    maps = map_frames(frames)
    assert maps and maps[-1]["data"]["grid"][4][4] == 1


def test_execute_plan_clear_broadcasts_map_frame():
    """按规划批量清障后应广播 map 帧。"""
    engine = blank_engine()
    engine.map.grid[3][3] = 1
    engine.plan_route([5, 3])
    frames: list[dict] = []
    engine.add_event_listener(frames.append)
    engine.execute_plan_clear()
    maps = map_frames(frames)
    assert maps and maps[-1]["data"]["grid"][3][3] == 0


def test_update_map_broadcasts_map_frame():
    """整图替换 / 新建地图后应广播 map 帧。"""
    engine = blank_engine()
    frames: list[dict] = []
    engine.add_event_listener(frames.append)
    engine.new_map(20, 14)
    maps = map_frames(frames)
    assert maps and maps[-1]["data"]["width"] == 20

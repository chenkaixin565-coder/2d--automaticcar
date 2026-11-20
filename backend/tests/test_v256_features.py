"""
V2.5.6 测试：低电量自动返航必须广播一个显眼的 auto_charge 事件。
"""

from app.services.simulation_engine import SimulationEngine


def make_engine() -> SimulationEngine:
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


def test_low_battery_emits_auto_charge_notice():
    engine = make_engine()
    frames = []
    engine.add_event_listener(frames.append)
    engine.battery = 15.0
    engine.mode = "manual"
    engine.tick()
    auto = [
        f
        for f in frames
        if f.get("type") == "notice" and (f.get("data") or {}).get("kind") == "auto_charge"
    ]
    assert auto, "低电量自动返航必须广播 auto_charge 事件"
    assert auto[0]["data"]["battery"] == 15.0
    assert engine.mode == "charging"


def test_manual_go_charge_does_not_emit_auto_charge():
    engine = make_engine()
    frames = []
    engine.add_event_listener(frames.append)
    engine.go_charge()
    auto = [
        f
        for f in frames
        if f.get("type") == "notice" and (f.get("data") or {}).get("kind") == "auto_charge"
    ]
    assert auto == [], "手动返航不应该触发‘自动返航’大提示"

"""
V2.6.0 回归测试：

- 返航被挡：暂停并要求手动擦除，擦完自动继续返航
- 跳过：整条路线的障碍都记入待清障（不再只记一格）
- 跳过按钮是否还有意义（can_skip）
"""

from app.services.simulation_engine import SimulationEngine


def blank_engine(goals=None) -> SimulationEngine:
    engine = SimulationEngine()
    engine.update_map(
        {
            "width": 12,
            "height": 8,
            "grid": [[0] * 12 for _ in range(8)],
            "start": [1, 1],
            "goals": goals or [[9, 6]],
            "charge_point": [1, 6],
        }
    )
    return engine


def test_charge_blocked_pauses_and_resumes_after_erase():
    engine = blank_engine()
    # 用固定屏障把充电点围住：普通清障救不了，必须人工擦除
    engine.map.grid[5][1] = 2
    engine.map.grid[6][2] = 2
    engine.battery = 15.0
    engine.tick()
    assert engine.mode == "charging"
    assert engine.blocked is not None
    assert engine.blocked["reason"] == "charge_unreachable"

    engine.dismiss_blocked()
    assert engine.blocked is None
    engine.set_cell(1, 5, 0)
    assert engine.blocked is None
    assert engine.path, "擦掉挡路屏障后应自动恢复返航路线"


def test_skip_records_whole_blocked_route():
    engine = blank_engine()
    for x in (4, 7):
        for y in range(1, 7):
            engine.map.grid[y][x] = 1
    engine.start_patrol()
    assert engine.blocked is not None
    cells = engine.blocked.get("cells") or []
    assert len(cells) >= 2
    engine.patrol_decision("skip")
    assert engine.pending, "跳过后应把整条路线的障碍记入待清障"
    assert len(engine.pending) >= 2


def test_can_skip_reflects_remaining_reachable_goal():
    engine = blank_engine(goals=[[3, 1], [9, 6]])
    # 第一个点 (3,1) 被屏障围死，第二个点 (9,6) 可达
    engine.map.grid[1][4] = 2
    engine.map.grid[2][3] = 2
    engine.map.grid[1][2] = 2
    engine.start_patrol()
    assert engine.blocked is not None
    assert engine.blocked.get("can_skip") is True


def test_can_skip_false_when_no_next_goal():
    engine = blank_engine(goals=[[3, 1]])
    engine.map.grid[1][4] = 2
    engine.map.grid[2][3] = 2
    engine.map.grid[1][2] = 2
    engine.start_patrol()
    assert engine.blocked is not None
    assert engine.blocked.get("can_skip") is False

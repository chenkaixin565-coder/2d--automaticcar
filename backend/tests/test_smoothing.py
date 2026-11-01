"""
路径平滑单元测试模块。

模块功能：验证视线检测（超覆盖 Bresenham）不会"擦墙穿过去"，抽稀后的关键点
能还原成相邻格路径，且长度不超过原路径。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

from app.algorithms.smoothing import (
    expand_path,
    line_of_sight,
    smooth_and_expand,
    smooth_path,
)


def test_line_of_sight_across_open_space():
    """空旷地图上任意两点通视。"""
    grid = [[0] * 8 for _ in range(8)]
    assert line_of_sight(grid, (0, 0), (7, 7)) is True
    assert line_of_sight(grid, (1, 1), (6, 2)) is True


def test_line_of_sight_blocked_by_wall():
    """直线上有障碍时不通视。"""
    grid = [[0] * 8 for _ in range(8)]
    for y in range(8):
        grid[y][4] = 1
    assert line_of_sight(grid, (0, 0), (7, 0)) is False


def test_smooth_path_removes_staircase():
    """阶梯状路径应被抽稀成少量关键点，首尾保持不变。"""
    grid = [[0] * 8 for _ in range(8)]
    staircase = [
        [1, 1], [2, 1], [2, 2], [3, 2], [3, 3], [4, 3], [4, 4], [5, 4], [5, 5],
    ]
    smoothed = smooth_path(grid, staircase)
    assert smoothed[0] == [1, 1]
    assert smoothed[-1] == [5, 5]
    assert len(smoothed) < len(staircase)


def test_expand_path_is_eight_connected():
    """回填后的每一对相邻格在八邻域内连通（机器人可以逐格走）。"""
    points = [[1, 1], [5, 5], [5, 1], [8, 4]]
    expanded = expand_path(points)
    assert expanded[0] == [1, 1]
    assert expanded[-1] == [8, 4]
    for previous, current in zip(expanded, expanded[1:]):
        dx = abs(current[0] - previous[0])
        dy = abs(current[1] - previous[1])
        assert max(dx, dy) == 1, f"相邻格不连通: {previous} -> {current}"


def test_smooth_and_expand_never_gets_longer():
    """抽稀+回填的结果必须是一条第 8 连通的合法路径，且不比原路径更长。"""
    grid = [[0] * 10 for _ in range(10)]
    grid[0][5] = 1  # 一个无关障碍，确保实现不会擅自穿越
    original = [
        [1, 1], [2, 1], [3, 1], [3, 2], [4, 2], [5, 2], [5, 3], [6, 3], [7, 3],
    ]
    result = smooth_and_expand(grid, original)
    assert result[0] == original[0]
    assert result[-1] == original[-1]
    assert len(result) <= len(original)
    for x, y in result:
        assert grid[y][x] == 0
    for previous, current in zip(result, result[1:]):
        assert max(abs(current[0] - previous[0]), abs(current[1] - previous[1])) == 1


def test_short_path_is_returned_unchanged():
    """长度 ≤2 的路径不需要平滑，原样返回副本。"""
    grid = [[0] * 4 for _ in range(4)]
    assert smooth_and_expand(grid, [[1, 1], [2, 1]]) == [[1, 1], [2, 1]]
    assert smooth_and_expand(grid, []) == []

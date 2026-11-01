"""
路径平滑模块（视线法 line-of-sight 抽稀 + Bresenham 回填）。

模块功能：A* 在栅格上得到的是逐格路径，四邻域模式下常出现"阶梯状"冗余拐点。
本模块用视线检测把同一条直线上的冗余点抽掉（string pulling），再按 Bresenham
把"跳跃"的线段回填成相邻格序列，保证机器人仍然逐格执行、不会瞬移。

为什么必须回填：仿真引擎每 tick 只走到 path[1]，若只保留拐点，机器人会一步跨
好几格，电量与耗时都会失真。因此对外只暴露"抽稀 + 回填"后的等价路径，长度
不会超过原路径，且每一对相邻格在八邻域下仍然连通。

作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

# 单次视线检查允许跨越的最大格数；限制它可把平滑的开销控制在 O(n)。
_MAX_SPAN = 32


def _supercover_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """
    返回两点之间"线段真正穿过"的全部栅格（超覆盖 Bresenham）。

    与普通 Bresenham 的区别：线段恰好经过两个格的公共角点时，把两侧的格
    都算进来，避免视线检测把"擦着墙角穿过去"误判为通视。

    :param x0: 起点 x。
    :param y0: 起点 y。
    :param x1: 终点 x。
    :param y1: 终点 y。
    :return: 线段穿过的格坐标列表（含首尾）。
    """
    cells: list[tuple[int, int]] = [(x0, y0)]
    dx = x1 - x0
    dy = y1 - y0
    nx = abs(dx)
    ny = abs(dy)
    sign_x = (dx > 0) - (dx < 0)
    sign_y = (dy > 0) - (dy < 0)

    if nx == 0:
        for step in range(1, ny + 1):
            cells.append((x0, y0 + sign_y * step))
        return cells
    if ny == 0:
        for step in range(1, nx + 1):
            cells.append((x0 + sign_x * step, y0))
        return cells

    x, y = x0, y0
    ix = iy = 0
    while ix < nx or iy < ny:
        # 比较两个方向"走到下一格中线"的进度，决定这一步先横走还是先竖走。
        tx = (1 + 2 * ix) / (2 * nx)
        ty = (1 + 2 * iy) / (2 * ny)
        if tx < ty:
            x += sign_x
            ix += 1
            cells.append((x, y))
        elif tx > ty:
            y += sign_y
            iy += 1
            cells.append((x, y))
        else:
            # 正好穿过格点：两侧的格都视为被线段擦过。
            cells.append((x + sign_x, y))
            cells.append((x, y + sign_y))
            x += sign_x
            y += sign_y
            ix += 1
            iy += 1
            cells.append((x, y))

    return cells


def line_of_sight(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> bool:
    """
    判断两格之间是否通视（线段穿过的所有格都可通行）。

    :param grid: 二维栅格数组，0=可通行。
    :param start: 起点 (x, y)。
    :param goal: 终点 (x, y)。
    :return: 是否通视。
    """
    height = len(grid)
    width = len(grid[0]) if height else 0
    for x, y in _supercover_line(start[0], start[1], goal[0], goal[1]):
        if not (0 <= x < width and 0 <= y < height) or grid[y][x] != 0:
            return False
    return True


def smooth_path(grid: list[list[int]], path: list[list[int]]) -> list[list[int]]:
    """
    用视线法抽稀少余拐点，只保留"必须转弯"的关键点。

    策略是贪心前向：从当前锚点出发，尽量把视线延伸到最远的后续点，
    直到再远就看不见为止；然后把该点设为新锚点继续。路径首尾必定保留。

    :param grid: 二维栅格数组。
    :param path: A* 输出的逐格路径 [[x, y], ...]。
    :return: 抽稀后的关键点路径（数量 ≤ 原路径）。
    """
    if len(path) <= 2:
        return [list(p) for p in path]

    points = [(int(p[0]), int(p[1])) for p in path]
    out: list[list[int]] = [list(points[0])]
    anchor = 0
    while anchor < len(points) - 1:
        farthest = anchor + 1
        limit = min(len(points) - 1, anchor + _MAX_SPAN)
        probe = anchor + 2
        while probe <= limit and line_of_sight(grid, points[anchor], points[probe]):
            farthest = probe
            probe += 1
        out.append(list(points[farthest]))
        anchor = farthest
    return out


def expand_path(points: list[list[int]]) -> list[list[int]]:
    """
    把抽稀后的关键点路径回填成相邻格序列（Bresenham 超覆盖）。

    :param points: 关键点路径 [[x, y], ...]。
    :return: 逐格路径，相邻两点在八邻域下连通。
    """
    if len(points) <= 1:
        return [list(p) for p in points]

    expanded: list[list[int]] = [list(points[0])]
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        segment = _supercover_line(
            int(previous[0]), int(previous[1]), int(current[0]), int(current[1])
        )
        for x, y in segment[1:]:
            if not expanded or expanded[-1] != [x, y]:
                expanded.append([x, y])
    return expanded


def smooth_and_expand(grid: list[list[int]], path: list[list[int]]) -> list[list[int]]:
    """
    先抽稀再回填，得到"拐点更少、但仍逐格连通"的执行路径。

    :param grid: 二维栅格数组。
    :param path: A* 输出的逐格路径。
    :return: 处理后的逐格路径；输入为空时原样返回。
    """
    if len(path) <= 2:
        return [list(p) for p in path]
    smoothed = smooth_path(grid, path)
    if len(smoothed) >= len(path):
        return [list(p) for p in path]
    expanded = expand_path(smoothed)
    # 回填结果理论上不会比原路径长；一旦变长说明实现异常，直接退回原路径。
    return expanded if len(expanded) <= len(path) else [list(p) for p in path]

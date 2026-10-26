#!/usr/bin/env python3
"""
路径规划对照基准脚本。

模块功能：在同一批随机栅格地图上分别运行 A* 与 BFS，统计
  - 平均扩展节点数（visited_count）
  - 平均耗时（毫秒）
  - 最优代价是否一致（BFS 作为无权图最短路基准）
并输出可直接粘进 docs/algorithm.md 的 Markdown 表格。

用法：
    cd backend
    python tools/benchmark_paths.py --size 50 --density 0.2 --samples 100
    python tools/benchmark_paths.py --size 200 --density 0.2 --samples 20 --perf

作者：智能巡检机器人二维仿真系统 V2.2.1 开发组
日期：2026-10-27
版本：V2.2.1
"""

import argparse
import json
import random
import statistics
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.algorithms.astar import astar  # noqa: E402
from app.algorithms.bfs import bfs  # noqa: E402


def make_grid(size: int, density: float, rng: random.Random) -> list[list[int]]:
    """生成带边界墙、内部按密度随机布障的方格地图。"""
    grid = [[0] * size for _ in range(size)]
    for i in range(size):
        grid[0][i] = grid[size - 1][i] = 1
        grid[i][0] = grid[i][size - 1] = 1
    for y in range(1, size - 1):
        for x in range(1, size - 1):
            if rng.random() < density:
                grid[y][x] = 1
    return grid


def pick_free(grid: list[list[int]], rng: random.Random) -> tuple[int, int]:
    """随机选一个可通行格。"""
    size = len(grid)
    while True:
        x = rng.randrange(1, size - 1)
        y = rng.randrange(1, size - 1)
        if grid[y][x] == 0:
            return x, y


def run(size: int, density: float, samples: int, seed: int) -> dict:
    """跑一批样本并汇总统计量。"""
    rng = random.Random(seed)
    rows = []
    attempts = 0

    while len(rows) < samples and attempts < samples * 50:
        attempts += 1
        grid = make_grid(size, density, rng)
        start = pick_free(grid, rng)
        goal = pick_free(grid, rng)
        if start == goal:
            continue

        t0 = time.perf_counter()
        result_a = astar(grid, start, goal)
        t_a = (time.perf_counter() - t0) * 1000

        if not result_a["path"]:
            # 只统计可达样本：不可达时两者都返回空，对比没有意义。
            continue

        t0 = time.perf_counter()
        result_b = bfs(grid, start, goal)
        t_b = (time.perf_counter() - t0) * 1000

        rows.append(
            {
                "astar_visited": result_a["visited_count"],
                "bfs_visited": result_b["visited_count"],
                "astar_cost": result_a["cost"],
                "bfs_cost": result_b["cost"],
                "astar_ms": t_a,
                "bfs_ms": t_b,
            }
        )

    if not rows:
        raise SystemExit("没有采到可达样本，请降低障碍密度")

    same_cost = sum(1 for r in rows if r["astar_cost"] == r["bfs_cost"])
    return {
        "size": size,
        "density": density,
        "samples": len(rows),
        "attempts": attempts,
        "astar_visited_mean": statistics.mean(r["astar_visited"] for r in rows),
        "bfs_visited_mean": statistics.mean(r["bfs_visited"] for r in rows),
        "astar_ms_mean": statistics.mean(r["astar_ms"] for r in rows),
        "bfs_ms_mean": statistics.mean(r["bfs_ms"] for r in rows),
        "astar_ms_p95": sorted(r["astar_ms"] for r in rows)[max(0, int(len(rows) * 0.95) - 1)],
        "same_cost_ratio": same_cost / len(rows),
        "expand_ratio": statistics.mean(r["astar_visited"] for r in rows)
        / max(1, statistics.mean(r["bfs_visited"] for r in rows)),
    }


def to_markdown(stats: dict) -> str:
    """输出可直接粘贴的 Markdown 表格。"""
    return (
        f"| 算法 | 平均扩展节点 | 平均耗时 |\n"
        f"| --- | --- | --- |\n"
        f"| A*（曼哈顿，四邻域） | {stats['astar_visited_mean']:.1f} | "
        f"{stats['astar_ms_mean']:.2f} ms |\n"
        f"| BFS（对照基线） | {stats['bfs_visited_mean']:.1f} | "
        f"{stats['bfs_ms_mean']:.2f} ms |\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=50)
    parser.add_argument("--density", type=float, default=0.2)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--perf", action="store_true", help="额外跑 200x200 性能基准")
    args = parser.parse_args()

    stats = run(args.size, args.density, args.samples, args.seed)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("\nMarkdown:\n")
    print(to_markdown(stats))

    if args.perf:
        perf = run(200, 0.2, 20, args.seed + 1)
        print("200x200 性能基准：")
        print(json.dumps(perf, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

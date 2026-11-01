"""
路径规划基准脚本。

模块功能：在同一批随机地图上对比三种算法，产出 `docs/algorithm.md` 里
"扩展节点数 / 耗时 / 最优代价" 三张表所需的原始数据：
  - A*（八邻域，octile 启发，斜向代价 √2）
  - A*（四邻域，曼哈顿启发，与 V2.2.1 及更早版本一致）
  - BFS（四邻域无权最短步数基线）

用法：
    cd backend
    python tools/benchmark_paths.py --size 50 --density 0.2 --samples 100
    python tools/benchmark_paths.py --size 50 --density 0.2 --samples 100 --perf
    python tools/benchmark_paths.py --json docs/benchmark-paths.json

随机种子固定，扩展节点数是确定值；不同机器的耗时会有浮动。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

# 允许直接执行 `python tools/benchmark_paths.py`：把 backend/ 加入模块搜索路径。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.algorithms.astar import astar  # noqa: E402
from app.algorithms.bfs import bfs  # noqa: E402

DEFAULT_SEED = 20261030


def build_grid(size: int, density: float, rng: random.Random) -> list[list[int]]:
    """
    生成"四周墙 + 内部随机障碍"的方形地图。

    :param size: 边长。
    :param density: 内部障碍比例（0~1）。
    :param rng: 随机数发生器。
    :return: 二维栅格数组。
    """
    grid = [[0] * size for _ in range(size)]
    for x in range(size):
        grid[0][x] = 1
        grid[size - 1][x] = 1
    for y in range(size):
        grid[y][0] = 1
        grid[y][size - 1] = 1
    for y in range(1, size - 1):
        for x in range(1, size - 1):
            if rng.random() < density:
                grid[y][x] = 1
    return grid


def run_once(grid: list[list[int]], start: tuple[int, int], goal: tuple[int, int]) -> dict:
    """
    在给定起终点上跑三种算法并计时。

    :param grid: 栅格地图。
    :param start: 起点。
    :param goal: 终点。
    :return: 每种算法的 {nodes, ms, cost, reachable}。
    """
    out: dict[str, dict] = {}

    for name, runner in (
        ("astar8", lambda: astar(grid, start, goal, diagonal=True)),
        ("astar4", lambda: astar(grid, start, goal, diagonal=False)),
        ("bfs4", lambda: bfs(grid, start, goal)),
    ):
        began = time.perf_counter()
        result = runner()
        elapsed_ms = (time.perf_counter() - began) * 1000
        out[name] = {
            "nodes": result["visited_count"],
            "ms": round(elapsed_ms, 3),
            "cost": result["cost"],
            "steps": max(0, len(result["path"]) - 1),
            "reachable": bool(result["path"]),
        }
    return out


def summarize(samples: list[dict], key: str, field: str) -> dict:
    """
    统计某个算法某个指标。

    :param samples: 样本列表。
    :param key: 算法名。
    :param field: 指标名。
    :return: {'mean', 'p95'}。
    """
    values = [sample[key][field] for sample in samples if sample[key]["reachable"]]
    if not values:
        return {"mean": 0, "p95": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(math.ceil(len(ordered) * 0.95)) - 1)
    return {"mean": round(statistics.mean(values), 1), "p95": round(ordered[p95_index], 3)}


def benchmark(size: int, density: float, samples: int, seed: int = DEFAULT_SEED) -> dict:
    """
    跑一批随机起终点，返回统计结果。

    :param size: 地图边长。
    :param density: 障碍比例。
    :param samples: 采样组数。
    :param seed: 随机种子。
    :return: 统计字典。
    """
    rng = random.Random(seed)
    grid = build_grid(size, density, rng)

    runs: list[dict] = []
    attempts = 0
    while len(runs) < samples and attempts < samples * 50:
        attempts += 1
        start = (rng.randrange(1, size - 1), rng.randrange(1, size - 1))
        goal = (rng.randrange(1, size - 1), rng.randrange(1, size - 1))
        if grid[start[1]][start[0]] or grid[goal[1]][goal[0]]:
            continue
        result = run_once(grid, start, goal)
        if not result["bfs4"]["reachable"]:
            continue
        runs.append(result)

    reachable = [run for run in runs if run["astar4"]["reachable"] and run["bfs4"]["reachable"]]
    same_cost = sum(1 for run in reachable if abs(run["astar4"]["cost"] - run["bfs4"]["cost"]) < 1e-9)

    summary = {
        "size": size,
        "density": density,
        "samples": len(runs),
        "seed": seed,
        "astar8": {
            "nodes": summarize(runs, "astar8", "nodes"),
            "ms": summarize(runs, "astar8", "ms"),
            "mean_cost": summarize(runs, "astar8", "cost")["mean"],
            "mean_steps": summarize(runs, "astar8", "steps")["mean"],
        },
        "astar4": {
            "nodes": summarize(runs, "astar4", "nodes"),
            "ms": summarize(runs, "astar4", "ms"),
            "mean_cost": summarize(runs, "astar4", "cost")["mean"],
            "mean_steps": summarize(runs, "astar4", "steps")["mean"],
        },
        "bfs4": {
            "nodes": summarize(runs, "bfs4", "nodes"),
            "ms": summarize(runs, "bfs4", "ms"),
            "mean_cost": summarize(runs, "bfs4", "cost")["mean"],
        },
        "optimal_cost_equal": f"{same_cost}/{len(reachable)}",
        "astar8_node_ratio_vs_bfs": round(
            summary_ratio(runs, "astar8", "bfs4", "nodes"), 4
        ),
        "astar8_steps_vs_astar4": round(
            summary_ratio(runs, "astar8", "astar4", "steps"), 4
        ),
    }
    return summary


def summary_ratio(runs: list[dict], numerator: str, denominator: str, field: str) -> float:
    """
    计算两个算法某指标的比值（分子均值 / 分母均值）。

    :param runs: 样本列表。
    :param numerator: 分子算法名。
    :param denominator: 分母算法名。
    :param field: 指标名。
    :return: 比值；分母为 0 时返回 0。
    """
    top = summarize(runs, numerator, field)["mean"]
    bottom = summarize(runs, denominator, field)["mean"]
    return top / bottom if bottom else 0.0


def render_markdown(results: list[dict]) -> str:
    """
    把统计结果渲染成可直接粘进文档的 Markdown。

    :param results: benchmark() 返回的列表。
    :return: Markdown 文本。
    """
    lines = [
        "| 地图 | 算法 | 平均扩展节点 | 平均耗时 | 平均代价 |",
        "|---|---|---|---|---|",
    ]
    for item in results:
        scope = f"{item['size']}×{item['size']} / 障碍 {int(item['density'] * 100)}%"
        for key, label in (("astar8", "A*（八邻域）"), ("astar4", "A*（四邻域）"), ("bfs4", "BFS（四邻域）")):
            lines.append(
                f"| {scope} | {label} | {item[key]['nodes']['mean']} | "
                f"{item[key]['ms']['mean']} ms | {item[key]['mean_cost']} |"
            )
    return "\n".join(lines)


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="A* / BFS 路径规划基准")
    parser.add_argument("--size", type=int, default=50, help="地图边长")
    parser.add_argument("--density", type=float, default=0.2, help="内部障碍比例")
    parser.add_argument("--samples", type=int, default=100, help="有效样本数")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子")
    parser.add_argument("--perf", action="store_true", help="追加 200×200 性能基准")
    parser.add_argument("--json", type=str, default="", help="把统计写入 JSON 文件")
    args = parser.parse_args()

    results = [benchmark(args.size, args.density, args.samples, args.seed)]
    if args.perf:
        results.append(benchmark(200, args.density, max(20, args.samples // 5), args.seed))

    print(render_markdown(results))
    print()
    for item in results:
        print(
            f"{item['size']}×{item['size']}: "
            f"A*8 扩展 {item['astar8']['nodes']['mean']} 节点（BFS 的 "
            f"{item['astar8_node_ratio_vs_bfs'] * 100:.1f}%），"
            f"步数比四邻域少 {(1 - item['astar8_steps_vs_astar4']) * 100:.1f}%；"
            f"四邻域 A* 与 BFS 最优代价一致 {item['optimal_cost_equal']}。"
        )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)
        print(f"\n已写入 {args.json}")


if __name__ == "__main__":
    main()

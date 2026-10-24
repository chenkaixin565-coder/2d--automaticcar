#!/usr/bin/env python3
"""
软著架构图生成脚本。

用 matplotlib 绘制分层架构图：浏览器层 -> 通信层 -> 后端服务层 ->
引擎内核 -> 算法模块。输出 docs/copyright/architecture.png。

运行方式：python3 docs/copyright/build_architecture.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# 中文字体（按本环境实际可用字体回退：Noto Sans CJK JP 覆盖全部简体字形）
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans Kaithi", "Noto Serif CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
ax.set_xlim(0, 12)
ax.set_ylim(0, 8)
ax.axis("off")
ax.set_title("智能巡检机器人二维仿真系统 V1.0 架构图", fontsize=16, pad=16)


def box(x, y, w, h, text, fc, ec="#334155", fs=10.5, tc="#0f172a", weight="normal"):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
        linewidth=1.4, edgecolor=ec, facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc, weight=weight)


def arrow(x1, y1, x2, y2, text="", style="-|>", ls="-", color="#475569", fs=9, offset=(0, 0.12)):
    ax.add_patch(
        FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                        linewidth=1.4, color=color, linestyle=ls)
    )
    if text:
        ax.text((x1 + x2) / 2 + offset[0], (y1 + y2) / 2 + offset[1], text,
                ha="center", va="center", fontsize=fs, color="#334155",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


# ---------- 浏览器层 ----------
box(0.5, 6.3, 11, 1.35, "", "#eff6ff", ec="#3b82f6")
ax.text(6, 7.42, "浏 览 器（Vue 3 + Vite + 原生 Canvas）", ha="center", fontsize=11.5, weight="bold", color="#1e3a8a")
box(0.8, 6.45, 2.5, 0.72, "界面组件层\nMapCanvas / 控制台 / 仪表盘", "#dbeafe", fs=9)
box(3.6, 6.45, 2.6, 0.72, "RobotService 抽象\n（界面与数据源解耦）", "#dbeafe", fs=9)
box(6.5, 6.45, 2.5, 0.72, "SimulatedService\n离线仿真（默认）", "#dcfce7", fs=9)
box(9.3, 6.45, 2.0, 0.72, "RemoteService\n后端模式（?backend=）", "#fee2e2", fs=9)

# ---------- 通信层 ----------
box(0.5, 5.15, 11, 0.78, "通信协议：REST（地图 / 路径 / 传感器 / 事件）  +  WebSocket（state 帧 5Hz、anomaly / notice 事件帧）",
    "#fef9c3", ec="#ca8a04", fs=10)

# ---------- 后端层 ----------
box(0.5, 3.15, 11, 1.7, "", "#f0fdf4", ec="#22c55e")
ax.text(6, 4.62, "FastAPI 后端（Uvicorn 单容器，同时托管前端静态页）", ha="center", fontsize=11.5, weight="bold", color="#14532d")
box(0.8, 3.35, 2.4, 1.0, "REST 路由\n/api/v1/*", "#bbf7d0", fs=9.5)
box(3.5, 3.35, 2.4, 1.0, "WebSocket 路由\n/api/v1/ws", "#bbf7d0", fs=9.5)
box(6.2, 3.35, 2.4, 1.0, "SimulationEngine\n仿真引擎（状态机）", "#bbf7d0", fs=9.5, weight="bold")
box(8.9, 3.35, 2.4, 1.0, "PatrolManager\n巡检调度", "#bbf7d0", fs=9.5)

# ---------- 引擎内核 ----------
box(0.5, 1.55, 5.6, 1.3, "", "#faf5ff", ec="#a855f7")
ax.text(3.3, 2.62, "引擎内核组件", ha="center", fontsize=10.5, weight="bold", color="#581c87")
box(0.75, 1.7, 1.65, 0.72, "SensorSimulator\n三向射线/电量/温度", "#e9d5ff", fs=8.5)
box(2.6, 1.7, 1.65, 0.72, "AnomalyDetector\n规则 + 孤立森林", "#e9d5ff", fs=8.5)
box(4.45, 1.7, 1.5, 0.72, "A* 寻路\n四邻域 + 曼哈顿", "#e9d5ff", fs=8.5)

# ---------- 存储/日志 ----------
box(6.5, 1.55, 5.0, 1.3, "", "#fff7ed", ec="#f97316")
ax.text(9, 2.62, "数据与持久化", ha="center", fontsize=10.5, weight="bold", color="#7c2d12")
box(6.75, 1.7, 2.2, 0.72, "后端运行日志\nlogging 分级落盘", "#fed7aa", fs=8.5)
box(9.1, 1.7, 2.2, 0.72, "浏览器 localStorage\n地图 / 形象 / 主题", "#fed7aa", fs=8.5)

# ---------- 箭头 ----------
arrow(6, 6.3, 6, 5.95, "数据帧双向流动", offset=(1.9, 0))
arrow(6, 5.15, 6, 4.87, "")
arrow(6.2, 3.35, 6.2, 2.87, "")
arrow(6, 1.55, 6, 1.35, "", color="#f97316")
ax.text(6, 1.12, "异常事件 / 通知实时推送", ha="center", fontsize=9, color="#334155")

plt.tight_layout()
out = "/workspace/docs/copyright/architecture.png"
plt.savefig(out, bbox_inches="tight", facecolor="white")
print(f"已生成：{out}")

#!/usr/bin/env python3
"""
软著源代码文档生成脚本。

按登记要求生成《源代码》文档：源程序前后各 30 页、每页 50 行，
页眉含软件名称与版本号，页脚含页码；连续空行折叠为一行，
避免空行占比超标。源程序总量不足 3000 行时应提交全部，本项目约
7400 行，按 60 页标准节选。

运行方式：python3 docs/copyright/build_source_doc.py
输出文件：docs/copyright/source-code.md
"""

import os
from pathlib import Path

SOFTWARE_NAME = "智能巡检机器人二维仿真系统"
VERSION = "V1.0"
PAGE_LINES = 50
FRONT_PAGES = 30
BACK_PAGES = 30

# 源码组织顺序：后端核心 -> 前端核心 -> 测试（与答辩讲述顺序一致）
SOURCE_FILES = [
    "backend/app/main.py",
    "backend/app/core/config.py",
    "backend/app/core/constants.py",
    "backend/app/models/map.py",
    "backend/app/models/robot.py",
    "backend/app/models/events.py",
    "backend/app/algorithms/astar.py",
    "backend/app/services/simulation_engine.py",
    "backend/app/services/sensors.py",
    "backend/app/services/anomaly.py",
    "backend/app/services/patrol.py",
    "backend/app/api/rest.py",
    "backend/app/api/websocket.py",
    "frontend/src/services/robotService.js",
    "frontend/src/services/simulatedService.js",
    "frontend/src/services/remoteService.js",
    "frontend/src/services/mapPresets.js",
    "frontend/src/services/astar.js",
    "frontend/src/services/index.js",
    "frontend/src/utils/mapIO.js",
    "frontend/src/utils/robotAvatar.js",
    "frontend/src/App.vue",
    "frontend/src/components/MapCanvas.vue",
    "frontend/src/components/ControlPanel.vue",
    "frontend/src/components/StatusDashboard.vue",
    "frontend/src/components/AlertList.vue",
    "frontend/src/components/PlaybackBar.vue",
    "frontend/src/components/Joystick.vue",
    "frontend/src/components/MobileControls.vue",
    "frontend/src/components/ThemeToggle.vue",
    "backend/tests/test_simulation_engine.py",
    "backend/tests/test_api.py",
    "backend/tests/test_astar.py",
    "backend/tests/test_anomaly_ml.py",
    "frontend/src/services/__tests__/astar.test.js",
    "frontend/src/services/__tests__/simulatedService.test.js",
    "frontend/src/services/__tests__/features.test.js",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_source_lines():
    """按预定顺序拼接全部源码行，返回 [(文件路径, [行]), ...]。"""
    docs = []
    for rel in SOURCE_FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            print(f"警告：文件不存在，已跳过 {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        # 折叠连续空行，降低空行占比
        lines = []
        prev_blank = False
        for line in text.splitlines():
            if line.strip() == "":
                if prev_blank:
                    continue
                prev_blank = True
            else:
                prev_blank = False
            lines.append(line)
        docs.append((rel, lines))
    return docs


def paginate(lines, start_index, page_count):
    """从 start_index 起取 page_count 页，返回页列表。"""
    pages = []
    for i in range(page_count):
        chunk = lines[start_index + i * PAGE_LINES : start_index + (i + 1) * PAGE_LINES]
        if not chunk:
            break
        pages.append(chunk)
    return pages


def render_page(chunk, page_no, total_pages):
    """渲染单页：页眉 + 行号源码 + 页脚。"""
    out = [
        f"<!-- 第 {page_no} 页 / 共 {total_pages} 页 -->",
        "",
        f"**{SOFTWARE_NAME} {VERSION} 源代码**",
        "",
        "```",
    ]
    for offset, line in enumerate(chunk):
        out.append(f"{offset + 1:>3} | {line}")
    out.append("```")
    out.append("")
    out.append(f"第 {page_no} 页 / 共 {total_pages} 页")
    out.append("")
    out.append("---")
    out.append("")
    return out


def main():
    docs = load_source_lines()
    all_lines = []
    for rel, lines in docs:
        all_lines.append(f"# ===== 文件：{rel} =====")
        all_lines.extend(lines)
    total = len(all_lines)
    print(f"源程序总行数（折叠空行后）：{total}")

    front = paginate(all_lines, 0, FRONT_PAGES)
    back = paginate(all_lines, max(0, total - BACK_PAGES * PAGE_LINES), BACK_PAGES)
    pages = front + back
    total_pages = len(pages)
    print(f"生成页数：前 {len(front)} 页 + 后 {len(back)} 页 = {total_pages} 页")

    output = [
        f"# {SOFTWARE_NAME} {VERSION} 源代码",
        "",
        f"软件名称：{SOFTWARE_NAME}",
        f"版本号：{VERSION}",
        f"源程序总行数：{total} 行",
        f"本文档节选：前 {FRONT_PAGES} 页 + 后 {BACK_PAGES} 页，每页 {PAGE_LINES} 行",
        "",
        "---",
        "",
    ]
    for idx, chunk in enumerate(pages, start=1):
        output.extend(render_page(chunk, idx, total_pages))

    out_path = PROJECT_ROOT / "docs" / "copyright" / "source-code.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(output), encoding="utf-8")
    print(f"已生成：{out_path}")


if __name__ == "__main__":
    main()

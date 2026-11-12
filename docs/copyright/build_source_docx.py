#!/usr/bin/env python3
"""
生成软著用的《源代码》Word 文档。

要求：前 30 页 + 后 30 页，每页 50 行，页眉含软件名称与版本，页脚含页码。
与 build_source_doc.py 使用同一份文件顺序和空行折叠规则，只是输出从 Markdown
换成可直接打印的 .docx。

运行：
    python docs/copyright/build_source_docx.py
输出：
    docs/copyright/智能巡检机器人二维仿真系统-V2.4.1-源代码.docx
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent

# 复用现有脚本里的文件清单与空行折叠逻辑
spec = importlib.util.spec_from_file_location("build_source_doc", HERE / "build_source_doc.py")
base = importlib.util.module_from_spec(spec)
sys.modules["build_source_doc"] = base
spec.loader.exec_module(base)

SOFTWARE_NAME = "智能巡检机器人二维仿真系统"
VERSION = "V2.4.1"
PAGE_LINES = 50
FRONT_PAGES = 30
BACK_PAGES = 30
# 每行最多显示多少个"半角字符位"（中文按 2 个算），超过就折成下一行，
# 保证每页恰好 50 行、不会因为 Word 自动换行把版面撑破。
MAX_UNITS = 104


def visual_width(text: str) -> int:
    """估算一行在等宽字体下的显示宽度（半角=1，全角=2）。"""
    width = 0
    for ch in text:
        width += 2 if ord(ch) > 0x2E80 else 1
    return width


def wrap_line(line: str) -> list[str]:
    """把过长的源码行按显示宽度切成多行（视觉上等同自动换行）。"""
    if visual_width(line) <= MAX_UNITS:
        return [line]
    chunks: list[str] = []
    current = ""
    current_w = 0
    for ch in line:
        w = 2 if ord(ch) > 0x2E80 else 1
        if current_w + w > MAX_UNITS:
            chunks.append(current)
            current = ch
            current_w = w
        else:
            current += ch
            current_w += w
    if current:
        chunks.append(current)
    return chunks or [line]


def build_physical_lines(source_lines: list[str]) -> list[str]:
    """把所有源码行展开成"物理行"（含折行、文件分隔标题）。"""
    result: list[str] = []
    for rel, lines in source_lines:
        result.append(f"# ===== 文件：{rel} =====")
        for line in lines:
            result.extend(wrap_line(line))
    return result


def add_field(paragraph, instruction: str) -> None:
    """在段落里插入 Word 域（PAGE / NUMPAGES）。"""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(separate)
    run._r.append(text)
    run._r.append(end)


def style_run(run, size: float = 8.0, bold: bool = False) -> None:
    """统一设置等宽字体与中文回退字体。"""
    run.font.name = "Consolas"
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), "宋体")


def main() -> None:
    docs = base.load_source_lines()
    physical = build_physical_lines(docs)
    total = len(physical)
    print(f"物理行数（折叠空行 + 折长行后）：{total}")

    front = physical[: FRONT_PAGES * PAGE_LINES]
    back = physical[max(0, total - BACK_PAGES * PAGE_LINES):]
    pages = [front[i:i + PAGE_LINES] for i in range(0, len(front), PAGE_LINES)]
    pages += [back[i:i + PAGE_LINES] for i in range(0, len(back), PAGE_LINES)]
    pages = [p for p in pages if p]
    print(f"共 {len(pages)} 页（前 {len(front) // PAGE_LINES} + 后 {len(back) // PAGE_LINES}）")

    doc = Document()

    # 页面：A4，窄边距，给代码留足宽度
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.6)
    section.left_margin = Cm(1.6)
    section.right_margin = Cm(1.6)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.8)

    # 页眉
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run(f"{SOFTWARE_NAME} {VERSION} 源代码")
    style_run(run, size=9, bold=True)

    # 页脚：第 X 页 共 Y 页
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("第 ")
    style_run(run, size=9)
    add_field(footer, " PAGE ")
    run = footer.add_run(" 页  共 ")
    style_run(run, size=9)
    add_field(footer, " NUMPAGES ")
    run = footer.add_run(" 页")
    style_run(run, size=9)

    for page_index, page in enumerate(pages):
        for line_index, line in enumerate(page):
            paragraph = doc.add_paragraph()
            if page_index > 0 and line_index == 0:
                paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            paragraph.paragraph_format.line_spacing = Pt(12)
            run = paragraph.add_run(line if line else " ")
            style_run(run, size=8)

    out_path = HERE / f"{SOFTWARE_NAME}-{VERSION}-源代码.docx"
    doc.save(out_path)
    print(f"已生成：{out_path}")


if __name__ == "__main__":
    main()

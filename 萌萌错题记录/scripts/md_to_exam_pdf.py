#!/usr/bin/env python3
"""将组卷 Markdown 转为可打印 PDF（图片内嵌 base64，避免 file:// 本地图加载失败）。"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import re
import subprocess
import sys
import tempfile

import markdown

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

PRINT_CSS = """
@page {
  size: A4;
  margin: 18mm 16mm 24mm 16mm;
  @bottom-center {
    content: "第 " counter(page) " 页 / 共 " counter(pages) " 页";
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 9pt;
    color: #666;
  }
}
body {
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-size: 11pt; line-height: 1.55; color: #111;
}
h1 { font-size: 16pt; border-bottom: 2px solid #333; padding-bottom: 6px; margin-top: 0; }
.exam-header {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px; border-bottom: 2px solid #333; padding-bottom: 6px; margin-top: 0;
}
.exam-header h1 {
  border-bottom: none; padding-bottom: 0; margin: 0; flex: 1 1 auto;
}
.exam-header .exam-date {
  flex: 0 0 auto; font-size: 10pt; font-weight: normal; white-space: nowrap;
  color: #333;
}
h2 { font-size: 13pt; margin-top: 1.2em; page-break-after: avoid; }
blockquote {
  background: #f6f8fa; border-left: 4px solid #4a90d9;
  margin: 0.8em 0; padding: 8px 12px; font-size: 10pt;
}
h2 + blockquote { page-break-inside: avoid; }
hr { border: none; border-top: 1px dashed #ccc; margin: 1.2em 0; }
img {
  max-width: 100%; max-height: 280px; display: block; margin: 10px auto;
  object-fit: contain;
}
figure.geom { margin: 10px auto 14px; text-align: center; page-break-inside: avoid; }
figure.geom svg { display: block; margin: 0 auto; max-width: 220px; height: auto; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; }
th, td { border: 1px solid #ccc; padding: 6px 8px; }
div[style*="dashed"] {
  min-height: 90px !important; border: 1px dashed #999 !important;
  margin: 10px 0 !important; padding: 8px !important; background: #fafafa;
}
.exam-status {
  display: inline-block; font-size: 11pt; font-weight: 600;
  margin: 0 0 10px; padding: 4px 12px; border-radius: 4px;
}
.exam-status--done { background: #e6f4ea; color: #137333; border: 1px solid #81c995; }
.exam-status--pending { background: #fef7e0; color: #b06000; border: 1px solid #f9ab00; }
h2.exam-part { page-break-before: always; }
.tag-review { font-size: 9pt; color: #b06000; }
/* 答题卡：紧凑行高；主题+变式（1.1/1.2）同一行并排 */
table.sheet { table-layout: fixed; }
table.sheet th, table.sheet td { padding: 5px 8px; vertical-align: middle; }
table.sheet td.sheet-answer { min-height: auto; vertical-align: middle; }
table.sheet .sheet-compact { line-height: 1.35; }
table.sheet .q-sub {
  font-size: 9pt; color: #555; margin-right: 0.12em; white-space: nowrap;
}
table.sheet .sheet-compact .q-sub + .q-sub { margin-left: 0.65em; }
/* 选择/判断：短横线，不印 ABCD */
table.sheet .blank-short {
  display: inline-block; width: 2.4em; border-bottom: 1px solid #333;
  min-height: 1.05em; vertical-align: bottom; margin-right: 0.25em;
}
/* 填空：行内中等宽度横线（与 1.1/1.2 同排） */
table.sheet .blank-mid {
  display: inline-block; width: 5.5em; border-bottom: 1px solid #333;
  min-height: 1.05em; vertical-align: bottom; margin-right: 0.35em;
}
/* legacy：整行填空（数学应用题等仍可用） */
table.sheet .blank-line {
  display: block; border-bottom: 1px solid #333; min-height: 1.2em;
  margin: 3px 0; width: 100%;
}
/* 标准答案表：与答题卡同风格紧凑 */
table:not(.sheet) th, table:not(.sheet) td { padding: 4px 8px; }
/* 英语 legacy：仍可用 sheet-mc / sheet-opt（数学 math 模式改用 blank-short） */
table.sheet .sheet-mc {
  display: inline-block; min-width: 3.2em; border-bottom: 1px solid #333;
  text-align: center; margin-right: 1em; vertical-align: bottom;
}
table.sheet .sheet-opt {
  display: inline-block; min-width: 2.4em; margin-right: 1.6em; text-align: center;
}
/* 概念热身：只保留概念块，不展示引导语 blockquote */
h2:has(+ blockquote) + blockquote { display: none; }
h2 + blockquote + h3 { margin-top: 0.2em; }
/* 组卷 LaTeX → 可打印分数（md_to_exam_pdf 预处理，勿手写 \\dfrac） */
.math-inline { white-space: nowrap; }
.math-block {
  margin: 0.8em 0; padding: 8px 12px; text-align: center;
  font-size: 11pt; line-height: 1.85;
}
.mixed-num { display: inline-flex; align-items: center; white-space: nowrap; }
.math-frac {
  display: inline-block; vertical-align: middle; text-align: center;
  font-size: 0.88em; margin: 0 0.12em;
}
.math-frac .num {
  display: block; border-bottom: 1px solid #333;
  padding: 0 0.25em; line-height: 1.15;
}
.math-frac .den { display: block; padding: 0 0.25em; line-height: 1.15; }
.q-num { font-weight: 800; }
/* 题卷概要/填空横线（避免 Markdown 吞掉 ______） */
span.q-blank {
  display: inline-block; min-width: 5em; height: 1.1em;
  border-bottom: 1px solid #333; vertical-align: baseline;
  margin: 0 0.15em;
}
/* 数学题 · 题干 + 题下虚线答题区 */
.q-item { margin: 0 0 18px; page-break-inside: avoid; }
.q-item > p { margin: 0 0 8px; line-height: 1.55; }
.q-calc {
  border: 1px dashed #666; background: transparent;
  min-height: 100px; margin: 0; padding: 0;
}
.q-calc.short { min-height: 88px; }
.q-calc.mid { min-height: 112px; }
.q-calc.tall { min-height: 168px; }
"""

def build_print_css(_math_inline: bool = False) -> str:
    return PRINT_CSS


def parse_frontmatter_title(text: str) -> str | None:
    return parse_frontmatter_field(text, "title")


def parse_frontmatter_field(text: str, field: str) -> str | None:
    """从 YAML frontmatter 读取指定字段。"""
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n([\s\S]*?)\n---", text)
    if not m:
        return None
    prefix = f"{field}:"
    for line in m.group(1).splitlines():
        if line.strip().startswith(prefix):
            raw = line.split(":", 1)[1].strip()
            if (raw.startswith('"') and raw.endswith('"')) or (
                raw.startswith("'") and raw.endswith("'")
            ):
                raw = raw[1:-1]
            return raw.strip() or None
    return None


def resolve_exam_date_iso(full_text: str, md_path: str) -> str | None:
    """组卷日期：优先 YAML date，否则从 exam_/dictation_ stem 解析。"""
    iso = parse_frontmatter_field(full_text, "date")
    if iso:
        return iso.strip().strip('"').strip("'")
    stem = os.path.splitext(os.path.basename(md_path))[0]
    m = re.match(r"^(?:exam|dictation|memo)_(\d{2})(\d{2})(\d{2})_\d+$", stem)
    if m:
        yy, mm, dd = m.group(1), m.group(2), m.group(3)
        return f"20{yy}-{mm}-{dd}"
    return None


def format_exam_date_cn(iso_date: str) -> str:
    """YYYY-MM-DD → 组卷日期：yyyy年m月d日"""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", iso_date.strip())
    if not m:
        return f"组卷日期：{iso_date}"
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"组卷日期：{y}年{mo}月{d}日"


def inject_exam_header_date(html: str, date_label: str) -> str:
    """卷头 h1 右侧注入组卷日期。"""
    if not date_label:
        return html

    def repl(match: re.Match) -> str:
        title = match.group(1)
        return (
            f'<div class="exam-header"><h1>{title}</h1>'
            f'<span class="exam-date">{_escape_html(date_label)}</span></div>'
        )

    return re.sub(r"<h1>(.*?)</h1>", repl, html, count=1, flags=re.DOTALL)


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        return re.sub(r"^---[\s\S]*?---\n", "", text, count=1)
    return text


def _latex_frac_html(num: str, den: str) -> str:
    return (
        f'<span class="math-frac"><span class="num">{num}</span>'
        f'<span class="den">{den}</span></span>'
    )


def _convert_latex_fracs(text: str) -> str:
    """带分数 4\\frac{1}{6} 与 \\dfrac{a}{b} / \\frac{a}{b}。"""
    text = re.sub(
        r"(\d+)\\(?:d)?frac\{([^{}]+)\}\{([^{}]+)\}",
        lambda m: (
            f'<span class="mixed-num">{m.group(1)}'
            f"{_latex_frac_html(m.group(2), m.group(3))}</span>"
        ),
        text,
    )
    text = re.sub(
        r"\\(?:d)?frac\{([^{}]+)\}\{([^{}]+)\}",
        lambda m: _latex_frac_html(m.group(1), m.group(2)),
        text,
    )
    return text


def _convert_latex_tokens(text: str) -> str:
    """LaTeX 片段 → HTML/Unicode（小学组卷常用子集）。"""
    text = _convert_latex_fracs(text)
    replacements = [
        (r"\\times", "×"),
        (r"\\div", "÷"),
        (r"\\le", "≤"),
        (r"\\ge", "≥"),
        (r"\\neq", "≠"),
        (r"\\ldots", "…"),
        (r"\\cdots", "⋯"),
        (r"\\gcd", "gcd"),
        (r"\\mid", "∣"),
        (r"\\Rightarrow", "⇒"),
        (r"\\Longleftrightarrow", "⟺"),
        (r"\\mathbf\{([^{}]*)\}", r"<strong>\1</strong>"),
        (r"\\text\{([^{}]*)\}", r"\1"),
        (r"\\mathrm\{([^{}]*)\}", r"\1"),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text)
    text = text.replace(r"\{", "{").replace(r"\}", "}")
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    return text.strip()


def preprocess_latex_for_print(md_text: str) -> str:
    """
    Markdown 会把 \\( \\) 吞成普通括号，导致 PDF 露出 \\dfrac 原文。
    在 markdown.markdown 之前把 LaTeX 转为内联 HTML 分数。
    """

    def block_repl(match: re.Match) -> str:
        inner = _convert_latex_tokens(match.group(1))
        return f'<div class="math-block">{inner}</div>'

    def inline_repl(match: re.Match) -> str:
        inner = _convert_latex_tokens(match.group(1))
        return f'<span class="math-inline">{inner}</span>'

    md_text = re.sub(r"\\\[(.*?)\\\]", block_repl, md_text, flags=re.DOTALL)
    md_text = re.sub(r"\\\((.*?)\\\)", inline_repl, md_text)
    return md_text


# 题号样式：1、 / 1.1、 / ## 第 N 题 / 表格题号列 / 默写 N.
_QNUM_LINE = re.compile(r"^(?P<prefix>\s*)(?P<num>\d+(?:\.\d+)?)(、)", re.MULTILINE)
_QNUM_HEADING = re.compile(r"^(## 第 )(\d+)( 题)", re.MULTILINE)
_QNUM_TABLE = re.compile(r"^\| (\d+(?:\.\d+)?) \|", re.MULTILINE)
_QNUM_DICTATION = re.compile(r"^(?P<prefix>\s*)(?P<num>\d+)(\.)\s", re.MULTILINE)
_SHEET_TABLE = re.compile(r"<table class=\"sheet\">[\s\S]*?</table>")
_SHEET_QNUM = re.compile(r"(<tr>\s*<td[^>]*>)(\d+(?:\.\d+)?)")


def protect_fill_blanks(md_text: str) -> str:
    """将题卷 ______ 转为可见下划线（Markdown 否则会吞掉或乱解析）。"""
    return re.sub(r"_{3,}", '<span class="q-blank"></span>', md_text)


def bold_question_numbers_md(md_text: str) -> str:
    """题卷/答案表/默写卷：题号加粗（md 阶段）。"""
    md_text = _QNUM_LINE.sub(r"\g<prefix>**\g<num>\g<3>**", md_text)
    md_text = _QNUM_HEADING.sub(r"\1**\2**\3", md_text)
    md_text = _QNUM_TABLE.sub(r"| **\1** |", md_text)
    md_text = _QNUM_DICTATION.sub(r"\g<prefix>**\g<num>\g<3>** ", md_text)
    return md_text


def bold_question_numbers_html(html: str) -> str:
    """答题卡 HTML 表 + 题块段落：题号加粗。"""

    def _bold_sheet_table(match: re.Match) -> str:
        return _SHEET_QNUM.sub(r'\1<strong class="q-num">\2</strong>', match.group(0))

    html = _SHEET_TABLE.sub(_bold_sheet_table, html)
    html = re.sub(
        r"(<p[^>]*>)(\d+(?:\.\d+)?)(、)",
        r'\1<strong class="q-num">\2\3</strong>',
        html,
    )
    html = re.sub(
        r"\*\*(\d+(?:\.\d+)?、)\*\*",
        r'<strong class="q-num">\1</strong>',
        html,
    )
    return html


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _file_to_data_uri(path: str) -> str | None:
    if not path or path.startswith(("data:", "http://", "https://")):
        return path
    if not os.path.isfile(path):
        return None
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def inline_markdown_images(md_text: str, base_dir: str) -> tuple[str, list[str]]:
    missing: list[str] = []

    def repl(match: re.Match) -> str:
        alt, path = match.group(1), match.group(2).strip()
        if path.startswith(("data:", "http://", "https://")):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(base_dir, path))
        uri = _file_to_data_uri(abs_path)
        if not uri:
            missing.append(abs_path)
            return match.group(0)
        return f"![{alt}]({uri})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md_text), missing


def inline_html_images(html: str, base_dir: str) -> tuple[str, list[str]]:
    missing: list[str] = []

    def repl(match: re.Match) -> str:
        src = match.group(1).strip()
        if src.startswith(("data:", "http://", "https://")):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(base_dir, src))
        uri = _file_to_data_uri(abs_path)
        if not uri:
            missing.append(abs_path)
            return match.group(0)
        return match.group(0).replace(src, uri, 1)

    html = re.sub(r'<img\s+[^>]*src=["\']([^"\']+)["\']', repl, html)
    return html, missing


def strip_exam_status_badge(md_text: str) -> str:
    """卷面不再显示完成状态徽章（旧卷兼容：生成 PDF 时自动剔除）。"""
    md_text = re.sub(
        r'<p\s+class="exam-status[^"]*"[^>]*>.*?</p>\s*',
        "",
        md_text,
        flags=re.DOTALL,
    )
    return md_text


def insert_answer_sheet_page_breaks(html: str) -> str:
    """答题卡三件套 / 数学·语文 legacy：答案节前分页。"""
    for keyword in ("第二部分", "第三部分", "标准答案"):
        pat = re.compile(
            rf"<h2((?![^>]*page-break-before)[^>]*)>([^<]*{keyword}[^<]*)</h2>"
        )
        html = pat.sub(
            r'<h2\1 class="exam-part" style="page-break-before:always;">\2</h2>',
            html,
            count=1,
        )
    return html


def find_chrome() -> str:
    for path in CHROME_PATHS:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("未找到 Chrome/Chromium，无法生成 PDF")


def md_to_pdf(md_path: str, pdf_path: str | None = None) -> str:
    """从组卷 .md 生成同目录 .pdf；HTML 仅作 Chrome 打印中间态（临时文件，不落盘）。"""
    md_path = os.path.abspath(md_path)
    if not os.path.isfile(md_path):
        raise FileNotFoundError(md_path)

    base_dir = os.path.dirname(md_path)
    pdf_path = os.path.abspath(pdf_path or md_path.replace(".md", ".pdf"))

    with open(md_path, encoding="utf-8") as f:
        full_text = f.read()

    page_title = parse_frontmatter_title(full_text) or os.path.splitext(
        os.path.basename(md_path)
    )[0]
    raw = strip_frontmatter(full_text)
    raw = strip_exam_status_badge(raw)
    raw = preprocess_latex_for_print(raw)
    raw = protect_fill_blanks(raw)
    raw = bold_question_numbers_md(raw)

    raw, miss_md = inline_markdown_images(raw, base_dir)
    body = markdown.markdown(raw, extensions=["tables", "fenced_code"])
    body = insert_answer_sheet_page_breaks(body)
    body = bold_question_numbers_html(body)
    exam_iso = resolve_exam_date_iso(full_text, md_path)
    if exam_iso:
        body = inject_exam_header_date(body, format_exam_date_cn(exam_iso))
    body, miss_html = inline_html_images(body, base_dir)
    missing = sorted(set(miss_md + miss_html))
    if missing:
        print("警告：以下图片未找到，PDF 中可能缺失：", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)

    html_doc = (
        f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{_escape_html(page_title)}</title>"
        f"<style>{build_print_css()}</style></head><body>{body}</body></html>"
    )
    fd, html_path = tempfile.mkstemp(suffix=".html", prefix="exam_print_")
    os.close(fd)
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_doc)

        chrome = find_chrome()
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            f"file://{html_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "Chrome 打印 PDF 失败")
    finally:
        try:
            os.remove(html_path)
        except OSError:
            pass

    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="组卷 Markdown → 可打印 PDF")
    parser.add_argument("md_path", help="试卷 .md 路径")
    parser.add_argument("-o", "--output", help="输出 PDF 路径（默认同名 .pdf）")
    args = parser.parse_args()
    pdf = md_to_pdf(args.md_path, args.output)
    print(f"✅ PDF 已生成：{pdf}")


if __name__ == "__main__":
    main()

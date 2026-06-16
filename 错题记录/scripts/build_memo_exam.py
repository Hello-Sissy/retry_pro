#!/usr/bin/env python3
"""生成 memo_*.md 词语默写卷（调用 pick_memo_spaced 逻辑 + 落盘）。"""

from __future__ import annotations

import argparse
import random
import re
import sys
from datetime import date
from pathlib import Path

import frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo_wordlist import (  # noqa: E402
    answer_for_entry,
    auto_pick_types,
    load_all_pools,
    normalize_pool_type,
    pick_from_pool,
)
from spaced_review_common import parse_date  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
OUT_DIRS = [BASE / "02_自定义组卷" / "未完成", BASE / "02_自定义组卷" / "已完成"]


def next_memo_seq(today: date) -> int:
    yy, mm, dd = today.year % 100, today.month, today.day
    prefix = f"memo_{yy:02d}{mm:02d}{dd:02d}_"
    max_n = 0
    for d in OUT_DIRS:
        if not d.is_dir():
            continue
        for p in d.glob(f"{prefix}*.md"):
            m = re.match(rf"{re.escape(prefix)}(\d+)$", p.stem)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def format_question(num: int, entry, pool: str) -> str:
    f = entry.fields
    line = f"________________________________________________"
    if pool == "语文字形":
        return f"{num}、根据拼音写出汉字：{f.get('拼音', '').strip()} {line}"
    if pool == "专名":
        return f"{num}、{f.get('中文', '').strip()} → 写英文专名 {line}"
    if pool == "短语":
        return f"{num}、{f.get('中文', '').strip()} {line}"
    if pool == "句子":
        return f"{num}、{f.get('中文', '').strip()} {line}"
    if pool == "词性转换":
        return (
            f"{num}、{f.get('原词', '').strip()} → **{f.get('目标词性', '').strip()}** "
            f"{f.get('中文', '').strip()} {line}"
        )
    return f"{num}、{line}"


def section_title(pool: str, idx: int) -> str:
    titles = {
        "语文字形": "语文字形默写",
        "专名": "英语专有名词",
        "短语": "短语默写",
        "句子": "句子默写",
        "词性转换": "词性转换",
    }
    cn = ["一", "二", "三", "四", "五"][idx]
    return f"## {cn}、{titles.get(pool, pool)}"


def build_body(sections: list[tuple[str, list]], start_num: int = 1) -> tuple[str, dict, dict, int]:
    lines: list[str] = []
    answers: dict = {}
    mapping: dict = {}
    num = start_num
    for sec_idx, (pool, picked) in enumerate(sections):
        lines.append(section_title(pool, sec_idx))
        lines.append("")
        for entry, _mode in picked:
            lines.append(format_question(num, entry, pool))
            lines.append("")
            answers[num] = answer_for_entry(entry)
            mapping[num] = {
                "pool": pool,
                "key": entry.key,
                "review_count": entry.review_count(),
            }
            num += 1
        if sec_idx < len(sections) - 1:
            lines.append("---")
            lines.append("")

    # 标准答案
    lines.append("---")
    lines.append("")
    lines.append("## 标准答案")
    lines.append("")
    lines.append("> **已复习次数**：组卷时词表 `复习次数`（历次已完成默写卷中出现并批改的累计，不论对错）。本卷批改完成后 +1；可念给孩子听。")
    lines.append("")
    lines.append("| 题号 | 标准答案 | 已复习次数 |")
    lines.append("|:---:|:---|:---:|")
    for q, ans in sorted(answers.items()):
        rc = mapping[q]["review_count"]
        lines.append(f"| {q} | {ans} | {rc} |")

    return "\n".join(lines), answers, mapping, num - 1


def main() -> None:
    p = argparse.ArgumentParser(description="生成 memo_* 词语默写卷")
    p.add_argument("--types", help="指定类型，逗号分隔")
    p.add_argument("--per-type", "-n", type=int, default=8)
    p.add_argument("--type-count", type=int, default=2)
    p.add_argument("--today", help="YYYY-MM-DD")
    p.add_argument("--seed", type=int)
    p.add_argument("--dry-run", action="store_true", help="只打印路径不写文件")
    args = p.parse_args()

    rng = random.Random(args.seed)
    today = parse_date(args.today) or date.today()
    pools = load_all_pools()

    if args.types:
        type_names = []
        for t in args.types.split(","):
            canonical = normalize_pool_type(t.strip())
            if not canonical:
                print(f"未知类型: {t}", file=sys.stderr)
                sys.exit(1)
            type_names.append(canonical)
    else:
        type_names = auto_pick_types(pools, args.type_count, today, rng)

    sections: list[tuple[str, list]] = []
    for pool in type_names:
        picked, _ = pick_from_pool(pools.get(pool, []), args.per_type, today, rng)
        sections.append((pool, picked))

    type_label = "+".join(type_names)
    seq = next_memo_seq(today)
    stem = f"memo_{today.year % 100:02d}{today.month:02d}{today.day:02d}_{seq:02d}"
    body, answers, mapping, total = build_body(sections)

    meta = {
        "exam_type": "memo",
        "memo_id": stem,
        "date": today.isoformat(),
        "title": f"学生 词语默写卷·{type_label}",
        "sections": [{"type": pool, "count": len(picked)} for pool, picked in sections],
        "完成日期": [],
        "answers": answers,
        "mapping": mapping,
    }

    h1 = f"# 学生 词语默写卷 (ID: {stem.replace('_', '')})"
    content = f"{h1}\n\n{body}\n"
    post = frontmatter.Post(content, **meta)
    full_md = frontmatter.dumps(post)

    out_path = BASE / "02_自定义组卷" / "未完成" / f"{stem}.md"
    if args.dry_run:
        print(full_md[:500])
        print(f"... → {out_path}")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_md, encoding="utf-8")
    print(f"✅ 已生成 {out_path}（共 {total} 题）")


if __name__ == "__main__":
    main()

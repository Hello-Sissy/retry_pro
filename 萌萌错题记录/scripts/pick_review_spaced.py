#!/usr/bin/env python3
"""按艾宾浩斯间隔从 已毕业/ 抽取长线记忆复检题（默认 1 道）。"""

from __future__ import annotations

import argparse
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spaced_review_common import (  # noqa: E402
    MAX_REVIEW_LEVEL,
    REVIEW_INTERVALS,
    advance_review_schedule,
    init_review_on_graduate,
    parse_date,
)

BASE = Path(__file__).resolve().parent.parent
ACTIVE_ROOT = BASE / "01_错题库"
EXAM_DIRS = [BASE / "02_自定义组卷" / "未完成", BASE / "02_自定义组卷" / "已完成"]


def _stem_date(stem: str) -> date | None:
    m = re.match(r"^(?:exam|dictation|memo)_(\d{2})(\d{2})(\d{2})_\d+$", stem)
    if not m:
        return None
    yy, mm, dd = (int(x) for x in m.groups())
    return date(2000 + yy, mm, dd)


def _exam_completion_dates(stem: str) -> list[date]:
    dates: list[date] = []
    for d in EXAM_DIRS:
        md = d / f"{stem}.md"
        if not md.is_file():
            continue
        post = frontmatter.load(md)
        raw = post.get("完成日期") or []
        if isinstance(raw, str):
            raw = [raw]
        for item in raw:
            parsed = parse_date(item)
            if parsed:
                dates.append(parsed)
        if not dates:
            parsed = parse_date(post.get("date"))
            if parsed:
                dates.append(parsed)
            else:
                sd = _stem_date(stem)
                if sd:
                    dates.append(sd)
    return dates


def _last_review_from_links(meta: dict) -> date | None:
    stems = meta.get("关联组卷") or []
    if isinstance(stems, str):
        stems = [stems]
    best: date | None = None
    for stem in stems:
        stem = str(stem).strip()
        if not stem:
            continue
        for cd in _exam_completion_dates(stem):
            if best is None or cd > best:
                best = cd
    return best


def _effective_next_review(meta: dict, today: date) -> tuple[date, int, str]:
    level = int(meta.get("review_level", 0) or 0)
    level = max(0, min(level, MAX_REVIEW_LEVEL))

    explicit = parse_date(meta.get("next_review"))
    if explicit:
        overdue = (today - explicit).days
        return explicit, overdue, "next_review"

    last = _last_review_from_links(meta)
    if last:
        interval = REVIEW_INTERVALS[level]
        nxt = last + timedelta(days=interval)
        overdue = (today - nxt).days
        return nxt, overdue, f"关联组卷推算(level={level})"

    return today, 0, "无记录·视为到期"


def collect_graduated(
    subject: str | None = None,
    module_prefix: str | None = None,
) -> list[tuple[Path, dict, date, int, str]]:
    pool: list[tuple[Path, dict, date, int, str]] = []
    today = date.today()
    for md in ACTIVE_ROOT.rglob("*.md"):
        if "已毕业" not in md.parts:
            continue
        post = frontmatter.load(md)
        m = int(post.get("mastery", 4) or 4)
        if m < 4:
            continue
        if subject and post.get("subject") != subject:
            continue
        mod = post.get("module") or ""
        if module_prefix and not str(mod).startswith(module_prefix):
            continue
        meta = post.metadata
        nxt, overdue, src = _effective_next_review(meta, today)
        pool.append((md, meta, nxt, overdue, src))
    return pool


def pick_review(
    pool: list[tuple[Path, dict, date, int, str]],
    *,
    today: date | None = None,
) -> tuple[Path, dict, date, int, str, str] | None:
    if not pool:
        return None
    today = today or date.today()

    due = [item for item in pool if item[3] >= 0]
    if due:
        items = due[:]
        weights = [max(1, item[3] + 1) for item in items]
        idx = random.choices(range(len(items)), weights=weights, k=1)[0]
        chosen_item = items[idx]
        md, meta, nxt, overdue, src = chosen_item
        return md, meta, nxt, overdue, src, "到期池·逾期加权"

    earliest = min(pool, key=lambda x: x[2])
    md, meta, nxt, overdue, src = earliest
    days_until = (nxt - today).days
    return md, meta, nxt, overdue, src, f"无逾期·最近到期({days_until}天后)"


def main() -> None:
    p = argparse.ArgumentParser(description="艾宾浩斯间隔抽取已毕业复检题")
    p.add_argument("-n", type=int, default=1, help="抽取数量（默认 1）")
    p.add_argument("--subject", help="数学|语文|英语")
    p.add_argument("--module", help="模块前缀，如 E2.")
    p.add_argument("--today", help="模拟今天 YYYY-MM-DD（调试用）")
    p.add_argument("--seed", type=int, help="随机种子")
    args = p.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    today = parse_date(args.today) or date.today()
    pool = collect_graduated(args.subject, args.module)
    if not pool:
        print("无符合条件的已毕业题。")
        return

    due_count = sum(1 for _, _, _, od, _ in pool if od >= 0)
    print(f"已毕业候选 {len(pool)} 道，其中到期 {due_count} 道（截至 {today}）\n")

    n = min(args.n, len(pool))
    remaining = pool[:]
    for i in range(n):
        if args.today:
            remaining = []
            for md, meta, _, _, _ in pool:
                nxt, overdue, src = _effective_next_review(meta, today)
                remaining.append((md, meta, nxt, overdue, src))

        result = pick_review(remaining, today=today)
        if not result:
            break
        md, meta, nxt, overdue, src, mode = result
        level = int(meta.get("review_level", 0) or 0)
        print(
            f"  [{i + 1}] {meta.get('id', '?')} · {meta.get('title', md.stem)}\n"
            f"      下次复习 {nxt} · 逾期 {max(0, overdue)} 天 · level {level} · {src} · {mode}"
        )
        remaining = [x for x in remaining if x[0] != md]


if __name__ == "__main__":
    main()

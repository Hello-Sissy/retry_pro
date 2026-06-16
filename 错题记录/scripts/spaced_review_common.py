#!/usr/bin/env python3
"""艾宾浩斯间隔复习共用常量与日期工具。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

# review_level 0→首次 +1 天，做对后依次拉长
REVIEW_INTERVALS = [1, 3, 7, 14, 30, 60]
MAX_REVIEW_LEVEL = len(REVIEW_INTERVALS) - 1
MASTERED_LEVEL_THRESHOLD = 2  # review_level >= 2 → 状态=已掌握（仍会到期进卷）


def parse_date(s: str | date | None) -> date | None:
    if s is None or s == "":
        return None
    if isinstance(s, date):
        return s
    raw = str(s).strip().strip("'\"")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def advance_review_schedule(level: int, from_date: date) -> tuple[int, date]:
    """做对后推进档位与下次复习日。"""
    new_level = min(int(level) + 1, MAX_REVIEW_LEVEL)
    days = REVIEW_INTERVALS[new_level]
    return new_level, from_date + timedelta(days=days)


def init_review_on_entry(entry_date: date) -> tuple[int, date]:
    """新词录入或写错后重置。"""
    return 0, entry_date + timedelta(days=REVIEW_INTERVALS[0])


def init_review_on_graduate(graduation_date: date) -> tuple[int, date]:
    """错题毕业移入 已毕业/ 时初始化。"""
    return init_review_on_entry(graduation_date)


def status_from_level(level: int) -> str:
    return "已掌握" if level >= MASTERED_LEVEL_THRESHOLD else "在练"


def overdue_days(next_review: date, today: date) -> int:
    return (today - next_review).days

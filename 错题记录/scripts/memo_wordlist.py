#!/usr/bin/env python3
"""词语默写五类词表：解析、艾宾浩斯抽题、批改回写。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from spaced_review_common import (
    MASTERED_LEVEL_THRESHOLD,
    advance_review_schedule,
    init_review_on_entry,
    overdue_days,
    parse_date,
    status_from_level,
)

BASE = Path(__file__).resolve().parent.parent

POOL_CONFIG: dict[str, dict[str, Any]] = {
    "语文字形": {
        "path": BASE / "04_语文默写清单/默写词表.md",
        "aliases": ["语文字形", "语文", "chn"],
    },
    "专名": {
        "path": BASE / "03_英语默写/专有名词词表.md",
        "aliases": ["专名", "专有名词", "noun"],
    },
    "短语": {
        "path": BASE / "03_英语默写/短语词表.md",
        "aliases": ["短语", "phrase"],
    },
    "句子": {
        "path": BASE / "03_英语默写/句子词表.md",
        "aliases": ["句子", "sentence"],
    },
    "词性转换": {
        "path": BASE / "03_英语默写/词性转换词表.md",
        "aliases": ["词性转换", "wordform", "词形"],
    },
}

TYPE_ALIASES: dict[str, str] = {}
for canonical, cfg in POOL_CONFIG.items():
    for alias in [canonical, *cfg["aliases"]]:
        TYPE_ALIASES[alias.lower()] = canonical


@dataclass
class MemoEntry:
    pool: str
    row_index: int  # 0-based data row in table
    fields: dict[str, str]
    key: str
    file_path: Path

    @property
    def status(self) -> str:
        return self.fields.get("状态", "在练").strip() or "在练"

    def review_level(self) -> int:
        raw = self.fields.get("review_level", "").strip()
        if raw.isdigit():
            return max(0, min(5, int(raw)))
        return 0

    def review_count(self) -> int:
        """历次已完成默写卷中出现并批改的次数（方案 A：不论对错）。"""
        raw = self.fields.get("复习次数", "").strip()
        if raw.isdigit():
            return max(0, int(raw))
        return 0

    def effective_next_review(self, today: date) -> tuple[date, int, str]:
        """返回 (next_review, overdue_days, source)。"""
        explicit = parse_date(self.fields.get("next_review"))
        if explicit:
            return explicit, overdue_days(explicit, today), "next_review"

        stored = parse_date(self.fields.get("入库日期")) or today
        level = self.review_level()

        if self.status == "已掌握":
            from spaced_review_common import REVIEW_INTERVALS

            level = max(level, MASTERED_LEVEL_THRESHOLD)
            nxt = stored + timedelta(days=REVIEW_INTERVALS[min(level, 5)])
            return nxt, overdue_days(nxt, today), "已掌握推算"

        # 在练且无 next_review → 视为到期
        return today, 0, "在练·视为到期"


def normalize_pool_type(name: str) -> str | None:
    return TYPE_ALIASES.get(name.strip().lower())


def make_key(pool: str, fields: dict[str, str]) -> str:
    if pool == "语文字形":
        return fields.get("词语", "").strip()
    if pool == "专名":
        return fields.get("中文", "").strip()
    if pool in ("短语", "句子"):
        return fields.get("中文", "").strip()
    if pool == "词性转换":
        return "|".join(
            [
                fields.get("原词", "").strip(),
                fields.get("目标词性", "").strip(),
                fields.get("中文", "").strip(),
            ]
        )
    return ""


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    parts = [p.strip() for p in line.strip("|").split("|")]
    return parts


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in cells if c)


def parse_wordlist(path: Path, pool: str) -> tuple[list[str], list[MemoEntry]]:
    """返回 (file_lines, entries)。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries: list[MemoEntry] = []
    headers: list[str] = []
    in_table = False
    data_row = 0

    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = _split_table_row(line)
        if not cells:
            continue
        if _is_separator_row(cells):
            in_table = True
            continue
        if not in_table:
            headers = [h.strip() for h in cells]
            continue
        if not headers:
            continue
        fields = {headers[j]: cells[j] if j < len(cells) else "" for j in range(len(headers))}
        # 跳过空行
        if pool == "语文字形" and not fields.get("词语", "").strip():
            continue
        if pool == "专名" and not fields.get("英文", "").strip():
            continue
        if pool in ("短语", "句子") and not fields.get("中文", "").strip():
            continue
        if pool == "词性转换" and not fields.get("原词", "").strip():
            continue

        key = make_key(pool, fields)
        entries.append(
            MemoEntry(pool=pool, row_index=data_row, fields=fields, key=key, file_path=path)
        )
        data_row += 1

    return lines, entries


def load_pool(pool: str) -> list[MemoEntry]:
    canonical = normalize_pool_type(pool) or pool
    cfg = POOL_CONFIG.get(canonical)
    if not cfg:
        raise ValueError(f"未知词表类型: {pool}")
    _, entries = parse_wordlist(cfg["path"], canonical)
    return entries


def load_all_pools() -> dict[str, list[MemoEntry]]:
    return {name: load_pool(name) for name in POOL_CONFIG}


def score_pool(entries: list[MemoEntry], today: date) -> float:
    score = 0.0
    for e in entries:
        _, od, _ = e.effective_next_review(today)
        if od >= 0:
            score += max(1, od + 1)
        if e.status == "在练":
            score += 0.5
    return score


def pick_from_pool(
    entries: list[MemoEntry],
    n: int,
    today: date,
    rng: random.Random,
) -> tuple[list[tuple[MemoEntry, str]], list[MemoEntry]]:
    """返回 ([(entry, pick_mode), ...], remaining_unused)。"""
    if not entries:
        return [], []

    n = min(n, len(entries))
    chosen: list[tuple[MemoEntry, str]] = []
    remaining = entries[:]

    def weighted_pick(candidates: list[MemoEntry], weights: list[int]) -> MemoEntry:
        idx = rng.choices(range(len(candidates)), weights=weights, k=1)[0]
        return candidates[idx]

    # 1. 到期池
    due = [e for e in remaining if e.effective_next_review(today)[1] >= 0]
    while due and len(chosen) < n:
        weights = [max(1, e.effective_next_review(today)[1] + 1) for e in due]
        pick = weighted_pick(due, weights)
        chosen.append((pick, "到期池"))
        due.remove(pick)
        remaining.remove(pick)

    # 2. 在练补足
    practicing = [e for e in remaining if e.status == "在练"]
    while practicing and len(chosen) < n:
        weights = []
        for e in practicing:
            stored = parse_date(e.fields.get("入库日期")) or today
            weights.append(max(1, (today - stored).days + 1))
        pick = weighted_pick(practicing, weights)
        chosen.append((pick, "在练补足"))
        practicing.remove(pick)
        remaining.remove(pick)

    # 3. 已掌握未到期 → 最早 next_review
    rest = sorted(remaining, key=lambda e: e.effective_next_review(today)[0])
    for e in rest:
        if len(chosen) >= n:
            break
        chosen.append((e, "最近到期补足"))
        remaining.remove(e)

    return chosen, remaining


def auto_pick_types(
    pools: dict[str, list[MemoEntry]],
    count: int,
    today: date,
    rng: random.Random,
) -> list[str]:
    scored = [(score_pool(entries, today), name) for name, entries in pools.items() if entries]
    scored.sort(key=lambda x: (-x[0], x[1]))
    if not scored:
        return []
    top_score = scored[0][0]
    top = [name for s, name in scored if s == top_score]
    rng.shuffle(top)
    selected = top[:count]
    if len(selected) < count:
        rest = [name for _, name in scored if name not in selected]
        selected.extend(rest[: count - len(selected)])
    return selected[:count]


def apply_grade(entry: MemoEntry, correct: bool, grade_date: date) -> dict[str, str]:
    """返回要写入 fields 的更新。"""
    level = entry.review_level()
    updates: dict[str, str] = {"复习次数": str(entry.review_count() + 1)}

    if correct:
        new_level, nxt = advance_review_schedule(level, grade_date)
        updates["review_level"] = str(new_level)
        updates["next_review"] = nxt.isoformat()
        updates["状态"] = status_from_level(new_level)
    else:
        new_level, nxt = init_review_on_entry(grade_date)
        updates["review_level"] = str(new_level)
        updates["next_review"] = nxt.isoformat()
        updates["状态"] = "在练"

    return updates


def _ensure_header_columns(headers: list[str]) -> list[str]:
    out = headers[:]
    if "复习次数" not in out:
        if "连续对" in out:
            idx = out.index("连续对") + 1
            out.insert(idx, "复习次数")
        else:
            out.append("复习次数")
    for col in ("review_level", "next_review"):
        if col not in out:
            out.append(col)
    return out


def update_entry_in_file(entry: MemoEntry, updates: dict[str, str]) -> None:
    path = entry.file_path
    lines = path.read_text(encoding="utf-8").splitlines()
    headers: list[str] = []
    in_table = False
    data_idx = -1
    target_line = -1

    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = _split_table_row(line)
        if not cells:
            continue
        if _is_separator_row(cells):
            in_table = True
            continue
        if not in_table:
            headers = _ensure_header_columns([h.strip() for h in cells])
            sep_parts = [":---"] * len(headers)
            lines[i + 1] = "|" + "|".join(sep_parts) + "|"
            continue
        data_idx += 1
        if data_idx == entry.row_index:
            target_line = i
            break

    if target_line < 0:
        raise ValueError(f"找不到词表行: {entry.pool} / {entry.key}")

    fields = {**entry.fields, **updates}
    row_cells = [fields.get(h, "") for h in headers]
    lines[target_line] = "| " + " | ".join(row_cells) + " |"

    # 更新表头行（若刚加列）
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and i + 1 < len(lines):
            cells = _split_table_row(line)
            if cells and not _is_separator_row(cells):
                if "词语" in cells or "中文" in cells or "英文" in cells:
                    if "review_level" not in cells:
                        lines[i] = "| " + " | ".join(_ensure_header_columns(cells)) + " |"
                    break

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_entry(pool: str, key: str) -> MemoEntry | None:
    for e in load_pool(pool):
        if e.key == key:
            return e
    return None


def answer_for_entry(entry: MemoEntry) -> str:
    f = entry.fields
    if entry.pool == "语文字形":
        return f.get("词语", "").strip()
    if entry.pool == "专名":
        return f.get("英文", "").strip()
    if entry.pool in ("短语", "句子"):
        return f.get("英文", "").strip()
    if entry.pool == "词性转换":
        return f.get("英文", "").strip()
    return ""

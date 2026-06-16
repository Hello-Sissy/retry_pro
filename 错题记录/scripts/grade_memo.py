#!/usr/bin/env python3
"""词语默写卷 memo_* 批改：回写词表 review_level / next_review / 状态。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo_wordlist import apply_grade, find_entry, normalize_pool_type, update_entry_in_file  # noqa: E402
from spaced_review_common import parse_date  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
MEMO_DIRS = [BASE / "02_自定义组卷" / "未完成", BASE / "02_自定义组卷" / "已完成"]


def resolve_memo(stem: str) -> Path:
    hits = []
    for d in MEMO_DIRS:
        p = d / f"{stem}.md"
        if p.is_file():
            hits.append(p)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise FileNotFoundError(f"找不到 {stem}.md")
    raise FileNotFoundError(f"{stem} 在多处存在: {hits}")


def parse_results(text: str) -> dict[int, bool]:
    """解析 1对2错1.1对 或 1对，2错。"""
    out: dict[int, bool] = {}
    text = text.replace("，", ",").replace(" ", "")
    for m in re.finditer(r"(\d+)对", text):
        out[int(m.group(1))] = True
    for m in re.finditer(r"(\d+)错", text):
        out[int(m.group(1))] = False
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="批改 memo_* 词语默写卷")
    p.add_argument("stem", help="如 memo_260610_01")
    p.add_argument("results", help='如 "1对2错3对"')
    p.add_argument("--date", help="批改日期 YYYY-MM-DD，默认今天")
    args = p.parse_args()

    grade_date = parse_date(args.date) or date.today()
    md_path = resolve_memo(args.stem)
    post = frontmatter.load(md_path)
    mapping_raw = post.get("mapping") or {}
    mapping: dict[int, dict] = {}
    for k, v in mapping_raw.items():
        mapping[int(k)] = v if isinstance(v, dict) else {}
    results = parse_results(args.results)

    updated = 0
    for qnum, correct in sorted(results.items()):
        if qnum not in mapping:
            print(f"警告：题号 {qnum} 不在 mapping 中", file=sys.stderr)
            continue
        item = mapping[qnum]
        pool = item.get("pool") or item.get("type")
        row_key = item.get("key")
        if not pool or not row_key:
            print(f"警告：题号 {qnum} mapping 不完整", file=sys.stderr)
            continue
        pool = normalize_pool_type(str(pool)) or str(pool)
        entry = find_entry(pool, str(row_key))
        if not entry:
            print(f"警告：找不到词条 {pool} / {row_key}", file=sys.stderr)
            continue
        updates = apply_grade(entry, correct, grade_date)
        update_entry_in_file(entry, updates)
        updated += 1
        mark = "对" if correct else "错"
        print(
            f"  {qnum} {mark} → {pool} / {row_key} · 复习次数 {updates['复习次数']}"
            f" · level {updates['review_level']} · next {updates['next_review']}"
        )

    # 完成日期
    done = post.get("完成日期") or []
    if isinstance(done, str):
        done = [done]
    iso = grade_date.isoformat()
    if iso not in done:
        done.append(iso)
    post["完成日期"] = done

    # 移至已完成
    out_dir = BASE / "02_自定义组卷" / "已完成"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / md_path.name
    pdf_src = md_path.with_suffix(".pdf")
    dest.write_text(frontmatter.dumps(post), encoding="utf-8")
    if md_path.resolve() != dest.resolve():
        md_path.unlink(missing_ok=True)
    pdf_dest = dest.with_suffix(".pdf")
    if pdf_src.is_file():
        if pdf_dest.exists():
            pdf_dest.unlink()
        pdf_src.rename(pdf_dest)

    print(f"\n✅ 默写批改完成，已更新词表 {updated} 行；{args.stem} → 已完成/")


if __name__ == "__main__":
    main()

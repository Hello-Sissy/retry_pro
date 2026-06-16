#!/usr/bin/env python3
"""词语默写：艾宾浩斯抽题（默认 2 类 × 8 题）。"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

# 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo_wordlist import (  # noqa: E402
    POOL_CONFIG,
    auto_pick_types,
    load_all_pools,
    normalize_pool_type,
    pick_from_pool,
)
from spaced_review_common import parse_date  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="词语默写艾宾浩斯抽题")
    p.add_argument("--types", help="指定类型，逗号分隔，如 短语,词性转换")
    p.add_argument("--per-type", "-n", type=int, default=8, help="每类抽取数量（默认 8）")
    p.add_argument("--type-count", type=int, default=2, help="自动模式下选几类（默认 2）")
    p.add_argument("--today", help="模拟今天 YYYY-MM-DD")
    p.add_argument("--seed", type=int, help="随机种子")
    p.add_argument("--json", action="store_true", help="输出 JSON（供组卷脚本消费）")
    args = p.parse_args()

    rng = random.Random(args.seed)
    today = parse_date(args.today) or date.today()
    pools = load_all_pools()

    if args.types:
        type_names = []
        for t in args.types.split(","):
            t = t.strip()
            canonical = normalize_pool_type(t)
            if not canonical:
                print(f"未知类型: {t}", file=sys.stderr)
                sys.exit(1)
            type_names.append(canonical)
    else:
        type_names = auto_pick_types(pools, args.type_count, today, rng)

    if not type_names:
        print("无可用词表类型。")
        return

    result: dict = {"date": today.isoformat(), "sections": []}

    print(f"词语默写抽题（截至 {today}）\n")
    for pool in type_names:
        entries = pools.get(pool, [])
        picked, _ = pick_from_pool(entries, args.per_type, today, rng)
        section = {
            "type": pool,
            "requested": args.per_type,
            "picked": len(picked),
            "items": [],
        }
        print(f"## {pool}（{len(picked)}/{args.per_type}）")
        for entry, mode in picked:
            nxt, od, src = entry.effective_next_review(today)
            item = {
                "pool": pool,
                "key": entry.key,
                "mode": mode,
                "next_review": nxt.isoformat(),
                "overdue_days": max(0, od),
                "status": entry.status,
                "review_level": entry.review_level(),
                "fields": entry.fields,
            }
            section["items"].append(item)
            label = entry.key.replace("|", " · ")
            print(
                f"  - {label}\n"
                f"    {mode} · 下次 {nxt} · 逾期 {max(0, od)} 天 · "
                f"level {entry.review_level()} · {entry.status}"
            )
        if len(picked) < args.per_type:
            print(f"  ⚠ 该类仅 {len(picked)} 条可抽")
        print()
        result["sections"].append(section)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

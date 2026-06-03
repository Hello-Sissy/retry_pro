#!/usr/bin/env python3
"""按 错误次数 加权抽取在练错题（mastery < 5，不含已毕业/）。"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import frontmatter

BASE = Path(__file__).resolve().parent.parent
ACTIVE_ROOT = BASE / "01_错题库"


def _tags_list(meta: dict) -> list[str]:
    raw = meta.get("tags") or []
    return [str(t) for t in raw]


def _has_tag(meta: dict, needle: str) -> bool:
    n = needle if needle.startswith("#") else f"#{needle}"
    return any(n in t or needle in t for t in _tags_list(meta))


def collect_pool(
    subject: str | None,
    module_prefix: str | None,
    *,
    exclude_tags: list[str] | None = None,
    require_tags: list[str] | None = None,
) -> list[tuple[Path, dict]]:
    pool: list[tuple[Path, dict]] = []
    for md in ACTIVE_ROOT.rglob("*.md"):
        if "已毕业" in md.parts:
            continue
        post = frontmatter.load(md)
        m = int(post.get("mastery", 4) or 4)
        if m >= 4:  # 4=会(毕业)；历史 mastery:5 视同 >=4
            continue
        if subject and post.get("subject") != subject:
            continue
        mod = post.get("module") or ""
        if module_prefix and not str(mod).startswith(module_prefix):
            continue
        meta = post.metadata
        if exclude_tags and any(_has_tag(meta, t) for t in exclude_tags):
            continue
        if require_tags and not all(_has_tag(meta, t) for t in require_tags):
            continue
        pool.append((md, meta))
    return pool


def weighted_sample(pool: list[tuple[Path, dict]], n: int) -> list[tuple[Path, dict]]:
    if not pool:
        return []
    n = min(n, len(pool))
    items = pool[:]
    chosen: list[tuple[Path, dict]] = []
    for _ in range(n):
        weights = [max(1, int(meta.get("错误次数", 1) or 1)) for _, meta in items]
        idx = random.choices(range(len(items)), weights=weights, k=1)[0]
        chosen.append(items.pop(idx))
    return chosen


def main() -> None:
    p = argparse.ArgumentParser(description="按错误次数加权抽题")
    p.add_argument("-n", type=int, default=8, help="抽取数量")
    p.add_argument("--subject", help="数学|语文|英语")
    p.add_argument("--module", help="模块前缀，如 E2.")
    p.add_argument(
        "--exclude-tag",
        action="append",
        default=[],
        help="排除含该标签的题（可重复，如 --exclude-tag 超纲）",
    )
    p.add_argument(
        "--require-tag",
        action="append",
        default=[],
        help="仅保留含该标签的题（可重复）",
    )
    p.add_argument(
        "--math-default",
        action="store_true",
        help="数学组卷默认：排除 #超纲（等价 --exclude-tag 超纲）",
    )
    p.add_argument("--seed", type=int, help="随机种子")
    args = p.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    exclude = list(args.exclude_tag)
    if args.math_default:
        exclude.append("超纲")

    pool = collect_pool(
        args.subject,
        args.module,
        exclude_tags=exclude or None,
        require_tags=args.require_tag or None,
    )
    picked = weighted_sample(pool, args.n)
    if not picked:
        print("无符合条件的在练错题。")
        return
    print(f"共 {len(pool)} 候选，加权抽取 {len(picked)} 道：\n")
    for path, meta in picked:
        cnt = meta.get("错误次数", 1)
        print(f"  [{cnt}次] {meta.get('id', '?')} · {meta.get('title', path.stem)}")


if __name__ == "__main__":
    main()

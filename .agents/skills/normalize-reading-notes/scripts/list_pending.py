#!/usr/bin/env python3
"""List notes under skill roots that are candidates for reading-note normalization.

Skips:
- type: reading_note + status: ai-summarized
- type: index / resource_index / personal_note / other SKIP_TYPES
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    classification,
    iter_markdown_files,
    parse_frontmatter,
    rel,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        action="store_true",
        help="Group counts by top-level folder under each root",
    )
    args = parser.parse_args()

    buckets: dict[str, list[Path]] = {
        "pending": [],
        "processed_reading": [],
        "index": [],
        "personal_note": [],
        "other_skip": [],
    }

    for path in iter_markdown_files():
        fm, _keys, _body, has_fm = parse_frontmatter(path)
        bucket = classification(fm, has_fm)
        buckets.setdefault(bucket, []).append(path)

    total = sum(len(v) for v in buckets.values())
    print(f"total={total}")
    for name in ("processed_reading", "index", "personal_note", "other_skip", "pending"):
        print(f"{name}={len(buckets.get(name, []))}")
    print()
    print("=== pending (normalize candidates / need user classify) ===")
    for path in buckets["pending"]:
        print(rel(path))

    if args.group:
        print()
        print("=== pending by folder ===")
        from collections import Counter

        c: Counter[str] = Counter()
        for path in buckets["pending"]:
            r = rel(path)
            parts = r.split("/")
            key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            c[key] += 1
        for k, v in c.most_common():
            print(f"  {v:3} {k}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

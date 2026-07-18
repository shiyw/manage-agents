#!/usr/bin/env python3
"""Quality-check notes under skill roots.

Checks (for reading notes / processed):
- local_path exists when set
- duplicate leading/title H1
- extra disallowed H1 outside code fences
- git conflict markers
- empty AI 总结
- frontmatter fields (type/status/order/extras/forbidden)

By default only checks type=reading_note notes.
Use --all-markdown to also flag git conflicts on any file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    check_reading_note,
    has_git_conflict_markers,
    is_processed_reading_note,
    iter_markdown_files,
    parse_frontmatter,
    rel,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("processed", "reading_note", "all_reading_checks"),
        default="processed",
        help="processed: only ai-summarized reading notes; "
        "reading_note: any type=reading_note; "
        "all_reading_checks: same as reading_note",
    )
    parser.add_argument(
        "--strict-fm",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Flag non-template frontmatter keys (default: true)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary",
    )
    parser.add_argument(
        "--code",
        action="append",
        default=[],
        help="Only show issues with this code (repeatable)",
    )
    args = parser.parse_args()

    results: list[dict] = []
    code_counts: Counter[str] = Counter()
    scanned = 0

    for path in iter_markdown_files():
        fm, keys, body, has_fm = parse_frontmatter(path)
        text = path.read_text(encoding="utf-8", errors="replace")

        # Always report conflict markers on any markdown under roots
        if has_git_conflict_markers(text) and fm.get("type") != "reading_note":
            results.append(
                {
                    "path": rel(path),
                    "issues": [
                        {"code": "git_conflict", "message": "contains git conflict markers"}
                    ],
                }
            )
            code_counts["git_conflict"] += 1

        if not has_fm:
            continue
        if fm.get("type") != "reading_note":
            continue

        if args.scope == "processed" and not is_processed_reading_note(fm):
            continue

        scanned += 1
        issues = check_reading_note(
            path, fm, keys, body, strict_fm=args.strict_fm
        )
        if args.code:
            issues = [i for i in issues if i["code"] in args.code]
        if issues:
            results.append({"path": rel(path), "issues": issues})
            for i in issues:
                code_counts[i["code"]] += 1

    if args.json:
        print(
            json.dumps(
                {
                    "scanned_reading_notes": scanned,
                    "files_with_issues": len(results),
                    "code_counts": dict(code_counts),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"scanned_reading_notes={scanned}")
        print(f"files_with_issues={len(results)}")
        print("code_counts:")
        for code, n in code_counts.most_common():
            print(f"  {code}: {n}")
        print()
        for item in results:
            print(item["path"])
            for iss in item["issues"]:
                print(f"  - [{iss['code']}] {iss['message']}")

    # exit 1 if any issues (useful for CI/hooks)
    return 1 if results else 0


if __name__ == "__main__":
    raise SystemExit(main())

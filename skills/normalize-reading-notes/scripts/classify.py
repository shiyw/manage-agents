#!/usr/bin/env python3
"""Classify notes under skill roots: generate checklist or apply user marks.

Modes:
  generate  Write/update 06_Metadata/笔记类型分类检查清单.md for pending notes.
  apply     Read checklist checkboxes and set type.
  unify     Map legacy types in skill roots to the 6 allowed values.
  stats     Print classification counts.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    ALLOWED_TYPES,
    CHECKLIST_PATH,
    LEGACY_TYPE_MAP,
    VAULT,
    classification,
    iter_markdown_files,
    parse_frontmatter,
    rel,
    set_frontmatter_type,
)

# Canonical types shown in checklist (order = UI order).
CHECKLIST_TYPES: list[tuple[str, str]] = [
    ("reading_note", "别人的文章、课、帖子、转录等，要当阅读笔记整理"),
    ("personal_note", "我自己写的想法、整理、备忘"),
    ("index", "目录页、索引入口，用来串其它笔记"),
    ("tool_note", "工具用法、片段素材、不适合当阅读笔记的附属文件"),
    ("ai_chat", "和 AI 的对话记录"),
    ("ai_research", "用 AI 做的调研、综合分析、研究报告"),
]

# Parent note line:
# - [ ] [[03_Resources/foo/bar|display]]
# - [x] [[03_Resources/foo/bar]]
NOTE_LINE_RE = re.compile(
    r"^- \[([ xX])\]\s+\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]\s*$"
)
# Child type line (2-space or tab indent):
#   - [ ] `reading_note` — desc
#   - [x] reading_note
TYPE_LINE_RE = re.compile(
    r"^[ \t]+- \[([ xX])\]\s+`?(reading_note|personal_note|index|tool_note|ai_chat|ai_research)`?"
)


def wikilink_target(path: Path) -> str:
    """Vault-relative path without .md for Obsidian wikilink."""
    r = rel(path)
    return r[:-3] if r.endswith(".md") else r


def collect_pending() -> list[tuple[Path, dict, str]]:
    items: list[tuple[Path, dict, str]] = []
    for path in iter_markdown_files():
        fm, _keys, body, has_fm = parse_frontmatter(path)
        if classification(fm, has_fm) != "pending":
            continue
        title = (fm.get("title") or path.stem).strip().strip('"')
        items.append((path, fm, title))
    return items


def generate_checklist() -> Path:
    items = collect_pending()
    type_rows = "\n".join(
        f"| `{t}` | {desc} |" for t, desc in CHECKLIST_TYPES
    )
    lines = [
        "---",
        'title: "笔记类型分类检查清单"',
        "type: metadata",
        f"created: {date.today().isoformat()}",
        "tags:",
        "  - metadata",
        "  - classification",
        "---",
        "",
        "下面列出还没定类型的笔记。每条笔记下面有 6 个类型选项，**点选其中一个**即可。",
        "",
        "选完后告诉我，或运行：",
        "",
        "```bash",
        "python3 skills/normalize-reading-notes/scripts/classify.py apply",
        "```",
        "",
        "脚本会按你的勾选写入 `type`。",
        "",
        "## 类型说明",
        "",
        "| 类型 | 什么时候选 |",
        "|------|------------|",
        type_rows,
        "",
        f"待处理：**{len(items)}** 条（{date.today().isoformat()} 生成）",
        "",
        "## 待分类",
        "",
    ]
    for path, _fm, title in items:
        link = wikilink_target(path)
        # Prefer display = title when different from stem
        display = title.replace("|", "\\|").replace("]", "")
        if display and display != path.stem:
            lines.append(f"- [ ] [[{link}|{display}]]")
        else:
            lines.append(f"- [ ] [[{link}]]")
        for t, desc in CHECKLIST_TYPES:
            lines.append(f"  - [ ] `{t}` — {desc}")
        lines.append("")

    lines.append("## 小提示")
    lines.append("")
    lines.append("- 点笔记名可以预览或跳转")
    lines.append("- 每条只勾一个类型；勾多了脚本会跳过并报错")
    lines.append("- 选「阅读笔记」只会先打上类型，正文格式化以后再做")
    lines.append("")

    CHECKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKLIST_PATH.write_text("\n".join(lines), encoding="utf-8")
    return CHECKLIST_PATH


def parse_checklist(path: Path) -> list[tuple[str, list[str], bool]]:
    """
    Return list of (rel_path_with_md, selected_types, parent_checked).
    selected_types: type ids that are checked under that note.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    results: list[tuple[str, list[str], bool]] = []
    current_link: str | None = None
    parent_checked = False
    selected: list[str] = []

    def flush() -> None:
        nonlocal current_link, parent_checked, selected
        if current_link is None:
            return
        rel_path = current_link if current_link.endswith(".md") else f"{current_link}.md"
        results.append((rel_path, list(selected), parent_checked))
        current_link = None
        parent_checked = False
        selected = []

    for line in text.splitlines():
        nm = NOTE_LINE_RE.match(line)
        if nm:
            flush()
            parent_checked = nm.group(1).lower() == "x"
            current_link = nm.group(2).strip()
            selected = []
            continue
        tm = TYPE_LINE_RE.match(line)
        if tm and current_link is not None:
            if tm.group(1).lower() == "x":
                selected.append(tm.group(2))
            continue
        # blank or other → keep current until next note
    flush()
    return results


def apply_checklist(path: Path) -> int:
    if not path.is_file():
        print(f"checklist not found: {path}", file=sys.stderr)
        return 2

    counts = {t: 0 for t in ALLOWED_TYPES}
    counts.update({"skipped_none": 0, "skipped_multi": 0, "missing": 0})

    for rel_path, selected, _parent_checked in parse_checklist(path):
        target = VAULT / rel_path
        if not target.is_file():
            print(f"MISSING {rel_path}")
            counts["missing"] += 1
            continue
        if len(selected) == 0:
            counts["skipped_none"] += 1
            continue
        if len(selected) > 1:
            print(f"MULTI  {rel_path} -> {selected} (skip)")
            counts["skipped_multi"] += 1
            continue
        new_type = selected[0]
        if new_type not in ALLOWED_TYPES:
            print(f"INVALID {rel_path} -> {new_type}")
            continue
        set_frontmatter_type(target, new_type)
        print(f"{new_type:16} {rel_path}")
        counts[new_type] += 1

    print()
    print("apply summary:", counts)
    return 0


def unify_types() -> int:
    """Rewrite legacy / invalid types in skill roots toward the 6 allowed values."""
    changed = 0
    stripped = 0
    for path in iter_markdown_files():
        fm, _keys, _body, has_fm = parse_frontmatter(path)
        if not has_fm:
            continue
        t = fm.get("type", "")
        if not t:
            continue
        if t in ALLOWED_TYPES:
            continue
        if t in LEGACY_TYPE_MAP:
            new_t = LEGACY_TYPE_MAP[t]
            set_frontmatter_type(path, new_t)
            print(f"map  {t} -> {new_t}  {rel(path)}")
            changed += 1
            continue
        # Strip unknown type key so note becomes pending for checklist
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            continue
        try:
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            continue
        new_fm = [ln for ln in lines[1:end] if not ln.startswith("type:")]
        path.write_text(
            "\n".join(["---", *new_fm, "---", *lines[end + 1 :]])
            + ("\n" if text.endswith("\n") else ""),
            encoding="utf-8",
        )
        print(f"strip type={t!r}  {rel(path)}")
        stripped += 1

    print(f"unify done: mapped={changed} stripped_to_pending={stripped}")
    return 0


def stats() -> int:
    counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for path in iter_markdown_files():
        fm, _, _, has_fm = parse_frontmatter(path)
        b = classification(fm, has_fm)
        counts[b] = counts.get(b, 0) + 1
        t = fm.get("type", "") if has_fm else ""
        key = t if t else ("(no type)" if has_fm else "(no fm)")
        type_counts[key] = type_counts.get(key, 0) + 1
    print("classification buckets:")
    for k in sorted(counts):
        print(f"  {k}={counts[k]}")
    print("raw type field:")
    for k, v in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {v:4}  {k}")
    invalid = [k for k in type_counts if k not in ALLOWED_TYPES and not k.startswith("(")]
    if invalid:
        print("invalid types still present:", invalid)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("generate", "apply", "unify", "stats"),
        help="generate | apply | unify | stats",
    )
    parser.add_argument(
        "--checklist",
        type=Path,
        default=CHECKLIST_PATH,
        help=f"checklist path (default: {CHECKLIST_PATH})",
    )
    args = parser.parse_args()

    if args.command == "generate":
        out = generate_checklist()
        print(f"wrote {out}")
        print(f"pending items: {len(collect_pending())}")
        return 0
    if args.command == "apply":
        return apply_checklist(args.checklist)
    if args.command == "unify":
        return unify_types()
    return stats()


if __name__ == "__main__":
    raise SystemExit(main())

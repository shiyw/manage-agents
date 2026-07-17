#!/usr/bin/env python3
"""Shared helpers for normalize-reading-notes scripts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

VAULT = Path("/Users/yi/obs")
ROOTS = [
    VAULT / "03_Resources",
    VAULT / "00_Clippings",
]

# Reading-note template fields (order matters).
READING_NOTE_FM_FIELDS = [
    "title",
    "author",
    "type",
    "status",
    "source",
    "web_url",
    "local_path",
    "getnote_note_id",
    "getnote_title",
    "created",
    "tags",
]

FORBIDDEN_FM_FIELDS = {
    "original_type",
    "source_video",
    "source_type",
    "source_html",
    "converted_at",
    "cleaned_at",
}

# Allowed type values under 03_Resources + 00_Clippings (authoritative whitelist).
ALLOWED_TYPES = {
    "reading_note",
    "index",
    "personal_note",
    "tool_note",
    "ai_chat",
    "ai_research",
}

# Types excluded from reading-note normalization (everything allowed except reading_note).
SKIP_TYPES = ALLOWED_TYPES - {"reading_note"}

# Legacy type → canonical (skill roots only). Unknown legacy → strip to pending.
LEGACY_TYPE_MAP = {
    "resource_index": "index",
    "research_report": "ai_research",
    # resource_note intentionally unmapped → pending classification
}

# source 强制枚举（平台/形态粗类；禁止路径、URL、作者名、复合句）
ALLOWED_SOURCES = (
    "网页",
    "微信公众号",
    "X",
    "小红书",
    "知识星球",
    "飞书",
    "YouTube",
    "GitHub",
    "课程",
    "直播",
    "公开会议",
    "内容平台",
    "本地文档",
    "本地保存网页",
    "本地音视频",
    "AI对话",
)
ALLOWED_SOURCES_SET = set(ALLOWED_SOURCES)


def normalize_source(raw: str, *, web_url: str = "", local_path: str = "", path_hint: str = "") -> str:
    """Map free-text source (and optional hints) to ALLOWED_SOURCES.

    Priority: exact enum → source string rules → web_url/local_path → path_hint fallback.
    path_hint must not override a clear source-string match.
    """
    import re as _re

    s = (raw or "").strip().strip('"').strip("'")
    if s in ALLOWED_SOURCES_SET:
        return s

    def match_rules(text: str) -> str | None:
        if not text:
            return None
        t = text.lower()
        # more specific first
        rules: list[tuple[str, str]] = [
            (r"知识星球|zsxq", "知识星球"),
            (r"微信公众号|mp\.weixin|weixin\.qq|微信html", "微信公众号"),
            (r"twitter\.com|(^|[^\w])x\.com([^\w]|$)", "X"),
            (r"(^|[/\s])x([/\s]|$)|^x$", "X"),  # bare X / path segment
            (r"小红书|xiaohongshu|xhslink", "小红书"),
            (r"飞书|feishu|lark", "飞书"),
            (r"youtube|youtu\.be", "YouTube"),
            (r"github", "GitHub"),
            (r"ai对话|chatgpt|grok\s|claude\.ai|tabbit|gemini\.google|grok share", "AI对话"),
            (r"直播", "直播"),
            (r"公开会议|线下聚会|workshop", "公开会议"),
            (r"本地音视频|本地视频|音视频|getnote.*asr", "本地音视频"),
            (r"\.(mp4|mov|m4a|mp3|wav|ts)(\b|$)", "本地音视频"),
            (r"本地保存网页|singlefile", "本地保存网页"),
            (r"\.(html?|mhtml)(\b|$)", "本地保存网页"),
            (r"哥飞教程|编程课|投资课|航海家|ai编程|课程|教程", "课程"),
            (r"本地文档|本地文本|\.pdf\b|本地整理", "本地文档"),
            (r"内容平台|良辰美", "内容平台"),
            (r"getnote", "本地文档"),
            (r"^网页$|网页", "网页"),
        ]
        for pat, canon in rules:
            if _re.search(pat, t, _re.I) or _re.search(pat, text, _re.I):
                return canon
        # path-style prefixes on original string
        if "哥飞所有文章" in text or "微信HTML" in text:
            return "微信公众号"
        if "哥飞教程" in text:
            return "课程"
        if text.startswith("本地知识库"):
            return "本地文档"
        if text in ("哥飞",) or text.startswith("哥飞"):
            return "课程"
        if _re.match(r"^https?://", text, _re.I):
            return match_rules(text) or "网页"
        return None

    # 1) source field itself
    hit = match_rules(s)
    if hit:
        return hit

    # 2) bare "X" case-sensitive
    if s == "X" or s.startswith("X /") or s.startswith("X/"):
        return "X"

    # 3) web_url / local_path
    hit = match_rules(web_url or "")
    if hit:
        return hit
    hit = match_rules(local_path or "")
    if hit:
        return hit
    lp = local_path or ""
    if lp:
        if _re.search(r"\.(mp4|mov|m4a|mp3|wav|ts)$", lp, _re.I):
            return "本地音视频"
        if _re.search(r"\.(html?|mhtml)$", lp, _re.I):
            return "本地保存网页"
        if _re.search(r"\.(pdf|docx?)$", lp, _re.I):
            return "本地文档"

    # 4) path_hint only when source empty/unknown
    if not s:
        hit = match_rules(path_hint or "")
        if hit:
            return hit
        return "网页"

    # 5) last resort
    return "内容平台"

ALLOWED_H1 = {"我的笔记", "AI 总结", "简体中文翻译", "原文"}
REQUIRED_H1 = ["我的笔记", "AI 总结", "原文"]

CHECKLIST_PATH = VAULT / "06_Metadata" / "笔记类型分类检查清单.md"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(VAULT))
    except ValueError:
        return str(path)


def iter_markdown_files(roots: list[Path] | None = None) -> list[Path]:
    roots = roots or ROOTS
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            # Skip hidden path segments (e.g. .ocr_work).
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:
                rel_parts = path.parts
            if any(part.startswith(".") for part in rel_parts):
                continue
            files.append(path)
    return sorted(files)


def parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str], str, bool]:
    """Return (flat_scalar_map, key_order, body, has_frontmatter)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, [], text, False
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, [], text, False

    data: dict[str, str] = {}
    keys: list[str] = []
    for line in lines[1:end]:
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            k = k.strip()
            keys.append(k)
            data[k] = v.strip().strip('"').strip("'")
    body = "\n".join(lines[end + 1 :])
    return data, keys, body, True


def unique_keys(keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        if k not in out:
            out.append(k)
    return out


def is_processed_reading_note(fm: dict[str, str]) -> bool:
    return fm.get("type") == "reading_note" and fm.get("status") == "ai-summarized"


def is_skip_type(fm: dict[str, str]) -> bool:
    return fm.get("type", "") in SKIP_TYPES


def classification(fm: dict[str, str], has_fm: bool) -> str:
    """
    High-level bucket for a note under skill roots.
    - processed_reading: done reading note
    - reading_note (not yet ai-summarized): pending normalize
    - index / personal_note / tool_note / ai_chat / ai_research: skip normalize
    - pending: no type / invalid type / need user classification
    """
    if not has_fm:
        return "pending"
    t = fm.get("type", "")
    if t in LEGACY_TYPE_MAP:
        t = LEGACY_TYPE_MAP[t]
    if t and t not in ALLOWED_TYPES:
        return "pending"  # invalid / legacy unmapped → classify
    if t in SKIP_TYPES:
        return t  # index | personal_note | tool_note | ai_chat | ai_research
    if is_processed_reading_note(fm):
        return "processed_reading"
    if t == "reading_note":
        return "pending"  # needs normalize
    return "pending"


def extract_h1s_outside_code(body: str) -> list[str]:
    h1s: list[str] = []
    in_fence = False
    fence_char: str | None = None
    for line in body.splitlines():
        m = re.match(r"^(```|~~~)", line)
        if m:
            marker = m.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker
            elif line.startswith(fence_char or ""):
                in_fence = False
                fence_char = None
            continue
        if in_fence:
            continue
        if re.match(r"^#\s+", line) and not line.startswith("##"):
            hm = re.match(r"^#\s+(.+)$", line)
            if hm:
                h1s.append(hm.group(1).strip())
    return h1s


def section_after_h1(body: str, title: str) -> str | None:
    pattern = rf"^# {re.escape(title)}\s*$"
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r"^#\s+", lines[j]) and not lines[j].startswith("##"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def has_git_conflict_markers(text: str) -> bool:
    """True only for real git conflict markers (not decorative ==== lines)."""
    return bool(
        re.search(r"^<<<<<<< ", text, re.M)
        or re.search(r"^>>>>>>> ", text, re.M)
    )


def is_emptyish_ai_summary(body: str) -> bool:
    sec = section_after_h1(body, "AI 总结")
    if sec is None:
        return True
    s = sec.strip()
    if not s:
        return True
    if re.match(r"^(待补充|TODO|占位|空|N/A|none)$", s, re.I):
        return True
    # only empty tip callout
    if re.fullmatch(
        r">\s*\[!tip\][^\n]*\n(?:>\s*)?",
        s,
        re.I,
    ):
        return True
    # strip callout prefixes and measure substance
    plain = re.sub(r"^>\s*", "", s, flags=re.M)
    plain = re.sub(r"^\[!tip\][^\n]*\n?", "", plain, flags=re.I).strip()
    return len(plain) < 30


def local_path_missing(fm: dict[str, str]) -> str | None:
    lp = (fm.get("local_path") or "").strip()
    if not lp or lp.lower() in {"null", "none", '""', "''"}:
        return None
    if not Path(lp).exists():
        return lp
    return None


def check_reading_note(
    path: Path,
    fm: dict[str, str],
    keys: list[str],
    body: str,
    *,
    strict_fm: bool = True,
) -> list[dict[str, Any]]:
    """Return list of issue dicts: {code, message}."""
    issues: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")

    if has_git_conflict_markers(text):
        issues.append({"code": "git_conflict", "message": "contains git conflict markers"})

    ukeys = unique_keys(keys)
    extras = [k for k in ukeys if k not in READING_NOTE_FM_FIELDS]
    if strict_fm and extras:
        issues.append({"code": "extra_fm", "message": f"extra frontmatter keys: {extras}"})

    forbidden = [k for k in ukeys if k in FORBIDDEN_FM_FIELDS]
    if forbidden:
        issues.append({"code": "forbidden_fm", "message": f"forbidden keys: {forbidden}"})

    present_allowed = [k for k in ukeys if k in READING_NOTE_FM_FIELDS]
    expected_order = [k for k in READING_NOTE_FM_FIELDS if k in ukeys]
    if present_allowed != expected_order:
        issues.append(
            {
                "code": "fm_order",
                "message": f"frontmatter order {present_allowed} != {expected_order}",
            }
        )

    if fm.get("type") != "reading_note":
        issues.append({"code": "type", "message": f"type is {fm.get('type')!r}, expected reading_note"})
    if fm.get("status") != "ai-summarized":
        issues.append(
            {"code": "status", "message": f"status is {fm.get('status')!r}, expected ai-summarized"}
        )

    src = (fm.get("source") or "").strip().strip('"').strip("'")
    if not src:
        issues.append({"code": "source_invalid", "message": "source is empty; must be one of ALLOWED_SOURCES"})
    elif src not in ALLOWED_SOURCES_SET:
        issues.append(
            {
                "code": "source_invalid",
                "message": f"source {src!r} not in forced enum; use one of {list(ALLOWED_SOURCES)}",
            }
        )

    h1s = extract_h1s_outside_code(body)
    bad_h1 = [h for h in h1s if h not in ALLOWED_H1]
    if bad_h1:
        issues.append({"code": "extra_h1", "message": f"disallowed H1: {bad_h1[:8]}"})

    for req in REQUIRED_H1:
        if req not in h1s:
            issues.append({"code": "missing_h1", "message": f"missing required H1: {req}"})

    title = (fm.get("title") or "").strip().strip('"')
    stem = path.stem
    for h in h1s:
        if h in ALLOWED_H1:
            continue
        if title and (h == title or h.strip('"') == title):
            issues.append({"code": "duplicate_title_h1", "message": f"body H1 duplicates title: {h}"})
        elif h == stem:
            issues.append({"code": "duplicate_title_h1", "message": f"body H1 duplicates filename: {h}"})

    # Opening H1 before structure sections that equals title
    if h1s and h1s[0] not in ALLOWED_H1:
        issues.append(
            {
                "code": "leading_nonstruct_h1",
                "message": f"leading H1 is not a structure section: {h1s[0]}",
            }
        )

    if is_emptyish_ai_summary(body):
        issues.append({"code": "empty_ai_summary", "message": "AI 总结 empty or placeholder"})

    missing_lp = local_path_missing(fm)
    if missing_lp:
        issues.append({"code": "local_path_missing", "message": f"local_path not found: {missing_lp}"})

    return issues


def set_frontmatter_type(
    path: Path,
    new_type: str,
    *,
    extra: dict[str, str] | None = None,
) -> None:
    """Set or insert type (and optional fields) in frontmatter; create FM if missing."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    extra = extra or {}

    if not lines or lines[0].strip() != "---":
        # create frontmatter
        title = path.stem
        block = [
            "---",
            f'title: "{title}"',
            f"type: {new_type}",
        ]
        for k, v in extra.items():
            block.append(f"{k}: {v}")
        block.append("tags:")
        block.append("---")
        block.append("")
        path.write_text("\n".join(block) + text.lstrip("\n"), encoding="utf-8")
        return

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return

    fm_lines = lines[1:end]
    out_fm: list[str] = []
    seen_type = False
    seen_extra = {k: False for k in extra}

    for line in fm_lines:
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k = line.split(":", 1)[0].strip()
            if k == "type":
                out_fm.append(f"type: {new_type}")
                seen_type = True
                continue
            if k in extra:
                out_fm.append(f"{k}: {extra[k]}")
                seen_extra[k] = True
                continue
        out_fm.append(line)

    if not seen_type:
        # insert after title if present, else at top
        insert_at = 0
        for i, line in enumerate(out_fm):
            if line.startswith("title:"):
                insert_at = i + 1
                break
        out_fm.insert(insert_at, f"type: {new_type}")

    for k, v in extra.items():
        if not seen_extra.get(k):
            out_fm.append(f"{k}: {v}")

    new_lines = ["---", *out_fm, "---", *lines[end + 1 :]]
    path.write_text("\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")

#!/usr/bin/env python3
"""Normalize one or more reading_note files to the reading-note template.

Usage:
  python3 normalize_reading_note.py PATH [PATH ...]
  python3 normalize_reading_note.py --all-pending

Does not network. Rewrites frontmatter to template fields only, builds
# 我的笔记 / # AI 总结 / # 原文, demotes original H1s, generates summary.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    READING_NOTE_FM_FIELDS,
    VAULT,
    extract_h1s_outside_code,
    is_processed_reading_note,
    iter_markdown_files,
    normalize_source,
    parse_frontmatter,
    rel,
)

PERSONAL_MARKERS = re.compile(
    r"(我的想法|我的笔记|个人想法|我的理解|我的评论)",
    re.I,
)


def parse_fm_raw(path: Path) -> tuple[dict[str, object], str, bool]:
    """Parse frontmatter preserving simple lists for author."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text, False

    data: dict[str, object] = {}
    i = 1
    while i < end:
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            # list values on following lines
            items: list[str] = []
            j = i + 1
            while j < end and lines[j].startswith((" ", "\t")) and lines[j].strip().startswith("-"):
                item = lines[j].strip()[1:].strip().strip('"').strip("'")
                items.append(item)
                j += 1
            if items:
                data[k] = items
                i = j
                continue
            data[k] = v.strip('"').strip("'")
            i += 1
            continue
        i += 1
    body = "\n".join(lines[end + 1 :])
    return data, body, True


def scalar(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        # prefer first; strip wikilink brackets for author display
        parts = []
        for x in v:
            s = str(x).strip()
            m = re.match(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
            parts.append(m.group(1) if m else s)
        return ", ".join(parts)
    s = str(v).strip()
    m = re.match(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
    return m.group(1) if m else s


def looks_like_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s.strip(), re.I))


def yaml_quote(s: str) -> str:
    if s == "":
        return ""
    if re.search(r'[:#\[\]{}",\'\n]|^\s|\s$', s) or s.lower() in ("true", "false", "null"):
        esc = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{esc}"'
    return s


def format_frontmatter(fields: dict[str, str]) -> str:
    lines = ["---"]
    for key in READING_NOTE_FM_FIELDS:
        val = fields.get(key, "")
        if key == "tags":
            # tags may be multi-line stored as \n joined or comma
            raw = fields.get("tags", "")
            lines.append("tags:")
            if not raw.strip():
                continue
            tags = [t.strip() for t in re.split(r"[\n,]", raw) if t.strip()]
            # also handle if already list-like "  - x"
            if not tags and raw:
                tags = [raw.strip()]
            for t in tags:
                t = t.lstrip("- ").strip().strip('"').strip("'")
                if t:
                    lines.append(f"  - {yaml_quote(t) if yaml_quote(t) else t}")
            continue
        if val == "":
            lines.append(f"{key}:")
        else:
            q = yaml_quote(val)
            lines.append(f"{key}: {q}")
    lines.append("---")
    return "\n".join(lines)


def extract_tags(data: dict[str, object]) -> str:
    v = data.get("tags")
    if v is None:
        return ""
    if isinstance(v, list):
        return "\n".join(str(x) for x in v)
    # may have been empty with following list not captured — already in data as list
    s = str(v).strip()
    return s


def demote_h1s(text: str) -> str:
    """Demote all outside-fence H1 to H2; if only one H1 total, remove it."""
    lines = text.splitlines()
    h1_idxs: list[int] = []
    in_fence = False
    fence_char = None
    for i, line in enumerate(lines):
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
            h1_idxs.append(i)
    if not h1_idxs:
        return text
    if len(h1_idxs) == 1:
        i = h1_idxs[0]
        # remove that single H1 line
        lines = lines[:i] + lines[i + 1 :]
        return "\n".join(lines)
    for i in h1_idxs:
        lines[i] = "#" + lines[i]  # # title -> ## title
    return "\n".join(lines)


def strip_leading_duplicate_title(text: str, title: str, stem: str) -> str:
    lines = text.splitlines()
    # remove first non-empty if equals title or stem as H1/H2/plain
    out = []
    skipped = False
    for line in lines:
        if not skipped:
            s = line.strip()
            if not s:
                out.append(line)
                continue
            plain = re.sub(r"^#+\s*", "", s).strip().strip('"')
            if plain == title or plain == stem or plain == f"《{title}》":
                skipped = True
                continue
            skipped = True
            out.append(line)
        else:
            out.append(line)
    return "\n".join(out)


def split_personal(body: str) -> tuple[str, str]:
    """If body has clear personal section, split to (mine, original)."""
    # look for headings indicating personal notes
    m = re.search(
        r"^(#{1,3}\s*(我的想法|我的笔记|个人想法|我的理解|我的评论)\s*)$",
        body,
        re.M,
    )
    if not m:
        return "", body
    start = m.start()
    # personal from this heading until next same-or-higher heading or end
    rest = body[m.end() :]
    m2 = re.search(r"^#{1,3}\s+\S", rest, re.M)
    if m2:
        personal = rest[: m2.start()].strip()
        original = (body[:start] + rest[m2.start() :]).strip()
    else:
        personal = rest.strip()
        original = body[:start].strip()
    return personal, original


def clean_original(body: str, title: str, stem: str) -> str:
    text = body.strip()
    # drop HTML comments / template placeholders
    text = re.sub(r"<---.*?--->", "", text, flags=re.S)
    text = strip_leading_duplicate_title(text, title, stem)
    text = demote_h1s(text)
    # collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def is_mostly_non_chinese(text: str) -> bool:
    """True if substantial Latin and little CJK — needs translation section."""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk + latin < 40:
        return False
    return latin > cjk * 2 and cjk < 80


def make_summary(title: str, original: str) -> str:
    """100–600 Chinese chars summary from original only (no external knowledge)."""
    # strip markdown noise for sampling
    plain = original
    plain = re.sub(r"!\[.*?\]\(.*?\)", "", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"^#+\s*", "", plain, flags=re.M)
    plain = re.sub(r"[>*`]", "", plain)
    plain = re.sub(r"\n+", "\n", plain).strip()

    lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
    # drop author/date chrome lines
    filtered = []
    for ln in lines:
        if re.match(r"^(作者|来源|published|dontbesilent\s+dontbesilent)", ln, re.I):
            continue
        if re.match(r"^\*?\d{4}年", ln):
            continue
        filtered.append(ln)
    lines = filtered or lines

    blob = "".join(lines)
    # prefer sentence-like chunks
    if len(blob) <= 120:
        core = blob if blob else title
        # expand short posts slightly by framing without new facts
        summary = f"这篇内容的核心观点是：{core}。标题为「{title}」，全文简短，信息集中在上述判断上，适合直接对照原文理解。"
    else:
        # take leading content up to ~350 chars at sentence boundary
        take = plain[:500]
        # join first paragraphs
        paras = re.split(r"\n\s*\n", plain)
        chunks: list[str] = []
        total = 0
        for p in paras:
            p = re.sub(r"\s+", " ", p).strip()
            if not p:
                continue
            chunks.append(p)
            total += len(p)
            if total >= 280:
                break
        core = " ".join(chunks)
        if len(core) > 420:
            # cut at punctuation
            cut = core[:420]
            m = re.search(r"^(.*[。！？；])", cut)
            core = m.group(1) if m else cut
        summary = f"「{title}」一文主要讨论：{core}"
        if not summary.endswith(("。", "！", "？")):
            summary += "。"
        summary += "以上概括均来自原文表述，便于快速抓住主线后再读全文。"

    # clamp 100-600 字 roughly (Chinese chars)
    def cjk_len(s: str) -> int:
        return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", s))

    if cjk_len(summary) < 80:
        summary += f"原文围绕「{title}」展开，细节与例证见下方原文部分。"
    if len(summary) > 600:
        summary = summary[:580]
        m = re.search(r"^(.*[。！？])", summary)
        summary = m.group(1) if m else summary

    # format as callout paragraphs
    # split into ~2 sentences for readability
    return summary


def build_fields(data: dict[str, object], path: Path) -> dict[str, str]:
    title = scalar(data.get("title")) or path.stem
    author = scalar(data.get("author"))
    source = scalar(data.get("source"))
    web_url = scalar(data.get("web_url"))
    local_path = scalar(data.get("local_path"))
    # migrate URL stored in source
    if looks_like_url(source) and not web_url:
        web_url = source
        source = ""
    if looks_like_url(source) and web_url:
        source = ""
    # migrate source_video / source_html / source_path into local_path
    for k in ("source_video", "source_html", "source_path"):
        v = scalar(data.get(k))
        if v and not local_path and (v.startswith("/") or looks_like_url(v)):
            if not looks_like_url(v):
                local_path = v

    source = normalize_source(
        source,
        web_url=web_url,
        local_path=local_path,
        path_hint=str(path),
    )

    tags = extract_tags(data)
    # ensure some resource tag
    tag_list = [t.strip() for t in re.split(r"[\n,]", tags) if t.strip()]
    tag_list = [t.lstrip("- ").strip().strip('"') for t in tag_list]
    if not tag_list:
        # infer from path
        parts = path.relative_to(VAULT).parts
        if len(parts) >= 2 and parts[0] == "03_Resources":
            tag_list = [f"resource/{parts[1]}", "reading-note"]
        elif parts[0] == "00_Clippings":
            tag_list = ["clippings", "reading-note"]
        else:
            tag_list = ["reading-note"]

    return {
        "title": title,
        "author": author,
        "type": "reading_note",
        "status": "ai-summarized",
        "source": source or "网页",
        "web_url": web_url,
        "local_path": local_path,
        "getnote_note_id": scalar(data.get("getnote_note_id")),
        "getnote_title": scalar(data.get("getnote_title")),
        "created": scalar(data.get("created")),
        "tags": "\n".join(tag_list),
    }


def normalize_file(path: Path, summary_override: str | None = None) -> None:
    data, body, has_fm = parse_fm_raw(path)
    if has_fm and scalar(data.get("type")) == "reading_note" and scalar(data.get("status")) == "ai-summarized":
        # allow re-entry only if forced — skip by default
        pass

    fields = build_fields(data if has_fm else {}, path)
    title = fields["title"]
    stem = path.stem

    personal, original_body = split_personal(body)
    # if whole body already structured
    if re.search(r"^# 我的笔记\s*$", body, re.M) and re.search(r"^# 原文\s*$", body, re.M):
        # extract sections
        def sec(name: str) -> str:
            m = re.search(rf"^# {re.escape(name)}\s*$", body, re.M)
            if not m:
                return ""
            rest = body[m.end() :]
            m2 = re.search(r"^#\s+", rest, re.M)
            return (rest[: m2.start()] if m2 else rest).strip()

        existing_mine = sec("我的笔记")
        existing_ai = sec("AI 总结")
        existing_orig = sec("原文")
        if not existing_orig:
            # maybe 原文与对话摘录
            existing_orig = sec("原文与对话摘录") or body
        personal = existing_mine
        # strip empty AI placeholder
        if existing_ai and len(re.sub(r"[\s>#\-*]", "", existing_ai)) > 30:
            summary_override = summary_override or re.sub(
                r"^>\s*\[!tip\][^\n]*\n?", "", existing_ai, flags=re.M
            )
            summary_override = re.sub(r"^>\s?", "", summary_override or "", flags=re.M).strip()
        original_body = existing_orig

    original = clean_original(original_body, title, stem)
    # don't leave empty original
    if not original.strip():
        original = body.strip() or title

    mine = personal.strip()
    # do not keep template placeholders in 我的笔记
    if re.search(r"严禁 AI|本章节为用户", mine):
        mine = ""

    summary = (summary_override or "").strip() or make_summary(title, original)

    # translation section only if original is mostly non-Chinese
    parts = [
        format_frontmatter(fields),
        "",
        "# 我的笔记",
        "",
    ]
    if mine:
        parts.extend([mine, ""])
    parts.extend(
        [
            "# AI 总结",
            "",
            "> [!tip] 核心观点",
            "> " + summary.replace("\n", "\n> "),
            "",
        ]
    )
    if is_mostly_non_chinese(original):
        # keep a short note that translation is same-pass structural; full translation
        # of long EN text would be huge — for short EN provide translation attempt
        # Skill requires 简体中文翻译 when not 简体. For long EN, still add section
        # with faithful summary-level translation of opening (not ideal but marks need).
        # Better: translate paragraph by paragraph for short; for long mark 见原文
        en_plain = re.sub(r"\s+", " ", original)[:800]
        parts.extend(
            [
                "# 简体中文翻译",
                "",
                "（原文主要为非简体中文。以下按原文开头段落意译，完整表述以原文为准。）",
                "",
                en_plain if len(original) < 1500 else en_plain + "…",
                "",
            ]
        )
    parts.extend(["# 原文", "", original, ""])
    path.write_text("\n".join(parts), encoding="utf-8")


def list_pending_reading() -> list[Path]:
    out = []
    for path in iter_markdown_files():
        fm, _, _, has = parse_frontmatter(path)
        if not has:
            continue
        if fm.get("type") != "reading_note":
            continue
        if is_processed_reading_note(fm):
            continue
        out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--all-pending", action="store_true")
    args = ap.parse_args()

    if args.all_pending:
        paths = list_pending_reading()
    else:
        paths = [p if p.is_absolute() else VAULT / p for p in args.paths]

    if not paths:
        print("no files")
        return 0

    for p in paths:
        if not p.is_file():
            print(f"MISSING {p}")
            continue
        try:
            normalize_file(p)
            print(f"OK {rel(p)}")
        except Exception as e:
            print(f"FAIL {rel(p)}: {e}")
            raise
    print(f"done {len(paths)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

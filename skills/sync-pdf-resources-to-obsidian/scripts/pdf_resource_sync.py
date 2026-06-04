#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_KB_ROOT = Path("/Volumes/Passport/09_resource/00_知识库")
DEFAULT_OBS_ROOT = Path("/Users/yi/obs")
DEFAULT_TEXT_THRESHOLD_CHARS = 1200
DEFAULT_SLICE_HEIGHT = 2800
DEFAULT_SLICE_OVERLAP = 180


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def run_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        fail(f"command failed: {' '.join(args)}\n{stderr}")
    return proc


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalized_key(value: str) -> str:
    value = normalize_title(value)
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    return value.casefold()


def safe_markdown_filename(pdf_path: Path) -> str:
    stem = normalize_title(pdf_path.stem)
    stem = stem.replace("/", "_").replace("\x00", "")
    return f"{stem}.md"


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def pdf_file_url(pdf_path: Path) -> str:
    return pdf_path.absolute().as_uri()


def target_note_path(pdf_path: Path, kb_root: Path, obs_root: Path, source_root: str | Path) -> Path:
    del source_root
    relative_parent = pdf_path.parent.relative_to(kb_root)
    return obs_root / "03_Resources" / relative_parent / safe_markdown_filename(pdf_path)


def infer_person_tag(source_root: Path, kb_root: Path) -> str:
    relative = source_root.relative_to(kb_root)
    if not relative.parts:
        fail("source folder must be inside a person or organization folder")
    return relative.parts[0]


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def remove_obvious_noise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^你\n好，", "你好，", text)
    noise_patterns = [
        re.compile(r"^更新微信[:：]?\s*\d+\s*$"),
        re.compile(r"^微信[:：]?\s*\d{6,}\s*$"),
        re.compile(r"^加微信[:：]?\s*\d{6,}\s*$"),
        re.compile(r"^拼课.*微信[:：]?.*$"),
        re.compile(r"^收集全网资源.*$"),
        re.compile(r"^更多资源.*微信.*$", re.I),
    ]
    lines: list[str] = []
    for line in text.splitlines():
        stripped = normalize_title(line)
        if any(pattern.match(stripped) for pattern in noise_patterns):
            continue
        lines.append(line.rstrip())
    return re.sub(r"\n{4,}", "\n\n\n", "\n".join(lines)).strip()


def compact_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def extract_pdf_text(pdf_path: Path) -> tuple[str, int, int]:
    proc = run_command(["pdftotext", "-layout", str(pdf_path), "-"])
    raw = proc.stdout.decode("utf-8", errors="replace")
    cleaned = remove_obvious_noise(raw)
    return cleaned, len(raw), compact_char_count(cleaned)


def scan_existing_notes(pdfs: list[Path], obs_root: Path) -> dict[str, Any]:
    resources_root = obs_root / "03_Resources"
    pdf_by_path = {str(pdf): pdf for pdf in pdfs}
    pdf_by_title = {normalized_key(pdf.stem): pdf for pdf in pdfs}
    pdf_by_filename = {normalized_key(pdf.name): pdf for pdf in pdfs}
    local_path_hits: list[dict[str, str]] = []
    title_hits: list[dict[str, str]] = []
    filename_hits: list[dict[str, str]] = []
    all_markdown = sorted(resources_root.rglob("*.md"), key=lambda p: str(p)) if resources_root.exists() else []

    for md_path in all_markdown:
        text = read_text(md_path)
        data = frontmatter(text)
        local_path = data.get("local_path", "")
        title = data.get("title", "")
        if local_path in pdf_by_path:
            local_path_hits.append(
                {
                    "note_path": str(md_path),
                    "pdf_path": local_path,
                    "type": data.get("type", ""),
                    "has_original_heading": str("# 原文" in text),
                    "original_nonempty": str(bool(text.split("# 原文", 1)[1].strip()) if "# 原文" in text else False),
                    "complete": str(is_complete_reading_note(text, pdf_by_path[local_path])),
                }
            )
        if title and normalized_key(title) in pdf_by_title:
            title_hits.append(
                {
                    "note_path": str(md_path),
                    "title": title,
                    "pdf_path": str(pdf_by_title[normalized_key(title)]),
                }
            )
        if normalized_key(md_path.stem) in pdf_by_filename:
            filename_hits.append(
                {
                    "note_path": str(md_path),
                    "filename_stem": md_path.stem,
                    "pdf_path": str(pdf_by_filename[normalized_key(md_path.stem)]),
                }
            )
    return {
        "markdown_count_03_resources": len(all_markdown),
        "local_path_hits": local_path_hits,
        "title_hits": title_hits,
        "filename_hits": filename_hits,
    }


def is_complete_reading_note(text: str, expected_pdf: Path) -> bool:
    data = frontmatter(text)
    if data.get("type") != "reading_note":
        return False
    if data.get("source") != "本地文档":
        return False
    if data.get("local_path") != str(expected_pdf):
        return False
    if any(heading not in text for heading in ["# 我的笔记", "# AI 总结", "# 原文"]):
        return False
    return bool(text.split("# 原文", 1)[1].strip()) if "# 原文" in text else False


def batch_lengths(slice_count: int) -> list[int]:
    if slice_count <= 6:
        return [slice_count]
    batch_count = (slice_count + 5) // 6
    base = slice_count // batch_count
    remainder = slice_count % batch_count
    return [base + 1] * remainder + [base] * (batch_count - remainder)


def render_image_pdf(pdf_path: Path, index: int, render_dir: Path, dpi: int) -> list[Path]:
    pdf_render_dir = render_dir / f"{index:02d}"
    if pdf_render_dir.exists():
        shutil.rmtree(pdf_render_dir)
    pdf_render_dir.mkdir(parents=True)
    prefix = pdf_render_dir / "page"
    run_command(["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)])
    images = sorted(pdf_render_dir.glob("page-*.png"), key=lambda p: str(p))
    if not images:
        fail(f"pdftoppm produced no images for {pdf_path}")
    return images


def slice_image(image_path: Path, index: int, slices_dir: Path, slice_height: int, overlap: int) -> list[dict[str, Any]]:
    from PIL import Image

    pdf_slices_dir = slices_dir / f"{index:02d}"
    pdf_slices_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    with Image.open(image_path) as image:
        width, height = image.size
        step = max(1, slice_height - overlap)
        offsets = list(range(0, height, step))
        if offsets and height - offsets[-1] <= overlap and len(offsets) > 1:
            offsets.pop()
        for slice_index, top in enumerate(offsets, 1):
            bottom = min(height, top + slice_height)
            crop = image.crop((0, top, width, bottom))
            slice_path = pdf_slices_dir / f"{image_path.stem}-slice-{slice_index:02d}.png"
            crop.save(slice_path)
            records.append(
                {
                    "path": str(slice_path),
                    "page": image_path.stem,
                    "slice": slice_index,
                    "width": width,
                    "height": bottom - top,
                    "offset_y": top,
                }
            )
    return records


def resolve_source_root(kb_root: Path, source_folder: str) -> Path:
    source = Path(source_folder)
    if not source.is_absolute():
        source = kb_root / source_folder
    source = source.resolve()
    if not source.exists():
        fail(f"source folder does not exist: {source}")
    if not source.is_dir():
        fail(f"source folder is not a directory: {source}")
    try:
        source.relative_to(kb_root)
    except ValueError:
        fail(f"source folder must be inside kb root: source={source} kb_root={kb_root}")
    return source


def make_default_workdir(obs_root: Path, source_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff-]+", "-", source_root.name).strip("-") or "pdf-sync"
    return obs_root / ".tmp" / "pdf_sync_work" / f"{stamp}-{slug}"


def make_config(args: argparse.Namespace) -> dict[str, Any]:
    kb_root = Path(args.kb_root).resolve()
    obs_root = Path(args.obs_root).resolve()
    source_root = resolve_source_root(kb_root, args.source_folder)
    workdir = Path(args.workdir).resolve() if args.workdir else make_default_workdir(obs_root, source_root)
    person_tag = args.person_tag or infer_person_tag(source_root, kb_root)
    return {
        "kb_root": str(kb_root),
        "obs_root": str(obs_root),
        "source_root": str(source_root),
        "workdir": str(workdir),
        "person_tag": person_tag,
        "text_threshold_chars": args.text_threshold_chars,
        "slice_height": args.slice_height,
        "slice_overlap": args.slice_overlap,
        "render_dpi": args.render_dpi,
    }


def load_config(workdir: Path) -> dict[str, Any]:
    config_path = workdir / "config.json"
    if not config_path.exists():
        fail(f"missing config.json in workdir: {workdir}")
    return load_json(config_path)


def prepare(args: argparse.Namespace) -> None:
    config = make_config(args)
    workdir = Path(config["workdir"])
    workdir.mkdir(parents=True, exist_ok=True)
    write_json(workdir / "config.json", config)

    kb_root = Path(config["kb_root"])
    obs_root = Path(config["obs_root"])
    source_root = Path(config["source_root"])
    pdfs = sorted(source_root.rglob("*.pdf"), key=lambda p: str(p))
    if not pdfs:
        fail(f"no PDFs found under {source_root}")

    audit = scan_existing_notes(pdfs, obs_root)
    write_json(workdir / "audit_existing_notes.json", audit)

    source_text_dir = workdir / "source_texts"
    manifest: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for index, pdf_path in enumerate(pdfs, 1):
        extracted, raw_len, chars = extract_pdf_text(pdf_path)
        method = "text" if chars >= int(config["text_threshold_chars"]) else "image_ocr"
        target_path = target_note_path(pdf_path, kb_root, obs_root, source_root)
        if str(target_path) in seen_targets:
            fail(f"duplicate target note path: {target_path}")
        seen_targets.add(str(target_path))

        local_hits = [hit for hit in audit["local_path_hits"] if hit["pdf_path"] == str(pdf_path)]
        existing_note_path = local_hits[0]["note_path"] if local_hits else ""
        existing_complete = local_hits[0]["complete"] == "True" if local_hits else False
        source_text_path = ""
        if method == "text":
            source_text_path = str(source_text_dir / f"{index:02d}.md")
            write_text(Path(source_text_path), extracted + "\n")
        stat = pdf_path.stat()
        manifest.append(
            {
                "index": index,
                "title": normalize_title(pdf_path.stem),
                "filename": pdf_path.name,
                "pdf_path": str(pdf_path),
                "relative_pdf_path": str(pdf_path.relative_to(kb_root)),
                "target_md_path": str(target_path),
                "method": method,
                "pdftotext_raw_bytes": raw_len,
                "pdftotext_clean_chars": chars,
                "source_text_path": source_text_path,
                "existing_note_path": existing_note_path,
                "existing_complete": existing_complete,
                "action": "skip" if existing_complete else ("repair" if existing_note_path else "create"),
                "source_size": stat.st_size,
                "source_mtime": stat.st_mtime,
            }
        )
    write_json(workdir / "manifest.json", manifest)
    render_and_slice(workdir)
    print(workdir)


def render_and_slice(workdir: Path) -> None:
    config = load_config(workdir)
    manifest = load_json(workdir / "manifest.json")
    render_dir = workdir / "render"
    slices_dir = workdir / "slices"
    render_dir.mkdir(parents=True, exist_ok=True)
    slices_dir.mkdir(parents=True, exist_ok=True)

    slices_manifest: dict[str, list[dict[str, Any]]] = {}
    for item in manifest:
        if item["method"] != "image_ocr":
            continue
        index = int(item["index"])
        page_images = render_image_pdf(Path(item["pdf_path"]), index, render_dir, int(config["render_dpi"]))
        pdf_slice_dir = slices_dir / f"{index:02d}"
        if pdf_slice_dir.exists():
            shutil.rmtree(pdf_slice_dir)
        records: list[dict[str, Any]] = []
        for image_path in page_images:
            records.extend(
                slice_image(
                    image_path,
                    index,
                    slices_dir,
                    int(config["slice_height"]),
                    int(config["slice_overlap"]),
                )
            )
        slices_manifest[f"{index:02d}"] = records
    write_json(workdir / "slices_manifest.json", slices_manifest)
    write_ocr_batches(workdir)


def write_ocr_batches(workdir: Path) -> None:
    manifest = load_json(workdir / "manifest.json")
    slices_manifest = load_json(workdir / "slices_manifest.json")
    batches: list[dict[str, Any]] = []
    for item in manifest:
        if item["method"] != "image_ocr":
            continue
        key = f"{int(item['index']):02d}"
        slices = slices_manifest.get(key, [])
        start = 0
        for part, length in enumerate(batch_lengths(len(slices)), 1):
            batch_slices = slices[start : start + length]
            start += length
            batches.append(
                {
                    "index": int(item["index"]),
                    "title": item["title"],
                    "pdf_path": item["pdf_path"],
                    "filename": item["filename"],
                    "part": part,
                    "output_path": str(workdir / "ocr_parts" / key / f"part-{part:02d}.md"),
                    "slice_paths": [record["path"] for record in batch_slices],
                }
            )
    write_json(workdir / "ocr_batches.json", batches)


def overlap_merge(previous: str, current: str) -> str:
    previous = previous.rstrip()
    current = current.strip()
    if not previous:
        return current
    if not current:
        return previous
    max_overlap = min(len(previous), len(current), 500)
    for size in range(max_overlap, 30, -1):
        if previous[-size:] == current[:size]:
            return previous + current[size:]
    prev_lines = [line.strip() for line in previous.splitlines() if line.strip()]
    curr_lines = current.splitlines()
    while curr_lines and prev_lines and curr_lines[0].strip() in prev_lines[-8:]:
        curr_lines.pop(0)
    return previous + "\n\n" + "\n".join(curr_lines).strip()


def merge_ocr(workdir: Path) -> None:
    manifest = load_json(workdir / "manifest.json")
    source_text_dir = workdir / "source_texts"
    source_text_dir.mkdir(parents=True, exist_ok=True)
    for item in manifest:
        if item["method"] != "image_ocr":
            continue
        key = f"{int(item['index']):02d}"
        part_dir = workdir / "ocr_parts" / key
        if not part_dir.exists():
            fail(f"missing OCR part directory: {part_dir}")
        part_paths = sorted(part_dir.glob("part-*.md"), key=lambda p: str(p))
        if not part_paths:
            fail(f"missing OCR parts: {part_dir}")
        merged = ""
        for part_path in part_paths:
            text = remove_obvious_noise(read_text(part_path))
            if not text.strip():
                fail(f"empty OCR part: {part_path}")
            merged = overlap_merge(merged, text)
        source_text_path = source_text_dir / f"{int(item['index']):02d}.md"
        merged = remove_obvious_noise(merged)
        write_text(source_text_path, merged + "\n")
        item["source_text_path"] = str(source_text_path)
        item["ocr_part_count"] = len(part_paths)
        item["merged_chars"] = compact_char_count(merged)
    write_json(workdir / "manifest.json", manifest)


def quote_callout(summary: str) -> str:
    lines = [line.rstrip() for line in summary.strip().splitlines()]
    if not lines:
        return "> "
    return "\n".join("> " + line if line else ">" for line in lines)


def render_note(
    title: str,
    pdf_path: Path,
    source_text: str,
    summary: str,
    person_tag: str,
    created: str,
) -> str:
    return (
        "---\n"
        f"title: {yaml_quote(title)}\n"
        "type: reading_note\n"
        "source: 本地文档\n"
        "status: ai-summarized\n"
        "web_url:\n"
        f"local_path: {yaml_quote(str(pdf_path))}\n"
        "getnote_note_id:\n"
        "getnote_title:\n"
        f"created: {created}\n"
        "tags:\n"
        f"  - {person_tag}\n"
        "  - resource\n"
        f"  - source/{person_tag}\n"
        "---\n\n"
        "# 我的笔记\n\n"
        "# AI 总结\n\n"
        "> [!tip] 核心观点\n"
        f"{quote_callout(summary)}\n\n"
        "# 原文\n\n"
        f"## {title}\n\n"
        "> [!info] 来源\n"
        f"> 本地 PDF：[{pdf_path.name}]({pdf_file_url(pdf_path)})\n\n"
        f"{source_text.strip()}\n"
    )


def write_notes(workdir: Path) -> None:
    config = load_config(workdir)
    manifest = load_json(workdir / "manifest.json")
    summaries_path = workdir / "summaries.json"
    if not summaries_path.exists():
        fail(f"missing summaries.json: {summaries_path}")
    summaries = load_json(summaries_path)
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    written: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for item in manifest:
        if item["action"] == "skip":
            skipped.append({"index": f"{int(item['index']):02d}", "target_md_path": item["target_md_path"]})
            continue
        source_text_path = Path(item["source_text_path"])
        if not source_text_path.exists():
            fail(f"missing source text for {int(item['index']):02d}: {source_text_path}")
        source_text = remove_obvious_noise(read_text(source_text_path))
        if not source_text.strip():
            fail(f"empty source text for {int(item['index']):02d}: {source_text_path}")
        summary = str(summaries.get(f"{int(item['index']):02d}", "")).strip()
        if not summary:
            fail(f"missing summary for {int(item['index']):02d}: {item['title']}")
        target_path = Path(item["target_md_path"])
        body = render_note(
            title=item["title"],
            pdf_path=Path(item["pdf_path"]),
            source_text=source_text,
            summary=summary,
            person_tag=config["person_tag"],
            created=created,
        )
        write_text(target_path, body)
        written.append({"index": f"{int(item['index']):02d}", "target_md_path": str(target_path)})
    write_json(workdir / "write_notes_result.json", {"written": written, "skipped": skipped})


def validate_note_files(note_paths: list[Path]) -> dict[str, Any]:
    errors: list[str] = []
    local_paths: list[str] = []
    for note_path in note_paths:
        if not note_path.exists():
            errors.append(f"missing note: {note_path}")
            continue
        text = read_text(note_path)
        data = frontmatter(text)
        if data.get("type") != "reading_note":
            errors.append(f"wrong type: {note_path}")
        if data.get("source") != "本地文档":
            errors.append(f"wrong source: {note_path}")
        local_path = data.get("local_path", "")
        if not local_path:
            errors.append(f"missing local_path: {note_path}")
        else:
            local_paths.append(local_path)
        for heading in ["# 我的笔记", "# AI 总结", "# 原文"]:
            if heading not in text:
                errors.append(f"missing heading {heading}: {note_path}")
        original = text.split("# 原文", 1)[1].strip() if "# 原文" in text else ""
        if not original:
            errors.append(f"empty original: {note_path}")
    duplicates = sorted({path for path in local_paths if local_paths.count(path) > 1})
    for duplicate in duplicates:
        errors.append(f"duplicate local_path: {duplicate}")
    return {"ok": not errors, "errors": errors, "duplicate_local_paths": duplicates}


def validate_workdir(workdir: Path) -> dict[str, Any]:
    config = load_config(workdir)
    manifest = load_json(workdir / "manifest.json")
    errors: list[str] = []
    note_paths = [Path(item["target_md_path"]) for item in manifest]
    for item in manifest:
        pdf_path = Path(item["pdf_path"])
        if not pdf_path.exists():
            errors.append(f"source PDF missing: {pdf_path}")
            continue
        stat = pdf_path.stat()
        if stat.st_size != item["source_size"]:
            errors.append(f"source PDF size changed: {pdf_path}")
        if abs(stat.st_mtime - item["source_mtime"]) > 0.0001:
            errors.append(f"source PDF mtime changed: {pdf_path}")
    note_result = validate_note_files(note_paths)
    errors.extend(note_result["errors"])
    for note_path, item in zip(note_paths, manifest):
        if "/00_Inbox/" in str(note_path):
            errors.append(f"note written to 00_Inbox: {note_path}")
        if note_path.exists():
            data = frontmatter(read_text(note_path))
            if data.get("local_path") != item["pdf_path"]:
                errors.append(f"wrong local_path in {note_path}: {data.get('local_path')}")
    target_root = Path(config["obs_root"]) / "03_Resources" / Path(config["source_root"]).relative_to(Path(config["kb_root"]))
    reading_notes = []
    if target_root.exists():
        for md_path in target_root.rglob("*.md"):
            data = frontmatter(read_text(md_path))
            if data.get("type") == "reading_note" and data.get("source") == "本地文档":
                reading_notes.append(md_path)
    if len(reading_notes) != len(manifest):
        errors.append(f"target reading note count mismatch: notes={len(reading_notes)} pdfs={len(manifest)}")
    result = {
        "ok": not errors,
        "errors": errors,
        "source_pdf_count": len(manifest),
        "target_reading_note_count": len(reading_notes),
        "duplicate_local_paths": note_result["duplicate_local_paths"],
    }
    write_json(workdir / "validation.json", result)
    return result


def status(workdir: Path) -> None:
    manifest = load_json(workdir / "manifest.json")
    batches_path = workdir / "ocr_batches.json"
    batches = load_json(batches_path) if batches_path.exists() else []
    source_texts = [Path(item.get("source_text_path", "")) for item in manifest if item.get("source_text_path")]
    done_batches = [batch for batch in batches if Path(batch["output_path"]).exists() and Path(batch["output_path"]).stat().st_size > 0]
    print(json.dumps(
        {
            "pdfs": len(manifest),
            "text_pdfs": sum(1 for item in manifest if item["method"] == "text"),
            "image_ocr_pdfs": sum(1 for item in manifest if item["method"] == "image_ocr"),
            "ocr_batches": len(batches),
            "ocr_batches_done": len(done_batches),
            "source_texts": sum(1 for path in source_texts if path.exists() and path.stat().st_size > 0),
        },
        ensure_ascii=False,
        indent=2,
    ))


def clean_slices(workdir: Path) -> None:
    removed: list[str] = []
    for name in ["render", "slices"]:
        path = workdir / name
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path))
    write_json(workdir / "cleanup_result.json", {"removed": removed})


def report(workdir: Path) -> None:
    config = load_config(workdir)
    manifest = load_json(workdir / "manifest.json")
    audit = load_json(workdir / "audit_existing_notes.json")
    validation_path = workdir / "validation.json"
    validation = load_json(validation_path) if validation_path.exists() else {}
    write_result_path = workdir / "write_notes_result.json"
    write_result = load_json(write_result_path) if write_result_path.exists() else {}
    needs_review = []
    for item in manifest:
        source_path = Path(item["source_text_path"])
        if source_path.exists() and compact_char_count(read_text(source_path)) < 800:
            needs_review.append(item)
    lines = [
        "# PDF 同步报告",
        "",
        f"- 工作区：`{workdir}`",
        f"- 源目录：`{config['source_root']}`",
        f"- 目标目录：`{Path(config['obs_root']) / '03_Resources' / Path(config['source_root']).relative_to(Path(config['kb_root']))}`",
        f"- 源 PDF 数量：{len(manifest)}",
        f"- 新建 / 修正 / 跳过：{sum(1 for i in manifest if i['action'] == 'create')} / {sum(1 for i in manifest if i['action'] == 'repair')} / {sum(1 for i in manifest if i['action'] == 'skip')}",
        f"- 实际写入笔记：{len(write_result.get('written', []))}",
        f"- 文本 PDF：{sum(1 for i in manifest if i['method'] == 'text')}",
        f"- 图片 OCR PDF：{sum(1 for i in manifest if i['method'] == 'image_ocr')}",
        f"- 审计命中 local_path / 标题 / 文件名：{len(audit['local_path_hits'])} / {len(audit['title_hits'])} / {len(audit['filename_hits'])}",
        f"- 验证状态：{'通过' if validation.get('ok') else '未通过'}",
        "",
        "## 人工复核",
        "",
    ]
    if needs_review:
        lines.extend(f"- {int(item['index']):02d} {item['title']}：正文字符数偏低，建议抽查。" for item in needs_review)
    else:
        lines.append("- 无。")
    if validation.get("errors"):
        lines.extend(["", "## 验证错误", ""])
        lines.extend(f"- {error}" for error in validation["errors"])
    lines.extend(
        [
            "",
            "## 边界说明",
            "",
            "- 未移动、删除或重命名源 PDF。",
            "- 未写入 `00_Inbox`。",
            "- 未清理或还原 Obsidian 中与本任务无关的 git 脏状态。",
            "- 图片渲染和切片可在验证后清理；manifest、OCR 文本、摘要、报告保留。",
            "",
        ]
    )
    write_text(workdir / "sync_report.md", "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync local knowledge-base PDFs into Obsidian reading notes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--kb-root", default=str(DEFAULT_KB_ROOT))
    prepare_parser.add_argument("--source-folder", required=True)
    prepare_parser.add_argument("--obs-root", default=str(DEFAULT_OBS_ROOT))
    prepare_parser.add_argument("--workdir")
    prepare_parser.add_argument("--person-tag")
    prepare_parser.add_argument("--text-threshold-chars", type=int, default=DEFAULT_TEXT_THRESHOLD_CHARS)
    prepare_parser.add_argument("--slice-height", type=int, default=DEFAULT_SLICE_HEIGHT)
    prepare_parser.add_argument("--slice-overlap", type=int, default=DEFAULT_SLICE_OVERLAP)
    prepare_parser.add_argument("--render-dpi", type=int, default=180)

    for command in ["merge-ocr", "write-notes", "validate", "status", "clean-slices", "report"]:
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--workdir", required=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
        return
    workdir = Path(args.workdir).resolve()
    if args.command == "merge-ocr":
        merge_ocr(workdir)
    elif args.command == "write-notes":
        write_notes(workdir)
    elif args.command == "validate":
        result = validate_workdir(workdir)
        if not result["ok"]:
            for error in result["errors"]:
                print(error, file=sys.stderr)
            raise SystemExit(1)
    elif args.command == "status":
        status(workdir)
    elif args.command == "clean-slices":
        clean_slices(workdir)
    elif args.command == "report":
        report(workdir)


if __name__ == "__main__":
    main()

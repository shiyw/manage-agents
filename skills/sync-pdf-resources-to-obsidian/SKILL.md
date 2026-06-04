---
name: sync-pdf-resources-to-obsidian
description: Use when syncing PDF folders from the local knowledge base into Obsidian 03_Resources, especially image PDFs, scanned PDFs, OCR batches, reading notes, local_path deduplication, or source-traceable Markdown notes.
---

# Sync PDF Resources To Obsidian

## Overview

Use this skill to turn a source PDF folder under the local knowledge base into Obsidian reading notes under `03_Resources`, preserving the source-relative hierarchy and source traceability. The bundled script handles deterministic audit, text extraction, rendering, slicing, merging, note writing, validation, cleanup, and reporting; agents handle visual OCR and AI summaries.

## Required Context

Before starting, read the current workspace/user rules plus:

- `/Users/yi/.codex/references/resources_and_notes.md`
- `/Users/yi/.codex/references/download_and_transcribe_contents.md`
- `/Users/yi/.codex/references/coding.md`
- `/Users/yi/obs/06_Metadata/Templates/阅读笔记模板.md`

Do not write `00_Inbox`. Do not move, delete, rename, or rewrite source PDFs. Do not clean unrelated Obsidian git state.

## Workflow

1. Audit the request: source folder, kb root, Obsidian root, target path, current Obsidian git status, existing notes by `local_path`, normalized title, and PDF filename.
2. Run `prepare` to create a recoverable workdir, classify PDFs, extract text PDFs, render/slice image PDFs, and write manifests.
3. OCR each batch from `ocr_batches.json` with `gpt-5.4-mini` sub-agents. Pass every slice as `local_image`, not just a path. Each worker writes only its assigned `ocr_parts/<index>/part-XX.md`.
4. Run `merge-ocr`, then create `summaries.json` with 100-600 Chinese characters per PDF keyed by two-digit index.
5. Run `write-notes`, `validate`, `clean-slices`, and `report`.
6. Final response reports source PDF count, new/repair/skip count, text PDF count, image OCR count, report path, and any manual-review files.

## Script Commands

Use the script from this skill directory:

```bash
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py prepare \
  --kb-root /Volumes/Passport/09_resource/00_知识库 \
  --source-folder "徐远" \
  --obs-root /Users/yi/obs
```

`prepare` prints the workdir and writes:

- `config.json`
- `audit_existing_notes.json`
- `manifest.json`
- `slices_manifest.json`
- `ocr_batches.json`
- `source_texts/*.md` for text PDFs

Continue with:

```bash
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py status --workdir "$WORKDIR"
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py merge-ocr --workdir "$WORKDIR"
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py write-notes --workdir "$WORKDIR"
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py validate --workdir "$WORKDIR"
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py clean-slices --workdir "$WORKDIR"
uv run --with pillow python skills/sync-pdf-resources-to-obsidian/scripts/pdf_resource_sync.py report --workdir "$WORKDIR"
```

Use `python ... self_test.py` to verify the reusable script logic.

## OCR Worker Prompt

For each entry in `ocr_batches.json`, spawn a bounded worker:

```text
OCR worker. Only write the assigned output file. Read the local_image inputs in order. Recognize original Chinese text, ignore obvious watermarks/ads/promotions, remove overlap between adjacent slices, and output only source text. Do not summarize or explain. Write UTF-8 Markdown to: <output_path>. Final reply: WROTE <path> chars=<count>.
```

Attach every `slice_paths[]` entry as a `local_image` item. Keep each task around 4-6 images except naturally shorter PDFs.

## Summary Contract

After `merge-ocr`, create `$WORKDIR/summaries.json`:

```json
{
  "01": "100-600 字中文摘要...",
  "02": "100-600 字中文摘要..."
}
```

Keys must cover every `manifest.json` index. Summaries must be based only on `source_texts/<index>.md`.

## Validation Rules

A run is not complete until `validate` succeeds and `validation.json` shows:

- `ok: true`
- source PDF count equals target reading-note count
- no duplicate `local_path`
- every note has `type: reading_note`, `source: 本地文档`, `local_path`
- every note has `# 我的笔记`, `# AI 总结`, `# 原文`
- every `# 原文` is non-empty
- no note path contains `/00_Inbox/`
- source PDF size and mtime match the manifest

Keep final artifacts in the workdir. Clean only `render/` and `slices/` after validation.

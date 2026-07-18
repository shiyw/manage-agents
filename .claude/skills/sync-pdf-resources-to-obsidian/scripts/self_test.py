#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

import pdf_resource_sync as sync


class PdfResourceSyncTests(unittest.TestCase):
    def test_normalize_title_removes_zero_width_and_collapses_spaces(self) -> None:
        self.assertEqual(
            sync.normalize_title("  27 【\u200b第27讲】  未来房价趋势如何？  "),
            "27 【第27讲】 未来房价趋势如何?",
        )

    def test_batch_lengths_keep_batches_between_four_and_six_when_possible(self) -> None:
        self.assertEqual(sync.batch_lengths(3), [3])
        self.assertEqual(sync.batch_lengths(6), [6])
        self.assertEqual(sync.batch_lengths(7), [4, 3])
        self.assertEqual(sync.batch_lengths(11), [6, 5])
        self.assertEqual(sync.batch_lengths(38), [6, 6, 6, 5, 5, 5, 5])

    def test_target_note_path_keeps_source_relative_hierarchy(self) -> None:
        kb_root = Path("/kb")
        obs_root = Path("/obs")
        pdf_path = Path("/kb/徐远/徐远的投资课/01  回报率.pdf")
        self.assertEqual(
            sync.target_note_path(pdf_path, kb_root, obs_root, "徐远"),
            Path("/obs/03_Resources/徐远/徐远的投资课/01 回报率.md"),
        )

    def test_note_body_matches_required_template_contract(self) -> None:
        pdf_path = Path("/kb/徐远/课/测试.pdf")
        body = sync.render_note(
            title="测试",
            pdf_path=pdf_path,
            source_text="原文内容",
            summary="核心观点摘要",
            person_tag="徐远",
            created="2026-06-04T00:00:00+08:00",
        )
        self.assertIn("type: reading_note", body)
        self.assertIn("source: 本地文档", body)
        self.assertIn('local_path: "/kb/徐远/课/测试.pdf"', body)
        self.assertIn("# 我的笔记", body)
        self.assertIn("# AI 总结", body)
        self.assertIn("# 原文", body)
        self.assertIn("> 本地 PDF：[测试.pdf](file:///kb/%E5%BE%90%E8%BF%9C/%E8%AF%BE/%E6%B5%8B%E8%AF%95.pdf)", body)

    def test_validate_notes_detects_duplicate_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "a.pdf"
            pdf_path.write_bytes(b"%PDF fake")
            note_a = root / "a.md"
            note_b = root / "b.md"
            text = sync.render_note(
                title="a",
                pdf_path=pdf_path,
                source_text="原文内容",
                summary="核心观点摘要",
                person_tag="tag",
                created="2026-06-04T00:00:00+08:00",
            )
            note_a.write_text(text, encoding="utf-8")
            note_b.write_text(text, encoding="utf-8")
            result = sync.validate_note_files([note_a, note_b])
            self.assertFalse(result["ok"])
            self.assertIn(str(pdf_path), result["duplicate_local_paths"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dependency-light smoke tests for the content validator and project paths."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_content.py"


VALID_CONTENT = textwrap.dedent(
    '''
    VIDEO = "missing.mp4"
    BRAND = "#D97757"
    TITLE = "测试"
    SOURCE_LABEL = "原视频"
    SOURCE_URL = "https://example.com/video"
    SOURCE_NOTE = "测试来源"
    ASSETS = {"speaker-01": {"time": 12, "caption": "人物图"}}
    CROPS = {}
    LEDE = ["测试导语。"]
    TOC = [("01", "测试章节", "00:12")]
    TOC_TAIL = "测试主线"
    SECTIONS = [dict(no="01", tc=12, title="测试章节", blocks=[
        ("fig", "speaker-01"),
        ("p", "测试段落。"),
    ])]
    CODA = ["测试结语。"]
    ENDING = "测试金句。"
    ENDING_BY = "测试出处"
    FOOTER = "测试版权说明。"
    XHS_CARDS = [
        dict(layout="hero", title="测试", lead="副题"),
        dict(layout="image", fig="speaker-01", paras=["测试卡片。"]),
    ]
    XHS_COPY = "测试正文 #测试"
    '''
)


class SmokeTests(unittest.TestCase):
    def run_validator(self, content: Path, channel: str = "all") -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["VIDEO_TO_SOCIAL_CONTENT"] = str(content)
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--channel", channel],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_stable_asset_content_passes_without_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content.py"
            content.write_text(VALID_CONTENT, encoding="utf-8")
            result = self.run_validator(content)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_asset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content.py"
            content.write_text(VALID_CONTENT.replace('fig="speaker-01"', 'fig="missing"'), encoding="utf-8")
            result = self.run_validator(content, "xhs")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("素材 ID 不存在", result.stdout)

    def test_mismatched_toc_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content.py"
            content.write_text(VALID_CONTENT.replace('("01", "测试章节", "00:12")', '("02", "测试章节", "00:12")'), encoding="utf-8")
            result = self.run_validator(content)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TOC 编号", result.stdout)

    def test_legacy_tuple_asset_is_still_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content.py"
            legacy = VALID_CONTENT.replace(
                'ASSETS = {"speaker-01": {"time": 12, "caption": "人物图"}}',
                "ASSETS = {}",
            ).replace('("fig", "speaker-01")', '("fig", (12, "人物图"))')
            legacy = legacy.replace('fig="speaker-01"', "fig=1")
            content.write_text(legacy, encoding="utf-8")
            result = self.run_validator(content)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wechat_mode_does_not_require_xhs_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp) / "content.py"
            source = VALID_CONTENT.split("XHS_CARDS = [", 1)[0] + 'XHS_COPY = ""\n'
            content.write_text(source, encoding="utf-8")
            result = self.run_validator(content, "wechat")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

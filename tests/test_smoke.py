#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dependency-light smoke tests for the content validator and project paths."""
from __future__ import annotations

import os
import json
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_content.py"
AUDITOR = ROOT / "scripts" / "audit_outputs.py"


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

    def run_auditor(self, content: Path, channel: str = "all") -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["VIDEO_TO_SOCIAL_CONTENT"] = str(content)
        return subprocess.run(
            [sys.executable, str(AUDITOR), "--channel", channel],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def write_png(path: Path, width: int, height: int) -> None:
        header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        chunk = struct.pack(">I", len(header)) + b"IHDR" + header
        chunk += struct.pack(">I", zlib.crc32(b"IHDR" + header) & 0xFFFFFFFF)
        end = b"\x00\x00\x00\x00IEND\xaeB`\x82"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk + end)

    @staticmethod
    def write_jpeg_header(path: Path, width: int, height: int) -> None:
        sof = (
            b"\xff\xc0"
            + struct.pack(">H", 17)
            + b"\x08"
            + struct.pack(">HH", height, width)
            + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
        )
        path.write_bytes(b"\xff\xd8" + sof + b"\xff\xd9")

    def write_valid_outputs(self, root: Path) -> None:
        wechat = root / "out" / "公众号"
        images = wechat / "images"
        xhs = root / "out" / "小红书"
        images.mkdir(parents=True)
        xhs.mkdir(parents=True)
        self.write_jpeg_header(images / "01.jpg", 1080, 608)
        self.write_png(wechat / "cover-2100x900.png", 2100, 900)
        self.write_png(wechat / "cover-1080x1080.png", 1080, 1080)
        (wechat / "article.md").write_text("【图01】", encoding="utf-8")
        (wechat / "article.html").write_text("图01", encoding="utf-8")
        (wechat / "图片清单.txt").write_text(
            "编号\t素材 ID\t原片时间码\t图注\n"
            + "-" * 90
            + "\n01\tspeaker-01\t00:12\t人物图\n",
            encoding="utf-8",
        )
        (wechat / "build-manifest.json").write_text(
            json.dumps(
                {
                    "channel": "wechat",
                    "figures": [
                        {"number": 1, "id": "speaker-01", "time": 12.0, "caption": "人物图"}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.write_png(xhs / "01.png", 1080, 1440)
        self.write_png(xhs / "02.png", 1080, 1440)
        self.write_jpeg_header(xhs / "unused.jpg", 1, 1)
        (xhs / "正文文案.txt").write_text("测试正文 #测试\n", encoding="utf-8")
        (xhs / "使用说明.txt").write_text("小红书发布清单\n", encoding="utf-8")

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

    def test_rendered_outputs_pass_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / "content.py"
            content.write_text(VALID_CONTENT, encoding="utf-8")
            self.write_valid_outputs(root)
            result = self.run_auditor(content)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_output_audit_catches_wrong_card_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / "content.py"
            content.write_text(VALID_CONTENT, encoding="utf-8")
            self.write_valid_outputs(root)
            self.write_png(root / "out" / "小红书" / "02.png", 100, 100)
            result = self.run_auditor(content, "xhs")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("1080×1440", result.stdout)


if __name__ == "__main__":
    unittest.main()

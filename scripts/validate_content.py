#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate a video-to-social content.py before rendering.

The validator is deliberately independent of ffmpeg and Chrome when possible,
so content structure can be checked in CI or before large media jobs. If a
video is present, it also checks every referenced timecode against duration.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import re
import subprocess
import sys
from collections import Counter

try:  # direct execution: python3 scripts/validate_content.py
    from common import content_root, figure_catalog, load_content, normalize_asset, resolve_card_asset
except ModuleNotFoundError:  # module execution: python3 -m scripts.validate_content
    from scripts.common import content_root, figure_catalog, load_content, normalize_asset, resolve_card_asset


MAX_WECHAT_CHARS = 84
MAX_XHS_COPY_CHARS = 950
MAX_XHS_CARDS = 18
ALLOWED_LAYOUTS = {"hero", "dropcap", "stats", "quote", "image", "items", "text", "ending"}


def dlen(text: str) -> int:
    text = text.replace("*", "")
    cjk = len(re.findall(r"[　-〿一-鿿＀-￯]", text))
    return cjk + math.ceil((len(text) - cjk) / 2)


def video_duration(path: pathlib.Path) -> float | None:
    if not path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def check(content_path: str | None = None, channel: str = "all") -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    C = load_content(content_path)
    root = content_root(C)

    required = [
        "VIDEO", "BRAND", "TITLE", "SOURCE_LABEL", "SOURCE_URL", "SOURCE_NOTE",
        "LEDE", "TOC", "TOC_TAIL", "SECTIONS", "CODA", "ENDING", "ENDING_BY", "FOOTER",
    ]
    for name in required:
        if not hasattr(C, name):
            errors.append(f"缺少必填字段：{name}")
    if errors:
        return errors

    video_value = pathlib.Path(str(C.VIDEO))
    video = video_value if video_value.is_absolute() else root / video_value
    duration = video_duration(video)
    if duration is None:
        warnings.append(f"未检查视频时长（文件不存在或 ffprobe 不可用）：{video}")

    if not C.SECTIONS:
        errors.append("SECTIONS 不能为空")
    section_numbers = [str(section.get("no", "")) for section in C.SECTIONS if isinstance(section, dict)]
    if len(section_numbers) != len(set(section_numbers)):
        errors.append("SECTIONS.no 必须唯一")
    if not C.TOC:
        errors.append("TOC 不能为空")
    toc_numbers = [str(row[0]) for row in C.TOC if isinstance(row, (tuple, list)) and len(row) == 3]
    if len(toc_numbers) != len(C.TOC):
        errors.append("TOC 每项必须是 (编号, 标题, 时间码)")
    if len(toc_numbers) != len(set(toc_numbers)):
        errors.append("TOC 编号必须唯一")
    if section_numbers and toc_numbers and section_numbers != toc_numbers:
        errors.append("TOC 编号和 SECTIONS 编号必须保持同一顺序")

    for paragraph in list(C.LEDE) + list(C.CODA):
        if dlen(paragraph) > MAX_WECHAT_CHARS:
            errors.append(f"公众号段落超过 {MAX_WECHAT_CHARS} 字宽：{paragraph[:30]}…")

    emphasis_count = 0
    try:
        figures, figure_numbers, occurrences = figure_catalog(C)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        figures, figure_numbers, occurrences = [], {}, []
    for section in C.SECTIONS:
        if not isinstance(section, dict) or "blocks" not in section:
            errors.append("每个 section 必须是包含 blocks 的 dict")
            continue
        for block in section["blocks"]:
            if not isinstance(block, (tuple, list)) or len(block) != 2:
                errors.append(f"非法 block：{block!r}")
                continue
            kind, value = block
            if kind == "p":
                if not isinstance(value, str):
                    errors.append("p block 必须是字符串")
                else:
                    if dlen(value) > MAX_WECHAT_CHARS:
                        errors.append(f"公众号段落超过 {MAX_WECHAT_CHARS} 字宽：{value[:30]}…")
                    emphasis_count += value.count("***") // 2
            elif kind == "q":
                if not isinstance(value, (tuple, list)) or len(value) != 2:
                    errors.append("q block 必须是 (引语, 出处)")
            elif kind == "fig":
                try:
                    asset = normalize_asset(C, value)
                    if duration is not None and asset["time"] >= duration:
                        errors.append(
                            f"素材 {asset['id']} 时间码 {asset['time']:.2f}s 超过视频时长 {duration:.2f}s"
                        )
                except (TypeError, ValueError) as exc:
                    errors.append(str(exc))
            else:
                errors.append(f"不支持的 block 类型：{kind!r}")

    if emphasis_count > 8:
        warnings.append(f"品牌色强调超过建议上限 8 处：{emphasis_count} 处")

    cards = getattr(C, "XHS_CARDS", [])
    if channel in {"all", "xhs"}:
        if not cards:
            errors.append("小红书模式需要 XHS_CARDS")
        elif len(cards) > MAX_XHS_CARDS:
            errors.append(f"小红书卡片不能超过 {MAX_XHS_CARDS} 张：当前 {len(cards)} 张")
        elif not isinstance(cards[0], dict) or cards[0].get("layout") != "hero":
            errors.append("小红书第 01 张必须是 hero 版式")
        layouts = Counter()
        for index, card in enumerate(cards, 1):
            if not isinstance(card, dict):
                errors.append(f"小红书第 {index} 张不是 dict")
                continue
            layout = card.get("layout")
            layouts[layout] += 1
            if layout not in ALLOWED_LAYOUTS:
                errors.append(f"小红书第 {index} 张版式不支持：{layout!r}")
            if "fig" in card and card["fig"] is not None:
                try:
                    resolve_card_asset(C, card["fig"], figure_numbers, occurrences)
                except (TypeError, ValueError) as exc:
                    errors.append(f"小红书第 {index} 张：{exc}")
        copy = getattr(C, "XHS_COPY", "")
        copy_length = len(copy.replace("\n", ""))
        if copy_length > MAX_XHS_COPY_CHARS:
            errors.append(f"小红书正文超过建议上限 {MAX_XHS_COPY_CHARS} 字：当前 {copy_length} 字")
        repeated = [layout for layout, count in layouts.items() if layout and count > 3]
        if repeated:
            warnings.append(f"小红书同一版式重复较多：{', '.join(repeated)}")

    assets = getattr(C, "ASSETS", {}) or {}
    if not isinstance(assets, dict):
        errors.append("ASSETS 必须是 dict")
    else:
        for asset_id, asset in assets.items():
            if not isinstance(asset_id, str) or not asset_id.strip():
                errors.append("ASSETS 的 ID 必须是非空字符串")
            if not isinstance(asset, dict):
                errors.append(f"ASSETS[{asset_id!r}] 必须是 dict")
                continue
            if "time" not in asset and "seconds" not in asset and "sec" not in asset:
                errors.append(f"ASSETS[{asset_id!r}] 缺少 time")
            if not str(asset.get("caption", asset.get("description", ""))).strip():
                errors.append(f"ASSETS[{asset_id!r}] 缺少 caption")

    if warnings:
        print("检查提醒：")
        for warning in warnings:
            print(f"  ⚠️ {warning}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate video-to-social content.py")
    parser.add_argument("--content", help="content.py path; defaults to project root")
    parser.add_argument("--channel", choices=("all", "wechat", "xhs"), default="all")
    args = parser.parse_args()
    try:
        errors = check(args.content, args.channel)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"验证器异常：{exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"验证失败：{len(errors)} 个问题")
        for error in errors:
            print(f"  ❌ {error}")
        return 1
    print("验证通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

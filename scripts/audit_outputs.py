#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit rendered output files before they are handed off for publishing.

This check is intentionally dependency-free.  It validates the files and
image dimensions produced by the builders, so a successful renderer cannot
silently leave a partial or mis-sized delivery directory behind.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from typing import Any

try:  # direct execution: python3 scripts/audit_outputs.py
    from common import content_root, figure_catalog, load_content, output_dir
except ModuleNotFoundError:  # module execution: python3 -m scripts.audit_outputs
    from scripts.common import content_root, figure_catalog, load_content, output_dir


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


def image_size(path: pathlib.Path) -> tuple[int, int] | None:
    """Read PNG/JPEG dimensions without requiring Pillow."""
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if data.startswith(PNG_SIGNATURE) and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height

    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 3 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index:index + 2])[0]
        if length < 2 or index + length > len(data):
            break
        if marker in JPEG_SOF_MARKERS and length >= 7:
            height, width = struct.unpack(">HH", data[index + 3:index + 7])
            return width, height
        index += length
    return None


def require_file(path: pathlib.Path, errors: list[str], label: str) -> bool:
    if not path.is_file():
        errors.append(f"缺少{label}：{path}")
        return False
    if path.stat().st_size == 0:
        errors.append(f"{label}为空：{path}")
        return False
    return True


def numbered_files(directory: pathlib.Path, suffix: str) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    numbered = sorted(directory.glob(f"[0-9][0-9].{suffix}"))
    extras = sorted(
        path for path in directory.glob(f"*.{suffix}")
        if path not in numbered
    )
    return numbered, extras


def check_dimensions(
    paths: list[pathlib.Path],
    expected: tuple[int, int],
    errors: list[str],
    label: str,
) -> None:
    for path in paths:
        actual = image_size(path)
        if actual != expected:
            actual_label = f"{actual[0]}×{actual[1]}" if actual else "无法读取"
            errors.append(
                f"{label}尺寸不正确：{path.name} 为 {actual_label}，应为 {expected[0]}×{expected[1]}"
            )


def check_width(paths: list[pathlib.Path], expected: int, errors: list[str], label: str) -> None:
    for path in paths:
        actual = image_size(path)
        if actual is None or actual[0] != expected:
            actual_label = f"{actual[0]}×{actual[1]}" if actual else "无法读取"
            errors.append(
                f"{label}宽度不正确：{path.name} 为 {actual_label}，应为 {expected}"
            )


def audit_wechat(content: Any, root: pathlib.Path, errors: list[str]) -> None:
    out = output_dir("公众号", root)
    required = {
        "article.html": "公众号 HTML",
        "article.md": "公众号 Markdown",
        "图片清单.txt": "公众号图片清单",
        "build-manifest.json": "公众号构建清单",
        "cover-2100x900.png": "公众号横版封面",
        "cover-1080x1080.png": "公众号方形封面",
    }
    for name, label in required.items():
        require_file(out / name, errors, label)

    check_dimensions(
        [out / "cover-2100x900.png"] if (out / "cover-2100x900.png").is_file() else [],
        (2100, 900),
        errors,
        "公众号封面",
    )
    check_dimensions(
        [out / "cover-1080x1080.png"] if (out / "cover-1080x1080.png").is_file() else [],
        (1080, 1080),
        errors,
        "公众号封面",
    )

    manifest_path = out / "build-manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("根节点不是 dict")
            manifest = loaded
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"公众号构建清单无法读取：{exc}")
    if manifest and manifest.get("channel") != "wechat":
        errors.append("公众号构建清单的 channel 不是 wechat")

    try:
        expected_figures, _, _ = figure_catalog(content)
    except (TypeError, ValueError) as exc:
        errors.append(f"无法从内容源建立公众号素材目录：{exc}")
        expected_figures = []
    actual_figures = manifest.get("figures", []) if manifest else []
    if not isinstance(actual_figures, list):
        errors.append("公众号构建清单的 figures 不是数组")
        actual_figures = []
    if len(actual_figures) != len(expected_figures):
        errors.append(
            f"公众号素材数量不一致：清单 {len(actual_figures)} 张，内容源 {len(expected_figures)} 张"
        )
    for index, expected in enumerate(expected_figures, 1):
        if index > len(actual_figures) or not isinstance(actual_figures[index - 1], dict):
            continue
        actual = actual_figures[index - 1]
        if actual.get("number") != index or actual.get("id") != expected["id"]:
            errors.append(
                f"公众号第 {index:02d} 张素材映射不一致："
                f"清单为 {actual.get('id')!r}，内容源为 {expected['id']!r}"
            )

    image_dir = out / "images"
    if not image_dir.is_dir():
        errors.append(f"缺少公众号配图目录：{image_dir}")
        images, extras = [], []
    else:
        images, extras = numbered_files(image_dir, "jpg")
    if extras:
        errors.append(f"公众号配图目录有非标准文件：{', '.join(path.name for path in extras)}")
    if len(images) != len(expected_figures):
        errors.append(
            f"公众号配图数量不一致：实际 {len(images)} 张，内容源 {len(expected_figures)} 张"
        )
    expected_names = [f"{index:02d}.jpg" for index in range(1, len(expected_figures) + 1)]
    if [path.name for path in images] != expected_names:
        errors.append(f"公众号配图编号不连续：实际 {[path.name for path in images]}")
    check_width(images, 1080, errors, "公众号配图")

    manifest_text_path = out / "图片清单.txt"
    if manifest_text_path.is_file():
        lines = manifest_text_path.read_text(encoding="utf-8").splitlines()
        rows = [line.split("\t", 3) for line in lines[2:] if line.strip()]
        if len(rows) != len(expected_figures):
            errors.append(
                f"图片清单条目数量不一致：实际 {len(rows)} 条，内容源 {len(expected_figures)} 条"
            )
        for index, row in enumerate(rows, 1):
            if len(row) != 4 or row[0] != f"{index:02d}":
                errors.append(f"图片清单第 {index:02d} 行格式不正确")
                continue
            if index <= len(expected_figures) and row[1] != expected_figures[index - 1]["id"]:
                errors.append(f"图片清单第 {index:02d} 行素材 ID 不一致")

    article_md = out / "article.md"
    article_html = out / "article.html"
    for index in range(1, len(expected_figures) + 1):
        token = f"图{index:02d}"
        for path in (article_md, article_html):
            if path.is_file() and token not in path.read_text(encoding="utf-8"):
                errors.append(f"{path.name} 缺少素材标记：{token}")


def audit_xhs(content: Any, root: pathlib.Path, errors: list[str]) -> None:
    out = output_dir("小红书", root)
    cards = getattr(content, "XHS_CARDS", []) or []
    if not out.is_dir():
        errors.append(f"缺少小红书输出目录：{out}")
        return
    images, extras = numbered_files(out, "png")
    if extras:
        errors.append(f"小红书输出目录有非标准 PNG：{', '.join(path.name for path in extras)}")
    expected_names = [f"{index:02d}.png" for index in range(1, len(cards) + 1)]
    if [path.name for path in images] != expected_names:
        errors.append(f"小红书卡片编号不连续：实际 {[path.name for path in images]}")
    if len(images) != len(cards):
        errors.append(f"小红书卡片数量不一致：实际 {len(images)} 张，内容源 {len(cards)} 张")
    check_dimensions(images, (1080, 1440), errors, "小红书卡片")

    require_file(out / "使用说明.txt", errors, "小红书使用说明")
    copy = str(getattr(content, "XHS_COPY", "") or "")
    copy_path = out / "正文文案.txt"
    if copy.strip():
        if require_file(copy_path, errors, "小红书正文文案"):
            actual = copy_path.read_text(encoding="utf-8").rstrip("\n")
            if actual != copy:
                errors.append("小红书正文文案与 content.py 不一致")
    elif copy_path.exists():
        errors.append("content.py 没有 XHS_COPY，但输出目录存在正文文案.txt")


def audit(content_path: str | None = None, channel: str = "all") -> list[str]:
    content = load_content(content_path)
    root = content_root(content)
    errors: list[str] = []
    if channel in {"all", "wechat"}:
        audit_wechat(content, root, errors)
    if channel in {"all", "xhs"}:
        audit_xhs(content, root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit rendered video-to-social outputs")
    parser.add_argument("--content", help="content.py path; defaults to project root")
    parser.add_argument("--channel", choices=("all", "wechat", "xhs"), default="all")
    args = parser.parse_args()
    try:
        errors = audit(args.content, args.channel)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"输出审计异常：{exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"输出审计失败：{len(errors)} 个问题")
        for error in errors:
            print(f"  ❌ {error}")
        return 1
    print(f"输出审计通过 ✅（{args.channel}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

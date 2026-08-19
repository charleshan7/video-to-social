#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared project helpers for the video-to-social build scripts.

The scripts are intentionally executable both from the project root and as
``python3 scripts/<name>.py``.  Keeping path and content loading here avoids
subtle differences between the documented commands and the actual runtime.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent


def load_content(content_path: str | os.PathLike[str] | None = None) -> Any:
    """Load the project's root ``content.py`` with a useful error message."""
    path = Path(content_path or os.environ.get("VIDEO_TO_SOCIAL_CONTENT", PROJECT_ROOT / "content.py"))
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        raise SystemExit(
            "找不到 content.py。请先复制模板：\n"
            "  cp scripts/content_template.py content.py\n"
            f"当前查找位置：{path}"
        )

    module_name = "video_to_social_content"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"无法加载文案源：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.__video_to_social_root__ = path.parent
    return module


def content_root(content: Any) -> Path:
    """Return the project root associated with a loaded content module."""
    return Path(getattr(content, "__video_to_social_root__", PROJECT_ROOT)).resolve()


def chrome_binary() -> str:
    """Find a Chrome/Chromium executable, allowing explicit configuration."""
    configured = os.environ.get("VIDEO_TO_SOCIAL_CHROME") or os.environ.get("CHROME_BIN")
    candidates = [
        configured,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit(
        "找不到 Chrome/Chromium。请安装浏览器，或设置 VIDEO_TO_SOCIAL_CHROME=/path/to/chrome。"
    )


def find_media_binary(name: str) -> str | None:
    """Locate ffmpeg/ffprobe, or return ``None``.  Never raises.

    ``imageio-ffmpeg`` ships a bundled ffmpeg build, so a project installed
    from requirements works even when the host has no system ffmpeg.
    Callers that can degrade gracefully (``validate_content``) use this;
    callers that cannot use :func:`ffmpeg_binary` / :func:`ffprobe_binary`.
    """
    configured = os.environ.get(f"VIDEO_TO_SOCIAL_{name.upper()}")
    if configured:
        return configured if Path(configured).is_file() else shutil.which(configured)

    found = shutil.which(name)
    if found:
        return found

    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
        except ImportError:
            return None
        return imageio_ffmpeg.get_ffmpeg_exe()

    return None


def _media_binary(name: str) -> str:
    found = find_media_binary(name)
    if found:
        return found
    raise SystemExit(
        f"找不到 {name}。请安装 ffmpeg（macOS: brew install ffmpeg），"
        f"或 pip install imageio-ffmpeg，"
        f"或设置 VIDEO_TO_SOCIAL_{name.upper()}=/path/to/{name}。"
    )


def ffmpeg_binary() -> str:
    return _media_binary("ffmpeg")


def ffprobe_binary() -> str:
    return _media_binary("ffprobe")


def _legacy_asset_id(seconds: float, caption: str) -> str:
    digest = hashlib.sha1(caption.encode("utf-8")).hexdigest()[:10]
    return f"legacy-{seconds:g}-{digest}"


def _lookup_crop(content: Any, seconds: float) -> str | None:
    crops = getattr(content, "CROPS", {}) or {}
    for key in (seconds, int(seconds) if seconds.is_integer() else None, str(seconds)):
        if key is not None and key in crops:
            return crops[key]
    return None


def normalize_asset(content: Any, ref: Any) -> dict[str, Any]:
    """Normalize a stable asset ID or legacy ``(seconds, caption)`` tuple.

    New content should use ``ASSETS = {"speaker-01": {"time": 140, ...}}``
    and reference it by ID.  The tuple form remains supported for existing
    projects so this refactor does not invalidate their content.py files.
    """
    assets = getattr(content, "ASSETS", {}) or {}
    asset_id: str | None = None
    raw: Any = ref

    if isinstance(ref, str):
        asset_id = ref
        if ref not in assets:
            raise ValueError(f"素材 ID 不存在：{ref}")
        raw = assets[ref]

    if isinstance(raw, dict):
        seconds = raw.get("time", raw.get("seconds", raw.get("sec")))
        caption = raw.get("caption", raw.get("description", ""))
        crop = raw.get("crop")
        if asset_id is None and raw.get("id"):
            asset_id = str(raw["id"])
    elif isinstance(raw, (tuple, list)) and len(raw) == 2:
        seconds, caption = raw
        crop = None
        if asset_id is None:
            try:
                legacy_seconds = float(seconds)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"素材 {ref!r} 的 time 不是数字：{seconds!r}") from exc
            asset_id = _legacy_asset_id(legacy_seconds, str(caption))
    else:
        raise ValueError(
            f"素材 {ref!r} 格式不正确；请使用稳定 ID，或旧格式 (秒数, 图注)。"
        )

    if seconds is None or str(caption).strip() == "":
        raise ValueError(f"素材 {asset_id or ref!r} 必须包含 time 和 caption。")
    try:
        seconds = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"素材 {asset_id or ref!r} 的 time 不是数字：{seconds!r}") from exc
    if asset_id is None:
        asset_id = _legacy_asset_id(seconds, str(caption))
    if seconds < 0:
        raise ValueError(f"素材 {asset_id or ref!r} 的 time 不能为负数。")
    return {
        "id": str(asset_id),
        "time": seconds,
        "caption": str(caption),
        "crop": crop if crop is not None else _lookup_crop(content, seconds),
    }


def figure_catalog(content: Any) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    """Return unique output figures, ID-to-number map, and occurrence order."""
    unique: list[dict[str, Any]] = []
    by_id: dict[str, int] = {}
    occurrences: list[dict[str, Any]] = []
    for section in getattr(content, "SECTIONS", []) or []:
        if not isinstance(section, dict):
            continue
        for block in section.get("blocks", []):
            if not isinstance(block, (tuple, list)) or len(block) != 2:
                continue
            kind, value = block
            if kind != "fig":
                continue
            asset = normalize_asset(content, value)
            if asset["id"] not in by_id:
                by_id[asset["id"]] = len(unique) + 1
                unique.append(asset)
            occurrences.append(asset)
    return unique, by_id, occurrences


def resolve_card_asset(
    content: Any,
    ref: Any,
    by_id: dict[str, int],
    occurrences: list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    """Resolve a new stable card asset or legacy numeric ``fig`` reference."""
    if isinstance(ref, int):
        if ref < 1 or ref > len(occurrences):
            raise ValueError(f"小红书卡片引用了不存在的图片序号：{ref}")
        asset = occurrences[ref - 1]
    else:
        asset = normalize_asset(content, ref)
    if asset["id"] not in by_id:
        raise ValueError(
            f"小红书卡片引用素材 {asset['id']!r}，但它没有出现在公众号 SECTIONS 的 fig 中。"
        )
    return asset, by_id[asset["id"]]


def output_dir(channel: str, root: Path | None = None) -> Path:
    return (root or PROJECT_ROOT) / "out" / channel

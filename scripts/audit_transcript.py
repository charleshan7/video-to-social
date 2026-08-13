#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find likely Whisper hallucination runs in a transcript JSON file."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import Any


def timestamp_seconds(value: Any) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            parts = text.replace(",", ".").split(":")
            if len(parts) == 3:
                try:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                except ValueError:
                    return value
            return value
    return str(value)


def segment_time(item: dict[str, Any], key: str, fallback: str | None = None) -> float | str | None:
    value = item.get(key)
    if value is None and fallback:
        value = item.get(fallback)
    if value is None:
        timestamps = item.get("timestamps")
        if isinstance(timestamps, dict):
            value = timestamps.get("from" if key == "start" else "to")
    return timestamp_seconds(value)


def load_segments(path: pathlib.Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON 根节点必须是对象")
    raw = payload.get("transcription", payload.get("segments", []))
    if not isinstance(raw, list):
        raise ValueError("transcription/segments 必须是数组")
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            segments.append(
                {
                    "index": index,
                    "text": text,
                    "start": segment_time(item, "start", "offset"),
                    "end": segment_time(item, "end"),
                }
            )
    return segments


def repeated_runs(
    segments: list[dict[str, Any]], min_run: int = 10
) -> list[list[dict[str, Any]]]:
    """Return maximal adjacent runs of identical normalized text."""
    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous: str | None = None
    for segment in segments:
        text = " ".join(segment["text"].split()).casefold()
        if text == previous:
            current.append(segment)
        else:
            if len(current) >= min_run:
                runs.append(current)
            current = [segment]
            previous = text
    if len(current) >= min_run:
        runs.append(current)
    return runs


def global_repeats(segments: list[dict[str, Any]], minimum: int = 9) -> list[tuple[str, int]]:
    counts = Counter(" ".join(segment["text"].split()).casefold() for segment in segments)
    return [(text, count) for text, count in counts.most_common() if count >= minimum]


def format_time(value: Any) -> str:
    if value is None:
        return "未知时间"
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{int(seconds) // 60:02d}:{seconds % 60:05.2f}"


def audit(
    path: pathlib.Path, min_run: int = 10, global_minimum: int = 9
) -> tuple[list[list[dict[str, Any]]], list[tuple[str, int]], int]:
    segments = load_segments(path)
    return repeated_runs(segments, min_run), global_repeats(segments, global_minimum), len(segments)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Whisper transcript repetition")
    parser.add_argument("transcript", type=pathlib.Path, help="transcript.json")
    parser.add_argument("--min-run", type=int, default=10, help="adjacent identical segments to flag")
    parser.add_argument("--global-minimum", type=int, default=9, help="global repeated segments to flag")
    args = parser.parse_args()
    if args.min_run < 2 or args.global_minimum < 2:
        parser.error("--min-run 和 --global-minimum 必须至少为 2")
    try:
        runs, repeats, segment_count = audit(args.transcript, args.min_run, args.global_minimum)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"转录审计失败：{exc}", file=sys.stderr)
        return 2

    print(f"段数 {segment_count}")
    if runs:
        print("⚠️ 发现连续重复段，可能是 Whisper 幻觉：")
        for run in runs:
            first, last = run[0], run[-1]
            print(
                f"  x{len(run)} · {format_time(first.get('start'))}–{format_time(last.get('end'))} · "
                f"{first['text'][:80]}"
            )
        print("  → 定位时间范围后，用 whisper-cli 的 -mc 0 关闭上下文继承重转录。")
    else:
        print("✅ 未发现连续重复段")
    if repeats:
        print("全局重复提醒：")
        for text, count in repeats[:5]:
            print(f"  x{count} · {text[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

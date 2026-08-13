#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the WeChat article and its source-frame manifest.

Run from the project root with ``python3 scripts/build_wechat.py``.  Content
is loaded explicitly from the root ``content.py`` so the documented command
works without setting PYTHONPATH.
"""
from __future__ import annotations

import base64
import argparse
import html
import json
import math
import pathlib
import re
import shutil
import subprocess

try:  # direct execution: python3 scripts/build_wechat.py
    from common import content_root, load_content, normalize_asset, output_dir
except ModuleNotFoundError:  # module execution: python3 -m scripts.build_wechat
    from scripts.common import content_root, load_content, normalize_asset, output_dir


C = load_content()
PROJECT_ROOT = content_root(C)
VIDEO_VALUE = pathlib.Path(getattr(C, "VIDEO", "keynote.mp4"))
VIDEO = VIDEO_VALUE if VIDEO_VALUE.is_absolute() else PROJECT_ROOT / VIDEO_VALUE
OUT = output_dir("公众号", PROJECT_ROOT)
IMGDIR = OUT / "images"
WIDTH, QUALITY = 1080, 3
MAX_CHARS = 84

B, INK, SUB, PAD, BODY, NOTE = (
    C.BRAND,
    "#333333",
    "#666666",
    "16px",
    15,
    13,
)


def tc(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def dlen(text: str) -> int:
    """Estimate rendered width: CJK characters are 1, other chars 0.5."""
    text = text.replace("*", "")
    cjk = len(re.findall(r"[　-〿一-鿿＀-￯]", text))
    return cjk + math.ceil((len(text) - cjk) / 2)


def rich(text: str) -> str:
    """Render the two emphasis levels; triple stars must be handled first."""
    escaped = html.escape(text)
    escaped = re.sub(
        r"\*\*\*(.+?)\*\*\*",
        f'<strong style="font-weight:600;color:{B}">\\1</strong>',
        escaped,
    )
    return re.sub(
        r"\*\*(.+?)\*\*",
        '<strong style="font-weight:600;color:#1A1A1A">\\1</strong>',
        escaped,
    )


def figure_catalog() -> tuple[list[dict], dict[str, int]]:
    """Collect unique figures in first-use order and map asset IDs to numbers."""
    unique: list[dict] = []
    by_id: dict[str, int] = {}
    for section in getattr(C, "SECTIONS", []) or []:
        for kind, value in section.get("blocks", []):
            if kind != "fig":
                continue
            asset = normalize_asset(C, value)
            if asset["id"] not in by_id:
                by_id[asset["id"]] = len(unique) + 1
                unique.append(asset)
    return unique, by_id


def resolve_figure(value: object, by_id: dict[str, int]) -> tuple[dict, int]:
    asset = normalize_asset(C, value)
    try:
        return asset, by_id[asset["id"]]
    except KeyError as exc:
        raise SystemExit(f"正文引用了未登记的图片素材：{asset['id']}") from exc


def grab(asset: dict, dest: pathlib.Path) -> None:
    if not VIDEO.is_file():
        raise SystemExit(
            f"找不到视频文件：{VIDEO}\n"
            "请先运行 ./scripts/fetch_video.sh <URL>，或修改 content.py 里的 VIDEO。"
        )
    crop = asset.get("crop")
    vf = (crop + "," if crop else "") + f"scale={WIDTH}:-2:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{asset['time']:.3f}",
            "-i",
            str(VIDEO),
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            str(QUALITY),
            str(dest),
        ],
        check=True,
    )


def main(frames_only: bool = False) -> None:
    figures, by_id = figure_catalog()
    if figures and not VIDEO.is_file():
        raise SystemExit(
            f"找不到视频文件：{VIDEO}\n"
            "请先运行 ./scripts/fetch_video.sh <URL>，或修改 content.py 里的 VIDEO。"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    IMGDIR.mkdir(parents=True)

    uris: dict[int, str] = {}
    total = 0
    manifest = ["编号\t素材 ID\t原片时间码\t图注", "-" * 90]
    for number, asset in enumerate(figures, 1):
        path = IMGDIR / f"{number:02d}.jpg"
        grab(asset, path)
        raw = path.read_bytes()
        total += len(raw)
        uris[number] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
        manifest.append(
            f"{number:02d}\t{asset['id']}\t{tc(asset['time'])}\t{asset['caption']}"
        )
    (OUT / "图片清单.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    (OUT / "build-manifest.json").write_text(
        json.dumps(
            {
                "channel": "wechat",
                "video": str(VIDEO),
                "figures": [
                    {
                        "number": number,
                        "id": asset["id"],
                        "time": asset["time"],
                        "caption": asset["caption"],
                    }
                    for number, asset in enumerate(figures, 1)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if frames_only:
        print(f"共享源图已准备（frames-only）· {len(figures)} 张 → {IMGDIR}")
        return

    over = [
        (section["no"], dlen(value), value[:24])
        for section in C.SECTIONS
        for kind, value in section["blocks"]
        if kind == "p" and dlen(value) > MAX_CHARS
    ]
    over += [("导语", dlen(p), p[:24]) for p in C.LEDE if dlen(p) > MAX_CHARS]
    over += [("结语", dlen(p), p[:24]) for p in C.CODA if dlen(p) > MAX_CHARS]

    # ── Markdown ───────────────────────────────────────────
    md = [
        f"# {C.TITLE}",
        "",
        f"{C.SOURCE_LABEL}：{C.SOURCE_URL}",
        "",
        f"*{C.SOURCE_NOTE}*",
        "",
    ]
    md += [x for p in C.LEDE for x in (p, "")]
    md += ["## 本期内容全景", ""] + [
        f"- **{number}** [{timecode}] {title}"
        for number, title, timecode in C.TOC
    ] + ["", f"→ {C.TOC_TAIL}", ""]
    for section in C.SECTIONS:
        md += ["", f"## {section['no']}、{section['title']}", ""]
        for kind, value in section["blocks"]:
            if kind == "p":
                md += [value, ""]
            elif kind == "q":
                md += [f"> {value[0]}", ">", f"> —— {value[1]}", ""]
            elif kind == "fig":
                asset, number = resolve_figure(value, by_id)
                md += [
                    f"【图{number:02d}】{asset['caption']}（原片 {tc(asset['time'])}）",
                    "",
                ]
    md += ["---", ""] + [x for p in C.CODA for x in (p, "")]
    md += [f"> {C.ENDING}", ">", f"> —— {C.ENDING_BY}", "", C.FOOTER]
    (OUT / "article.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ── WeChat HTML: inline styles only ────────────────────
    paragraph_style = (
        f'style="font-size:{BODY}px;line-height:1.8;font-weight:300;color:{INK};'
        "margin:0 0 16px;letter-spacing:.3px;text-align:justify"
    )
    h = [
        f'<section style="padding:0 {PAD};font-weight:300;color:{INK};'
        "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
        "'Source Han Sans SC','Noto Sans CJK SC',sans-serif\">"
    ]
    h.append(
        f'<p style="font-size:20px;line-height:1.5;font-weight:600;color:{INK};margin:0 0 14px">'
        + html.escape(C.TITLE)
        + "</p>"
    )
    h.append(
        f'<p style="font-size:{NOTE}px;line-height:1.75;font-weight:300;color:{SUB};'
        f'margin:0 0 22px;padding:10px 12px;background:#F5F7F6;border-left:2px solid {B}">'
        f'{html.escape(C.SOURCE_LABEL)}：<span style="color:#999;word-break:break-all">'
        f'{html.escape(C.SOURCE_URL)}</span><br>{html.escape(C.SOURCE_NOTE)}</p>'
    )
    for paragraph in C.LEDE:
        h.append(f'<p {paragraph_style}>{rich(paragraph)}</p>')

    h.append(
        f'<p style="font-size:{NOTE}px;letter-spacing:2px;color:{B};font-weight:600;'
        'margin:26px 0 12px">本 期 内 容 全 景</p>'
    )
    for number, title, timecode in C.TOC:
        h.append(
            f'<p style="font-size:{BODY}px;line-height:1.65;font-weight:300;color:{INK};margin:0 0 8px">'
            f'<span style="color:{B};font-weight:600">{html.escape(str(number))}</span>　'
            f'{html.escape(title)}　<span style="color:{SUB};font-size:12px">'
            f'{html.escape(timecode)}</span></p>'
        )
    h.append(
        f'<p style="font-size:{NOTE}px;font-weight:300;color:{SUB};margin:14px 0 8px;'
        'padding-top:12px;border-top:1px solid #ECECEC">→ '
        + html.escape(C.TOC_TAIL)
        + "</p>"
    )

    for section in C.SECTIONS:
        h.append(
            '<p style="margin:34px 0 16px;padding-top:20px;border-top:1px solid #ECECEC;'
            f'font-size:18px;line-height:1.5;font-weight:600;color:{INK}">'
            f'<span style="color:{B}">{html.escape(section["no"])}</span>　'
            f'{html.escape(section["title"])}</p>'
        )
        for kind, value in section["blocks"]:
            if kind == "p":
                h.append(f'<p {paragraph_style}>{rich(value)}</p>')
            elif kind == "q":
                quote, by = value
                h.append(
                    f'<p style="font-size:16px;line-height:1.75;font-weight:600;color:{B};'
                    f'border-left:2px solid {B};padding:2px 0 2px 14px;margin:20px 0 6px;'
                    'text-align:justify">'
                    + html.escape(quote)
                    + "</p>"
                )
                h.append(
                    f'<p style="font-size:12px;font-weight:300;color:{SUB};margin:0 0 20px;'
                    'padding-left:16px">—— '
                    + html.escape(by)
                    + "</p>"
                )
            elif kind == "fig":
                asset, number = resolve_figure(value, by_id)
                h.append(
                    '<p style="margin:20px 0 0"><img src="'
                    + uris[number]
                    + '" style="width:100%;display:block;border-radius:2px" alt="'
                    + html.escape(asset["caption"])
                    + '"></p>'
                )
                h.append(
                    f'<p style="font-size:12px;line-height:1.6;font-weight:300;color:{SUB};'
                    f'text-align:center;margin:8px 0 22px">图{number:02d}｜'
                    f'{html.escape(asset["caption"])}（原片 {tc(asset["time"])}）</p>'
                )

    h.append(
        '<p style="margin:34px 0 16px;padding-top:20px;border-top:1px solid #ECECEC;'
        f'font-size:18px;line-height:1.5;font-weight:600;color:{INK}">写在最后</p>'
    )
    for paragraph in C.CODA:
        h.append(f'<p {paragraph_style}>{rich(paragraph)}</p>')
    h.append(
        f'<p style="font-size:17px;line-height:1.75;font-weight:600;color:{B};text-align:center;'
        'margin:30px 0 6px;padding:20px 6px 0;border-top:1px solid #ECECEC">'
        + html.escape(C.ENDING)
        + "</p>"
    )
    h.append(
        f'<p style="font-size:12px;font-weight:300;color:{SUB};text-align:center;margin:0 0 26px">—— '
        + html.escape(C.ENDING_BY)
        + "</p>"
    )
    h.append(
        f'<p style="font-size:12px;line-height:1.75;font-weight:300;color:{SUB};margin:0;'
        'padding-top:12px;border-top:1px solid #ECECEC;text-align:justify">'
        + html.escape(C.FOOTER)
        + "</p>"
    )
    h.append("</section>")
    (OUT / "article.html").write_text("\n".join(h), encoding="utf-8")

    zh = len(
        re.findall(
            r"[一-鿿]",
            "\n".join(
                [
                    value
                    for section in C.SECTIONS
                    for kind, value in section["blocks"]
                    if kind == "p"
                ]
                + C.LEDE
                + C.CODA
            ),
        )
    )
    print(
        f"正文中文 {zh} 字 · {len(C.SECTIONS)} 节 · 配图 {len(figures)} 张 "
        f"（{total / 1048576:.2f} MB）"
    )
    print("段落 ≤4 行体检：", "全部合规 ✅" if not over else f"{len(over)} 处超长 ⚠️")
    for section_no, length, preview in over:
        print(f"   第{section_no}节 {length} 字：{preview}…")
    print(f"→ {OUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build WeChat article assets")
    parser.add_argument(
        "--frames-only",
        action="store_true",
        help="只抽取公众号编号源图和 manifest，不生成文章 HTML/Markdown",
    )
    args = parser.parse_args()
    main(args.frames_only)

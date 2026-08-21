#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文案源模板 —— 复制成项目根目录的 content.py 后填写。

content.py 是唯一的内容源。公众号和小红书共享同一批素材，但各自有
独立的结构和渲染规则。新项目请用稳定的素材 ID，不要在卡片里写图片
序号；这样新增图片时，旧卡片不会整体漂移。
"""

# ── 项目与来源 ─────────────────────────────────────────────
VIDEO = "keynote.mp4"  # 相对项目根目录；也可以填绝对路径
BRAND = "#D97757"       # 两个渠道共享的品牌色

TITLE = "《在这里写标题》"
SOURCE_LABEL = "原视频"
SOURCE_URL = "https://..."
SOURCE_NOTE = "《原标题》· 日期 · 地点 · 时长"
# 由 scripts/fetch_video.sh 或 scripts/download_source.py 生成；不得省略。
SOURCE_DOWNLOAD_MANIFEST = "source_download.json"

# 头图主体必须是采访人或演讲者；同一身份可服务公众号人物图和小红书首图。
HERO_SUBJECT = {
    "name": "采访人或演讲者姓名",
    "role": "interviewer",  # 只能是 interviewer 或 speaker
    "asset_id": "speaker-01",
    "source_url": SOURCE_URL,
    "source_quote": "页面/节目资料中确认身份的原文",
    "confidence": "high",
    "hero_time": 140,
    "candidate_count": 8,
    # 同主题宽窗口至少 8 帧；只允许一帧 selected=True。
    "candidates": [
        {"time": 132, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 134, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 136, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 138, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 140, "selected": True, "note": "最终头图候选"},
        {"time": 142, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 144, "selected": False, "note": "完整头部/双眼状态"},
        {"time": 146, "selected": False, "note": "完整头部/双眼状态"},
    ],
}

# ── 素材登记：稳定 ID 是唯一推荐写法 ────────────────────────
# time 使用原片秒数；caption 是文章图注；crop 可选，按素材覆盖裁剪。
ASSETS = {
    "speaker-01": {
        "time": 140,
        "caption": "人物图｜姓名、职务、一句背景介绍",
        "crop": None,
    },
    "slide-01": {
        "time": 258,
        "caption": "信息图｜图注要说清这张图在讲什么",
        "crop": None,
    },
}

# 旧项目仍可使用 CROPS = {秒数: ffmpeg crop 表达式}；新项目优先把 crop
# 写进 ASSETS，避免时间码映射散落在两个地方。
CROPS = {}

# ── 导语：公众号每段建议不超过 84 字宽 ──────────────────────
LEDE = [
    "第一句交代时间地点和基本事实。",
    "第二句给出这篇为什么值得读。",
    "第三句抛出全文主线。",
]

# ── 静态目录：(编号, 标题, 起始时间码) ───────────────────────
TOC = [
    ("01", "第一节标题", "02:54"),
]
TOC_TAIL = "一句话概括全文主线"

# ── 公众号正文：按讲者或议题分 5~8 节 ───────────────────────
# block 类型：
#   ("p", "段落")
#   ("fig", "素材 ID")
#   ("q", ("原话", "出处"))
SECTIONS = [
    dict(no="01", tc=174, title="第一节标题", blocks=[
        ("fig", "speaker-01"),
        ("p", "段落文字，每段控制在 84 字内（15px 下约 4 行）。"),
        ("p", "关键数字用 **12 万** 这样标；全场最关键的判断用 ***三星号*** 标。"),
        ("q", ("一句值得单独拎出来的原话。", "讲者姓名")),
        ("fig", "slide-01"),
    ]),
]

# ── 收尾 ───────────────────────────────────────────────────
CODA = [
    "回头看，全文主线其实是……",
    "**如果只能带走一件事……**",
]
ENDING = "适合做收尾的那句金句。"
ENDING_BY = "出处"
FOOTER = (
    "本文为解读，非逐字实录：带引号处为讲者原话中译，其余为整理者归纳。"
    "配图取自原片截帧，版权归原作者所有，此处作评述引用；图注标注原片时间码，可回原片核对。"
)

# ── 小红书卡片与正文 ───────────────────────────────────────
# fig 推荐使用素材 ID；旧项目的数字序号仍兼容，但不建议新项目继续使用。
XHS_CARDS = [
    dict(layout="hero", title="未来是<em>某某</em>", lead="副题<br>第二行"),
    dict(
        layout="image",
        fig="speaker-01",
        paras=["这一页给出核心判断。", "再用一段说明它为什么重要。"],
    ),
    dict(
        layout="ending",
        paras=["一句收束，留下可讨论的问题。"],
        big="你怎么看？",
        by="欢迎评论区聊聊",
        ask="如果只能带走一件事，你会选什么？",
    ),
]

XHS_COPY = """第一句要抓人，信息流里只显示前两行。

第二段给核心论点。

几个印象最深的：

1｜……
2｜……
3｜……

一句收束。

你怎么看？评论区聊聊 👇

#标签1 #标签2 #标签3"""

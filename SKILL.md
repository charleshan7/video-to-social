---
name: video-to-social
description: Use when turning a long talk, keynote, conference session, interview, webinar, or other video (B站/YouTube link or local MP4) into a Chinese WeChat long-form article, Xiaohongshu vertical cards, or both. Also use when regenerating an existing project, selecting only one output channel, validating video-to-social content, or restyling rendered outputs.
---

# video-to-social — 长视频转公众号长文 + 小红书卡片

把视频事实、时间码和图注维护在一个 `content.py`，再按渠道路由到独立的构建器。先建立稳定的素材登记和内容结构，再渲染；不要把平台排版规则、素材编号和临时经验散落在脚本里。

## 入口与路由

从项目根目录运行：

```bash
python3 scripts/validate_content.py --channel all
python3 scripts/build.py --channel wechat  # 公众号 + 两张封面
python3 scripts/build.py --channel xhs     # 小红书卡片；自动准备共享图片
python3 scripts/build.py --channel all
```

根据输入状态选择最短路径：

- 用户给链接：运行 `scripts/fetch_video.sh`；用户已有 MP4：跳过下载。
- 有现成字幕或转录：跳过 Whisper；没有才运行 `scripts/transcribe.sh`。
- 只要一个渠道：只构建该渠道；小红书只准备共享源图，不生成公众号文章；修改文案或版式：跳过取源和转录。
- 需要精确寻找姓名角标或幻灯片：使用 `scripts/find_frame.py`，再把结果登记到 `ASSETS`。

详细参数按需读取：

- 取源、转录、分章、选帧与核实：`references/pipeline.md`
- 公众号限制和复制发布：`references/wechat.md`
- 小红书版式和卡片节奏：`references/xiaohongshu.md`

## 内容源规则

复制模板并放在项目根目录：

```bash
cp scripts/content_template.py content.py
```

`ASSETS` 是素材唯一登记处。新项目用稳定 ID，不要把图片序号写进内容：

```python
ASSETS = {
    "speaker-01": {"time": 140, "caption": "人物图｜姓名与职务"},
    "slide-01": {"time": 258, "caption": "信息图｜核心指标", "crop": None},
}

SECTIONS = [
    dict(no="01", tc=174, title="第一节", blocks=[
        ("fig", "speaker-01"),
        ("p", "段落。关键数字用 **12 万** 标；最关键的判断用 ***品牌色*** 标。"),
        ("q", ("原话", "讲者")),
    ]),
]

XHS_CARDS = [
    dict(layout="hero", title="标题", lead="副题"),
    dict(layout="image", fig="speaker-01", paras=["卡片正文"]),
]
```

旧项目的 `("fig", (秒数, 图注))` 和小红书数字 `fig` 仍兼容；新内容不要继续扩大这两种隐式引用。

内容审计必须先于渲染：

```bash
python3 scripts/validate_content.py --channel all
```

它会检查必填字段、目录与章节编号、段落长度、素材格式、时间码、图片引用、卡片数量、首图版式和小红书正文长度；存在视频时还会用 `ffprobe` 检查时间码是否越界。

## 固定生产线

```text
① 识别输入       链接 / 本地视频 / 已有转录 / 目标渠道
② 取源与转录     只执行缺失环节；转录后检查连续重复和相似幻觉
③ 分章与核实     5~8 节；事实、人名、数据和时间码可回查
④ 登记素材       带字优先；把时间、图注、裁剪写入 ASSETS
⑤ 写唯一源       content.py 同时承载公众号结构和小红书结构
⑥ 验证与路由     validate_content.py → build.py --channel ...
⑦ 输出审计       audit_outputs.py 检查尺寸、数量、文件清单和渠道交付说明
```

共享原则：配图优先选择姓名角标、数据幻灯片、终端/界面文字；人物近景是最后选择。图注必须标原片时间码。公众号使用静态 HTML/Markdown，不依赖 JavaScript；小红书信息必须在卡片图中完成表达。

渠道硬约束：

| | 公众号 | 小红书 |
|---|---|---|
| 正文 | 3000~4000 字适合长文；单段建议 ≤84 字宽 | 正文建议 ≤950 字，标签也计入 |
| 图 | 文章图 + `2100×900` 和 `1080×1080` 封面 | ≤18 张，`1080×1440`，第 01 张必须是 `hero` |
| 排版 | 全内联样式；图片另附编号目录 | 图内完成信息，正文用于引流 |

## 交付物

```text
out/公众号/
  article.html · article.md · images/ · 图片清单.txt · build-manifest.json
  cover-2100x900.png · cover-1080x1080.png
out/小红书/
  01~NN.png · 正文文案.txt · 使用说明.txt
```

## 质量审计

把失败归类后修对应层：

- 所有场景都失败：修共享内容模型或共享规则。
- 只有一种渠道/版式失败：修渠道路由或 reference。
- 用户明确时间、图注或比例被改：修参数硬锁和验证器。
- 文件生成了但不能发布：修输出审计、尺寸、文件清单或发布说明。

转录幻觉、姓名角标、裁剪、公众号复制和卡片留白等经验不在这里重复，按需读取对应 reference。转录后运行 `python3 scripts/audit_transcript.py transcript.json`；每次修改后先跑语法检查和 `validate_content.py`，再用一个真实或最小视频样例完整前向测试；`build.py` 会自动执行 `audit_outputs.py`。

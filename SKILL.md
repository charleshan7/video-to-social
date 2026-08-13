---
name: video-to-social
description: Use when turning a long talk, keynote, conference session, or interview video (B站/YouTube 链接或本地 MP4) into a Chinese long-form WeChat article and/or Xiaohongshu vertical cards. Triggers include 视频转图文、长视频转公众号、把视频做成图文长文、keynote 解读、演讲拆解成文章、做小红书图文卡片、视频截帧配图. Also use when regenerating or restyling an article already built with this pipeline.
---

# video-to-social — 长视频转公众号长文 + 小红书卡片

## 核心原则

**一份文案源，两个渠道出片。** 文字、图注、时间码都只写一次（`content.py`），公众号和小红书各自的构建脚本从它取，口径永不分叉。

**配图必须带字。** 画面里有姓名角标、幻灯片文字、终端输出、界面截图的帧才有信息量；纯人物特写只能靠图注撑，是最后的选择。

**图注标原片时间码。** 这是解读类文章可信度的地基——读者能拿着 `22:21` 回原片核对。

## 流程

```
① 取源      yt-dlp 下片 + ffmpeg 抽 16k 单声道音频
② 转录      whisper.cpp → SRT/JSON（必须查幻觉，见下）
③ 分章      读转录切 5~8 节，定每节起止时间码
④ 选帧      按"带字优先"挑图，逐帧核对
⑤ 写文案    填 content.py（唯一源）
⑥ 出片      build_wechat.py / build_xhs.py / make_covers.py
```

详细步骤与参数见 [references/pipeline.md](references/pipeline.md)。

## 四个必踩的坑

**1. whisper 会幻觉，且专挑无人声段落。**
转录完**必须**扫重复：连续 10 行以上雷同即为幻觉段，用 `-ot/-d/-mc 0` 定点重转录。
实测一次丢了 2.5 分钟，而那恰好是全片信息密度最高的一段。

```bash
python3 -c "
import json,collections
segs=[s['text'].strip() for s in json.load(open('transcript.json'))['transcription']]
c=collections.Counter(segs)
for t,n in c.most_common(3):
    if n>8: print(f'⚠️ 幻觉嫌疑 x{n}: {t[:40]}')"
```

**2. 讲者姓名角标只出现几秒，按 10 秒采样必然扫漏。**
不要靠人眼翻缩略图。用 `scripts/find_frame.py` 拿一张参考图做全片逐秒灰度比对，几十秒定位到精确时间点。

**3. `object-fit:cover` 会裁掉原帧的上下，可能正好切掉姓名角标。**
人物图一律用自然高度满幅（1080×608），不要为了塞进固定高度而裁。

**4. 公众号会剥掉 JS。**
交互式时间轴、可折叠脑图这类在公众号里一律失效，改静态编号目录。这条决定了公众号版不能照搬网页版设计。

## 两个渠道的硬约束

| | 公众号 | 小红书 |
|---|---|---|
| 正文 | 不限，3000~4000 字合适 | **约 1000 字上限**（标签也算） |
| 图 | 单独上传，需两张封面 `2100×900` + `1080×1080` | **≤18 张**，`1080×1440`，首图定点击率 |
| 排版 | 内联样式能保留，JS 会被剥 | 信息全在图里，正文只是引流 |
| 段落 | 15px 下每行约 21 字，"每段≤4行" = **84 字上限** | 每卡 3~6 段，靠版式换气 |

排版规范见 [references/wechat.md](references/wechat.md)，卡片版式库见 [references/xiaohongshu.md](references/xiaohongshu.md)。

## 强调分两级

```
***文字***  品牌色加粗 —— 全文只留 5~8 处最关键的判断
**文字**    纯黑加粗   —— 关键数字与术语首次出现，不换色
```

加粗和换色都是强调手段，同时上是双重冗余。实测一篇 96 段的稿子里有 107 处加粗 = 等于没有重点，降到 38 处才立得住。

## 常见错误

| 症状 | 原因 | 修法 |
|---|---|---|
| 卡片中间一大块空白 | 内容不够却用 `fill` 把底部元素顶到底 | 补内容，或整块垂直居中让留白平分两端 |
| 配图看不清 | 用了远景舞台帧 | 换带字的帧；实在没有就裁出屏幕区域（`CROPS`） |
| 图片显示不全 | `object-fit:cover` 裁了原帧 | 改自然高度满幅 |
| 粘进公众号图片丢失 | data URI 不一定被编辑器接收 | 按 `images/` 编号顺序手动补传 |
| 正文超小红书上限 | 忘了标签也算字数 | 控制在 950 字以内 |

## 交付物

```
out/公众号/  article.html（浏览器全选复制→粘贴）· article.md · images/ · 图片清单.txt · 两张封面
out/小红书/  01~NN.png · 正文文案.txt · 使用说明.txt
```

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/fetch_video.sh` | 下片 + 抽音频 |
| `scripts/transcribe.sh` | whisper 转录 + 幻觉自检 |
| `scripts/find_frame.py` | 用参考图全片逐秒定位精确帧 |
| `scripts/content_template.py` | 文案源模板（唯一真源） |
| `scripts/build_wechat.py` | 公众号 HTML/MD/配图 |
| `scripts/build_xhs.py` | 小红书竖版卡片 |
| `scripts/make_covers.py` | 两张公众号封面 |

先 `cp -r scripts/ 项目目录/`，填好 `content.py` 再逐个跑。

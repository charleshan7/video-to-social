# 流水线细节

## ① 取源

```bash
yt-dlp -F "URL"                       # 先看清晰度
yt-dlp -f "30080+30280/bestvideo+bestaudio/best" --merge-output-format mp4 \
       -o "keynote.%(ext)s" "URL"
ffmpeg -v error -y -i keynote.mp4 -ar 16000 -ac 1 -c:a pcm_s16le audio.wav
```

**先查有没有现成字幕**，有就省掉整个转录环节：

```bash
yt-dlp --list-subs "URL"
```

B 站搬运版和 YouTube 原版通常内容一致；B 站往往 1080p 免登录直下，反而更省事。
两边都没字幕时才转录。

## ② 转录

模型放 `~/.cache/whisper-cpp/`。下载走国内镜像并且**必须绕开代理**：

```bash
curl --noproxy '*' -L -o ~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin \
  "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
```

> 本机全局挂了 Clash，套代理访问 hf-mirror 反而握手失败或龟速。
> 量化版 q5_0 约 547MB，质量接近 large-v3-turbo，M1 上 47 分钟音频约 7 分钟跑完。

```bash
whisper-cli -m ~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin \
            -f audio.wav -l en -t 8 -oj -osrt -of transcript -pp
```

### 幻觉自检（必做）

whisper 在音乐、演示画面、长时间无人声处会疯狂重复上一句。**跑完立刻查**：

```bash
python3 -c "
import json,collections
segs=[s['text'].strip() for s in json.load(open('transcript.json'))['transcription']]
for t,n in collections.Counter(segs).most_common(5):
    if n>8: print(f'x{n}  {t[:50]}')"
```

命中就定点重转录那一段（偏移与时长单位是毫秒，`-mc 0` 关掉上下文继承，这是防重复的关键）：

```bash
whisper-cli -m <模型> -f audio.wav -l en -ot 2550000 -d 160000 -mc 0 -of fix -otxt
```

## ③ 分章

把转录按 45 秒合并成块再读，比逐行读高效得多：

```python
import json
d = json.load(open('transcript.json'))['transcription']
def sec(t):
    h, m, rest = t.split(':'); return int(h)*3600 + int(m)*60 + int(rest.split(',')[0])
out, buf, start = [], [], None
for s in d:
    t = sec(s['timestamps']['from'])
    if start is None: start = t
    buf.append(s['text'].strip())
    if t - start >= 45:
        out.append(f"[{start//60:02d}:{start%60:02d}] " + ' '.join(buf)); buf, start = [], None
open('blocks.txt','w').write('\n\n'.join(out))
```

**按讲者分节**比按议题分节更好用：读者能跟着人物走，每节开头正好放一张人物图。

## ④ 选帧

### 先看全片有什么

```bash
ffmpeg -v error -y -i keynote.mp4 -vf "fps=1/60,scale=480:-1,tile=6x4" -frames:v 2 sheet%d.jpg
```

### 挑图优先级

1. **姓名角标**（姓名+职务，人物介绍最强）
2. **数据幻灯片**（大数字、曲线、架构图）
3. **终端 / 界面截图**（有可读文字的）
4. 人物近景（靠图注补信息，最后选择）

### 定位某一张特定帧

已知长什么样但不知道在第几秒时，别用肉眼翻缩略图——用 `find_frame.py` 做全片逐秒灰度比对。
姓名角标常常只出现 5~8 秒，10 秒采样必漏。

```bash
python3 find_frame.py keynote.mp4 参考图.jpg          # 全片搜
python3 find_frame.py keynote.mp4 参考图.jpg 130 200  # 缩范围后精搜
```

### 抽正式配图

```bash
ffmpeg -v error -y -ss <秒> -i keynote.mp4 -frames:v 1 \
       -vf "scale=1080:-2:flags=lanczos" -q:v 3 images/01.jpg
```

远景幻灯片读不清时，裁出屏幕区域（在 `content.py` 的 `CROPS` 里按秒登记）：

```python
CROPS = {287: "crop=in_w*0.368:in_h*0.345:in_w*0.010:in_h*0.238"}
```

### 诚实原则

配图的取景时间**应落在该章节的时间范围内**。图注里的时间码是给读者回查用的，跨节取图会让人对不上。

## ⑤ 核实

- **人名职务**：以现场姓名角标为准，再用官方页面/媒体报道交叉验证
- **反常数据**：讲者说了不合常识的东西（公司名、数字）时，去官网公告找一手出处，找不到就如实转述并标注存疑
- **不要猜**：双人同框谁左谁右，若片中没有单人角标，就不要写"左/右"

## ⑥ 出片

```bash
python3 build_wechat.py    # article.html + article.md + images/ + 图片清单.txt
python3 make_covers.py     # 2100×900 + 1080×1080
python3 build_xhs.py       # 01~NN.png
```

三个脚本都从同目录的 `content.py` 取数据。改文案只改 `content.py`，重跑即可。

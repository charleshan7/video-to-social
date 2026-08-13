#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成两张公众号封面：2100×900（消息主封面）与 1080×1080（方形分享封面）。

纯字体设计。不要拿带烧录字幕的视频帧当底图——压半透明蒙版后
原字幕仍会隐约透出来，显脏。

封面文案从 content.py 取 COVER_*，没有就退回 TITLE。
"""
import pathlib, subprocess
import content as C

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out" / "公众号"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B = C.BRAND

TITLE = getattr(C, "COVER_TITLE", C.TITLE)          # 可含 <em> 高亮与 <br>
SUB = getattr(C, "COVER_SUB", "")
EYEBROW = getattr(C, "COVER_EYEBROW", "")

BASE = f"""
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:100%;height:100%;overflow:hidden}}
  body{{background:#0C1214;color:#EAF1EE;
    font-family:"PingFang SC","Hiragino Sans GB","Source Han Sans SC",sans-serif;
    display:flex;flex-direction:column;justify-content:center;position:relative}}
  body::before{{content:"";position:absolute;left:-10%;top:-30%;width:70%;height:150%;
    background:radial-gradient(closest-side, {B}33, transparent 70%);pointer-events:none}}
  .mark{{position:absolute;opacity:.30}}
  .wrap{{position:relative;z-index:2}}
  .eyebrow{{font-family:ui-monospace,"SF Mono",Menlo,monospace;color:{B};text-transform:uppercase}}
  h1{{font-weight:700;letter-spacing:-.02em;line-height:1.16;color:#fff}}
  h1 em{{font-style:normal;color:{B}}}
  .rule{{background:{B};opacity:.55}}
  .sub{{color:#9DB0AC;line-height:1.55}}
"""

# 一个节点分出三条支线，呼应"编排"主题；用 SVG 画，避免旋转 div 交叉错位
MARK = f"""
<svg class="mark" viewBox="0 0 240 220" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M32 110 L120 110 L196 34 M120 110 L196 110 M120 110 L196 186"
        stroke="{B}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="26" cy="110" r="20" fill="{B}"/>
  <circle cx="200" cy="34"  r="13" fill="{B}"/>
  <circle cx="200" cy="110" r="13" fill="{B}"/>
  <circle cx="200" cy="186" r="13" fill="{B}"/>
</svg>
"""


def page(w, h, css_extra, body):
    return f'<meta charset="utf-8"><style>{BASE}{css_extra}</style>{body}{MARK}'


WIDE = page(2100, 900, """
  .wrap{padding:0 96px}
  .eyebrow{font-size:19px;letter-spacing:.34em;margin-bottom:34px}
  h1{font-size:96px}
  .rule{width:88px;height:3px;margin:38px 0 26px}
  .sub{font-size:27px;max-width:1180px}
  .mark{right:150px;top:50%;transform:translateY(-50%);width:280px;height:257px}
""", f'<div class="wrap"><div class="eyebrow">{EYEBROW}</div><h1>{TITLE}</h1>'
     f'<div class="rule"></div><div class="sub">{SUB}</div></div>')

SQUARE = page(1080, 1080, """
  .wrap{padding:0 84px}
  .eyebrow{font-size:17px;letter-spacing:.3em;margin-bottom:30px}
  h1{font-size:70px;line-height:1.22}
  .rule{width:76px;height:3px;margin:34px 0 24px}
  .sub{font-size:24px}
  .mark{right:84px;bottom:76px;width:190px;height:174px}
""", f'<div class="wrap"><div class="eyebrow">{EYEBROW}</div><h1>{TITLE}</h1>'
     f'<div class="rule"></div><div class="sub">{SUB}</div></div>')


def shoot(htm, w, h, dest):
    src = HERE / f"_cover_{w}x{h}.html"
    src.write_text(htm, encoding="utf-8")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                    f"--window-size={w},{h}", "--force-device-scale-factor=1",
                    "--virtual-time-budget=4000", f"--screenshot={dest}",
                    f"file://{src.resolve()}"], check=True, capture_output=True)
    src.unlink()
    print(f"  {dest.name}  {dest.stat().st_size/1024:.0f} KB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("生成封面：")
    shoot(WIDE, 2100, 900, OUT / "cover-2100x900.png")
    shoot(SQUARE, 1080, 1080, OUT / "cover-1080x1080.png")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书构建器：把 content.py 的 XHS_CARDS 渲染成 1080×1440 竖版卡片。

版式库（每页换一种，别复用模板）：
    hero      大字标题页，必须是第 01 张
    dropcap   栏目线 + 首字下沉 + 段落 + 图落底
    stats     大数字组 + 段落 + 图落底
    quote     上下发丝线夹住的大字引语 + 图 + 段落
    image     满幅图打头 + 图注 + 段落
    items     编号条目 + 段落 + 图落底
    text      纯文字页（用来调节节奏，不强求每页有图）
    ending    收尾页：引语 + 互动提问

在 content.py 里这样写：

    XHS_CARDS = [
      dict(layout="hero", title="未来是<em>某某</em>", lead="副题<br>第二行"),
      dict(layout="stats", eyebrow="三 个 数 字",
           stats=[("4 天","说明"),("20 天","说明")],
           paras=["段落一","段落二"], fig=2),
      dict(layout="image", fig=6, paras=["段落"], cap="自定义图注（可省，默认取 content 里的）"),
      dict(layout="text", eyebrow="栏 目 名", paras=[...],
           quote=("金句","出处")),
      ...
    ]

fig 推荐填稳定素材 ID（例如 ``speaker-01``）。旧项目也可填公众号图
的数字序号；两个渠道因此共用同一批配图和图注。
"""
import subprocess, base64, pathlib, re, html, shutil

try:  # direct execution: python3 scripts/build_xhs.py
    from common import chrome_binary, content_root, figure_catalog, load_content, resolve_card_asset, output_dir
except ModuleNotFoundError:  # module execution: python3 -m scripts.build_xhs
    from scripts.common import chrome_binary, content_root, figure_catalog, load_content, resolve_card_asset, output_dir


C = load_content()
PROJECT_ROOT = content_root(C)
HERE = PROJECT_ROOT
IMG = output_dir("公众号", PROJECT_ROOT) / "images"
OUT = output_dir("小红书", PROJECT_ROOT)
CHROME = chrome_binary()
W, H = 1080, 1440
B = C.BRAND

FIGURES, FIGURE_NUMBERS, FIGURE_OCCURRENCES = figure_catalog(C)


def tc(s):
    return f"{int(s)//60:02d}:{int(s)%60:02d}"


def rich(s):
    s = html.escape(s)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", f'<b style="color:{B}">\\1</b>', s)
    return re.sub(r"\*\*(.+?)\*\*", '<b>\\1</b>', s)


def uri(n):
    path = IMG / f"{n:02d}.jpg"
    if not path.is_file():
        raise SystemExit(
            f"找不到公众号配图：{path}\n"
            "请先运行 python3 scripts/build_wechat.py，或使用 python3 scripts/build.py --channel xhs。"
        )
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def capline(asset, extra=None):
    return f"{html.escape(extra or asset['caption'])}（原片 {tc(asset['time'])}）"


CSS = f"""
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden}}
  body{{background:#FCFBF9;color:#333;
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",sans-serif;
    display:flex;flex-direction:column}}
  .pad{{padding:0 62px}}
  .fill{{flex:1}}
  p{{font-size:31px;line-height:1.82;font-weight:300;margin-bottom:20px}}
  p:last-child{{margin-bottom:0}}
  p b{{font-weight:600;color:#111}}
  h1{{font-size:78px;line-height:1.24;font-weight:700;letter-spacing:-.02em;color:#1A1A1A}}
  h1 em,h3 em{{font-style:normal;color:{B}}}
  h3{{font-size:46px;line-height:1.32;font-weight:700;color:#1A1A1A;
    letter-spacing:-.01em;margin-bottom:26px}}
  .lead{{font-size:32px;line-height:1.7;color:#555;font-weight:300;margin-top:26px}}
  .dropcap::first-letter{{float:left;font-size:104px;line-height:.86;font-weight:700;
    color:{B};padding:6px 16px 0 0}}
  .rule{{height:1px;background:#DAD4CB}}
  .rule-dark{{height:2px;background:#2E2E2E}}
  .label{{font-size:19px;letter-spacing:.22em;color:#A5A5A5;font-weight:300}}
  .stats{{display:flex;gap:0}}
  .stat{{flex:1;padding:20px 0 0}}
  .stat + .stat{{border-left:1px solid #DAD4CB;padding-left:26px}}
  .stat b{{display:block;font-size:76px;line-height:1;font-weight:700;color:#111;
    letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
  .stat s{{display:block;text-decoration:none;font-size:21px;line-height:1.5;
    color:#8A8A8A;margin-top:14px;font-weight:300;padding-right:20px}}
  .pq{{font-size:48px;line-height:1.45;font-weight:700;color:#111;letter-spacing:-.01em}}
  .pq em{{font-style:normal;color:{B}}}
  .pqby{{font-size:22px;letter-spacing:.14em;color:#A5A5A5;font-weight:300}}
  /* 图一律满幅自然高度；别用 object-fit:cover 裁固定高度，会切掉姓名角标 */
  img{{display:block;width:100%}}
  .cap{{font-size:19px;line-height:1.6;color:#A5A5A5;font-weight:300;letter-spacing:.02em}}
  .items{{margin-top:6px}}
  .item{{display:flex;gap:24px;padding:24px 0;border-top:1px solid #DAD4CB}}
  .item:last-child{{border-bottom:1px solid #DAD4CB}}
  .item i{{font-style:normal;font-size:24px;font-weight:700;color:{B};
    padding-top:6px;min-width:76px;white-space:nowrap;font-variant-numeric:tabular-nums}}
  .item div{{font-size:29px;line-height:1.7;font-weight:300}}
  .item div b{{font-weight:600;color:#111}}
  .ask{{font-size:29px;line-height:1.6;color:#666;font-weight:300}}
"""


def paras(c):
    return "".join(f"<p>{rich(p)}</p>" for p in c.get("paras", []))


def figblock(c, top=16):
    if c.get("fig") is None:
        return ""
    asset, number = resolve_card_asset(C, c["fig"], FIGURE_NUMBERS, FIGURE_OCCURRENCES)
    return (f'<img src="{uri(number)}">'
            f'<div class="pad" style="padding-top:{top}px">'
            f'<div class="cap">{capline(asset, c.get("cap"))}</div></div>')


def eyebrow(c, dark=False):
    if not c.get("eyebrow"):
        return ""
    r = "rule-dark" if dark else "rule"
    return (f'<div class="label">{html.escape(c["eyebrow"])}</div>'
            f'<div class="{r}" style="margin:16px 0 30px"></div>')


def quoteblock(c):
    if not c.get("quote"):
        return ""
    q, by = c["quote"]
    return (f'<div class="rule" style="margin-bottom:26px"></div>'
            f'<div class="pq" style="font-size:42px">{q}</div>'
            f'<div class="pqby" style="margin-top:22px">{html.escape(by)}</div>')


def render(c):
    L = c["layout"]
    if L == "hero":
        return (f'<div class="fill"></div><div class="pad">'
                f'<h1>{c["title"]}</h1><div class="lead">{c.get("lead","")}</div></div>'
                f'<div class="fill" style="flex:.7"></div>')
    if L == "dropcap":
        ps = c.get("paras", [])
        first = f'<p class="dropcap">{rich(ps[0])}</p>' if ps else ""
        rest = "".join(f"<p>{rich(p)}</p>" for p in ps[1:])
        return (f'<div class="pad" style="padding-top:70px">{eyebrow(c)}{first}{rest}</div>'
                f'<div class="fill"></div>{figblock(c)}')
    if L == "stats":
        st = "".join(f'<div class="stat"><b>{html.escape(a)}</b><s>{html.escape(b)}</s></div>'
                     for a, b in c.get("stats", []))
        return (f'<div class="pad" style="padding-top:64px">{eyebrow(c, dark=True)}'
                f'<div class="stats">{st}</div></div>'
                f'<div class="pad" style="padding-top:38px">{paras(c)}</div>'
                f'<div class="fill"></div>{figblock(c)}')
    if L == "quote":
        q, by = c["quote"]
        return (f'<div class="pad" style="padding-top:68px;padding-bottom:24px">'
                f'<div class="rule" style="margin-bottom:26px"></div>'
                f'<div class="pq">{q}</div>'
                f'<div class="pqby" style="margin-top:22px">{html.escape(by)}</div>'
                f'<div class="rule" style="margin-top:26px"></div></div>'
                f'{figblock(c)}'
                f'<div class="pad" style="padding-top:32px;padding-bottom:60px">{paras(c)}</div>')
    if L == "image":
        return (f'{figblock(c)}'
                f'<div class="pad" style="padding-top:36px;padding-bottom:62px">{paras(c)}</div>')
    if L == "items":
        it = "".join(f'<div class="item"><i>{html.escape(a)}</i><div>{b}</div></div>'
                     for a, b in c.get("items", []))
        return (f'<div class="pad" style="padding-top:60px">{eyebrow(c)}'
                f'<div class="items">{it}</div></div>'
                f'<div class="pad" style="padding-top:30px;padding-bottom:20px">{paras(c)}</div>'
                f'<div class="fill"></div>{figblock(c)}')
    if L == "text":
        return (f'<div class="fill"></div><div class="pad">{eyebrow(c)}{paras(c)}'
                f'{quoteblock(c)}</div><div class="fill"></div>')
    if L == "ending":
        return (f'<div class="fill"></div><div class="pad">{eyebrow(c, dark=True)}{paras(c)}'
                f'<div class="pq" style="font-size:42px;margin-top:30px">{c["big"]}</div>'
                f'<div class="pqby" style="margin-top:24px">{html.escape(c.get("by",""))}</div>'
                f'<div class="rule" style="margin:36px 0 24px"></div>'
                f'<p class="ask">{c.get("ask","")}</p></div>'
                f'<div class="fill" style="flex:1.1"></div>')
    raise SystemExit(f"未知版式：{L}")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    cards = getattr(C, "XHS_CARDS", [])
    if not cards:
        raise SystemExit("content.py 里没有 XHS_CARDS")
    if cards and cards[0].get("layout") != "hero":
        raise SystemExit("小红书第 01 张必须使用 hero 版式")
    if len(cards) > 18:
        raise SystemExit(f"小红书最多 18 张，当前 {len(cards)} 张")

    for i, c in enumerate(cards, 1):
        htm = f'<meta charset="utf-8"><style>{CSS}</style>{render(c)}'
        src = HERE / f"_card_{i}.html"
        src.write_text(htm, encoding="utf-8")
        dest = OUT / f"{i:02d}.png"
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", f"--window-size={W},{H}",
                        "--force-device-scale-factor=1", "--virtual-time-budget=6000",
                        f"--screenshot={dest}", f"file://{src.resolve()}"],
                       check=True, capture_output=True)
        src.unlink()
        print(f"  {dest.name}  {dest.stat().st_size/1024:.0f} KB  ·  {c['layout']}")

    copy = getattr(C, "XHS_COPY", "")
    if copy:
        (OUT / "正文文案.txt").write_text(copy + "\n", encoding="utf-8")
        n = len(copy.replace("\n", ""))
        flag = "⚠️ 超出上限" if n > 950 else "✅"
        print(f"\n正文文案 {n} 字（建议 ≤950，标签也算）{flag}")
    (OUT / "使用说明.txt").write_text(
        "小红书发布清单\n\n"
        "1. 按 01.png 到最后一张的顺序上传，首图必须是标题页。\n"
        "2. 将正文文案.txt 粘贴到发布正文，检查标题栏和话题标签。\n"
        "3. 每张图为 1080×1440；如需改文案或图片，修改根目录 content.py 后重跑。\n",
        encoding="utf-8",
    )
    print(f"共 {len(cards)} 张 → {OUT}")


if __name__ == "__main__":
    main()

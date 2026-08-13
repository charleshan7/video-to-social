#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号构建器：从 content.py 生成 article.html / article.md / images/ / 图片清单.txt

排版参数按公众号实测调过（见 references/wechat.md）：
中文细体 300 / 正文 15px #333 / 子标题 18px / 注释 12~13px #666 / 两端缩进 16px。
每段上限 84 字（15px 下约 4 行），构建时逐段体检。
"""
import subprocess, base64, pathlib, re, html, shutil, math
import content as C

HERE = pathlib.Path(__file__).parent
VIDEO = HERE / getattr(C, "VIDEO", "keynote.mp4")
OUT = HERE / "out" / "公众号"
IMGDIR = OUT / "images"
WIDTH, QUALITY = 1080, 3
MAX_CHARS = 84

B, INK, SUB, PAD, BODY, NOTE = C.BRAND, "#333333", "#666666", "16px", 15, 13


def tc(s):
    return f"{int(s)//60:02d}:{int(s)%60:02d}"


def dlen(s):
    """估算一段占几个中文字宽：中日韩算 1，其余算 0.5。"""
    s = s.replace("*", "")
    cjk = len(re.findall(r"[　-〿一-鿿＀-￯]", s))
    return cjk + math.ceil((len(s) - cjk) / 2)


def rich(s):
    """***品牌色加粗*** / **纯黑加粗**。三星号必须先处理。"""
    s = html.escape(s)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", f'<strong style="font-weight:600;color:{B}">\\1</strong>', s)
    return re.sub(r"\*\*(.+?)\*\*", '<strong style="font-weight:600;color:#1A1A1A">\\1</strong>', s)


def grab(sec, dest):
    crop = getattr(C, "CROPS", {}).get(sec)
    vf = (crop + "," if crop else "") + f"scale={WIDTH}:-2:flags=lanczos"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sec:.3f}", "-i", str(VIDEO),
                    "-frames:v", "1", "-vf", vf, "-q:v", str(QUALITY), str(dest)], check=True)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    IMGDIR.mkdir(parents=True)

    figs, idx = [], {}
    for sec in C.SECTIONS:
        for kind, val in sec["blocks"]:
            if kind == "fig":
                figs.append((len(figs) + 1, val[0], val[1]))
                idx[val] = len(figs)

    uris, total, manifest = {}, 0, ["编号\t原片时间码\t图注", "-" * 70]
    for i, shot, cap in figs:
        p = IMGDIR / f"{i:02d}.jpg"
        grab(float(shot), p)
        raw = p.read_bytes()
        total += len(raw)
        uris[i] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
        manifest.append(f"{i:02d}\t{tc(shot)}\t{cap}")
    (OUT / "图片清单.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    over = [(s["no"], dlen(v), v[:24]) for s in C.SECTIONS for k, v in s["blocks"]
            if k == "p" and dlen(v) > MAX_CHARS]
    over += [("导语", dlen(p), p[:24]) for p in C.LEDE if dlen(p) > MAX_CHARS]
    over += [("结语", dlen(p), p[:24]) for p in C.CODA if dlen(p) > MAX_CHARS]

    # ── Markdown ───────────────────────────────────────────
    md = [f"# {C.TITLE}", "", f"{C.SOURCE_LABEL}：{C.SOURCE_URL}", "", f"*{C.SOURCE_NOTE}*", ""]
    md += [x for p in C.LEDE for x in (p, "")]
    md += ["## 本期内容全景", ""] + [f"- **{n}** [{k}] {t}" for n, t, k in C.TOC] + ["", f"→ {C.TOC_TAIL}", ""]
    for s in C.SECTIONS:
        md += ["", f"## {s['no']}、{s['title']}", ""]
        for kind, val in s["blocks"]:
            if kind == "p":
                md += [val, ""]
            elif kind == "q":
                md += [f"> {val[0]}", ">", f"> —— {val[1]}", ""]
            else:
                md += [f"【图{idx[val]:02d}】{val[1]}（原片 {tc(val[0])}）", ""]
    md += ["---", ""] + [x for p in C.CODA for x in (p, "")]
    md += [f"> {C.ENDING}", ">", f"> —— {C.ENDING_BY}", "", C.FOOTER]
    (OUT / "article.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ── 公众号 HTML（全内联样式） ──────────────────────────
    P = (f'style="font-size:{BODY}px;line-height:1.8;font-weight:300;color:{INK};'
         'margin:0 0 16px;letter-spacing:.3px;text-align:justify"')
    h = [f'<section style="padding:0 {PAD};font-weight:300;color:{INK};'
         "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
         "'Source Han Sans SC','Noto Sans CJK SC',sans-serif\">"]
    h.append(f'<p style="font-size:20px;line-height:1.5;font-weight:600;color:{INK};margin:0 0 14px">'
             + html.escape(C.TITLE) + '</p>')
    h.append(f'<p style="font-size:{NOTE}px;line-height:1.75;font-weight:300;color:{SUB};'
             f'margin:0 0 22px;padding:10px 12px;background:#F5F7F6;border-left:2px solid {B}">'
             f'{html.escape(C.SOURCE_LABEL)}：<span style="color:#999;word-break:break-all">'
             f'{html.escape(C.SOURCE_URL)}</span><br>{html.escape(C.SOURCE_NOTE)}</p>')
    for p in C.LEDE:
        h.append(f'<p {P}>{rich(p)}</p>')

    h.append(f'<p style="font-size:{NOTE}px;letter-spacing:2px;color:{B};font-weight:600;'
             'margin:26px 0 12px">本 期 内 容 全 景</p>')
    for n, t, k in C.TOC:
        h.append(f'<p style="font-size:{BODY}px;line-height:1.65;font-weight:300;color:{INK};margin:0 0 8px">'
                 f'<span style="color:{B};font-weight:600">{n}</span>　{html.escape(t)}'
                 f'　<span style="color:{SUB};font-size:12px">{k}</span></p>')
    h.append(f'<p style="font-size:{NOTE}px;font-weight:300;color:{SUB};margin:14px 0 8px;'
             'padding-top:12px;border-top:1px solid #ECECEC">→ ' + html.escape(C.TOC_TAIL) + '</p>')

    for s in C.SECTIONS:
        # 章节标题后不放时间码——目录里有就够了，放这儿只会挤到换行
        h.append('<p style="margin:34px 0 16px;padding-top:20px;border-top:1px solid #ECECEC;'
                 f'font-size:18px;line-height:1.5;font-weight:600;color:{INK}">'
                 f'<span style="color:{B}">{s["no"]}</span>　{html.escape(s["title"])}</p>')
        for kind, val in s["blocks"]:
            if kind == "p":
                h.append(f'<p {P}>{rich(val)}</p>')
            elif kind == "q":
                q, by = val
                h.append(f'<p style="font-size:16px;line-height:1.75;font-weight:600;color:{B};'
                         f'border-left:2px solid {B};padding:2px 0 2px 14px;margin:20px 0 6px;'
                         'text-align:justify">' + html.escape(q) + '</p>')
                h.append(f'<p style="font-size:12px;font-weight:300;color:{SUB};margin:0 0 20px;'
                         'padding-left:16px">—— ' + html.escape(by) + '</p>')
            else:
                i = idx[val]
                h.append('<p style="margin:20px 0 0"><img src="' + uris[i] +
                         '" style="width:100%;display:block;border-radius:2px" alt="'
                         + html.escape(val[1]) + '"></p>')
                # 图注时间码加括号：它是附注，不该和正文同级
                h.append(f'<p style="font-size:12px;line-height:1.6;font-weight:300;color:{SUB};'
                         f'text-align:center;margin:8px 0 22px">图{i:02d}｜{html.escape(val[1])}'
                         f'（原片 {tc(val[0])}）</p>')

    h.append('<p style="margin:34px 0 16px;padding-top:20px;border-top:1px solid #ECECEC;'
             f'font-size:18px;line-height:1.5;font-weight:600;color:{INK}">写在最后</p>')
    for p in C.CODA:
        h.append(f'<p {P}>{rich(p)}</p>')
    h.append(f'<p style="font-size:17px;line-height:1.75;font-weight:600;color:{B};text-align:center;'
             'margin:30px 0 6px;padding:20px 6px 0;border-top:1px solid #ECECEC">'
             + html.escape(C.ENDING) + '</p>')
    h.append(f'<p style="font-size:12px;font-weight:300;color:{SUB};text-align:center;margin:0 0 26px">—— '
             + html.escape(C.ENDING_BY) + '</p>')
    h.append(f'<p style="font-size:12px;line-height:1.75;font-weight:300;color:{SUB};margin:0;'
             'padding-top:12px;border-top:1px solid #ECECEC;text-align:justify">'
             + html.escape(C.FOOTER) + '</p>')
    h.append('</section>')
    (OUT / "article.html").write_text("\n".join(h), encoding="utf-8")

    zh = len(re.findall(r"[一-鿿]", "\n".join(
        [v for s in C.SECTIONS for k, v in s["blocks"] if k == "p"] + C.LEDE + C.CODA)))
    print(f"正文中文 {zh} 字 · {len(C.SECTIONS)} 节 · 配图 {len(figs)} 张（{total/1048576:.2f} MB）")
    print("段落 ≤4 行体检：", "全部合规 ✅" if not over else f"{len(over)} 处超长 ⚠️")
    for no, n, s in over:
        print(f"   第{no}节 {n} 字：{s}…")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()

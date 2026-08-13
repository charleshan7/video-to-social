#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用一张参考图在原片里逐帧比对，定位它的精确时间点。

姓名角标之类的元素常常只出现 5~8 秒，按 10 秒采样必然漏掉，
肉眼翻缩略图又看不清。这个脚本把两者都省了。

用法：
    python3 find_frame.py <video.mp4> <参考图.jpg>            # 全片逐秒搜
    python3 find_frame.py <video.mp4> <参考图.jpg> 130 200    # 缩范围后逐 0.25 秒精搜

原理：参考图和候选帧都裁到左下角（角标常驻区）、缩到 64×32 灰度，
逐帧算平均像素差。差值 <10 基本可判定命中。
"""
import subprocess, sys, pathlib, tempfile

# 角标常在左下角；要搜画面其它区域就改这里
CROP = "crop=in_w*0.36:in_h*0.26:in_w*0.04:in_h*0.72,scale=64:32"


def gray_bytes(src, pre_args=(), vf_extra=""):
    """把 src 按 CROP 裁剪缩放成灰度原始字节流。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".raw", delete=False).name
    vf = f"{vf_extra}{CROP},format=gray"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *pre_args, "-i", str(src),
                    "-vf", vf, "-f", "rawvideo", tmp], check=True)
    data = pathlib.Path(tmp).read_bytes()
    pathlib.Path(tmp).unlink()
    return data


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    video, ref = sys.argv[1], sys.argv[2]
    t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    t1 = float(sys.argv[4]) if len(sys.argv) > 4 else None
    fps = 4 if (t1 is not None and t1 - t0 <= 60) else 1

    ref_bytes = gray_bytes(ref)
    n = len(ref_bytes)

    pre = ["-ss", str(t0)] + (["-to", str(t1)] if t1 is not None else [])
    cand = gray_bytes(video, pre_args=pre, vf_extra=f"fps={fps},")

    res = []
    for i in range(len(cand) // n):
        blk = cand[i * n:(i + 1) * n]
        diff = sum(abs(a - b) for a, b in zip(ref_bytes, blk)) / n
        res.append((diff, t0 + i / fps))
    if not res:
        sys.exit("没有取到候选帧，检查时间范围")
    res.sort()

    print(f"比对完成：{len(res)} 帧，精度 {1/fps:.2f}s")
    for d, t in res[:5]:
        print(f"  {int(t)//60:02d}:{int(t)%60:02d} ({t:7.2f}s)   差值 {d:5.1f}"
              + ("   ← 命中" if d < 10 else ""))

    if res[0][0] >= 10:
        print("\n⚠️  最小差值仍偏大，这一帧可能不在搜索范围内。放宽范围（去掉起止参数）再试一次。")
    else:
        best = res[0][1]
        print(f"\n抽正式配图：")
        print(f'  ffmpeg -v error -y -ss {best:.2f} -i {video} -frames:v 1 \\')
        print(f'         -vf "scale=1080:-2:flags=lanczos" -q:v 3 out.jpg')


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# 探测 / 下字幕 / 最高质量下片 + 抽 16k 单声道音频。
# 用法：./scripts/fetch_video.sh <URL> [输出名] [--subs-only]
# 完整下载固定走 bestvideo*+bestaudio/best，并写 source_download.json。
#
# 先跑 --subs-only：字幕只有几十 KB，够把选题和分章都定完；
# 长视频 1080p 常常 400MB+，是整条流水线最慢的一环，选句阶段用不上。
set -euo pipefail
URL="${1:?用法: fetch_video.sh <URL> [name] [--subs-only]}"
NAME="${2:-keynote}"
SUBS_ONLY=""
for arg in "$@"; do [ "$arg" = "--subs-only" ] && SUBS_ONLY=1; done
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "▸ 可用清晰度"; yt-dlp -F "$URL" 2>&1 | tail -12
echo
echo "▸ 是否自带字幕（有的话可跳过转录）"; yt-dlp --list-subs "$URL" 2>&1 | tail -6
echo

if [ -n "$SUBS_ONLY" ]; then
  echo "▸ 只下字幕（--subs-only）"
  yt-dlp --skip-download --write-subs --sub-langs "en-orig,en,zh-Hans" \
         --sub-format srt --convert-subs srt -o "subs/%(id)s.%(ext)s" "$URL" || true
  ls -la subs/ 2>/dev/null || echo "  没抓到字幕轨，需要走 transcribe.sh 转录"
  echo "▸ 定完选题和分章后，去掉 --subs-only 再下片"
  exit 0
fi

echo "▸ 下载可获得的最高质量直接源"
python3 scripts/download_source.py "$URL" --out-dir "$ROOT" --basename "$NAME"
MEDIA="$(find "$ROOT" -maxdepth 1 -type f -name "${NAME}.*" -print | grep -E '\\.(mkv|mp4|webm|mov)$' | head -1 || true)"
[ -n "$MEDIA" ] || { echo "未找到合并后的视频文件，停止。" >&2; exit 1; }
echo "▸ 已选择 $MEDIA"
echo "▸ 抽音频"
ffmpeg -v error -y -i "$MEDIA" -ar 16000 -ac 1 -c:a pcm_s16le "${NAME}_audio.wav"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$MEDIA" \
  | awk '{printf "▸ 时长 %d 分 %d 秒\\n", $1/60, $1%60}'

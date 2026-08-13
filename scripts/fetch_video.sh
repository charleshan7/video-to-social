#!/usr/bin/env bash
# 下片 + 抽 16k 单声道音频。用法：./fetch_video.sh <URL> [输出名]
set -euo pipefail
URL="${1:?用法: fetch_video.sh <URL> [name]}"
NAME="${2:-keynote}"

echo "▸ 可用清晰度"; yt-dlp -F "$URL" 2>&1 | tail -12
echo
echo "▸ 是否自带字幕（有的话可跳过转录）"; yt-dlp --list-subs "$URL" 2>&1 | tail -6
echo
echo "▸ 下载"
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best" --merge-output-format mp4 \
       -o "${NAME}.%(ext)s" "$URL"
echo "▸ 抽音频"
ffmpeg -v error -y -i "${NAME}.mp4" -ar 16000 -ac 1 -c:a pcm_s16le "${NAME%.*}_audio.wav"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "${NAME}.mp4" \
  | awk '{printf "▸ 时长 %d 分 %d 秒\n", $1/60, $1%60}'

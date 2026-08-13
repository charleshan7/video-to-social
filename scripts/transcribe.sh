#!/usr/bin/env bash
# whisper 转录 + 幻觉自检。用法：./scripts/transcribe.sh <audio.wav> [语言]
set -euo pipefail
AUDIO="${1:?用法: transcribe.sh <audio.wav> [lang]}"
LANG="${2:-en}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODEL="$HOME/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin"

if [ ! -f "$MODEL" ]; then
  echo "▸ 下载模型（走国内镜像，必须绕开代理）"
  mkdir -p "$(dirname "$MODEL")"
  curl --noproxy '*' -L --retry 5 -C - -o "$MODEL" \
    "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
fi

echo "▸ 转录中"
whisper-cli -m "$MODEL" -f "$AUDIO" -l "$LANG" -t 8 -oj -osrt -of transcript -pp 2>&1 | tail -3

echo
echo "▸ 幻觉自检"
python3 scripts/audit_transcript.py transcript.json

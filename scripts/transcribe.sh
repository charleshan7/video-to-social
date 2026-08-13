#!/usr/bin/env bash
# whisper 转录 + 幻觉自检。用法：./transcribe.sh <audio.wav> [语言]
set -euo pipefail
AUDIO="${1:?用法: transcribe.sh <audio.wav> [lang]}"
LANG="${2:-en}"
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
python3 - <<'PY'
import json, collections
segs = [s['text'].strip() for s in json.load(open('transcript.json'))['transcription']]
hits = [(t, n) for t, n in collections.Counter(segs).most_common(5) if n > 8]
if hits:
    print("⚠️  发现重复段落，极可能是幻觉：")
    for t, n in hits:
        print(f"   x{n}  {t[:56]}")
    print("   → 定位时间范围后定点重转录：")
    print("     whisper-cli -m <模型> -f <音频> -ot <起始毫秒> -d <时长毫秒> -mc 0 -of fix -otxt")
else:
    print("✅ 未发现明显重复")
print(f"\n段数 {len(segs)} · 词数 {sum(len(s.split()) for s in segs)}")
PY

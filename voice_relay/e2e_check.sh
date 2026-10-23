#!/bin/bash
# 端到端自检: 用 macOS say 生成中文语音 -> 16kHz 单声道 PCM -> POST 到本地中转 -> 打印状态码与板子指令。
# 需要先在另一个终端运行 python3 server.py。say 在沙箱里输出为空，请在普通终端运行。
# 用法: ./e2e_check.sh [http://127.0.0.1:8787]
set -euo pipefail

HOST="${1:-http://127.0.0.1:8787}"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "健康检查:"
curl -s -m 5 "$HOST/api/health"
echo -e "\n"

run() {
  local label="$1" text="$2"
  say -v Tingting -o "$WORK/a.aiff" "$text"
  afconvert -f WAVE -d LEI16@16000 -c 1 "$WORK/a.aiff" "$WORK/a.wav"
  python3 -I - "$WORK/a.wav" "$WORK/a.pcm" <<'EOF'
import sys, wave
w = wave.open(sys.argv[1])
open(sys.argv[2], "wb").write(w.readframes(w.getnframes()))
EOF
  local code cmd size
  code=$(curl -s -m 90 -o "$WORK/reply.pcm" -D "$WORK/h.txt" -w '%{http_code}' \
         -H 'Content-Type: application/octet-stream' --data-binary @"$WORK/a.pcm" "$HOST/api/voice")
  cmd=$(grep -i '^X-Wake-Cmd:' "$WORK/h.txt" | tr -d '\r' || true)
  size=$(stat -f %z "$WORK/reply.pcm")
  printf '%-24s HTTP %-4s 回复音频 %7s 字节  %s\n' "$label" "$code" "$size" "$cmd"
}

# 注意顺序: 第一句不含唤醒词，且之前没有唤醒过，所以应当 204
run "闲聊(无唤醒词,应204)"   "今天天气不错"
run "唤醒+开始守夜(应N:1)"   "小夜，开始守夜"
run "追问窗口内记梦(无指令)" "我梦见在海里游泳"
run "唤醒+早安(应N:2)"       "小夜，早安"

echo
echo "梦境笔记文件:"
cat "$(dirname "$0")/notes.jsonl" 2>/dev/null || echo "(没有 notes.jsonl: 记梦这一步没有成功写入)"

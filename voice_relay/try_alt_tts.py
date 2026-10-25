#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试一个备用 TTS 模型/音色。读 .env（不打印 Key），请求 WAV，保存并报告音频格式与耗时。
用法: python3 try_alt_tts.py <模型名> [音色名]
例:   python3 try_alt_tts.py qwen3-tts-flash
      python3 try_alt_tts.py tts-1-hd alloy
成功后会保存 voice_relay/alt_tts_<模型>.wav，请人工播放确认是清晰的中文。"""
import io
import json
import sys
import time
import urllib.error
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from server import Config, load_env, _post  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
model = sys.argv[1]

load_env(HERE / ".env")
cfg = Config()
voice = sys.argv[2] if len(sys.argv) > 2 else cfg.tts_voice
if not cfg.base or not cfg.key:
    sys.exit("缺少 OPENDEV_BASE_URL 或 OPENDEV_API_KEY，请先填写 voice_relay/.env")

body = json.dumps({"model": model, "voice": voice, "input": "早安，昨晚卧室环境得分八十五分。",
                   "response_format": "wav"}).encode()
hdr = {"Authorization": f"Bearer {cfg.key}", "Content-Type": "application/json"}
t0 = time.time()
try:
    data = _post(f"{cfg.base}/audio/speech", body, hdr, timeout=40, tries=1)   # tries=1: 想看到真实的第一次结果
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace").replace(cfg.key, "***")[:300]
    sys.exit(f"失败 model={model} voice={voice}: HTTP {e.code} {detail}")
except Exception as e:
    sys.exit(f"失败 model={model} voice={voice}: {type(e).__name__}: {e}")

dt = time.time() - t0
if data[:4] != b"RIFF":
    kind = "MP3" if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3") else repr(data[:8])
    sys.exit(f"返回了 {len(data)} 字节，但不是 WAV 而是 {kind}（server.py 目前只接受 WAV）。耗时 {dt:.1f}s")
with wave.open(io.BytesIO(data), "rb") as w:
    info = f"{w.getnchannels()} 声道, {w.getframerate()} Hz, {w.getsampwidth() * 8} bit, {w.getnframes() / w.getframerate():.2f} 秒"
out = HERE / ("alt_tts_" + "".join(c if c.isalnum() or c in "-_." else "_" for c in model) + ".wav")
out.write_bytes(data)
print(f"成功 model={model} voice={voice}  耗时 {dt:.1f}s  {len(data)} 字节  {info}")
print(f"已保存 {out}，请用 afplay 播放确认是清晰的中文。")
print(f"提醒: server.py 只支持 16bit WAV；若上面不是 16bit，需要改解码。")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测上游(Opendev)接口。只读取 .env，绝不打印 API Key。
用法: python3 probe_upstream.py
输出: 模型清单、ASR/对话/TTS 各自的 HTTP 状态，以及 TTS 返回的真实音频格式。"""
import io
import json
import math
import os
import struct
import sys
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from server import Config, load_env, pcm_to_wav, SR  # noqa: E402

load_env(HERE / ".env")
cfg = Config()
miss = cfg.missing()
if miss:
    sys.exit("缺少环境变量: " + ", ".join(miss) + "。请先填写 voice_relay/.env")


def redact(b, limit=400):
    s = b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b)
    return s.replace(cfg.key, "***")[:limit]


def call(method, path, body=None, headers=None):
    h = {"Authorization": f"Bearer {cfg.key}",
         "User-Agent": os.environ.get("USER_AGENT", "curl/7.88.1")}   # 避开 Cloudflare 对 Python-urllib 的 1010 拦截
    h.update(headers or {})
    r = urllib.request.Request(cfg.base + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # 网络层错误
        return None, {}, str(e).encode()


def sine_pcm(sec=1.0, hz=440):
    n = int(SR * sec)
    return b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * hz * i / SR))) for i in range(n))


print(f"基址: {cfg.base}")
print(f"模型配置: ASR={cfg.asr_model}  CHAT={cfg.chat_model}  TTS={cfg.tts_model}/{cfg.tts_voice}\n")

# 1. 模型清单
st, _, body = call("GET", "/models")
print(f"[1] GET /models -> {st}")
if st == 200:
    try:
        ids = sorted(m["id"] for m in json.loads(body)["data"])
        print(f"    共 {len(ids)} 个模型，前 80 个: {ids[:80]}")
    except Exception:
        print("    返回格式不是标准 {data:[{id}]}: " + redact(body))
else:
    print("    " + redact(body))

# 2. ASR（1 秒正弦波，预期识别不出文字，但状态码应为 200）
boundary = uuid.uuid4().hex
mp = (f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{cfg.asr_model}\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nzh\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
      f'Content-Type: audio/wav\r\n\r\n').encode() + pcm_to_wav(sine_pcm()) + f"\r\n--{boundary}--\r\n".encode()
st, _, body = call("POST", "/audio/transcriptions", mp, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
print(f"\n[2] POST /audio/transcriptions -> {st}\n    " + redact(body))

# 3. 对话
st, _, body = call("POST", "/chat/completions",
                   json.dumps({"model": cfg.chat_model, "max_tokens": 40,
                               "messages": [{"role": "user", "content": "用一句话说你好"}]}).encode(),
                   {"Content-Type": "application/json"})
print(f"\n[3] POST /chat/completions -> {st}\n    " + redact(body))

# 4. TTS（要求 wav）
st, hdr, body = call("POST", "/audio/speech",
                     json.dumps({"model": cfg.tts_model, "voice": cfg.tts_voice,
                                 "input": "早安，昨晚卧室环境得分八十五分", "response_format": "wav"}).encode(),
                     {"Content-Type": "application/json"})
ctype = hdr.get("Content-Type") or hdr.get("content-type")
print(f"\n[4] POST /audio/speech -> {st}  Content-Type={ctype}  {len(body)} 字节")
if st == 200:
    head = body[:4]
    if head == b"RIFF":
        with wave.open(io.BytesIO(body), "rb") as w:
            print(f"    WAV: {w.getnchannels()} 声道, {w.getframerate()} Hz, {w.getsampwidth() * 8} bit, "
                  f"{w.getnframes() / w.getframerate():.2f} 秒")
        (HERE / "probe_tts.wav").write_bytes(body)
        print("    已保存 voice_relay/probe_tts.wav，请人工听一遍是否是清晰的中文")
    else:
        kind = "MP3" if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3") else repr(head)
        print(f"    返回的不是 WAV 而是 {kind}。server.py 目前只接受 WAV，需要改解码，请把这行原样汇报。")
else:
    print("    " + redact(body))

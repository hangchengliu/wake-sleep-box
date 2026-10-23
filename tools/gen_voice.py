#!/usr/bin/env python3
"""
生成 Wake 开发板用的离线语音词库 -> display_name/voice_data.h

必须在你自己的终端运行（需要 macOS 的 say + afconvert，沙箱里 say 输出为空）。
用法:
    python3 tools/gen_voice.py                # 默认声音 Tingting
    python3 tools/gen_voice.py --voice Flo
    python3 tools/gen_voice.py --check        # 只检查 say 能否出声，不生成

音频格式: 16kHz / 单声道 / 16bit，与固件 I2S 一致。
压缩: 8bit mu-law 不使用；为保证听感与简单解码，这里直接存 16bit PCM，
      再按 --max-kb 检查总大小，超出则报错而不是悄悄降质。
"""
import argparse
import array
import os
import struct
import subprocess
import sys
import tempfile
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_H = os.path.join(ROOT, "display_name", "voice_data.h")
SR = 16000

# id 必须与固件 display_name.ino 里的 enum 顺序完全一致（脚本会同时生成枚举，固件直接引用）。
# 数字 0-9、"十"、"百" 用于拼 0-100 的任意整数。
WORDS = [
    # --- 数字与量词 ---
    ("D0", "零"), ("D1", "一"), ("D2", "二"), ("D3", "三"), ("D4", "四"),
    ("D5", "五"), ("D6", "六"), ("D7", "七"), ("D8", "八"), ("D9", "九"),
    ("TEN", "十"), ("HUNDRED", "一百"),
    ("TWO_LIANG", "两"),
    # --- 句子成分 ---
    ("GOOD_MORNING", "早安"),
    ("LAST_NIGHT_SCORE", "昨晚卧室环境得分"),
    ("POINTS", "分"),
    ("NOISE_PRE", "整夜监测到"),
    ("NOISE_POST", "次突发噪音"),
    ("PEAK", "最高"),
    ("DB", "分贝"),
    ("NO_NOISE", "整夜没有明显噪音"),
    ("LEAK_PRE", "夜间漏光"),
    ("TIMES", "次"),
    ("NO_LEAK", "没有漏光"),
    ("UP_PRE", "起夜"),
    ("NO_UP", "没有起夜"),
    ("TEMP_BAD", "室温偏离了舒适区"),
    ("ADVICE_PRE", "建议"),
    # --- 五条建议 ---
    ("ADV_GOOD", "整夜安静无漏光温度舒适请继续保持"),
    ("ADV_NOISE", "睡前关紧窗户或使用耳塞和白噪音"),
    ("ADV_LEAK", "拉严遮光帘并遮住指示灯"),
    ("ADV_UP", "睡前一小时少喝水起夜只开微弱暖光"),
    ("ADV_TEMP", "睡前把空调定在二十到二十二度"),
    # --- 其他提示 ---
    ("NO_REPORT", "还没有晨间报告请先开始守夜"),
    ("GOOD_NIGHT", "晚安开始守夜"),
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def synth(voice, text, tmpdir, idx):
    aiff = os.path.join(tmpdir, f"w{idx}.aiff")
    wav = os.path.join(tmpdir, f"w{idx}.wav")
    r = run(["say", "-v", voice, "-o", aiff, text])
    if r.returncode != 0:
        sys.exit(f"say 失败: {r.stderr.strip()}")
    r = run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, wav])
    if r.returncode != 0:
        sys.exit(f"afconvert 失败: {r.stderr.strip()}")
    with wave.open(wav, "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        pcm = array.array("h")
        pcm.frombytes(w.readframes(w.getnframes()))
    return pcm


def trim_and_fade(pcm, thresh=350, pad=int(SR * 0.02)):
    """裁掉首尾静音，留少量余量，首尾做短淡入淡出避免拼接爆音。"""
    n = len(pcm)
    s = 0
    while s < n and abs(pcm[s]) < thresh:
        s += 1
    e = n
    while e > s and abs(pcm[e - 1]) < thresh:
        e -= 1
    s = max(0, s - pad)
    e = min(n, e + pad)
    out = array.array("h", pcm[s:e])
    fade = min(int(SR * 0.008), len(out) // 4)
    for i in range(fade):
        g = i / fade
        out[i] = int(out[i] * g)
        out[len(out) - 1 - i] = int(out[len(out) - 1 - i] * g)
    return out


def normalize(pcm, target=24000):
    peak = max((abs(x) for x in pcm), default=1)
    if peak < 100:
        return pcm
    k = min(target / peak, 6.0)
    return array.array("h", (max(-32768, min(32767, int(x * k))) for x in pcm))


def dummy_blobs():
    """仅用于编译测试的占位音（每词 0.3 秒正弦），不调用 say。"""
    import math
    out = []
    for i, _ in enumerate(WORDS):
        f0 = 300 + 25 * i
        out.append(array.array("h", (int(6000 * math.sin(2 * math.pi * f0 * t / SR))
                                     for t in range(int(SR * 0.3)))))
    return out


def real_blobs(voice, check_only):
    with tempfile.TemporaryDirectory() as tmp:
        probe = synth(voice, "早安", tmp, 0)
        if len(probe) < SR // 10:
            sys.exit("say 没有生成有效音频（时长≈0）。请在你自己的终端运行，不要在沙箱里运行。")
        if check_only:
            print(f"OK: 声音 {voice} 可用，'早安' 时长 {len(probe)/SR:.2f}s")
            return []
        blobs = []
        for i, (name, text) in enumerate(WORDS):
            pcm = normalize(trim_and_fade(synth(voice, text, tmp, i)))
            if len(pcm) < SR // 20:
                sys.exit(f"词 {name}('{text}') 生成后过短，声音可能不支持该字")
            blobs.append(pcm)
            print(f"  {name:18s} {text:14s} {len(pcm)/SR:5.2f}s {len(pcm)*2/1024:6.1f}KB")
        return blobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Tingting")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dummy", action="store_true",
                    help="仅供编译测试：生成每词 0.3 秒的蜂鸣占位音，不调用 say。不要烧录给用户听。")
    ap.add_argument("--max-kb", type=int, default=2600,
                    help="音频数据总大小上限(KB)；ota_1 约剩 3MB，需给固件增长留余量")
    args = ap.parse_args()

    if args.dummy:
        blobs = dummy_blobs()
        args.voice = "DUMMY(占位蜂鸣，勿烧录)"
    else:
        blobs = real_blobs(args.voice, args.check)
        if args.check:
            return

    total = sum(len(b) for b in blobs) * 2
    print(f"\n总计 {total/1024:.1f} KB ({sum(len(b) for b in blobs)/SR:.1f} 秒), 上限 {args.max_kb} KB")
    if total / 1024 > args.max_kb:
        sys.exit("超出体积上限：请换更短的文案，或调大 --max-kb（先确认固件仍能放进 4MB 分区）")

    with open(OUT_H, "w", encoding="utf-8") as f:
        f.write("// 由 tools/gen_voice.py 自动生成，请勿手改。\n")
        f.write(f"// 声音: {args.voice}, {SR}Hz 单声道 16bit, 词数: {len(WORDS)}\n")
        f.write("#pragma once\n#include <stdint.h>\n#include <pgmspace.h>\n\n")
        f.write("enum VoiceWord {\n")
        for name, _ in WORDS:
            f.write(f"    VW_{name},\n")
        f.write("    VW_COUNT\n};\n\n")
        offs, cur = [], 0
        for b in blobs:
            offs.append((cur, len(b)))
            cur += len(b)
        f.write("static const uint32_t voice_off[VW_COUNT] = {" +
                ",".join(str(o) for o, _ in offs) + "};\n")
        f.write("static const uint32_t voice_len[VW_COUNT] = {" +
                ",".join(str(n) for _, n in offs) + "};\n\n")
        f.write("static const int16_t voice_pcm[] PROGMEM = {\n")
        flat = array.array("h")
        for b in blobs:
            flat.extend(b)
        for i in range(0, len(flat), 16):
            f.write(",".join(str(x) for x in flat[i:i + 16]) + ",\n")
        f.write("};\n")
    print(f"已写入 {OUT_H} ({os.path.getsize(OUT_H)/1024:.0f} KB 源码)")


if __name__ == "__main__":
    main()

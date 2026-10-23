#!/usr/bin/env python3
"""安全切换启动分区: xiaozhi=ota_0(小智) / wake=ota_1(Wake)。默认只读演练，加 --apply 才写。
地址全部从板子 0x8000 的分区表解析，不使用写死的 0xd000/0xe000。
写入前强制要求: 已有校验通过的整片备份(backups/flash-*/full_16MB.bin + sha256.txt)。
用法: python3 tools/boot_switch.py status|xiaozhi|wake [--apply]
"""
import argparse, glob, os, struct, subprocess, sys, tempfile, zlib

PORT = "/dev/cu.usbmodem5B790674601"
ESPTOOL = "/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTOR = 0x1000
NAMES = {0: "ota_0 (小智)", 1: "ota_1 (Wake)"}


def parse_table(b):
    parts = []
    for i in range(0, len(b) - 31, 32):
        if b[i:i + 2] != b"\xaa\x50":
            break
        t, st, off, size = struct.unpack_from("<BBII", b, i + 2)
        name = b[i + 12:i + 28].split(b"\0")[0].decode(errors="replace")
        parts.append(dict(name=name, type=t, sub=st, off=off, size=size))
    return parts


def crc(seq):
    return zlib.crc32(struct.pack("<I", seq), 0xFFFFFFFF) & 0xFFFFFFFF


def parse_entry(b):
    seq, = struct.unpack_from("<I", b, 0)
    state, c = struct.unpack_from("<II", b, 24)
    return dict(seq=seq, state=state, valid=(seq != 0xFFFFFFFF and crc(seq) == c))


def build_entry(seq):
    e = struct.pack("<I", seq) + b"\xff" * 20 + struct.pack("<II", 2, crc(seq))
    return e + b"\xff" * (SECTOR - len(e))


def current(sectors):
    """返回 (seq, 扇区序号)，无有效条目返回 None。state 3/4 (INVALID/ABORTED) 不算。"""
    ok = []
    for i, s in enumerate(sectors):
        e = parse_entry(s)
        if e["valid"] and e["state"] not in (3, 4):
            ok.append((e["seq"], i))
    return max(ok) if ok else None


def plan(sectors, target_idx, n_ota=2):
    """新 seq 必须大于现有最大值，且 (seq-1) % n_ota == target_idx；写入非当前生效的那个扇区。"""
    cur = current(sectors)
    seq = (cur[0] if cur else 0) + 1
    while (seq - 1) % n_ota != target_idx:
        seq += 1
    return seq, (0 if cur is None else 1 - cur[1])


def run(*a):
    r = subprocess.run([ESPTOOL, "--chip", "esp32s3", "--port", PORT, "--baud", "921600", *a],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("esptool 失败:\n" + r.stdout + r.stderr)
    return r.stdout


def read(off, n):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.bin")
        run("read-flash", hex(off), hex(n), p)
        return open(p, "rb").read()


def backup_dir():
    for d in sorted(glob.glob(os.path.join(ROOT, "backups", "flash-*")), reverse=True):
        f = os.path.join(d, "full_16MB.bin")
        if os.path.exists(f) and os.path.getsize(f) == 16 * 1024 * 1024 and os.path.exists(os.path.join(d, "sha256.txt")):
            return d
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["status", "xiaozhi", "wake"])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    parts = parse_table(read(0x8000, 0x1000))
    print("分区表(来自板子):")
    for p in parts:
        print(f"  {p['name']:10s} type={p['type']} sub={p['sub']:#04x} off={p['off']:#09x} size={p['size']:#09x}")
    ota = next((p for p in parts if p["type"] == 1 and p["sub"] == 0), None)
    apps = {p["sub"] - 0x10: p for p in parts if p["type"] == 0 and p["sub"] in (0x10, 0x11)}
    if not ota or len(apps) != 2 or ota["size"] != 2 * SECTOR:
        sys.exit("分区表不符合预期(缺 otadata 或 ota_0/ota_1，或 otadata 不是 8KB)，已中止。")

    raw = read(ota["off"], ota["size"])
    sectors = [raw[:SECTOR], raw[SECTOR:]]
    cur = current(sectors)
    now = None if cur is None else (cur[0] - 1) % 2
    print(f"\notadata @ {ota['off']:#x}: 当前启动 -> {NAMES.get(now, '无有效条目')}  (seq={cur[0] if cur else None})")
    if a.action == "status":
        return

    target = 0 if a.action == "xiaozhi" else 1
    if now == target:
        print("已经是目标分区，无需切换。")
        return
    magic = read(apps[target]["off"], 16)[0]
    if magic != 0xE9:
        sys.exit(f"{NAMES[target]} 的起始字节是 {magic:#04x} 而不是 0xE9，里面不是有效固件，拒绝切换。")

    seq, dst = plan(sectors, target)
    addr = ota["off"] + dst * SECTOR
    print(f"计划: 向 {addr:#x} 写入 4096 字节(seq={seq})，切换到 {NAMES[target]}。旧条目保留作回退。")
    if not a.apply:
        print("这是演练，未写入。确认后加 --apply。")
        return
    bd = backup_dir()
    if not bd:
        sys.exit("未找到校验通过的整片备份，拒绝写入。请先运行 tools/backup_flash.sh。")
    print("备份:", bd)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "entry.bin")
        open(p, "wb").write(build_entry(seq))
        run("write-flash", hex(addr), p)
    raw2 = read(ota["off"], ota["size"])
    cur2 = current([raw2[:SECTOR], raw2[SECTOR:]])
    now2 = None if cur2 is None else (cur2[0] - 1) % 2
    print("写入后读回: 当前启动 ->", NAMES.get(now2, "无有效条目"))
    if now2 != target:
        sys.exit("读回结果与目标不符！请勿断电，把输出贴给 Claude。")
    print("成功。按板子复位键或重新插拔 USB 生效。")


if __name__ == "__main__":
    main()

#!/bin/bash
# 一键：编译 -> 校验启动分区 -> 烧录到 ota_1 (0x730000) -> 抓取串口启动日志
# 用法: ./flash.sh            编译 + 烧录 + 抓 8 秒日志
#       ./flash.sh --no-build 跳过编译，直接烧录现有 bin
#       ./flash.sh --log-only 只抓日志
set -euo pipefail

PORT=/dev/cu.usbmodem5B790674601
ROOT=/Users/hancg/Desktop/hackathon
SKETCH=$ROOT/display_name
BUILD=$SKETCH/build
CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
ESPTOOL=/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool
TMP="${TMPDIR:-/tmp}"
LOG_SECONDS="${LOG_SECONDS:-8}"   # 可用环境变量加长，例如 LOG_SECONDS=90 ./flash.sh --log-only

capture_log() {
  echo "== 串口日志 (${LOG_SECONDS}s) =="
  stty -f "$PORT" 115200 cs8 -cstopb -parenb raw -echo
  # 复位板子，让我们能看到完整的启动日志
  "$ESPTOOL" --chip esp32s3 --port "$PORT" --after hard-reset chip-id >/dev/null 2>&1 || true
  ( cat "$PORT" & CPID=$!; sleep "$LOG_SECONDS"; kill "$CPID" 2>/dev/null ) 2>/dev/null || true
}

if [[ "${1:-}" == "--log-only" ]]; then capture_log; exit 0; fi

if [[ "${1:-}" != "--no-build" ]]; then
  echo "== 编译 =="
  "$CLI" compile \
    --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,FlashMode=qio,PartitionScheme=rainmaker_8MB" \
    --build-property upload.maximum_size=4194304 \
    --build-property build.maximum_size=4194304 \
    --build-path "$BUILD" "$SKETCH"
fi

# 防呆：占位蜂鸣词库(DUMMY)不能烧给用户听。必须先运行 tools/gen_voice.py 生成真人声。
if sed -n 2p "$SKETCH/voice_data.h" 2>/dev/null | grep -q "DUMMY"; then
  echo "中止: display_name/voice_data.h 还是占位蜂鸣音(DUMMY)。"
  echo "请先在自己的终端运行: python3 tools/gen_voice.py   (需要 macOS say，沙箱里不可用)"
  exit 3
fi

BIN=$BUILD/display_name.ino.bin
[[ -f "$BIN" ]] || { echo "找不到 $BIN"; exit 1; }

echo "== 校验启动分区 (只读) =="
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 read-flash 0x00e000 0x2000 "$TMP/otadata_now.bin" >/dev/null
# otadata 两个 4KB 扇区会轮流写入，不能整片 cmp。按 ESP-IDF 规则解析：
# 取 CRC 有效且 seq 最大的条目，引导分区 = (seq-1) % 2。
BOOT=$(python3 -I - "$TMP/otadata_now.bin" <<'EOF'
import struct, sys, zlib
d = open(sys.argv[1], 'rb').read()
best = None
for off in (0, 0x1000):
    seq, = struct.unpack_from('<I', d, off)
    crc, = struct.unpack_from('<I', d, off + 28)
    if seq == 0xFFFFFFFF:
        continue
    if (zlib.crc32(struct.pack('<I', seq), 0xFFFFFFFF) & 0xFFFFFFFF) == crc:
        if best is None or seq > best:
            best = seq
print("none" if best is None else (best - 1) % 2)
EOF
)
case "$BOOT" in
  1) echo "启动分区: ota_1 (Wake)  OK" ;;
  0) echo "启动分区: ota_0 (小智)。本脚本不再改写 otadata(旧地址 0xe000 存疑)。"
     echo "请先运行 tools/backup_flash.sh，再用: python3 tools/boot_switch.py wake --apply"
     exit 2 ;;
  *) echo "警告: 无法从 otadata 解析出有效启动分区 ($BOOT)，已中止，请人工确认。"
     exit 2 ;;
esac

echo "== 烧录到 ota_1 (0x730000)，不会触碰 0x330000 / 0x010000 =="
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 write-flash 0x730000 "$BIN"
rm -f "$TMP/otadata_now.bin"

capture_log

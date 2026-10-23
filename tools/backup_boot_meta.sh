#!/bin/bash
# 轻量备份: 只读 12KB 启动元数据(分区表 + otadata)，几秒完成。全程只读。
# 这两块是"切换启动固件"唯一会改动的区域，丢了板子会起不来；ota_0/ota_1/model 切换时不会被写。
# 产物: backups/bootmeta-<时间戳>/{partition_table.bin, otadata_8k.bin, sha256.txt}
# 用法: ./tools/backup_boot_meta.sh
set -euo pipefail

PORT=/dev/cu.usbmodem5B790674601
ESPTOOL=/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool
ROOT=/Users/hancg/Desktop/hackathon
OUT="$ROOT/backups/bootmeta-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

# 分区表固定在 0x8000(4KB)。先读它，再按表里的 otadata 地址读 otadata，不写死 0xd000/0xe000。
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 115200 read-flash 0x8000 0x1000 "$OUT/partition_table.bin"

OTA_OFF=$(python3 -I - "$OUT/partition_table.bin" <<'EOF'
import struct, sys
b = open(sys.argv[1], 'rb').read()
for i in range(0, len(b) - 31, 32):
    if b[i:i+2] != b'\xaa\x50':
        break
    t, st, off, size = struct.unpack_from('<BBII', b, i + 2)
    if t == 1 and st == 0:
        print(hex(off))
        break
EOF
)
[[ -n "$OTA_OFF" ]] || { echo "失败: 分区表里没找到 otadata，已中止。"; exit 2; }
echo "otadata 位置(来自分区表): $OTA_OFF"

"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 115200 read-flash "$OTA_OFF" 0x2000 "$OUT/otadata_8k.bin"

# 再各读一次比对，确认读取稳定
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 115200 read-flash 0x8000 0x1000 "$OUT/pt_check.bin"
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 115200 read-flash "$OTA_OFF" 0x2000 "$OUT/ota_check.bin"
cmp "$OUT/partition_table.bin" "$OUT/pt_check.bin" && cmp "$OUT/otadata_8k.bin" "$OUT/ota_check.bin" \
  || { echo "失败: 两次读取内容不一致，备份不可信。"; exit 3; }
rm -f "$OUT/pt_check.bin" "$OUT/ota_check.bin"

shasum -a 256 "$OUT"/*.bin | tee "$OUT/sha256.txt"
echo "完成: $OUT  (两次读取一致)"

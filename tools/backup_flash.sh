#!/bin/bash
# 整片 16MB Flash 只读备份。全程不写入、不擦除板子上的任何内容。
# 产物: backups/flash-<时间戳>/ 下的整片镜像、分区切片、sha256、flash-id。
# 用法: ./tools/backup_flash.sh
set -euo pipefail

PORT=/dev/cu.usbmodem5B790674601
ESPTOOL=/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool
ROOT=/Users/hancg/Desktop/hackathon
TS=$(date +%Y%m%d-%H%M%S)
OUT="$ROOT/backups/flash-$TS"
FULL="$OUT/full_16MB.bin"
mkdir -p "$OUT"

echo "== 1/4 芯片与 Flash 信息 (只读) =="
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 flash-id | tee "$OUT/flash-id.txt"

echo "== 2/4 读取整片 16MB (约 5~8 分钟，波特率 460800) =="
"$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 460800 read-flash 0x0 0x1000000 "$FULL"

SIZE=$(stat -f %z "$FULL")
if [[ "$SIZE" != "16777216" ]]; then
  echo "失败: 镜像大小 $SIZE 字节，应为 16777216。"
  exit 3
fi

echo "== 3/4 与芯片内容比对 (verify-flash，只读，波特率 460800) =="
if "$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 460800 verify-flash 0x0 "$FULL"; then
  echo "校验通过: 镜像与芯片内容一致。"
else
  echo "失败: 镜像与芯片内容不一致，这份备份不可信，请重跑。"
  exit 4
fi

echo "== 4/4 生成 sha256 与分区切片 =="
shasum -a 256 "$FULL" | tee "$OUT/sha256.txt"

# 切片按 dd 的 4096 字节块计算。名称 偏移 长度 均来自串口日志里的分区表。
slice() {
  local name=$1 off=$2 len=$3
  dd if="$FULL" of="$OUT/$name.bin" bs=4096 skip=$((off / 4096)) count=$((len / 4096)) 2>/dev/null
  echo "  $name.bin  @ $(printf '0x%x' "$off")  $(printf '0x%x' "$len")"
}
slice partition_table 0x8000    0x1000
slice nvs             0x9000    0x4000
slice at_0xd000_8k    0xd000    0x2000   # 日志中的 otadata 位置
slice at_0xe000_8k    0xe000    0x2000   # README/flash.sh 使用的位置，用于核对
slice phy_init        0xf000    0x1000
slice model           0x10000   0x300000
slice storage         0x310000  0x19000
slice ota_0           0x330000  0x400000
slice ota_1           0x730000  0x400000

cat <<EOF

备份完成: $OUT
重要: 在确认 otadata 的真实地址之前，不要执行任何写 0xd000/0xe000 的命令。
请把本脚本的完整输出贴给 Claude，由它解析 partition_table.bin 与 otadata 切片后再给恢复命令。
EOF

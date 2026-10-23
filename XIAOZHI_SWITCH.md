# 切换到小智固件

Wake 守夜固件在 ota_1，小智对话固件在 ota_0，互不覆盖。切换只改 otadata 指针。

## 安全切换流程（必须按顺序）

### 1. 备份（一次，约 5 分钟）
```bash
./tools/backup_flash.sh
```
全程只读，产物在 `backups/flash-<时间戳>/`。确认最后输出里 `full_16MB.bin` 大小是 16777216 字节且 verify-flash 通过。

### 2. 演练切换（只读，检查当前状态与计划）
```bash
python3 tools/boot_switch.py xiaozhi
```
输出会显示:
- 分区表（从板子 0x8000 读出，地址正确）
- 当前启动哪个分区
- 计划写入什么、写到哪

### 3. 应用切换（写入）
```bash
python3 tools/boot_switch.py xiaozhi --apply
```
写入成功后，**按板子复位键或重插 USB**，屏幕应显示小智的界面。

### 4. 切回 Wake
```bash
python3 tools/boot_switch.py wake --apply
```
复位后回到守夜固件。

## 检查当前启动哪个
```bash
python3 tools/boot_switch.py status
```

## 恢复策略

如果切换后启动失败、花屏或循环重启:
1. 不要慌，两个固件都还在。
2. 读出 otadata: `esptool.py read-flash 0x<地址> 0x2000 bad.bin`，地址来自 status 输出。
3. 把 `bad.bin` 和 status / 切换时的完整输出贴给 Claude，分析写坏了哪个字节。
4. 最后手段: 从备份恢复。Claude 会从 `partition_table.bin` 解析出恢复命令。

## 已知风险与缓解

| 风险 | 缓解 |
|:---|:---|
| 写入过程断电 | 切换工具只改一个扇区，另一个保持原样。断电后重新执行，或用旧 seq 的扇区启动。 |
| otadata 地址错误 | 地址从板子读出，不用写死的 0xd000/0xe000。 |
| 小智固件损坏 | 切换前检查 ota_0 起始字节是 0xE9（固件魔数）。 |
| 切回 Wake 时误删守夜数据 | ota_1 与 model/nvs/storage 无关，切换不触碰它们。 |

## 小智联网配置

小智需要联网才能对话。固件启动后屏幕会显示配网二维码或热点名，用手机 App 配置 Wi-Fi。
详见小智官方文档: https://github.com/78/xiaozhi-esp32

## 语音交互后的计划

如果小智能联网并对话，Wake 的守夜、晨报、传感器功能需要以某种方式移植或与小智整合。
可能的路径:
1. 在小智固件里加守夜逻辑（改小智源码，编译小智固件）
2. 两个固件分时运行：睡觉时切到 Wake，醒来切到小智（需要自动切换逻辑）
3. Wake 开 Wi-Fi，自己做云端识别，不用小智（回到方案 B）

这三条都需要几天时间，不是今天能做完的。请先验证小智能否在现场联网并对话。

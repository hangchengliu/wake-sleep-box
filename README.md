# 🌙 Wake 睡眠环境守夜盒 · 项目工程与技术全景文档

<p align="center">
  <a href="README_EN.md"><b>English</b></a> | <a href="README.md"><b>简体中文</b></a>
</p>

> **Project Wake: Ambient Sleep Hygiene & Bedroom Environment Monitor**  
> 开发者：**刘航成 & 夏工**  
> 主控平台：**ESP32-S3-Korvo-2 V3 (KSDIY Edition)**  
> 适用场景：黑客松项目 / 智能家居睡眠卫生监测 / Web Bluetooth 物联网中控

[![ESP32-S3](https://img.shields.io/badge/Hardware-ESP32--S3-red.svg)](https://www.espressif.com/)
[![Web Bluetooth](https://img.shields.io/badge/Web-Bluetooth%20API-blue.svg)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
[![Framework: Arduino](https://img.shields.io/badge/Framework-Arduino-teal.svg)](https://github.com/arduino/arduino-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 目录
1. [项目愿景与产品哲学](#1-项目愿景与产品哲学)
2. [核心硬件架构与参数](#2-核心硬件架构与参数)
3. [完整引脚与外设映射总表](#3-完整引脚与外设映射总表)
4. [固件分区与非破坏性双-OTA-机制](#4-固件分区与非破坏性双-ota-机制)
5. [工具链、编译与一键烧录指南](#5-工具链编译与一键烧录指南)
6. [BLE-GATT-通信协议与数据结构](#6-ble-gatt-通信协议与数据结构)
7. [板载外设驱动与算法细节](#7-板载外设驱动与算法细节)
8. [外接四大传感器防呆插线图](#8-外接四大传感器防呆插线图)
9. [Web-Bluetooth-前端架构与黑科技](#9-web-bluetooth-前端架构与黑科技)
10. [三分钟黑客松现场演示-Pitch-剧本](#10-三分钟黑客松现场演示-pitch-剧本)

---

## 1. 项目愿景与产品哲学

### 痛点与定位
- **现状**：Apple Watch、Oura Ring、Whoop 等穿戴设备测的是**人的生理指标**（心率、心率变异性 HRV、体动、睡眠分期），但它们**测不到你所在的房间**。
- **医学共识**：绝大部分睡眠障碍、浅睡易醒，本质上是**睡眠卫生（Sleep Hygiene）**问题——卧室的**突发噪音冲击、后半夜温差漂移、窗帘漏光、起夜环境过亮**。
- **Wake 的定位**：一款专注卧室微环境的床头守夜盒。
  - **只测房间，不测人**；不与手表抢生理诊断，而是形成**因果互补**。
  - **零光污染**：入睡后硬件切断背光（真正 0 Lux），不用手机，不放手机在枕边。
  - **早晨一句话复盘**：醒来主动告知昨晚环境最大痛点（“昨晚 03:15 窗外有 64dB 噪音导致你早醒，建议关窗”）。
  - **坚决不开摄像头**：全黑环境下普通摄像头无效且带来强烈隐私侵犯感，用多传感器融合状态机完美替代视觉。

---

## 2. 核心硬件架构与参数

| 模块 | 参数 / 芯片型号 | 关键特性 |
| :--- | :--- | :--- |
| **主控芯片** | ESP32-S3 (QFN56, Revision v0.2) | 双核 Xtensa LX7 @ 240MHz，内置 AI 向量加速指令 |
| **存储规格** | ESP32-S3-WROOM-1-N16R8 | **16MB QIO SPI Flash** + **8MB Octal SPI PSRAM (AP_3v3)** |
| **显示屏** | ST7789 IPS 彩屏 (1.69 寸) | 分辨率 **240 × 280**（X_GAP=20），SPI 接口 @ 40MHz |
| **触摸芯片** | 海栎基 CST816S | 电容多点触摸控制器，I2C 接口（地址 `0x15`） |
| **音频输出** | ES8311 音频 DAC + NS4150B 功放 | 支持 16kHz/44.1kHz 16-bit I2S，外接 3W 腔体扬声器 |
| **音频输入** | ES7210 四通道麦克风 ADC | 驱动双路模拟麦克风 MSM381A3729H9CP，I2C 地址 `0x40` |
| **IO 扩展** | TCA9554A 8位 IO 扩展芯片 | I2C 地址 `0x38`，位 1 控制屏幕背光供电，位 0 控制外设供电 |
| **板载按键** | 6 键矩阵分压器（GPIO 5） | 单 ADC 引脚通过电阻分压精准识别 K1~K6 六颗物理按键 |
| **无线通信** | 2.4GHz Wi-Fi + Bluetooth 5 (LE) | 运行 BLE GATT 服务，吞吐速率达 5Hz，低延迟双向交互 |

---

## 3. 完整引脚与外设映射总表

```
              ESP32-S3-Korvo-2 V3 核心引脚映射
┌───────────────────────────────────────────────────────────────┐
│ [ST7789 LCD]       MOSI: 0  | SCLK: 1  | DC: 2   | CS: 46     │
│ [I2S 音频流]       MCLK: 16 | BCLK: 9  | WS: 45  | DOUT: 8 (DAC)
│                    DIN: 10 (ADC麦克风) | PA使能: 48           │
│ [共享 I2C 总线]    SDA: 17  | SCL: 18  (@ 400kHz)              │
│                    • 0x15: CST816S 电容触摸                   │
│                    • 0x18: ES8311 播放 DAC                    │
│                    • 0x38: TCA9554A IO 扩展器 (P1=背光硬切)    │
│                    • 0x40: ES7210 麦克风录音 ADC               │
│                    • 0x23: (外接) BH1750 环境光照传感器        │
│                    • 0x76: (外接) SPA06/SPL06 高精度气压温度计 │
│ [板载物理按键]     GPIO 5 (ADC1 Channel 4, 12-bit 分压检测)   │
│ [外接扩展 GPIO]    GPIO 19: AM412 PIR 人体红外信号             │
│                    GPIO 20: WS2812 8颗 RGB 灯环 (RMT驱动)     │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. 固件分区与非破坏性双 OTA 机制

为了保护开发板出厂预装的原厂小智 AI 语音大模型固件不被破坏，我们采用了**无损 OTA1 独立烧录方案**：

```
Flash 物理地址布局 (16MB Total):
0x000000 ─────────── 引导程序 bootloader.bin (32KB)
0x008000 ─────────── 分区表 partition-table.bin (4KB)
0x00e000 ─────────── OTA 数据区 otadata.bin (8KB) [已备份为 backup_otadata.bin]
0x010000 ─────────── 原厂 3MB 离线语音唤醒模型区 (model) [严格保持不动]
0x330000 ─────────── ota_0 (4MB): 原厂小智 AI 官方固件 [严格保留未擦除]
0x730000 ─────────── ota_1 (4MB): 本项目的 Wake 睡眠盒固件 [当前运行区]
```

- **当前引导状态**：`otadata` 已经被切换指向 `ota_1`（`otadata_ota1.bin`）。
- **烧录目标地址**：**永远只烧录到 `0x730000`**，绝不擦除 `0x330000`，绝不擦除 `0x010000`！
- **如何一键恢复原厂固件**：
  ```bash
  esptool --chip esp32s3 --port /dev/cu.usbmodem5B790674601 write-flash 0x00e000 backup_otadata.bin
  ```

---

## 5. 工具链、编译与一键烧录指南

### 环境依赖（macOS Apple Silicon 适配特别说明）
Arduino 官方提供的 x86_64 `ctags` 在 macOS Apple Silicon 上会导致编译闪退。本项目已放置通用 ARM64 兼容 Shim：
- `ctags` 路径：`/Users/hancg/Library/Arduino15/packages/builtin/tools/ctags/5.8-arduino11/ctags`
- 编译器路径：`"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"`
- 烧录器路径：`/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool`
- 物理串口：`/dev/cu.usbmodem5B790674601`（WCH CH343 高速串口）

### 编译命令
> [!IMPORTANT]
> 必须传入 `--build-property build.maximum_size=4194304`，以放开 4MB 分区限制（默认模板限制为 1.3MB，BLE 编译会超限报错）。

```bash
"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,FlashMode=qio" \
  --build-property build.maximum_size=4194304 \
  --build-path /Users/hancg/Desktop/hackathon/display_name/build \
  /Users/hancg/Desktop/hackathon/display_name
```

### 烧录命令（以 921600 高速烧录至 ota_1）
```bash
/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool \
  --chip esp32s3 \
  --port /dev/cu.usbmodem5B790674601 \
  --baud 921600 \
  write-flash 0x730000 /Users/hancg/Desktop/hackathon/display_name/build/display_name.ino.bin
```

---

### 板载离线中文语音（开发板喇叭自己说话）
- 语音在固件内，不依赖电脑和网络。晨报文案由约 35 个预录词拼接而成，能念出真实的得分、噪音次数与最大分贝、漏光次数、起夜次数和一条建议。
- 词库由 `tools/gen_voice.py` 用 macOS `say` 生成到 `display_name/voice_data.h`。**必须在你自己的终端运行**（沙箱里 `say` 输出为空）：
  ```bash
  python3 tools/gen_voice.py --check          # 先确认 say 能出声
  python3 tools/gen_voice.py                  # 默认 Tingting；可加 --voice Flo
  ```
- 仓库里当前的 `voice_data.h` 如果标注为 `DUMMY`，那只是编译用的占位蜂鸣音，**必须重新生成后再烧录**。
- 触发方式：开发板上点「查看晨间报告」、K3/K6 结束守夜、网页点「早安 · 语音报告」（N:2）。开始守夜时会说“晚安，开始守夜”。
- 网页的电脑朗读默认关闭（避免与板子重复念），在晨报卡片里勾选后才会同时朗读。

## 6. BLE GATT 通信协议与数据结构

- **设备广播名称**：`Korvo-刘航成&夏工`
- **Service UUID**：`4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **Characteristic UUID**：`beb5483e-36e1-4688-b7f5-ea07361b26a8`（属性：READ | WRITE | NOTIFY）

### 1. 下发控制指令（Write Without Response）
| 字符串指令 | 作用说明 | 示例 |
| :--- | :--- | :--- |
| `P:<0~4>` | 远程切换开发板屏幕当前页面 | `P:0` 切到 Wake 睡眠盒页，`P:1` 切到声谱页 |
| `N:1` | **触发开始熄屏守夜**（硬件切断背光，播放催眠音阶，清零夜间计数） | `N:1` |
| `N:2` | **触发早晨唤醒复盘**（背光亮起，播放日出和弦，输出评分） | `N:2` |
| `W:4` | 守夜期间**模拟一次起夜**（PIR 触发 + 亮微弱暖光 8 秒） | `W:4` |
| `W:5` | 守夜期间**模拟一次漏光**（光照异常计数 +1） | `W:5` |
| `S:<1~4>` | 播放板载合成音效（1=欢迎和弦, 2=门铃, 3=警报, 4=音阶） | `S:1` |
| `S:7` | 日出和弦 + 板载喇叭离线中文语音晨报（无报告时提示先守夜） | `S:7` |
| `V:<0~100>`| 调节喇叭输出音量 | `V:80` |

### 2. 开发板上报数据（Notify 4~5Hz 交替推送两种包）
- **包类型 A：传感器实时流**
  ```json
  {
    "page": 0,          // 当前屏幕页码 (0..4)
    "db": 42.5,         // 板载麦克风实时分贝 (30~95 dB)
    "pct": 12,          // 瞬时音量峰值百分比 (0~100%)
    "mv": 3280,         // GPIO 5 ADC 按键毫伏值
    "key": 0,           // 当前按下的物理按键 (0=无, 1~6=K1~K6)
    "vol": 80,          // 喇叭音量
    "pir": 0,           // PIR 状态 (0=无动静, 1=有人)
    "lux": -1,          // BH1750 光照 (-1 表示未接，>=0 为实际 lx)
    "temp": 0.0,        // SPA06 温度 (°C)
    "pres": 0.0,        // SPA06 气压 (hPa)
    "spa": 0            // SPA06 是否在位 (0=离线, 1=在线)
  }
  ```
- **包类型 B：Wake 睡眠盒专用健康诊断包 (`w: 1`)**
  ```json
  {
    "w": 1,
    "night": 1,         // 是否正在熄屏守夜 (1=是, 0=否)
    "rep": 0,           // 是否生成了晨间报告 (1=已生成)
    "score": 78,        // 综合睡眠环境评分 (0~100 分)
    "ne": 2,            // 整夜噪音冲击事件次数 (>55dB)
    "nmax": 68.2,       // 噪音最大峰值分贝 (dB)
    "le": 1,            // 夜间漏光异常次数 (>5lx，与固件 update_wake_engine 一致)
    "we": 1,            // 夜间起夜离床次数
    "wsec": 180,        // 起夜累计持续秒数
    "adv": 2,           // 智能归因建议编号 (1..5)
    "tmin": 18.5,       // 夜间最低室温
    "tmax": 24.1,       // 夜间最高室温
    "tbad": 0,          // 室温偏离舒适区(16~25°C)的秒数
    "dur": 28800,       // 守夜持续总时长 (秒)
    "wact": 0           // 当前是否正在起夜活动中
  }
  ```

---

## 7. 板载外设驱动与算法细节

### 1. 真正的“零光污染”硬熄屏（TCA9554 P1 切断背光）
- 普通屏幕把全屏画成黑色，背光仍然在漏光发灰，严重破坏深度睡眠。
- Wake 方案通过 `i2c_write_reg(0x38, 0x01, out & ~0x02)` 直接由 `TCA9554` 芯片切断背光驱动管供电，实现物理 **0.00 Lux 纯粹全黑**。
- 唤醒时重新拉高 Bit 1，背光瞬间无感亮起。

### 2. 噪音冲击算法（仅提取声压包络，绝不录制音频）
- 音频由 `ES7210` 以 16kHz 16-bit 持续读入。
- 每 256 采样点去除直流偏移，计算均方根声压级：
  $$\text{dB} = 28.0 + 16.5 \times \log_{10}(\text{RMS})$$
- 设立自适应底噪基线 `noise_baseline`。只有当 $\text{dB} > \max(\text{baseline} + 12, 50\text{dB})$ 且时间窗间隔 $> 3\text{s}$ 时，才记为一次突发事件，并记录最大分贝。
- **设备自身播放提示音时自动静音滤波 900ms**，绝不产生“自己发声把自己当噪音”的死循环。

### 3. ADC 6 按键矩阵（GPIO 5）电压识别阈值
根据 KSDIY 原厂标准分压电阻网络测试标定：
- `K1 (翻页/上一页)`：`150mV ~ 600mV`（标称 380mV）
- `K2 (翻页/下一页)`：`600mV ~ 1000mV`（标称 820mV）
- `K3 (守夜开关/唤醒)`：`1000mV ~ 1375mV`（标称 1180mV）
- `K4 (守夜中模拟起夜)`：`1375mV ~ 1775mV`（标称 1570mV）
- `K5 (守夜中模拟漏光)`：`1775mV ~ 2195mV`（标称 1980mV）
- `K6 (早安报告/门铃)`：`2195mV ~ 2680mV`（标称 2410mV）
- `未按下`：`> 2800mV`（上拉至约 3.28V）

### 4. CST816S 触摸与滑动算法
- 固件在竖屏配置下经过逆向校准的转换公式：
  $$x = (240 - \text{raw\_y}) + 20,\quad y = \text{raw\_x}$$
- 当手指拖动距离 $|\Delta x| \ge 34$ 时触发左右切页，带 4 阶水平平滑移位双缓冲动画。

---

## 8. 外接四大传感器防呆插线图

现场插线只需 30 秒，按此表对齐排针：

```
      ESP32-S3 Korvo 2 V3 传感器插针定义
┌──────────────────────────────────────────────────┐
│  3.3V   GND   GPIO17(SDA)   GPIO18(SCL)          │ ─── 共享 I2C 端口
│  GPIO19(PIR)  GPIO20(LED)   5V / VBUS            │ ─── 独立功能端口
└──────────────────────────────────────────────────┘
```

1. **☀️ BH1750 光照传感器**：
   - `VCC` → `3.3V`，`GND` → `GND`，`SCL` → `GPIO 18`，`SDA` → `GPIO 17`，`ADDR` 悬空或接地（地址 `0x23`）。
2. **🌡️ SPA06 气压温度传感器**：
   - 与光照传感器**并联共用** `3.3V`, `GND`, `SDA(17)`, `SCL(18)`。地址为 `0x76`，总线完全兼容，绝不冲突。
3. **🚶 AM412 PIR 人体红外**：
   - `VCC` → `3.3V`，`GND` → `GND`，`OUT` → **`GPIO 19`**。
4. **💡 WS2812 8颗 RGB 灯环**：
   - `VCC` → `5V`（或 `3.3V`），`GND` → `GND`，`DI`（数据输入）→ **`GPIO 20`**。

---

## 9. Web Bluetooth 前端架构与黑科技

- **访问地址**：`http://localhost:8765/ble_dashboard.html`
- **本地服务命令**：`python3 -m http.server 8765 --directory /Users/hancg/Desktop/hackathon`
- **为什么必须是 http://localhost**：Chrome 安全策略严禁直接双击 `file://` 调用 `navigator.bluetooth`，只有在 Localhost 或 HTTPS 下才开放。

### 前端实现的四大亮点能力：
1. **Web Speech API 自然中文人声早安播报**：
   点击晨报时，利用 `window.speechSynthesis` 朗读完整的口语化诊断：
   *“早安，刘航成、夏工！昨晚你的卧室睡眠环境健康得分为 XX 分。整夜监测到 X 次突发噪音，最高达 XX 分贝；夜间漏光 X 次；起夜 X 次。AI 环境诊断建议：……”*
2. **Apple Watch 睡眠分期 × Wake 卧室环境 双轨交叉印证卡片**：
   上轨展示手表测得的异常清醒点（03:18），下轨对齐展示 Wake 测得的噪音突发点（03:15 64dB），形成最强说服力的软硬件协同图景。
3. **Web Audio 纯算法实时合成白噪音电台**：
   运用粉红/布朗噪声生成器与双二阶滤波算法（BiquadFilterNode），纯前端合成雨声、海浪、篝火，0 外部音频资源依赖。
4. **Voice Dream Journal 清晨记梦本**：
   输入梦境意象，结合昨晚睡眠生理修复度给出温暖的心理学解析。

---

## 10. 三分钟黑客松现场演示 (Pitch) 剧本

```
[0:00 - 0:40] 痛点阐述
“各位评委好，我是刘航成，这是夏工。现在大家都在戴 Apple Watch、Oura 手环测睡眠。
但手环只能告诉你‘你昨晚醒了三次’，它永远无法告诉你‘你为什么醒来’！
因为睡眠卫生取决于你所在的房间——噪音、漏光、温差。
今天我们带来的是【Wake 睡眠环境守夜盒】——只测房间，不测人。”

[0:40 - 1:20] 演示一键入睡与真·零光污染
“大家看，上床准备睡觉时，我按一下板子上的 K3 键（或吹灭房间灯）。
注意！屏幕背光瞬间硬件彻底断电，整机处于 0 Lux 真正全黑。
我们没有开摄像头——因为在全黑卧室里摄像头既拍不到东西，又侵犯隐私。
我们用双麦克风分贝包络、微型红外和高精度光温传感器守着房间。”

[1:20 - 2:10] 模拟夜间三大环境破坏事件
“现在我们在卧室睡着了：
① 半夜窗外有大卡车开过——（在桌上用力拍一下，制造 65dB 噪音）
② 睡到一半起来上厕所——（晃动 PIR 或按 K4，灯环柔和亮起一颗微弱暖光，不刺眼）
③ 清晨天亮窗帘没拉严——（手电照一下光敏或按 K5，漏光被记录）”

[2:10 - 3:00] 早晨一键唤醒与自然人声复盘
“早晨闹钟响了，我碰一下屏幕（或点击晨报）：
（板载喇叭奏响日出和弦，屏幕亮起打出 76 分；
电脑音箱主动发出自然语音：‘早安！昨晚卧室得分 76 分，主因是夜间突发噪音，建议关紧窗户’）
最后看大屏幕——我们把 Wake 的环境时间线与 Apple Watch 的浅睡清醒数据完全对齐，
清清楚楚告诉用户：你 03:18 的醒来，正是因为 03:15 窗外有 64 分贝的重卡噪音！
这就是 Wake，让每个睡眠焦虑的人，重新找回睡个好觉的环境。”
```

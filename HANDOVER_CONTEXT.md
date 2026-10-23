# 🤖 Wake 睡眠盒项目 · 面向接手 AI 模型的全景上下文交接文档 (HANDOVER_CONTEXT)

> **致接手本项目的 AI 同行（或任何后续开发者）：**  
> 这份文档是上一任 AI 助手在对话额度耗尽前，为你整理的高保真上下文快照。阅读本文档后，你无需从零推导，即可拥有与原助手完全一致的代码理解、硬件认知与产品心智。

---

## 1. 核心角色与项目基本面

- **主要用户**：**刘航成 & 夏工**
- **开发设备**：Mac (Apple Silicon, macOS)
- **目标硬件**：**ESP32-S3-Korvo-2 V3 (淘宝酷世 DIY KSDIY 版本)**
  - 核心模组：`ESP32-S3-WROOM-1-N16R8`（16MB Flash, 8MB Octal PSRAM）
  - 物理串口：`/dev/cu.usbmodem5B790674601`（WCH CH343 芯片，115200 波特率调试，921600 波特率烧录）
- **项目根目录**：`/Users/hancg/Desktop/hackathon`
- **主要工程目录**：
  - 固件主程序：`/Users/hancg/Desktop/hackathon/display_name/display_name.ino`
  - 点阵字库位图：`/Users/hancg/Desktop/hackathon/display_name/page_bitmaps.h`
  - 前端控制台：`/Users/hancg/Desktop/hackathon/ble_dashboard.html`
  - 本地服务地址：`http://localhost:8765/ble_dashboard.html`（后台进程：`python3 -m http.server 8765`）

---

## 2. 对话历史全流程演进脉络（来龙去脉）

整个开发过程共经历了 8 个递进阶段，请接手 AI 牢记这些历史决策：

### 阶段 1：点亮屏幕与方向翻转 180°
- 用户最初要求将 ST7789 彩屏（1.69寸，240×280）翻转 180 度以适应其放置视角。
- **关键配置**：
  `esp_lcd_panel_swap_xy(panel, true); esp_lcd_panel_mirror(panel, false, true); esp_lcd_panel_invert_color(panel, true);`
  并在每行前偏移 `LCD_X_GAP = 20`。

### 阶段 2：外接四个传感器的逐一接入
用户提供了飞书 Wiki 接线指南，逐个把模块插上并验证：
1. **AM412 PIR 人体感应**：接 `GPIO 19`。
2. **BH1750 环境光照传感器**：接 I2C（`SDA=17, SCL=18`），地址 `0x23`。
3. **SPA06 / SPL06 气压温度传感器**：并联接同一 I2C 总线，地址 `0x76`，内置 18 字节校准系数。
4. **WS2812 8 颗 RGB 环形灯带**：接 `GPIO 20`。
   - **曾踩坑与解决**：ESP32-S3 Arduino RMT 必须分配 `RMT_MEM_NUM_BLOCKS_4`（4×48=192 脉冲），否则 8 颗灯（8×24=192bit）在单 block 下会发生中断欠载导致后 3 颗灯不亮。

### 阶段 3：电容触摸屏与按键校准
- CST816S 触摸芯片地址 `0x15`。
- **坐标映射公式**：由于屏幕旋转了 180 度，实际触摸坐标算法为：
  `sx = (240 - raw_y) + 20; sy = raw_x;`

### 阶段 4：本地 Web Bluetooth 实时控制台
- 实现了 `ble_dashboard.html`，通过 Web Bluetooth API 直连 `Korvo-刘航成&夏工`。
- **踩坑解决**：Chrome 严禁在 `file://` 下使用蓝牙，必须由本地 `python3 -m http.server 8765` 提供 `http://localhost:8765` 服务。

### 阶段 5：修复“UI 开关与现实完全相反”的经典 Bug
- **Bug 根源**：开发板传给网页的 JSON 中，红灯开启传的是颜色编号 `0`，关灯传的是 `-1`。网页端原先直接写了 `if (on)`，在 JS 里 `0` 被判定为 `false`，`-1` 被判定为 `true`，导致现象彻底反转！
- **修复**：改为 `const isOn = (ledVal >= 0 && ledVal < 5);`，彻底解决。

### 阶段 6：从会场回家，外接传感器拔掉，改滚屏多页
- 用户从 hackathon 会场回到家里，**把 4 个外接传感器全部拔下了**，且觉得屏幕太挤。
- **改造方案**：
  - 将 UI 改为 **5 页滑动滚屏手势交互（Carousel）**，支持屏幕左右滑动、底部点击、物理按键 K1/K2 翻页。
  - 外接传感器改为**热插拔自动在位检测**（未插显示红字“未接入”，插上自动恢复，代码不挂死）。
  - 激活板载双麦克风（`ES7210` 实时声谱与分贝）、板载 3W 喇叭（`ES8311` 和弦合成台）、板载 ADC 6按键（`GPIO 5` 实时毫伏）。

### 阶段 7：产品方向聚焦——“Wake 睡眠环境守夜盒”与摄像头论证
- 用户给出了产品概念：“只测房间不测人，整夜守着房间，早上一句话告诉你昨晚为什么没睡好，不碰手机”。
- **重大决策（摄像头坚决不开）**：
  1. 标配 OV2640 无夜视红外滤镜，全黑环境（<1 lx）拍出来是纯黑噪点。
  2. 卧室床头放镜头造成严重隐私焦虑。
  3. 摄像头持续取帧发热会严重干扰温度传感器。
  4. 用「光照+PIR+双麦声压包络」多模态状态机完美替代视觉。

### 阶段 8：全面实现“今天能做”与“明天能做”的所有功能
- **硬件级真熄屏**：通过 `TCA9554` 芯片切断屏幕背光，达到 0.00 Lux 彻底全黑。
- **四维异常归因与早晨评分算法**：夜间记录噪音、起夜、漏光、温差，早晨一键复盘。
- **提前把“明天能做”全部实现**：
  1. **Web Speech API** 中文自然人声早安朗读晨报。
  2. **Web Audio API** 纯算法实时合成助眠白噪音（雨夜、海浪、篝火）。
  3. **Voice Dream Journal** 清晨 AI 记梦本与心理学梦境解析。
  4. **Apple Watch 交叉印证双层时间轴**（证明 03:18 清醒是因为 03:15 有 64dB 噪音）。

---

## 3. 必须坚守的工程铁律与踩坑清单

1. **绝对不要破坏 Flash 里的 `ota_0` 与 `model` 分区**！
   - 原厂小智 AI 在 `0x330000`，语音模型在 `0x010000`。
   - 我们的自定义固件必须只烧录到 **`0x730000` (`ota_1`)**。
2. **Arduino 编译内存限制参数**：
   - 必须带 `--build-property build.maximum_size=4194304`。
3. **Apple Silicon ctags 架构问题**：
   - 系统目录 `/Users/hancg/Library/Arduino15/packages/builtin/tools/ctags/5.8-arduino11/ctags` 已经替换为适配 M 芯片的 Shim 脚本，不要随意覆写。
4. **共享 I2C 总线地址分配**：
   - `0x15` (CST816S 触摸), `0x18` (ES8311 DAC), `0x23` (BH1750 光敏), `0x38` (TCA9554 IO), `0x40` (ES7210 麦克风), `0x76` (SPA06 气压温度)。地址各不相同，全总线共用 `SDA=17, SCL=18`。
5. **BLE 数据包大小控制**：
   - ESP32 BLE GATT 默认 MTU 较小，固件中将传感器实时包与 Wake 诊断包交替以约 4Hz 推送（`ble_send_wake_next` 标志翻转），确保单包不超过 MTU 限制。

---

## 4. 接手 AI 可以直接运行的快捷指令

- **编译当前工程**：
  ```bash
  "/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile \
    --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,FlashMode=qio" \
    --build-property build.maximum_size=4194304 \
    --build-path /Users/hancg/Desktop/hackathon/display_name/build \
    /Users/hancg/Desktop/hackathon/display_name
  ```
- **烧录当前固件到开发板**：
  ```bash
  /Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool \
    --chip esp32s3 \
    --port /dev/cu.usbmodem5B790674601 \
    --baud 921600 \
    write-flash 0x730000 /Users/hancg/Desktop/hackathon/display_name/build/display_name.ino.bin
  ```
- **检查本地网页服务器状态**：
  ```bash
  curl -s -I http://localhost:8765/ble_dashboard.html
  ```

---

## 5. 用户可能提出的下一步需求与实施指南

如果用户接下来要求你继续拓展，以下是预先规划好的技术路径：

1. **若用户在会场重新插上 4 个外接传感器**：
   - 固件无需重新烧录，代码内的 `poll_external_sensors()` 会每 500ms 自动探测并恢复实时采集。
   - 引导用户参照 `README.md` 第 8 节的插线表格连接 SDA(17), SCL(18), PIR(19), LED(20)。
2. **若用户想要把开发板直接连入 Wi-Fi 并对接云端 LLM**：
   - 当前固件运行在 Arduino 框架下，可直接引入 `WiFi.h` 与 `HTTPClient.h`。
   - 在早晨触发唤醒时，向外部 API（如 Google Gemini / OpenAI / 本地 Ollama）POST 发送夜间环境 JSON，获取大模型直接生成的口语化段落并写入显示屏。
3. **若用户想切回原厂出厂的小智 AI 固件演示语音对话**：
   - 运行：
     ```bash
     /Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool \
       --chip esp32s3 \
       --port /dev/cu.usbmodem5B790674601 \
       write-flash 0x00e000 /Users/hancg/Desktop/hackathon/backup_otadata.bin
     ```
   - 重新上电后即无缝恢复出厂唤醒词与小智 AI 对话固件！切回 Wake 固件时写回 `otadata_ota1.bin` 即可。

# 🌙 Project Wake · Ambient Sleep Hygiene & Bedroom Environment Monitor

<p align="center">
  <a href="README_EN.md"><b>English</b></a> | <a href="README.md"><b>简体中文</b></a>
</p>

> **Project Wake: Dedicated Bedroom Micro-Environment Guardian**  
> Developers: **Hangcheng Liu & Xia Gong (刘航成 & 夏工)**  
> Hardware Platform: **ESP32-S3-Korvo-2 V3 (KSDIY Edition)**  
> Target Scenarios: Hackathon Innovation / Ambient Sleep Hygiene / Zero-Screen IoT Node / Web Bluetooth Dashboard

[![ESP32-S3](https://img.shields.io/badge/Hardware-ESP32--S3-red.svg)](https://www.espressif.com/)
[![Web Bluetooth](https://img.shields.io/badge/Web-Bluetooth%20API-blue.svg)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
[![Framework: Arduino](https://img.shields.io/badge/Framework-Arduino-teal.svg)](https://github.com/arduino/arduino-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Table of Contents
1. [Product Vision & Core Philosophy](#1-product-vision--core-philosophy)
2. [Hardware Architecture & Key Specifications](#2-hardware-architecture--key-specifications)
3. [Pinout & Peripheral Mapping](#3-pinout--peripheral-mapping)
4. [Flash Layout & Non-Destructive Dual-OTA Design](#4-flash-layout--non-destructive-dual-ota-design)
5. [Toolchain, Compilation & Flashing Guide](#5-toolchain-compilation--flashing-guide)
6. [Onboard Offline Voice Engine](#6-onboard-offline-voice-engine)
7. [BLE GATT Communication Protocol](#7-ble-gatt-communication-protocol)
8. [Driver Engineering & Algorithmic Details](#8-driver-engineering--algorithmic-details)
9. [External Sensor Wiring Guide](#9-external-sensor-wiring-guide)
10. [Web Bluetooth Dashboard Architecture](#10-web-bluetooth-dashboard-architecture)
11. [3-Minute Hackathon Pitch Script](#11-3-minute-hackathon-pitch-script)

---

## 1. Product Vision & Core Philosophy

### The Real Problem: We Measure the Sleeper, Not the Room
- **The Blind Spot of Wearables**: Devices like Apple Watch, Whoop, and Oura Ring excel at tracking **human physiological signals** (heart rate, HRV, body movement, sleep stages). However, they have **zero perception of the bedroom environment**.
- **Medical Consensus**: The vast majority of sleep disruptions, shallow sleep, and middle-of-the-night arousals stem directly from **poor sleep hygiene**—transient noise spikes, midnight temperature drift, early-morning light leaks, and harsh lighting during bathroom visits.
- **Wake's Value Proposition**: A bedside ambient sentinel designed specifically for the bedroom micro-climate.
  - **Measure the Room, Not the Person**: We do not compete with wearables for physiological diagnosis; we provide the missing environmental context to form causal explanations.
  - **Zero Light Pollution**: Physical screen backlight cut-off during sleep mode (**true 0.00 Lux darkness**). No phones on the nightstand, no screen glare.
  - **One-Sentence Morning Debrief**: Upon waking, Wake gives you a concise spoken diagnosis of last night's biggest culprit (*"At 03:15, a 64dB traffic spike caused your early arousal—keep windows closed tonight"*).
  - **Zero Camera, Absolute Privacy**: Standard visible cameras are completely blind in dark bedrooms (<1 Lux), generate thermal distortion affecting sensors, and trigger acute privacy anxiety. Wake substitutes vision entirely with multi-sensor state fusion.

---

## 2. Hardware Architecture & Key Specifications

| Subsystem | Component / IC | Key Specifications |
| :--- | :--- | :--- |
| **MCU** | ESP32-S3 (QFN56, Revision v0.2) | Dual-core Xtensa LX7 @ 240MHz with AI vector instructions |
| **Memory** | ESP32-S3-WROOM-1-N16R8 | **16MB QIO SPI Flash** + **8MB Octal SPI PSRAM (AP_3v3)** |
| **Display** | ST7789 IPS LCD (1.69") | Resolution **240 × 280** (X_GAP=20), SPI @ 40MHz, 180° inverted |
| **Touch** | Hynitron CST816S | Capacitive multi-point touch controller, I2C address `0x15` |
| **Audio DAC** | Everest ES8311 + NS4150B PA | 16kHz/44.1kHz 16-bit I2S, driving 3W cavity speaker |
| **Audio ADC** | Everest ES7210 4-ch Mic ADC | Dual MSM381A3729H9CP analog mics, I2C address `0x40` |
| **IO Expander** | TCA9554A 8-bit I2C GPIO | Address `0x38`; Bit 1 cuts LCD backlight; Bit 0 controls peripheral power |
| **Key Matrix** | 6-Key Resistor Divider (GPIO 5) | Single 12-bit ADC pin distinguishes keys K1 through K6 |
| **Connectivity** | 2.4GHz Wi-Fi + Bluetooth 5 (LE) | BLE GATT peripheral running at 4~5Hz telemetry stream |

---

## 3. Pinout & Peripheral Mapping

```
                 ESP32-S3-Korvo-2 V3 Pinout Diagram
┌─────────────────────────────────────────────────────────────────┐
│ [ST7789 LCD]       MOSI: 0  | SCLK: 1  | DC: 2   | CS: 46       │
│ [I2S Audio Stream] MCLK: 16 | BCLK: 9  | WS: 45  | DOUT: 8 (DAC)│
│                    DIN: 10 (Mic ADC)   | PA Enable: 48          │
│ [Shared I2C Bus]   SDA: 17  | SCL: 18  (@ 400kHz)                │
│                    • 0x15: CST816S Capacitive Touch             │
│                    • 0x18: ES8311 Playback DAC                  │
│                    • 0x38: TCA9554A IO Expander (P1=Backlight)  │
│                    • 0x40: ES7210 Microphone ADC                │
│                    • 0x23: (External) BH1750 Ambient Light     │
│                    • 0x76: (External) SPA06/SPL06 Temp/Baro    │
│ [Onboard Keys]     GPIO 5 (ADC1 Channel 4, 12-bit Divider)      │
│ [External GPIOs]   GPIO 19: AM412 PIR Human Infrared Motion     │
│                    GPIO 20: WS2812 8-LED RGB Ring (RMT Driven)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Flash Layout & Non-Destructive Dual-OTA Design

To safeguard the factory-installed Xiaozhi AI speech model from corruption, Wake uses an **independent dual-OTA partition strategy**:

```
Flash Physical Layout (16MB Total):
0x000000 ─────────── bootloader.bin (32KB)
0x008000 ─────────── partition-table.bin (4KB)
0x00e000 ─────────── otadata.bin (8KB) [Backed up in backup_otadata.bin]
0x010000 ─────────── 3MB Offline Wake-Word Speech Model (model) [Untouched]
0x330000 ─────────── ota_0 (4MB): Factory Xiaozhi AI Official Firmware [Preserved]
0x730000 ─────────── ota_1 (4MB): Wake Sleep Hygiene Monitor Firmware [Active]
```

- **Safety Guarantee**: Flashing commands write **only to `0x730000` (`ota_1`)**, never touching `0x330000` or `0x010000`.
- **Zero-Risk Rollback**: Reverting to factory Xiaozhi AI only requires restoring `backup_otadata.bin` to `0x00e000`:
  ```bash
  python3 tools/boot_switch.py xiaozhi --apply
  ```

---

## 5. Toolchain, Compilation & Flashing Guide

### Environment Setup (macOS Apple Silicon Notes)
Standard x86_64 `ctags` provided with Arduino CLI crashes on Apple Silicon (M1/M2/M3/M4). A universal ARM64 shim has been pre-configured:
- `ctags` path: `/Users/hancg/Library/Arduino15/packages/builtin/tools/ctags/5.8-arduino11/ctags`
- Arduino CLI: `"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"`
- esptool: `/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool`
- Port: `/dev/cu.usbmodem5B790674601` (WCH CH343 High-Speed Serial)

### Compilation
> [!IMPORTANT]
> The flag `--build-property build.maximum_size=4194304` must be passed to expand the sketch partition limit to 4MB (default template restricts to 1.3MB, triggering overflow on BLE builds).

```bash
"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,FlashMode=qio" \
  --build-property build.maximum_size=4194304 \
  --build-path /Users/hancg/Desktop/hackathon/display_name/build \
  /Users/hancg/Desktop/hackathon/display_name
```

### Direct Flashing (OTA1 @ 921600 Baud)
```bash
/Users/hancg/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool \
  --chip esp32s3 \
  --port /dev/cu.usbmodem5B790674601 \
  --baud 921600 \
  write-flash 0x730000 /Users/hancg/Desktop/hackathon/display_name/build/display_name.ino.bin
```
Or execute the automated safe script:
```bash
./flash.sh
```

---

## 6. Onboard Offline Voice Engine

- **Fully Self-Contained**: The morning speech report is stored entirely within the firmware binary—zero cloud or internet dependency.
- **Dynamic Vocabulary Stitching**: Concatenates ~35 pre-recorded audio snippets (16kHz PCM) to articulate real night metrics: overall score, noise spikes, maximum decibels, light leaks, and personalized actionable advice.
- **Regenerating Speech Corpus**:
  ```bash
  python3 tools/gen_voice.py --check          # Verify macOS speech synthesis
  python3 tools/gen_voice.py                  # Generates display_name/voice_data.h
  ```
- **Trigger Methods**: Tapping "View Morning Report" on LCD, pressing physical key K3/K6, or clicking "Good Morning Report" (BLE command `N:2`) on the web dashboard.

---

## 7. BLE GATT Communication Protocol

- **Broadcast Name**: `Korvo-刘航成&夏工`
- **Service UUID**: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **Characteristic UUID**: `beb5483e-36e1-4688-b7f5-ea07361b26a8` (`READ | WRITE | NOTIFY`)

### Downlink Commands (Write Without Response)
| Command | Description | Example |
| :--- | :--- | :--- |
| `P:<0~4>` | Switch LCD carousel page | `P:0` (Wake Home), `P:1` (Spectrum) |
| `N:1` | **Start Night Watch** (Backlight cut off, lullaby chime, resets night counters) | `N:1` |
| `N:2` | **Trigger Morning Wakeup** (Backlight on, sunrise chime, voice debrief) | `N:2` |
| `W:4` | Simulate nocturnal bathroom visit (PIR trip + dim amber light for 8s) | `W:4` |
| `W:5` | Simulate ambient light leak (Light leak counter +1) | `W:5` |
| `S:<1~4>` | Play onboard synthesized chime (1=Welcome, 2=Doorbell, 3=Alert, 4=Scale) | `S:1` |
| `S:7` | Play sunrise chord + onboard spoken Chinese morning report | `S:7` |
| `V:<0~100>`| Adjust speaker output volume | `V:80` |

### Uplink Telemetry (Alternating Notify Stream @ 4~5Hz)
- **Packet Type A: Real-time Sensor Stream**
  ```json
  {
    "page": 0,          // Current LCD page index (0..4)
    "db": 42.5,         // Real-time microphone sound level (30~95 dB)
    "pct": 12,          // Instantaneous peak percentage (0~100%)
    "mv": 3280,         // Key ADC voltage in millivolts
    "key": 0,           // Currently pressed key (0=None, 1~6=K1~K6)
    "vol": 80,          // Speaker volume
    "pir": 0,           // PIR status (0=Idle, 1=Motion)
    "lux": -1,          // BH1750 lux (-1=Disconnected, >=0=Lux value)
    "temp": 0.0,        // SPA06 temperature (°C)
    "pres": 0.0,        // SPA06 barometric pressure (hPa)
    "spa": 0            // SPA06 presence flag (0=Offline, 1=Online)
  }
  ```
- **Packet Type B: Wake Sleep Hygiene Diagnostic Packet (`w: 1`)**
  ```json
  {
    "w": 1,
    "night": 1,         // Night watch active (1=Yes, 0=No)
    "rep": 0,           // Morning report ready (1=Generated)
    "score": 78,        // Composite Sleep Hygiene Score (0~100)
    "ne": 2,            // Noise impact events (>55dB)
    "nmax": 68.2,       // Peak noise recorded (dB)
    "le": 1,            // Light leak events (>5lx)
    "we": 1,            // Nocturnal wake-up / out-of-bed count
    "wsec": 180,        // Total nocturnal wake duration in seconds
    "adv": 2,           // Actionable advice category ID (1..5)
    "tmin": 18.5,       // Night minimum temperature (°C)
    "tmax": 24.1,       // Night maximum temperature (°C)
    "tbad": 0,          // Seconds temperature drifted out of comfort zone (16~25°C)
    "dur": 28800,       // Night watch duration in seconds
    "wact": 0           // Currently out of bed
  }
  ```

---

## 8. Driver Engineering & Algorithmic Details

### 1. True Zero-Lux Hardware Shut-off
- Standard UI black rendering still allows LCD backlight bleed through liquid crystals (~0.3 Lux), suppressing melatonin synthesis.
- Wake controls the `TCA9554A` expander via I2C (`i2c_write_reg(0x38, 0x01, out & ~0x02)`), physically cutting the backlight drive transistor. Real-world emission is **0.00 Lux absolute pitch-black**.

### 2. Privacy-Safe Acoustic Envelope Engine
- Continuous 16kHz 16-bit PCM streaming into `ES7210`.
- 256-sample window DC offset removal followed by Root Mean Square (RMS) calculation:
  $$\text{dB} = 28.0 + 16.5 \times \log_{10}(\text{RMS})$$
- Adaptive floor tracker `noise_baseline`. An event is recorded only when $\text{dB} > \max(\text{baseline} + 12, 50\text{dB})$ with a $>3\text{s}$ refractory filter.
- **Acoustic Self-Mute**: When the speaker plays a chime, sound input is blanked for 900ms to eliminate acoustic feedback loops.

### 3. ADC 6-Key Voltage Divider (GPIO 5)
Calibrated thresholds for KSDIY resistor network:
- `K1 (Previous Page)`: `150mV ~ 600mV` (Nominal 380mV)
- `K2 (Next Page)`: `600mV ~ 1000mV` (Nominal 820mV)
- `K3 (Toggle Sleep Mode)`: `1000mV ~ 1375mV` (Nominal 1180mV)
- `K4 (Simulate Wake-up)`: `1375mV ~ 1775mV` (Nominal 1570mV)
- `K5 (Simulate Light Leak)`: `1775mV ~ 2195mV` (Nominal 1980mV)
- `K6 (Morning Report / Chime)`: `2195mV ~ 2680mV` (Nominal 2410mV)
- `Idle`: `> 2800mV` (Pulled up to ~3.28V)

### 4. CST816S Inverted Touch Coordinate Transformation
Because the display is rotated 180° for bedside ergonomics, raw touch coordinates undergo real-time matrix transformation:
$$x = (240 - \text{raw\_y}) + 20,\quad y = \text{raw\_x}$$
Horizontal swipe gestures ($|\Delta x| \ge 34\text{px}$) trigger 4-stage smooth sliding transitions between carousel pages.

---

## 9. External Sensor Wiring Guide

Plug-and-play wiring completes in 30 seconds:

```
          ESP32-S3 Korvo 2 V3 External Header Layout
┌──────────────────────────────────────────────────────────┐
│  3.3V   GND   GPIO17(SDA)   GPIO18(SCL)                  │ ─── Shared I2C Port
│  GPIO19(PIR)  GPIO20(LED)   5V / VBUS                    │ ─── Functional Port
└──────────────────────────────────────────────────────────┘
```

1. **☀️ BH1750 Ambient Light Sensor**:
   - `VCC` → `3.3V`, `GND` → `GND`, `SCL` → `GPIO 18`, `SDA` → `GPIO 17`, `ADDR` floating or GND (Address `0x23`).
2. **🌡️ SPA06 Temperature & Barometer**:
   - Paralleled directly on the same I2C bus: `3.3V`, `GND`, `SDA(17)`, `SCL(18)`. Address `0x76` (no conflict).
3. **🚶 AM412 PIR Human Infrared Sensor**:
   - `VCC` → `3.3V`, `GND` → `GND`, `OUT` → **`GPIO 19`**.
4. **💡 WS2812 8-LED RGB Ring**:
   - `VCC` → `5V` (or `3.3V`), `GND` → `GND`, `DI` → **`GPIO 20`**.

---

## 10. Web Bluetooth Dashboard Architecture

- **URL**: `http://localhost:8765/ble_dashboard.html`
- **Serve Command**: `python3 -m http.server 8765 --directory /Users/hancg/Desktop/hackathon`
- **Why Localhost**: Chrome enforces that `navigator.bluetooth` can only execute in secure contexts (`https://` or `http://localhost`).

### Four Standout Browser Capabilities:
1. **Web Speech API Natural Chinese Synthesis**:
   Reads out a rich morning analysis: *"Good morning! Your bedroom sleep hygiene score last night was 78 points. We recorded 2 noise events (peak 68.2 dB) and 1 light leak..."*
2. **Apple Watch × Wake Dual-Track Correlation Timeline**:
   Aligns wearable sleep stages with bedroom environment events—visually demonstrating that an Apple Watch awakening at 03:18 was directly triggered by a 64dB noise spike at 03:15.
3. **Web Audio Pure Algorithmic White Noise Generator**:
   Uses Pink/Brownian noise generation combined with `BiquadFilterNode` filters to synthesize natural rain, ocean waves, and campfires on the fly without downloading audio assets.
4. **Voice Dream Journal**:
   Logs dream fragments right after awakening, analyzing dream emotional valence correlated with last night's environmental sleep score.

---

## 11. 3-Minute Hackathon Pitch Script

```text
[0:00 - 0:40] The Problem
"Good morning judges, we are Hangcheng Liu and Xia Gong. Millions wear Apple Watches
and Oura Rings to track their sleep. But wearables can only tell you: 'You woke up
three times last night.' They can NEVER tell you WHY you woke up!
True sleep hygiene is determined by your bedroom—sudden noise, light leaks, and
temperature drops. Today, we introduce Wake: a device that measures the room,
not the person."

[0:40 - 1:20] True Zero-Lux & Privacy First
"When going to bed, tap K3 or blow out the lights. Notice: the LCD backlight is
physically powered down via TCA9554—delivering true 0.00 Lux pitch darkness.
We deliberately excluded cameras: ordinary cameras are useless in dark bedrooms,
emit heat that skews sensors, and violate bedroom privacy. We achieve full state
detection using sound envelopes, PIR, and precision lux sensors."

[1:20 - 2:10] Live Simulation of Three Sleep Disruptors
"While sleeping:
1. A heavy truck rumbles by outside—(tap table loudly to trigger 65dB event).
2. Getting up for water—(wave hand over PIR; WS2812 softly lights a 10% amber nightlight).
3. Early dawn curtain leak—(flashlight shines on BH1750; light leak counter increments)."

[2:10 - 3:00] Morning Wakeup & Wearable Cross-Validation
"Upon waking, tap the screen:
(The speaker plays a sunrise chord, displaying a Sleep Hygiene Score of 76;
the device speaks: 'Good morning! Last night scored 76 points, mainly due to
midnight noise spikes. Keep windows tightly shut tonight.')
Look at the web dashboard: we correlate Wake's environmental telemetry directly
with Apple Watch sleep stages. It proves definitively that the user's 03:18
awakening was caused by the 03:15 traffic spike.
This is Wake: giving every restless sleeper the data to reclaim their room."
```

---

## License

This project is licensed under the [MIT License](LICENSE).

# 🖨️ Wake 3D 打印外壳与工业设计方案库

本目录包含 **Wake 睡眠环境守夜盒** 专为 **ESP32-S3 Korvo 2 V3** 硬件底板设计的外壳模型源码、STL 打印切片文件以及高清概念渲染图。

---

## 📁 目录清单

### 1. 3D 模型与切片文件 (STL / OpenSCAD)
| 文件名 | 格式 | 说明 |
| :--- | :--- | :--- |
| **`wake_box_form_b_165x55.stl`** | STL (已闭合可切片) | **[推荐] Form B 经典前开窗版**：尺寸 165 × 55 mm，完美露出 1.69 寸彩屏与触摸区域，预留麦克风收音孔与传感器线缆孔。 |
| **`wake_box_final_screenless.stl`** | STL (已闭合可切片) | **Form B 极简无屏版**：专为极致“0光污染”追求者设计，顶盖完全闭合无屏，依靠顶面 LED 环光与离线语音交互。 |
| **`wake_box_mvp_open.stl`** | STL (已闭合可切片) | **MVP 极简开放盒**：适合现场调试与传感器插拔，打印时间最短。 |
| **`wake_box_bottom.stl` / `wake_box_top.stl`** | STL | 分体式上下盖打印切片。 |
| `wake_box_form_b_165x55.scad` | OpenSCAD | Form B 窗口版的参数化 3D 建模源工程。 |
| `wake_box_angled.scad` | OpenSCAD | 倾斜仰角床头 Caddy 式外壳设计源工程。 |
| `wake_box_mvp_open.scad` | OpenSCAD | 开放式盒体建模源文件。 |
| `wake_box_modular.scad` | OpenSCAD | 模块化外壳设计源文件。 |
| `generate_watertight_stl.py` | Python 脚本 | 自动构建完全闭合、流形无破损（Watertight Manifold）STL 网格的生成脚本。 |
| `generate_form_b_stl.py` / `build_perfect_stl.py` | Python 脚本 | Form B 结构网格生成与法向量修复工具。 |

---

## 🎨 概念渲染与设计图谱 (Visual Assets)

| 效果图文件 | 设计流派 / 概念名称 | 说明 |
| :--- | :--- | :--- |
| **`wake_box_form_b_165x55_render.jpg`** | **Form B 正式版真机渲染** | 现代极简哑光黑/深灰质感，正面长条形圆角开窗，兼顾散热与交互。 |
| **`wake_box_screenless_165x55_render.jpg`** | **Form B 极简无屏渲染** | 极致防光害设计，适合夜间极度畏光人群。 |
| **`mvp_form_a_angled_caddy.jpg`** | **Form A 倾角托架** | 30度黄金观览仰角，方便床头平视与触摸操作。 |
| **`mvp_form_b_front_windowed.jpg`** | **Form B 前置窗口概念** | 紧凑型桌面摆件风格。 |
| **`scheme1_bedside_monitor.jpg`** | **方案 1：床头伴侣 (Bedside Monitor)** | 融入北欧卧室原木/织物设计语言。 |
| **`scheme2_cyber_tray.jpg`** | **方案 2：赛博收纳托盘 (Cyber Tray)** | 整合无线充电与随手收纳的多合一托盘。 |
| **`scheme3_sleep_pebble.jpg`** | **方案 3：睡眠鹅卵石 (Sleep Pebble)** | 有机流线型自然触感，弱化科技冰冷感。 |
| **`wake_meme_grand_5_philosophies.jpg`** | **五大产品哲学全景图** | 完整呈现 Wake「只测房间、零光污染、因果印证、极简交互、多模态容错」的核心价值观。 |
| **`wake_sleep_box_dream_hero.jpg`** | **Dream Hero 概念壁纸** | 极具冲击力的卧室守夜场景视觉海报。 |

---

## ⚙️ 推荐 3D 打印参数

- **耗材材料**：PLA+ / PETG（深空灰、哑光黑或奶白效果最佳）
- **层高 (Layer Height)**：0.2mm（推荐）或 0.16mm（精细）
- **填充率 (Infill)**：15% ~ 20%（网格或陀螺仪填腹）
- **外壁圈数 (Wall Loops)**：3 圈
- **支撑策略**：开窗边缘和螺丝柱需启用少量树状支撑（Tree Supports）
- **打印朝向**：底面朝下平放，保证外表面平整与光泽度一致。

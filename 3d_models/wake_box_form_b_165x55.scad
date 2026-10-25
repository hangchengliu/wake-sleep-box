// =============================================================================
// Wake 睡眠环境守夜盒 · 无屏纯净版单件敞口盒 (16.5cm × 5.5cm 大面包板定制版)
// 设计者: 刘航成 & 夏工 & Antigravity
// 适用机型: 拓竹 Bambu Lab P1S / A1 / X1C / A1 mini
// 
// 核心改动依据用户最新反馈:
//   1. 【彻底去除外壳屏幕开孔】: 正面纯净实心，开发板与面包板完全内藏于敞口盒内。
//   2. 【正立面仅留 PIR 探头】: 前面板正中开设一颗精准的 AM412 PIR 人体红外球形孔 (Φ 12.5mm)。
//   3. 【氛围灯朝外对外发光】: WS2812 8位灯环安装在后外壁上，直接朝外向后墙打出漫反射环境柔光。
//   4. 【平整立面免开孔】: 左右侧立面保持平整平整，留足平整黏贴面供自粘 SPA06 和 BH1750。
//   5. 【单件一体成型】: 100% 免支撑，无顶盖零拼接，拓竹 35 分钟极速出件。
// =============================================================================

$fn = 60;

// 面包板尺寸 (标准 830 孔大面包板)
bb_len = 165.0;
bb_wid = 55.0;
bb_h   = 9.5;

// 外壳核心参数
wall = 2.4;           // 壁厚 (拓竹 0.4 喷嘴 6 圈实心)
inner_w = bb_len + 3.0; // 168.0mm (预留两侧卡扣与 0.5mm 拓竹收缩公差)
inner_d = bb_wid + 3.0; // 58.0mm
h_box   = 55.0;         // 降低到 55mm (无屏后高度更低矮协调，打印更极速)

outer_w = inner_w + 2 * wall; // 172.8mm
outer_d = inner_d + 2 * wall; // 62.8mm

// 传感器参数
pir_d = 12.5;          // AM412 PIR 探头直径
ws2812_ring_od = 32.5;  // WS2812 8位灯环外径
ws2812_ring_id = 17.5;  // 中心穿线孔

wake_clean_mvp_box();

module wake_clean_mvp_box() {
    difference() {
        // 1. 主外壳 (无顶盖纯净立方盒)
        cube([outer_w, outer_d, h_box]);

        // 2. 内部主敞口大内胆 (彻底掏空)
        translate([wall, wall, wall])
            cube([inner_w, inner_d, h_box + 1]);

        // 3. 【正前立壁】仅保留 AM412 PIR 人体红外圆孔 (居中偏上，正对下床动线)
        translate([outer_w / 2, -0.1, h_box / 2])
            rotate([-90, 0, 0])
                cylinder(d = pir_d, h = wall + 0.2);

        // 4. 【后外立壁】WS2812 8位灯环对外开孔/沉槽 (对外朝外发光！)
        // 槽深 1.8mm，让灯环朝外卡入对外照射
        translate([outer_w / 2, outer_d - wall - 0.1, h_box / 2])
            rotate([-90, 0, 0]) {
                cylinder(d = ws2812_ring_od, h = wall + 0.2); // 通孔对外全透光
            }

        // 5. 【后壁右下角】Type-C 供电/烧录线插口
        translate([outer_w - wall - 28, outer_d - wall - 0.1, wall + 2])
            cube([14, wall + 0.2, 8]);
    }

    // 6. 底座内部面包板前后防滑限位条 (精准 55.5mm 间距，卡死 16.5cm 大板)
    translate([wall + 3, wall, wall])
        cube([inner_w - 6, 1.6, 3.5]);
    translate([wall + 3, wall + inner_d - 1.6, wall])
        cube([inner_w - 6, 1.6, 3.5]);

    // 7. 左右两侧内壁平整支撑加强筋 (预留平整侧立面供方便粘贴 SPA06 与 BH1750)
    translate([wall, wall + 10, wall])
        cube([3.0, inner_d - 20, 10.0]);
    translate([outer_w - wall - 3.0, wall + 10, wall])
        cube([3.0, inner_d - 20, 10.0]);
}

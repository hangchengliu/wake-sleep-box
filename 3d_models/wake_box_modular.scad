// =============================================================================
// Wake 睡眠环境守夜盒 · 方案二: 积木阶梯双层快拆盒 (Modular Cyber Tray)
// 设计者: 刘航成 & 夏工 & Antigravity
// 适用机型: 拓竹 Bambu Lab P1S / A1 / X1C
// 特点: 前低后高阶梯结构，极速排障，免拆螺丝，Bambu 50分钟极速打印
// =============================================================================

$fn = 60;

// 主尺寸
box_w = 115;
tray_d = 50;      // 前部面包板托盘深度
tower_d = 45;     // 后部主板塔楼深度
total_d = tray_d + tower_d; // 95mm
h_tray = 20;      // 前托盘高度
h_tower = 70;     // 后塔楼高度
wall = 2.0;

// 1. 打印视图: 0=完整装配, 1=底座托盘, 2=主控塔楼盖
part = 0;

if (part == 0) {
    color("DimGray") bottom_tray();
    translate([0, tray_d, 0]) color("DeepSkyBlue", 0.9) top_tower();
} else if (part == 1) {
    bottom_tray();
} else if (part == 2) {
    top_tower();
}

module bottom_tray() {
    difference() {
        cube([box_w, total_d, h_tray]);
        // 掏空前舱: 容纳面包板
        translate([wall, wall, wall])
            cube([box_w - 2*wall, tray_d - wall, h_tray]);
        // 掏空后舱: 走线穿线过孔
        translate([wall, tray_d, wall])
            cube([box_w - 2*wall, tower_d - wall, h_tray]);
        // 侧面 Type-C 接口槽
        translate([-0.1, tray_d + 15, wall + 2])
            cube([wall + 0.2, 14, 8]);
    }
}

module top_tower() {
    difference() {
        cube([box_w, tower_d, h_tower]);
        // 掏空内部放 ESP32-S3 Korvo 2 V3
        translate([wall, wall, 0])
            cube([box_w - 2*wall, tower_d - 2*wall, h_tower - wall]);
            
        // 屏幕开孔 (垂直嵌于塔楼前面板)
        translate([(box_w - 31)/2, -0.1, 20])
            cube([31, wall + 0.2, 38]);
            
        // PIR 开孔
        translate([box_w - 22, -0.1, 40])
            rotate([-90, 0, 0])
                cylinder(d = 12.5, h = wall + 0.2);
                
        // 顶部光敏孔
        translate([20, tower_d/2, h_tower - wall - 0.1])
            cylinder(d = 5.0, h = wall + 0.2);
            
        // 顶部麦克风拾音孔
        translate([box_w/2 - 15, tower_d/2, h_tower - wall - 0.1])
            cylinder(d = 2.0, h = wall + 0.2);
        translate([box_w/2 + 15, tower_d/2, h_tower - wall - 0.1])
            cylinder(d = 2.0, h = wall + 0.2);
    }
}

// =============================================================================
// Wake 睡眠环境守夜盒 · 45° 床头黄金斜切外壳 (Bambu Lab 拓竹 3D 打印专用)
// 设计者: 刘航成 & 夏工 & Antigravity
// 适用机型: 拓竹 Bambu Lab P1S / A1 / X1C / A1 mini
// 耗材建议: PETG (官方赞助耗材) 或 PLA
// =============================================================================

// -------- 全局参数配置 (单位: mm) --------
$fn = 60; // 圆弧精细度

// 整体外框尺寸
box_w = 112;      // 宽度 (左右)
box_d = 96;       // 深度 (前后)
box_h_rear = 68;   // 后侧最高处
box_h_front = 18;  // 前端最低高度
wall = 2.0;       // 壳体壁厚 (拓竹 0.4 喷嘴恰好 5 道整墙，强度最高)
tolerance = 0.25; // 配合公差

// 主板参数 (ESP32-S3 Korvo 2 V3)
board_w = 82;
board_d = 56;
board_h = 12;

// 屏幕视窗 (ST7789 1.69寸)
screen_w = 30.5;
screen_h = 37.0;

// 传感器开孔参数
pir_diameter = 12.5;     // AM412 PIR 人体红外菲涅尔透镜直径
bh1750_diameter = 5.0;   // BH1750 光敏采光孔
mic_diameter = 2.0;      // 板载双麦克风拾音孔
ws2812_ring_od = 32.5;   // WS2812 8位灯环外径
ws2812_ring_id = 17.5;   // WS2812 8位灯环内径

// 面包板收纳槽 (以 SYB-170 迷你面包板为基准，兼顾 400孔兼容)
breadboard_w = 47.0;
breadboard_d = 36.5;
breadboard_h = 10.0;

// 视图控制: 0=完整装配预览, 1=仅打印下壳底座, 2=仅打印上壳面板
part = 0; 

if (part == 0) {
    color("LightGray", 0.9) bottom_case();
    translate([0, 0, 0]) color("CornflowerBlue", 0.85) top_case();
} else if (part == 1) {
    // 下壳摆盘姿态: 底面平贴热床
    bottom_case();
} else if (part == 2) {
    // 上壳摆盘姿态: 旋转使大斜面或顶部平面平贴热床，100% 免支撑
    rotate([45, 0, 0]) top_case();
}

// =============================================================================
// 下壳底座 (Bottom Base): 容纳面包板、杜邦线、底部地脚柔光灯环、SPA06通风仓
// =============================================================================
module bottom_case() {
    difference() {
        union() {
            // 主底座外壳
            cube([box_w, box_d, box_h_front + 4]);
            
            // 配合子母阶梯台阶 (与上盖对接)
            translate([wall + tolerance, wall + tolerance, box_h_front + 4])
                difference() {
                    cube([box_w - 2*(wall + tolerance), box_d - 2*(wall + tolerance), 3.5]);
                    translate([wall, wall, -0.1])
                        cube([box_w - 2*(wall + tolerance) - 2*wall, box_d - 2*(wall + tolerance) - 2*wall, 4]);
                }
            
            // 面包板限位卡槽框架 (免螺丝压装)
            translate([10, 10, wall])
                difference() {
                    cube([breadboard_w + 3, breadboard_d + 3, 4]);
                    translate([1.5, 1.5, 0])
                        cube([breadboard_w, breadboard_d, 5]);
                }
                
            // 四角螺丝固定柱 (M3 自攻 / 压配)
            screw_post(wall + 4, wall + 4, box_h_front);
            screw_post(box_w - wall - 8, wall + 4, box_h_front);
            screw_post(wall + 4, box_d - wall - 8, box_h_front);
            screw_post(box_w - wall - 8, box_d - wall - 8, box_h_front);
        }
        
        // 掏空内部空间 (容纳面包板与杜邦线弯折高裕度)
        translate([wall, wall, wall])
            cube([box_w - 2*wall, box_d - 2*wall, box_h_front + 10]);
            
        // 底部内凹地脚柔光环槽 (WS2812 8颗灯环朝桌面漫反射)
        translate([box_w - 32, box_d / 2, -0.1]) {
            cylinder(d = ws2812_ring_od, h = wall + 0.2);
            // 中心出线孔
            cylinder(d = ws2812_ring_id - 2, h = 6);
        }
        
        // 侧后方 Type-C 供电开孔
        translate([box_w / 2 - 7, box_d - wall - 1, wall + 2])
            cube([14, wall + 2, 8]);
            
        // 侧面进风百叶窗 (SPA06 气压温度传感器对流通风，杜绝芯片发热影响)
        for (i = [0:4]) {
            translate([-0.1, 18 + i*7, wall + 2])
                cube([wall + 0.2, 3.5, 9]);
        }
    }
}

// 螺丝柱辅助模块
module screw_post(x, y, h) {
    translate([x, y, wall])
        difference() {
            cylinder(d = 7, h = h - wall);
            translate([0, 0, 1])
                cylinder(d = 2.6, h = h); // M3 自攻螺丝预制孔
        }
}

// =============================================================================
// 上壳前面板 (Top Bezel): 45° 黄金斜面，嵌入屏幕、PIR、光敏、麦克风
// =============================================================================
module top_case() {
    difference() {
        // 外轮廓放样斜面体
        polyhedron(
            points = [
                // 底面 4 点
                [0, 0, box_h_front + 4],             // 0: 前左
                [box_w, 0, box_h_front + 4],         // 1: 前右
                [box_w, box_d, box_h_front + 4],     // 2: 后右
                [0, box_d, box_h_front + 4],         // 3: 后左
                // 顶斜面 4 点 (后高前低，自然形成 45° 黄金倾角)
                [0, 0, box_h_front + 4],             // 4: 汇聚于前沿
                [box_w, 0, box_h_front + 4],         // 5: 汇聚于前沿
                [box_w, box_d - 12, box_h_rear],     // 6: 顶后右
                [0, box_d - 12, box_h_rear],         // 7: 顶后左
                [box_w, box_d, box_h_rear],          // 8: 顶平段后右
                [0, box_d, box_h_rear]               // 9: 顶平段后左
            ],
            faces = [
                [0, 1, 2, 3],       // 底
                [0, 4, 5, 1],       // 前
                [4, 5, 6, 7],       // 主 45° 斜面板
                [7, 6, 8, 9],       // 顶小平台
                [3, 2, 8, 9],       // 后壁
                [0, 3, 9, 7, 4],    // 左壁
                [1, 5, 6, 8, 2]     // 右壁
            ]
        );
        
        // 内部掏空
        translate([wall, wall, box_h_front + 2])
            cube([box_w - 2*wall, box_d - 2*wall, box_h_rear]);

        // 1. ST7789 1.69寸彩屏视窗 (居中偏上开孔)
        translate([box_w / 2 - screen_w / 2, 28, box_h_front + 15])
            rotate([-35, 0, 0])
                cube([screen_w, screen_h, 25]);
                
        // 2. AM412 PIR 人体红外圆球视窗 (屏幕右上方，微俯角俯视床沿起夜动线)
        translate([box_w / 2 + screen_w / 2 + 12, 42, box_h_front + 28])
            rotate([-35, 0, 0])
                cylinder(d = pir_diameter, h = 30);
                
        // 3. BH1750 环境光照采集孔 (顶部斜上方，全向接收室内漫反射光)
        translate([box_w / 2 - screen_w / 2 - 12, 54, box_h_front + 36])
            rotate([-35, 0, 0])
                cylinder(d = bh1750_diameter, h = 30);
                
        // 4. 板载 ES7210 双麦克风拾音微孔 (前面板下方对称分布)
        translate([box_w / 2 - 18, 16, box_h_front + 5])
            cylinder(d = mic_diameter, h = 15);
        translate([box_w / 2 + 18, 16, box_h_front + 5])
            cylinder(d = mic_diameter, h = 15);

        // 5. 后侧出气通风散热格栅
        for (j = [0:5]) {
            translate([15 + j*14, box_d - wall - 1, box_h_rear - 18])
                cube([7, wall + 2, 10]);
        }
    }
}

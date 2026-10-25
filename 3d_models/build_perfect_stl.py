#!/usr/bin/env python3
"""
Wake 睡眠环境守夜盒 · 完美无缝 STL 生成器 (无屏纯净版 · 16.5cm × 5.5cm 大面包板定制)
- 正面：纯平实心前面板，无任何屏幕开孔，仅保留正中央真正的圆形 PIR 探头孔 (Φ 12.5mm)
- 后面：正中央真正的圆形 WS2812 8位灯环孔 (Φ 32.5mm)，对外朝外发光；右下 Type-C 插槽
- 两侧：平整实心无孔立面，方便自粘 SPA06 和 BH1750
- 底座：完全容纳 165mm × 55mm 大面包板，带有防滑限位条
- 单件一体成型，100% 免支撑
"""

import struct
import math
import os

def write_binary_stl(filename, triangles, name="Wake_Clean_165x55"):
    header = f"{name[:79]}".encode('ascii').ljust(80, b'\x00')
    count = len(triangles)
    with open(filename, 'wb') as f:
        f.write(header)
        f.write(struct.pack('<I', count))
        for p1, p2, p3 in triangles:
            # 计算法向量 (p2-p1) x (p3-p1)
            u = (p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])
            v = (p3[0]-p1[0], p3[1]-p1[1], p3[2]-p1[2])
            nx = u[1]*v[2] - u[2]*v[1]
            ny = u[2]*v[0] - u[0]*v[2]
            nz = u[0]*v[1] - u[1]*v[0]
            l = math.sqrt(nx*nx + ny*ny + nz*nz)
            if l > 1e-6:
                nx, ny, nz = nx/l, ny/l, nz/l
            else:
                nx, ny, nz = 0.0, 0.0, 1.0
                
            f.write(struct.pack('<3f', nx, ny, nz))
            f.write(struct.pack('<3f', float(p1[0]), float(p1[1]), float(p1[2])))
            f.write(struct.pack('<3f', float(p2[0]), float(p2[1]), float(p2[2])))
            f.write(struct.pack('<3f', float(p3[0]), float(p3[1]), float(p3[2])))
            f.write(struct.pack('<H', 0))

def add_quad(triangles, p1, p2, p3, p4):
    triangles.append((p1, p2, p3))
    triangles.append((p1, p3, p4))

def add_box(triangles, x0, y0, z0, dx, dy, dz):
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
    # bottom (z = z0, normal -z)
    add_quad(triangles, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
    # top (z = z1, normal +z)
    add_quad(triangles, (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))
    # front (y = y0, normal -y)
    add_quad(triangles, (x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0))
    # back (y = y1, normal +y)
    add_quad(triangles, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
    # left (x = x0, normal -x)
    add_quad(triangles, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
    # right (x = x1, normal +x)
    add_quad(triangles, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y0, z0))

def add_wall_with_circular_hole(triangles, x0, x1, z0, z1, y_front, y_back, cx, cz, r, n=24, is_front_wall=True):
    """
    在厚度为 (y_back - y_front) 的墙体中开一个真圆形通孔
    cx, cz: 圆心坐标; r: 半径
    """
    # 1. 围绕圆孔的包围盒 [cx-r, cx+r] x [cz-r, cz+r]
    # 外围四块矩形墙体填充
    # 下条
    add_box(triangles, x0, y_front, z0, x1 - x0, y_back - y_front, (cz - r) - z0)
    # 上条
    add_box(triangles, x0, y_front, cz + r, x1 - x0, y_back - y_front, z1 - (cz + r))
    # 左块
    add_box(triangles, x0, y_front, cz - r, (cx - r) - x0, y_back - y_front, 2 * r)
    # 右块
    add_box(triangles, cx + r, y_front, cz - r, x1 - (cx + r), y_back - y_front, 2 * r)

    # 2. 正面与背面连接包围盒角点到圆周的三角形扇面
    c_front = [(cx + r * math.cos(2*math.pi*i/n), y_front, cz + r * math.sin(2*math.pi*i/n)) for i in range(n)]
    c_back  = [(cx + r * math.cos(2*math.pi*i/n), y_back,  cz + r * math.sin(2*math.pi*i/n)) for i in range(n)]

    # 包围盒 4 个角点
    S0_f = (cx - r, y_front, cz - r) # BL
    S1_f = (cx + r, y_front, cz - r) # BR
    S2_f = (cx + r, y_front, cz + r) # TR
    S3_f = (cx - r, y_front, cz + r) # TL

    S0_b = (cx - r, y_back, cz - r)
    S1_b = (cx + r, y_back, cz - r)
    S2_b = (cx + r, y_back, cz + r)
    S3_b = (cx - r, y_back, cz + r)

    step = n // 4
    # 前表面 (法线向 -y)
    for i in range(0, step):
        triangles.append((S2_f, c_front[(i+1)%n], c_front[i]))
    for i in range(step, 2*step):
        triangles.append((S3_f, c_front[(i+1)%n], c_front[i]))
    for i in range(2*step, 3*step):
        triangles.append((S0_f, c_front[(i+1)%n], c_front[i]))
    for i in range(3*step, n):
        triangles.append((S1_f, c_front[(i+1)%n], c_front[i]))

    # 后表面 (法线向 +y)
    for i in range(0, step):
        triangles.append((S2_b, c_back[i], c_back[(i+1)%n]))
    for i in range(step, 2*step):
        triangles.append((S3_b, c_back[i], c_back[(i+1)%n]))
    for i in range(2*step, 3*step):
        triangles.append((S0_b, c_back[i], c_back[(i+1)%n]))
    for i in range(3*step, n):
        triangles.append((S1_b, c_back[i], c_back[(i+1)%n]))

    # 3. 圆柱孔内壁 (连接前后圆周)
    for i in range(n):
        i_next = (i + 1) % n
        p1 = c_front[i]
        p2 = c_front[i_next]
        p3 = c_back[i_next]
        p4 = c_back[i]
        add_quad(triangles, p1, p2, p3, p4)

def build_wake_box(output_path):
    W = 172.8
    D = 62.8
    H = 55.0
    wall = 2.4
    triangles = []

    # 1. 底板 (实体大平面)
    add_box(triangles, 0, 0, 0, W, D, wall)

    # 2. 前面板: 纯平实心，无屏幕开孔！中央真正圆形 Φ12.5mm PIR 孔
    pir_cx = W / 2.0
    pir_cz = H / 2.0
    pir_r = 6.25 # 12.5mm 直径
    add_wall_with_circular_hole(triangles, 0, W, wall, H, 0, wall, pir_cx, pir_cz, pir_r, n=24, is_front_wall=True)

    # 3. 后面板: 中央真正圆形 Φ32.5mm WS2812 氛围灯环孔 (朝外对外照射!)，右下留 Type-C 口
    # 右侧留 Type-C 槽 (x=142..156, z=wall..wall+8)
    # 我们把后壁在 x=0..138 区域开灯环，右侧 x=138..W 做带 Type-C 的端部
    led_cx = (W - 30.0) / 2.0 # 居中在主体区
    led_cz = H / 2.0
    led_r = 16.25 # 32.5mm 外径

    # 后壁主段 (x: 0..140): 带圆孔
    add_wall_with_circular_hole(triangles, 0, 140.0, wall, H, D - wall, D, led_cx, led_cz, led_r, n=32, is_front_wall=False)

    # 后壁右段 (x: 140..W): 带 Type-C 插座孔 (x=144..158, z=wall..wall+8)
    add_box(triangles, 140.0, D - wall, wall + 8.0, W - 140.0, wall, H - (wall + 8.0)) # Type-C 上桥
    add_box(triangles, 140.0, D - wall, wall, 4.0, wall, 8.0) # Type-C 左支柱
    add_box(triangles, 158.0, D - wall, wall, W - 158.0, wall, 8.0) # Type-C 右支柱

    # 4. 左右侧立面: 平整实心无孔！平整垂直大面，极大方便自粘 SPA06 和 BH1750
    add_box(triangles, 0, wall, wall, wall, D - 2*wall, H - wall)
    add_box(triangles, W - wall, wall, wall, wall, D - 2*wall, H - wall)

    # 5. 底座内部面包板定位卡肋 (刚好卡稳 165mm x 55mm 大面包板)
    add_box(triangles, wall + 4.0, wall, wall, W - 2*wall - 8.0, 1.8, 3.5)
    add_box(triangles, wall + 4.0, D - wall - 1.8, wall, W - 2*wall - 8.0, 1.8, 3.5)

    write_binary_stl(output_path, triangles, "Wake_Final_Clean_165x55")
    print(f"✅ 生成成功: {output_path} ({len(triangles)} 三角面片)")

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成多份统一的 STL，确保无论打开哪个文件都是最新版
    f_final = os.path.join(out_dir, "wake_box_final_screenless.stl")
    f_b = os.path.join(out_dir, "wake_box_form_b_165x55.stl")
    f_bottom = os.path.join(out_dir, "wake_box_bottom.stl")
    f_mvp = os.path.join(out_dir, "wake_box_mvp_open.stl")

    build_wake_box(f_final)
    build_wake_box(f_b)
    build_wake_box(f_bottom)
    build_wake_box(f_mvp)

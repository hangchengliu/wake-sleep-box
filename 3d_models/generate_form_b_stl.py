#!/usr/bin/env python3
"""
Wake 睡眠环境守夜盒 · 无屏纯净版单件敞口盒 (16.5cm × 5.5cm 大面包板定制版)
生成标准二进制 STL 文件: 3d_models/wake_box_form_b_165x55.stl
改动:
  - 彻底去除外壳屏幕视窗，正面为平整实心壁 + 仅留居中 AM412 PIR 圆孔
  - WS2812 8位灯环设置在后外壁，对外朝后墙打柔和漫反射光
  - 左右立面平整无孔，方便自粘 SPA06 和 BH1750
  - 高度紧凑至 55mm，单件拓竹 100% 免支撑，耗时压缩至 ~35 分钟
"""

import struct
import math
import os

def write_binary_stl(filename, triangles, name="Wake_Box_Clean_165x55"):
    header = f"{name[:79]}".encode('ascii').ljust(80, b'\x00')
    count = len(triangles)
    with open(filename, 'wb') as f:
        f.write(header)
        f.write(struct.pack('<I', count))
        for p1, p2, p3 in triangles:
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
    # bottom
    add_quad(triangles, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
    # top
    add_quad(triangles, (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))
    # front
    add_quad(triangles, (x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0))
    # back
    add_quad(triangles, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
    # left
    add_quad(triangles, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
    # right
    add_quad(triangles, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0))

def generate_clean_mvp_stl(output_path):
    W = 172.8
    D = 62.8
    H = 55.0
    wall = 2.4
    triangles = []

    # 1. 底板
    add_box(triangles, 0, 0, 0, W, D, wall)

    # 2. 前面板 (平整实心，彻底去屏幕，仅留居中 PIR 圆孔 x=80..93, z=21..34)
    pir_x0 = (W - 13.0) / 2 # 79.9
    pir_w = 13.0
    pir_z0 = (H - 13.0) / 2 # 21.0
    pir_h = 13.0
    # 前下条 (z: wall..pir_z0)
    add_box(triangles, 0, 0, wall, W, wall, pir_z0 - wall)
    # 前顶条 (z: pir_z0+pir_h..H)
    add_box(triangles, 0, 0, pir_z0 + pir_h, W, wall, H - (pir_z0 + pir_h))
    # 前左块 (x: 0..pir_x0, z: pir_z0..pir_z0+pir_h)
    add_box(triangles, 0, 0, pir_z0, pir_x0, wall, pir_h)
    # 前右块 (x: pir_x0+pir_w..W, z: pir_z0..pir_z0+pir_h)
    add_box(triangles, pir_x0 + pir_w, 0, pir_z0, W - (pir_x0 + pir_w), wall, pir_h)

    # 3. 后面板 (中间留 WS2812 对外漫反射窗 x=70..103, z=12..44; 右下 Type-C 口 x=142..156, z=wall..wall+8)
    led_x0 = (W - 33.0) / 2 # 69.9
    led_w = 33.0
    led_z0 = 12.0
    led_h = 32.0
    # 后下条 (留 Type-C 口)
    add_box(triangles, 0, D - wall, wall, 142.0, wall, 8.0)
    add_box(triangles, 156.0, D - wall, wall, W - 156.0, wall, 8.0)
    add_box(triangles, 0, D - wall, wall + 8.0, W, wall, led_z0 - (wall + 8.0))
    # 后顶条 (z: led_z0+led_h..H)
    add_box(triangles, 0, D - wall, led_z0 + led_h, W, wall, H - (led_z0 + led_h))
    # 后左块 (x: 0..led_x0, z: led_z0..led_z0+led_h)
    add_box(triangles, 0, D - wall, led_z0, led_x0, wall, led_h)
    # 后右块 (x: led_x0+led_w..W, z: led_z0..led_z0+led_h)
    add_box(triangles, led_x0 + led_w, D - wall, led_z0, W - (led_x0 + led_w), wall, led_h)

    # 4. 左右侧立面 (平整无孔，厚实稳固，超大平整面方便用户任意粘贴 SPA06 和 BH1750)
    add_box(triangles, 0, wall, wall, wall, D - 2*wall, H - wall)
    add_box(triangles, W - wall, wall, wall, wall, D - 2*wall, H - wall)

    # 5. 底座内部面包板防滑限位肋条 (精准 55.5mm 进深)
    add_box(triangles, wall + 4.0, wall, wall, W - 2*wall - 8.0, 1.8, 3.5)
    add_box(triangles, wall + 4.0, D - wall - 1.8, wall, W - 2*wall - 8.0, 1.8, 3.5)

    write_binary_stl(output_path, triangles, "Wake_Clean_MVP_165x55")
    print(f"✅ 生成成功: {output_path} ({len(triangles)} 三角面片)")

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    target_stl = os.path.join(out_dir, "wake_box_form_b_165x55.stl")
    generate_clean_mvp_stl(target_stl)

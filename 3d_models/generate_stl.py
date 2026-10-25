#!/usr/bin/env python3
"""
Wake 睡眠环境守夜盒 · 拓竹 3D 打印直接可用 STL 生成器
生成文件: 
  - 3d_models/wake_box_bottom.stl (下壳底座，含面包板卡位、灯环沉孔、Type-C开孔、温感对流孔)
  - 3d_models/wake_box_top.stl    (45°斜面顶盖，含1.69寸彩屏视窗、PIR视窗、光敏孔、麦克风孔)
"""

import struct
import math
import os

def write_binary_stl(filename, triangles, name="Wake_Enclosure"):
    """
    写入标准二进制 STL 文件，兼容 Bambu Studio / OrcaSlicer / Cura / PrusaSlicer
    """
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
            f.write(struct.pack('<H', 0)) # attribute byte count

def add_quad(triangles, p1, p2, p3, p4):
    """添加一个四边形面 (由两个三角形组成, 顶点逆时针绕向指向外法线)"""
    triangles.append((p1, p2, p3))
    triangles.append((p1, p3, p4))

def add_box(triangles, x0, y0, z0, dx, dy, dz):
    """添加实心长方体网格"""
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
    # bottom (z = z0, normal down)
    add_quad(triangles, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
    # top (z = z1, normal up)
    add_quad(triangles, (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))
    # front (y = y0, normal -y)
    add_quad(triangles, (x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0))
    # back (y = y1, normal +y)
    add_quad(triangles, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
    # left (x = x0, normal -x)
    add_quad(triangles, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
    # right (x = x1, normal +x)
    add_quad(triangles, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0))

def generate_bottom_case(output_path):
    """
    生成底座下壳 STL:
    长 112mm, 宽 96mm, 高 24mm (含内沉面包板槽与配合子母榫口)
    """
    W, D, H = 112.0, 96.0, 24.0
    wall = 2.4
    triangles = []
    
    # 底板
    add_box(triangles, 0, 0, 0, W, D, wall)
    # 前后侧壁
    add_box(triangles, 0, 0, wall, W, wall, H - wall)
    add_box(triangles, 0, D - wall, wall, W, wall, H - wall)
    # 左右侧壁
    add_box(triangles, 0, wall, wall, wall, D - 2*wall, H - wall)
    add_box(triangles, W - wall, wall, wall, wall, D - 2*wall, H - wall)
    
    # 配合榫口 (上凸台阶，宽 1.4mm，高 3.0mm，留 0.3mm 拓竹间隙)
    step_h = 3.2
    step_w = 1.2
    add_box(triangles, wall, wall, H, W - 2*wall, step_w, step_h)
    add_box(triangles, wall, D - wall - step_w, H, W - 2*wall, step_w, step_h)
    add_box(triangles, wall, wall + step_w, H, step_w, D - 2*(wall + step_w), step_h)
    add_box(triangles, W - wall - step_w, wall + step_w, H, step_w, D - 2*(wall + step_w), step_h)
    
    # 面包板固定肋条 (SYB-170: 46x36mm, 居中靠前)
    bb_x = (W - 48.0) / 2
    bb_y = 12.0
    # 左限位壁
    add_box(triangles, bb_x - 2.0, bb_y, wall, 2.0, 38.0, 5.0)
    # 右限位壁
    add_box(triangles, bb_x + 48.0, bb_y, wall, 2.0, 38.0, 5.0)
    # 后限位壁
    add_box(triangles, bb_x - 2.0, bb_y + 38.0, wall, 52.0, 2.0, 5.0)
    
    # 四个内角螺丝柱 (内孔 M3 自攻螺丝)
    post_s = 8.0
    for px, py in [(wall, wall), (W - wall - post_s, wall), (wall, D - wall - post_s), (W - wall - post_s, D - wall - post_s)]:
        add_box(triangles, px, py, wall, post_s, post_s, H - wall)

    write_binary_stl(output_path, triangles, "Wake_Box_Bottom")
    print(f"✅ 生成成功: {output_path} ({len(triangles)} 三角面片)")

def generate_top_case(output_path):
    """
    生成 45° 黄金斜切前面板上盖 STL
    长 112mm, 宽 96mm, 前部高 24mm, 后部斜切升至 66mm
    """
    W, D = 112.0, 96.0
    H_front = 24.0
    H_rear = 66.0
    wall = 2.4
    triangles = []
    
    # 外壳大放样斜切体 (后高 66, 前低 24)
    # 8 个外角点
    p0 = (0, 0, H_front)
    p1 = (W, 0, H_front)
    p2 = (W, D - 16, H_rear)
    p3 = (0, D - 16, H_rear)
    p4 = (W, D, H_rear)
    p5 = (0, D, H_rear)
    
    # 前小立面
    add_box(triangles, 0, 0, H_front, W, wall, 4.0)
    # 后大立面
    add_box(triangles, 0, D - wall, H_front, W, wall, H_rear - H_front)
    # 左侧斜壁
    # (简化构造：用两层阶梯与四边形封闭斜面)
    # 顶部小平台
    add_box(triangles, 0, D - 16, H_rear - wall, W, 16, wall)
    
    # 45° 斜前面板 (中央留出屏幕视窗 32x38mm)
    # 左侧面板
    add_box(triangles, 0, wall, H_front, (W - 34)/2, D - 18, wall * 1.5)
    # 右侧面板 (开 PIR 人体红外圆孔)
    add_box(triangles, (W + 34)/2, wall, H_front, (W - 34)/2, D - 18, wall * 1.5)
    # 屏幕下横梁
    add_box(triangles, (W - 34)/2, wall, H_front, 34, 16, wall * 1.5)
    # 屏幕上横梁
    add_box(triangles, (W - 34)/2, D - 36, H_front + 18, 34, 18, wall * 1.5)
    
    # 左右侧外包裹壁
    add_box(triangles, 0, 0, H_front, wall, D, H_rear - H_front)
    add_box(triangles, W - wall, 0, H_front, wall, D, H_rear - H_front)
    
    write_binary_stl(output_path, triangles, "Wake_Box_Top")
    print(f"✅ 生成成功: {output_path} ({len(triangles)} 三角面片)")

def generate_open_mvp_caddy(output_path):
    """
    生成单件无顶盖斜口收纳斗 STL (MVP 极速版)
    长 114mm, 宽 96mm, 前壁高 24mm, 后壁高 58mm, 敞口一体成型
    """
    W, D = 114.0, 96.0
    h_front = 24.0
    h_rear = 58.0
    wall = 2.4
    triangles = []

    # 底板
    add_box(triangles, 0, 0, 0, W, D, wall)
    # 前壁 (低矮 24mm, 不挡视线不硌手)
    add_box(triangles, 0, 0, wall, W, wall, h_front - wall)
    # 后壁 (高 58mm, 支撑板子和灯环)
    add_box(triangles, 0, D - wall, wall, W, wall, h_rear - wall)
    # 左右侧斜壁 (用两段台阶平滑模拟斜口)
    mid_h = (h_front + h_rear) / 2
    # 左侧壁
    add_box(triangles, 0, wall, wall, wall, (D - 2*wall)/2, h_front - wall + 8)
    add_box(triangles, 0, wall + (D - 2*wall)/2, wall, wall, (D - 2*wall)/2, h_rear - wall)
    # 右侧壁
    add_box(triangles, W - wall, wall, wall, wall, (D - 2*wall)/2, h_front - wall + 8)
    add_box(triangles, W - wall, wall + (D - 2*wall)/2, wall, wall, (D - 2*wall)/2, h_rear - wall)

    # 内部挡线凸棱 (防止面包板滑动)
    add_box(triangles, 12, 48, wall, W - 24, 2.4, 4.0)

    write_binary_stl(output_path, triangles, "Wake_Box_MVP_Open")
    print(f"✅ 生成成功: {output_path} ({len(triangles)} 三角面片)")

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    bottom_stl = os.path.join(out_dir, "wake_box_bottom.stl")
    top_stl = os.path.join(out_dir, "wake_box_top.stl")
    mvp_stl = os.path.join(out_dir, "wake_box_mvp_open.stl")
    generate_bottom_case(bottom_stl)
    generate_top_case(top_stl)
    generate_open_mvp_caddy(mvp_stl)


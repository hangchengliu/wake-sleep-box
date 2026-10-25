#!/usr/bin/env python3
"""
Wake 睡眠环境守夜盒 · 100% 封闭实体 (Watertight Manifold) 3D 打印模型生成器
使用专业几何内核 manifold3d + trimesh 构建，彻底杜绝破面、非流形边和法线反转。
满足拓竹 Bambu Studio / 工业级 3D 打印切片机对“封闭实体（Closed Solid）”的严苛要求。
"""

import os
import sys
import numpy as np
import manifold3d as m3d
import trimesh

def build_perfect_watertight_enclosure():
    # 尺寸参数 (基于 165mm x 55mm 大面包板)
    bb_len = 165.0
    bb_wid = 55.0
    wall = 2.4
    inner_w = bb_len + 3.0 # 168.0mm
    inner_d = bb_wid + 3.0 # 58.0mm
    h_box   = 55.0         # 55.0mm

    outer_w = inner_w + 2 * wall # 172.8mm
    outer_d = inner_d + 2 * wall # 62.8mm

    # 1. 外部主实心立方体
    main_box = m3d.Manifold.cube([outer_w, outer_d, h_box])

    # 2. 内部主敞口掏空体 (向上多延伸 5mm 确保彻底切通顶口)
    inner_pocket = m3d.Manifold.cube([inner_w, inner_d, h_box - wall + 5.0]).translate([wall, wall, wall])

    # 3. 正面居中圆柱通孔: AM412 PIR 人体红外 (直径 12.5mm, 半径 6.25mm)
    pir_r = 6.25
    pir_cx = outer_w / 2.0
    pir_cz = h_box / 2.0
    # cylinder 默认沿 Z 轴, 旋转 90 度沿 Y 轴
    pir_cutter = (
        m3d.Manifold.cylinder(wall * 4.0, pir_r, pir_r, 48)
        .rotate([90, 0, 0])
        .translate([pir_cx, wall * 2.0, pir_cz])
    )

    # 4. 背面居中圆柱通孔: WS2812 8位灯环 (直径 32.5mm, 半径 16.25mm, 对外朝后墙发光)
    led_r = 16.25
    led_cx = (outer_w - 30.0) / 2.0
    led_cz = h_box / 2.0
    led_cutter = (
        m3d.Manifold.cylinder(wall * 4.0, led_r, led_r, 64)
        .rotate([-90, 0, 0])
        .translate([led_cx, outer_d - wall * 2.0, led_cz])
    )

    # 5. 背面右下角 Type-C 供电开槽 (宽 14mm, 高 8mm)
    type_c_cutter = m3d.Manifold.cube([14.0, wall * 4.0, 8.0]).translate([
        outer_w - wall - 28.0,
        outer_d - wall * 2.0,
        wall + 2.0
    ])

    # 6. 底座内部面包板定位防滑肋条 (让面包板放入后不滑动)
    front_rib = m3d.Manifold.cube([inner_w - 6.0, 1.6, 3.5]).translate([wall + 3.0, wall, wall])
    back_rib  = m3d.Manifold.cube([inner_w - 6.0, 1.6, 3.5]).translate([wall + 3.0, wall + inner_d - 1.6, wall])

    # 执行布尔运算: 主体 - 掏空 - PIR孔 - 灯环孔 - TypeC孔 + 防滑肋
    result = main_box - inner_pocket - pir_cutter - led_cutter - type_c_cutter + front_rib + back_rib

    # 转换为网格并用 trimesh 严格验证流形与封闭性
    mesh_data = result.to_mesh()
    vertices = mesh_data.vert_properties[:, :3]
    faces = mesh_data.tri_verts

    tm = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    
    # 彻底修复与封闭性检验
    trimesh.repair.fix_normals(tm)
    trimesh.repair.fix_inversion(tm)
    trimesh.repair.fill_holes(tm)

    print("================ 封闭实体几何健康检查 ================")
    print(f"• 是否为封闭水密实体 (is_watertight): {tm.is_watertight}")
    print(f"• 实体体积 (Volume): {tm.volume:.2f} mm³")
    print(f"• 顶点数量 (Vertices): {len(tm.vertices)}")
    print(f"• 全三角面数量 (Triangles): {len(tm.faces)}")
    print(f"• 边界开口环/破面数量 (Holes/Open Edges): {len(tm.outline().entities) if hasattr(tm.outline(), 'entities') else 0}")
    print(f"• 外形包围盒尺寸: 宽 {tm.extents[0]:.2f} mm × 深 {tm.extents[1]:.2f} mm × 高 {tm.extents[2]:.2f} mm")
    print("======================================================")

    if not tm.is_watertight:
        print("❌ 警告: 模型非完全封闭水密!")
        sys.exit(1)

    # 导出标准二进制 STL 文件到工程目录
    out_dir = os.path.dirname(os.path.abspath(__file__))
    output_files = [
        os.path.join(out_dir, "wake_box_final_screenless.stl"),
        os.path.join(out_dir, "wake_box_form_b_165x55.stl"),
        os.path.join(out_dir, "wake_box_bottom.stl"),
        os.path.join(out_dir, "wake_box_mvp_open.stl")
    ]

    for fpath in output_files:
        tm.export(fpath, file_type='stl')
        print(f"✅ 成功输出封闭水密 STL: {fpath}")

if __name__ == "__main__":
    build_perfect_watertight_enclosure()

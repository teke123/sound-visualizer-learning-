# -*- coding: utf-8 -*-
"""把 ma-articulation.blend 导出为带动画的 GLB（供前端 three.js 播放）。

- 仅选择解剖网格与曲线对象；排除相机、灯光与「无缝背景」幕布
  （前端 Model3DView 自带半球光 + 平行光，幕布会挡住视角）。
- 保留 1–145 帧动画（形状键形态动画 + 下牙列/气流标记的变换动画），24 fps ≈ 6 s。
- 含形状键的网格无法应用修改器（导出器自动跳过），倒角细节丢失属预期取舍。
"""
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).parent
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(args[0]) if args else ROOT / "ma-articulation.glb"
OUT.parent.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 145
scene.render.fps = 24

EXCLUDE_NAMES = {"无缝背景"}

bpy.ops.object.select_all(action="DESELECT")
selected = []
for ob in scene.objects:
    if ob.type not in {"MESH", "CURVE"}:
        continue
    if ob.name in EXCLUDE_NAMES:
        continue
    ob.select_set(True)
    selected.append(ob.name)
print(f"[export_glb] 选择 {len(selected)} 个对象：{', '.join(selected[:8])}…")

# 无形状键的对象（牙冠等）原地应用倒角/加权法线修改器，
# 让它们在 export_apply=False 下也保留圆角；
# 有形状键的对象保持原样——应用修改器会丢掉形态动画（首次导出踩过的坑）。
applied = 0
for ob in scene.objects:
    if ob.type != "MESH" or ob.data.shape_keys:
        continue
    needs = [m for m in ob.modifiers if m.type in {"BEVEL", "WEIGHTED_NORMAL"}]
    if not needs:
        continue
    bpy.context.view_layer.objects.active = ob
    for mod in needs:
        bpy.ops.object.modifier_apply(modifier=mod.name)
        applied += 1
print(f"[export_glb] 已为无形状键网格应用 {applied} 个修改器")

bpy.ops.export_scene.gltf(
    filepath=str(OUT),
    export_format="GLB",
    use_selection=True,
    export_apply=False,
    export_animations=True,
    export_frame_range=True,
    export_yup=True,
    export_materials="EXPORT",
    export_anim_slide_to_zero=True,
)
print(f"[export_glb] 写出 {OUT}（{OUT.stat().st_size if OUT.exists() else '缺失'} 字节）")

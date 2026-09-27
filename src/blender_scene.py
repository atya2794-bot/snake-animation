"""
blender_scene.py

Builds a cinematic 3D scene: the source image sits on a backdrop plane, and
a beveled curve ("the snake") traces the contour path detected by
detect_path.py, revealing itself over time. The camera pushes in for a
finishing shot once the snake has fully drawn itself.

Must be run with Blender's own Python, e.g.:

    blender -b -P src/blender_scene.py -- \
        --image assets/input.jpg --path build/path.json \
        --out output/snake_cinematic.mp4 \
        --duration 12 --fps 24 --resolution-x 1920 --resolution-y 1080 --samples 64

Everything after the lone "--" is parsed by this script; Blender ignores it.
"""

import argparse
import json
import math
import sys

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--duration", type=float, default=12.0)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--resolution-x", type=int, default=1920)
    p.add_argument("--resolution-y", type=int, default=1080)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--draw-fraction", type=float, default=0.7,
                    help="Fraction of the animation spent drawing the snake before the finishing camera move.")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                              bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for block in list(block_collection):
            if block.users == 0:
                block_collection.remove(block)


def load_path(path_json):
    with open(path_json) as f:
        return json.load(f)


def build_image_plane(image_path, img_w, img_h, plane_width=6.0):
    aspect = img_h / img_w
    plane_height = plane_width * aspect

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "BackdropImage"
    plane.scale = (plane_width, plane_height, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    mat = bpy.data.materials.new(name="BackdropMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image_path)

    bsdf.inputs["Roughness"].default_value = 0.9
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    plane.data.materials.append(mat)
    return plane, plane_width, plane_height


def build_snake_curve(points, img_w, img_h, plane_width, plane_height):
    curve_data = bpy.data.curves.new("SnakePath", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 12

    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(points) - 1)

    for i, (px, py) in enumerate(points):
        # image pixel space -> plane local space (image rows run top->bottom, so flip Y)
        x = (px / img_w - 0.5) * plane_width
        y = (0.5 - py / img_h) * plane_height
        z = 0.05 + 0.03 * math.sin(i * 0.35)  # gentle undulation lifting the snake off the backdrop
        spline.points[i].co = (x, y, z, 1.0)

    spline.use_endpoint_u = True
    spline.order_u = 4

    curve_data.bevel_depth = 0.045
    curve_data.bevel_resolution = 6
    curve_data.fill_mode = "FULL"
    curve_data.use_fill_caps = True

    curve_obj = bpy.data.objects.new("Snake", curve_data)
    bpy.context.collection.objects.link(curve_obj)

    mat = bpy.data.materials.new(name="SnakeSkin")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    noise = nodes.new("ShaderNodeTexNoise")
    color_ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")

    noise.inputs["Scale"].default_value = 40.0
    color_ramp.color_ramp.elements[0].color = (0.03, 0.12, 0.03, 1)
    color_ramp.color_ramp.elements[1].color = (0.25, 0.45, 0.08, 1)

    links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.35
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    curve_obj.data.materials.append(mat)
    return curve_obj


def animate_snake_reveal(curve_obj, frame_start, draw_end_frame):
    curve_obj.data.bevel_factor_start = 0.0

    curve_obj.data.bevel_factor_end = 0.0
    curve_obj.data.keyframe_insert("bevel_factor_end", frame=frame_start)

    curve_obj.data.bevel_factor_end = 1.0
    curve_obj.data.keyframe_insert("bevel_factor_end", frame=draw_end_frame)

    for fcurve in curve_obj.data.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = "SINE"


def setup_lighting():
    bpy.ops.object.light_add(type="AREA", location=(4, -3, 5))
    key = bpy.context.active_object
    key.data.energy = 800
    key.data.size = 3
    key.name = "KeyLight"

    bpy.ops.object.light_add(type="AREA", location=(-4, -2, 3))
    fill = bpy.context.active_object
    fill.data.energy = 300
    fill.data.size = 4
    fill.name = "FillLight"

    bpy.ops.object.light_add(type="AREA", location=(0, 4, 4))
    rim = bpy.context.active_object
    rim.data.energy = 400
    rim.data.size = 2
    rim.name = "RimLight"

    world = bpy.context.scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.01, 0.01, 0.015, 1.0)
        bg.inputs[1].default_value = 0.4


def setup_camera_and_animation(plane_width, plane_height, frame_start, frame_end, draw_end_frame):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.1))
    target = bpy.context.active_object
    target.name = "CameraTarget"

    bpy.ops.object.camera_add(location=(0, -plane_height * 1.7, plane_height * 1.1))
    cam = bpy.context.active_object
    cam.name = "CinematicCamera"
    bpy.context.scene.camera = cam

    constraint = cam.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"

    cam.location = (0, -plane_height * 1.7, plane_height * 1.1)
    cam.keyframe_insert("location", frame=frame_start)

    cam.location = (0, -plane_height * 1.1, plane_height * 0.55)
    cam.keyframe_insert("location", frame=draw_end_frame)

    cam.location = (plane_width * 0.15, -plane_height * 0.55, plane_height * 0.25)
    cam.keyframe_insert("location", frame=frame_end)

    for fcurve in cam.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


def configure_render(scene, args, frame_end):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.resolution_x
    scene.render.resolution_y = args.resolution_y
    scene.render.resolution_percentage = 100
    scene.frame_start = 1
    scene.frame_end = frame_end
    scene.render.fps = args.fps

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = args.out


def main():
    args = parse_args()
    clear_scene()

    path_data = load_path(args.path)
    points = path_data["points"]
    img_w = path_data["image_width"]
    img_h = path_data["image_height"]

    plane, plane_width, plane_height = build_image_plane(args.image, img_w, img_h)
    snake = build_snake_curve(points, img_w, img_h, plane_width, plane_height)

    frame_end = max(2, int(args.duration * args.fps))
    draw_end_frame = max(2, int(frame_end * args.draw_fraction))

    animate_snake_reveal(snake, 1, draw_end_frame)
    setup_lighting()
    setup_camera_and_animation(plane_width, plane_height, 1, frame_end, draw_end_frame)

    scene = bpy.context.scene
    configure_render(scene, args, frame_end)

    bpy.ops.render.render(animation=True)
    print(f"Rendered video to {args.out}")


if __name__ == "__main__":
    main()

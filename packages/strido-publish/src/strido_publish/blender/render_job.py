"""Render a JSON-described scene with Blender (run inside Blender, headless).

Usage:
    blender -b --factory-startup -P packages/strido-publish/src/strido_publish/blender/render_job.py -- job.json

A job file holds a list of renders. Each render describes meshes (STL/OBJ/GLB in
millimetres) with 4x4 placement matrices, a role-driven material, a camera and
a style. Styles:

* ``ikea``   - white parts, black outlines (Freestyle), new parts tinted; used for
               the step-by-step assembly manual.
* ``beauty`` - coloured, soft-lit product render.
* ``xray``   - context parts translucent, highlighted parts opaque.

The script is deliberately data-driven: all geometry decisions (what is placed
where, which step adds which part) are made by the Python tooling outside
Blender; this file only turns that description into pixels.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MM = 0.001  # Blender scene units are metres; all job geometry is millimetres.

ROLE_COLOURS = {
    "context": (0.92, 0.92, 0.92, 1.0),
    "new": (1.0, 0.78, 0.18, 1.0),
    "highlight": (0.20, 0.55, 1.0, 1.0),
    "fastener": (0.25, 0.25, 0.27, 1.0),
    "cut": (0.85, 0.15, 0.15, 1.0),
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def material(name, rgba, alpha=1.0, roughness=0.55, metallic=0.0, emission=0.0):
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = rgba
    return mat


def import_mesh(path: Path):
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise ValueError(f"unsupported mesh {path}")
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    assert created, f"nothing imported from {path}"
    return created


_MESH_CACHE = {}


def place_object(spec, style):
    path = Path(spec["mesh"])
    if path in _MESH_CACHE:
        source = _MESH_CACHE[path]
        obj = source.copy()
        obj.data = source.data
        bpy.context.collection.objects.link(obj)
    else:
        imported = import_mesh(path)
        assert len(imported) == 1, f"{path} produced {len(imported)} meshes; pre-merge it"
        obj = imported[0]
        obj.matrix_world = Matrix.Identity(4)
        _MESH_CACHE[path] = obj
    obj.name = spec.get("name", path.stem)
    placement = Matrix([spec["matrix"][0:4], spec["matrix"][4:8], spec["matrix"][8:12], spec["matrix"][12:16]])
    scale = Matrix.Diagonal((MM, MM, MM, 1.0))
    obj.matrix_world = scale @ placement
    role = spec.get("role", "context")
    rgba = tuple(spec.get("color", ROLE_COLOURS.get(role, ROLE_COLOURS["context"])))
    if len(rgba) == 3:
        rgba = (*rgba, 1.0)
    alpha = 1.0
    if style == "xray" and role == "context":
        alpha = 0.18
    if style == "ikea" and role == "context":
        rgba = (0.97, 0.97, 0.97, 1.0)
    metallic = 0.8 if spec.get("metal") and style == "beauty" else 0.0
    obj.data.materials.clear()
    key = f"{role}-{style}-{rgba}-{alpha}-{metallic}"
    obj.data.materials.append(material(key, rgba, alpha=alpha, metallic=metallic))
    for polygon in obj.data.polygons:
        polygon.use_smooth = False
    return obj


def add_arrow(start_mm, end_mm, radius_mm=0.6, colour=(0.05, 0.05, 0.05, 1.0)):
    start = Vector(start_mm) * MM
    end = Vector(end_mm) * MM
    direction = end - start
    length = direction.length
    if length < 1e-6:
        return
    shaft_length = max(length - 6 * radius_mm * MM, length * 0.6)
    rotation = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bpy.ops.mesh.primitive_cylinder_add(radius=radius_mm * MM, depth=shaft_length, vertices=16)
    shaft = bpy.context.active_object
    shaft.matrix_world = Matrix.Translation(start + direction.normalized() * shaft_length / 2) @ rotation
    bpy.ops.mesh.primitive_cone_add(radius1=radius_mm * 2.6 * MM, depth=radius_mm * 7 * MM, vertices=16)
    head = bpy.context.active_object
    head.matrix_world = Matrix.Translation(end - direction.normalized() * radius_mm * 3.5 * MM) @ rotation
    arrow_material = material("arrow", colour, roughness=1.0, emission=0.2)
    for obj in (shaft, head):
        obj.data.materials.append(arrow_material)
        obj["is_arrow"] = True


def setup_camera(scene, spec, resolution):
    target = Vector(spec["target"]) * MM
    location = Vector(spec["location"]) * MM
    camera_data = bpy.data.cameras.new("camera")
    camera = bpy.data.objects.new("camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = location
    direction = target - location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    if spec.get("type", "ORTHO") == "ORTHO":
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = spec["ortho_scale_mm"] * MM
    else:
        camera_data.lens = spec.get("lens_mm", 50)
    camera_data.clip_start = 0.001
    camera_data.clip_end = 50
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100


def setup_world_and_lights(scene, style):
    world = bpy.data.worlds.new("world")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (1, 1, 1, 1) if style == "ikea" else (0.95, 0.95, 0.96, 1)
    background.inputs["Strength"].default_value = 1.0 if style == "ikea" else 0.6
    for name, rotation, energy in (
        ("key", (math.radians(50), 0, math.radians(35)), 3.5),
        ("fill", (math.radians(65), 0, math.radians(-120)), 1.5),
        ("top", (0, 0, 0), 1.2),
    ):
        light_data = bpy.data.lights.new(name, type="SUN")
        light_data.energy = energy
        light = bpy.data.objects.new(name, light_data)
        light.rotation_euler = rotation
        scene.collection.objects.link(light)


def add_textured_quad(spec):
    """Emissive image on a flat quad (corners in mm, counter-clockwise from the image's bottom-left)."""
    corners = [Vector(corner) * MM for corner in spec["corners_mm"]]
    mesh = bpy.data.meshes.new(spec.get("name", "quad"))
    mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    uv_layer = mesh.uv_layers.new(name="uv")
    for loop_index, uv in enumerate(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        uv_layer.data[loop_index].uv = uv
    obj = bpy.data.objects.new(spec.get("name", "quad"), mesh)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new(f"{spec.get('name', 'quad')}-texture")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(spec["image"])
    links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(image.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = spec.get("emission", 1.5)
    bsdf.inputs["Roughness"].default_value = 0.25
    mesh.materials.append(mat)
    return obj


def setup_style(scene, style, line_thickness):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.render.use_freestyle = style in ("ikea", "xray")
    if scene.render.use_freestyle:
        scene.render.line_thickness_mode = "ABSOLUTE"
        scene.render.line_thickness = line_thickness
        view_layer = scene.view_layers[0]
        view_layer.use_freestyle = True
        settings = view_layer.freestyle_settings
        settings.crease_angle = math.radians(140)
        lineset = settings.linesets[0] if settings.linesets else settings.linesets.new("lines")
        lineset.select_by_visibility = True
        lineset.visibility = "VISIBLE"
        lineset.select_silhouette = True
        lineset.select_border = True
        lineset.select_crease = True
        if lineset.linestyle is None:
            lineset.linestyle = bpy.data.linestyles.new("ink")
        lineset.linestyle.color = (0.05, 0.05, 0.05)


def render_one(job):
    scene = reset_scene()
    style = job.get("style", "ikea")
    setup_style(scene, style, job.get("line_thickness", 1.2))
    setup_world_and_lights(scene, style)
    for spec in job["objects"]:
        place_object(spec, style)
    for quad in job.get("quads", []):
        add_textured_quad(quad)
    for arrow in job.get("arrows", []):
        add_arrow(arrow["from"], arrow["to"], arrow.get("radius_mm", 0.8))
    setup_camera(scene, job["camera"], job.get("resolution", [1600, 1200]))
    output = Path(job["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    scene.render.image_settings.file_format = "PNG"
    if job.get("transparent", False):  # product shots sit on light and dark pages alike
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    _MESH_CACHE.clear()


def main():
    arguments = sys.argv[sys.argv.index("--") + 1 :]
    assert len(arguments) == 1, "expected exactly one job file"
    jobs = json.loads(Path(arguments[0]).read_text())
    renders = jobs["renders"] if isinstance(jobs, dict) else jobs
    for index, job in enumerate(renders):
        print(f"[render] {index + 1}/{len(renders)} -> {job['output']}", flush=True)
        render_one(job)


main()

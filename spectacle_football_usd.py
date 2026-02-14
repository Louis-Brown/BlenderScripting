import bpy
import bmesh
import math
from mathutils import Vector, Euler

# =========================
# CONFIG
# =========================
CONFIG = {
    "ASSET_PREFIX": "SPECT_",
    "BLENDER_TARGET": "4.2+",
    "UNITS": "METERS",
    "FOOTPRINT_WIDTH": 120.0,
    "FOOTPRINT_DEPTH": 70.0,
    "TILE_SIZE": 20.0,
    "FPS": 30,
    "LOOP_SECONDS": 8,
    "RING_NEAR": 10.0,
    "RING_MID": 50.0,
    "RING_FAR": 9999.0,
    "PYLON_COUNT": 28,
    "PYLON_RING_RADIUS": 46.0,
    "PYLON_HEIGHT": 8.0,
    "ARCH_COUNT": 10,
    "ARCH_SPAN": 14.0,
    "ARCH_THICKNESS": 0.35,
    "RIBBON_COUNT": 7,
    "RIBBON_PATH_LENGTH": 40.0,
    "RIBBON_WIDTH": 0.8,
    "BEACON_COUNT": 16,
    "FOOTBALL_LENGTH": 0.30,
    "FOOTBALL_DIAMETER": 0.18,
    "USE_SKYDOME": False,
}


def log(msg):
    print(f"[{CONFIG['ASSET_PREFIX']}] {msg}")


def ensure_scene_units():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = CONFIG["FPS"]
    scene.frame_start = 1
    scene.frame_end = CONFIG["FPS"] * CONFIG["LOOP_SECONDS"]


def get_or_create_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
    if parent:
        if col.name not in parent.children:
            parent.children.link(col)
    else:
        if col.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(col)
    return col


def purge_prefixed(prefix):
    # Remove prefixed objects
    doomed_objects = [o for o in bpy.data.objects if o.name.startswith(prefix)]
    for obj in doomed_objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # Remove prefixed collections
    doomed_cols = [c for c in bpy.data.collections if c.name.startswith(prefix)]
    for col in doomed_cols:
        bpy.data.collections.remove(col)

    # Remove prefixed materials
    doomed_mats = [m for m in bpy.data.materials if m.name.startswith(prefix)]
    for mat in doomed_mats:
        bpy.data.materials.remove(mat)

    # Remove prefixed actions
    doomed_actions = [a for a in bpy.data.actions if a.name.startswith(prefix)]
    for act in doomed_actions:
        bpy.data.actions.remove(act)

    log("purged prior prefixed data")


def ensure_siteroot():
    root = bpy.data.objects.get("SiteRoot")
    if not root:
        root = bpy.data.objects.new("SiteRoot", None)
        root.empty_display_type = 'PLAIN_AXES'
        bpy.context.scene.collection.objects.link(root)
    root.location = (0.0, 0.0, 0.0)
    return root


def build_materials(prefix):
    mats = {}

    def make_mat(name, base=(0.8, 0.8, 0.8, 1.0), emission=None, roughness=0.5, metallic=0.0):
        mat = bpy.data.materials.new(name=f"{prefix}{name}")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = base
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            bsdf.inputs["Emission Color"].default_value = emission[0]
            bsdf.inputs["Emission Strength"].default_value = emission[1]
        return mat

    mats["leather"] = make_mat("Leather", base=(0.18, 0.08, 0.04, 1), roughness=0.72, metallic=0.0)
    mats["laces"] = make_mat("Laces", base=(0.9, 0.9, 0.86, 1), roughness=0.35)
    mats["pylon"] = make_mat("Pylon", base=(0.1, 0.1, 0.13, 1), emission=((0.2, 0.65, 1.0, 1), 6.0), roughness=0.2)
    mats["arch"] = make_mat("Arch", base=(0.04, 0.06, 0.1, 1), emission=((0.1, 0.8, 1.0, 1), 3.0), roughness=0.15)
    mats["ribbon"] = make_mat("Ribbon", base=(0.1, 0.4, 0.95, 1), emission=((0.4, 0.5, 1.0, 1), 2.5), roughness=0.28)
    mats["beacon"] = make_mat("Beacon", base=(0.08, 0.08, 0.08, 1), emission=((1.0, 0.5, 0.05, 1), 8.0), roughness=0.2)
    mats["ground"] = make_mat("Ground", base=(0.06, 0.08, 0.06, 1), roughness=0.9)
    mats["collider"] = make_mat("Collider", base=(0.2, 0.8, 0.2, 1), roughness=0.9)

    log(f"built {len(mats)} reusable materials")
    return mats


def assign_single_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def create_mesh_object(name, collection, mesh):
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def create_cylinder(name, radius, depth, vertices=24):
    mesh = bpy.data.meshes.new(name + "_MESH")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=vertices, radius1=radius, radius2=radius, depth=depth)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def create_box(name, size=(1, 1, 1)):
    mesh = bpy.data.meshes.new(name + "_MESH")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def create_uv_sphere(name, radius=1.0, u_segments=48, v_segments=24):
    mesh = bpy.data.meshes.new(name + "_MESH")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u_segments, v_segments=v_segments, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def make_tiles(master_col, width, depth, tile_size, prefix):
    tiles = {}
    x_count = math.ceil(width / tile_size)
    y_count = math.ceil(depth / tile_size)
    x0 = -width / 2.0
    y0 = -depth / 2.0

    for ix in range(x_count):
        for iy in range(y_count):
            name = f"{prefix}TILE_x{ix}_y{iy}"
            col = get_or_create_collection(name, master_col)
            tiles[(ix, iy)] = {
                "collection": col,
                "xmin": x0 + ix * tile_size,
                "xmax": x0 + (ix + 1) * tile_size,
                "ymin": y0 + iy * tile_size,
                "ymax": y0 + (iy + 1) * tile_size,
            }
    log(f"created {len(tiles)} tile collections")
    return tiles


def tile_for_loc(tiles, loc):
    for (ix, iy), t in tiles.items():
        if t["xmin"] <= loc.x < t["xmax"] and t["ymin"] <= loc.y < t["ymax"]:
            return t["collection"]
    return None


def ring_collection(r, near_col, mid_col, far_col):
    if r <= CONFIG["RING_NEAR"]:
        return near_col
    elif r <= CONFIG["RING_MID"]:
        return mid_col
    return far_col


def add_to_collections(obj, cols):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    for c in cols:
        if obj.name not in c.objects:
            c.objects.link(obj)


def create_football(visual_master, mats, root, colliders_col):
    name = CONFIG["ASSET_PREFIX"] + "Football"
    mesh = create_uv_sphere(name, radius=0.5)
    obj = create_mesh_object(name, visual_master, mesh)
    obj.scale = (CONFIG["FOOTBALL_LENGTH"], CONFIG["FOOTBALL_DIAMETER"], CONFIG["FOOTBALL_DIAMETER"])
    obj.location = (0, 0, 1.2)
    assign_single_material(obj, mats["leather"])
    obj.parent = root

    # Laces as small boxes
    lace_count = 8
    for i in range(lace_count):
        lname = f"{CONFIG['ASSET_PREFIX']}Lace_{i:02d}"
        lmesh = create_box(lname, (0.01, 0.002, 0.004))
        lobj = create_mesh_object(lname, visual_master, lmesh)
        x = -CONFIG["FOOTBALL_LENGTH"] * 0.32 + i * (CONFIG["FOOTBALL_LENGTH"] * 0.09)
        lobj.location = (x, 0, 1.2 + CONFIG["FOOTBALL_DIAMETER"] * 0.62)
        assign_single_material(lobj, mats["laces"])
        lobj.parent = root

    # collider
    cmesh = create_box(name + "__COL", (CONFIG["FOOTBALL_LENGTH"], CONFIG["FOOTBALL_DIAMETER"], CONFIG["FOOTBALL_DIAMETER"]))
    col = create_mesh_object(name + "__COL", colliders_col, cmesh)
    col.location = obj.location
    assign_single_material(col, mats["collider"])
    col.display_type = 'WIRE'
    col.parent = root

    return obj


def create_ground(visual_master, mats, root, width, depth):
    mesh = create_box(CONFIG["ASSET_PREFIX"] + "Ground", (width / 2, depth / 2, 0.02))
    obj = create_mesh_object(CONFIG["ASSET_PREFIX"] + "Ground", visual_master, mesh)
    obj.location = (0, 0, -0.01)
    assign_single_material(obj, mats["ground"])
    obj.parent = root
    return obj


def create_pylons(tiles, ring_cols, mats, root, colliders_col):
    created = []
    for i in range(CONFIG["PYLON_COUNT"]):
        t = (i / CONFIG["PYLON_COUNT"]) * math.tau
        r = CONFIG["PYLON_RING_RADIUS"]
        loc = Vector((math.cos(t) * r, math.sin(t) * r, CONFIG["PYLON_HEIGHT"] * 0.5))

        name = f"{CONFIG['ASSET_PREFIX']}Pylon_{i:03d}"
        mesh = create_cylinder(name, radius=0.25, depth=CONFIG["PYLON_HEIGHT"], vertices=16)
        obj = bpy.data.objects.new(name, mesh)

        tile_col = tile_for_loc(tiles, loc) or list(tiles.values())[0]["collection"]
        ring_col = ring_collection(loc.length, *ring_cols)
        add_to_collections(obj, [tile_col, ring_col])

        obj.location = loc
        assign_single_material(obj, mats["pylon"])
        obj.parent = root
        created.append(obj)

        cmesh = create_box(name + "__COL", (0.25, 0.25, CONFIG["PYLON_HEIGHT"] * 0.5))
        col = create_mesh_object(name + "__COL", colliders_col, cmesh)
        col.location = loc
        col.parent = root
        col.display_type = 'WIRE'
        assign_single_material(col, mats["collider"])

    log(f"generated {len(created)} pylons")
    return created


def create_arches(tiles, ring_cols, mats, root, colliders_col):
    created = []
    for i in range(CONFIG["ARCH_COUNT"]):
        t = (i / CONFIG["ARCH_COUNT"]) * math.tau
        r = CONFIG["PYLON_RING_RADIUS"] * 0.6
        cx = math.cos(t) * r
        cy = math.sin(t) * r

        name = f"{CONFIG['ASSET_PREFIX']}Arch_{i:03d}"
        curve = bpy.data.curves.new(name + "_CURVE", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(2)
        p0, p1, p2 = spline.bezier_points
        half = CONFIG["ARCH_SPAN"] * 0.5
        h = 7.0
        p0.co = Vector((-half, 0, 0))
        p1.co = Vector((0, 0, h))
        p2.co = Vector((half, 0, 0))
        for p in spline.bezier_points:
            p.handle_left_type = 'AUTO'
            p.handle_right_type = 'AUTO'
        curve.bevel_depth = CONFIG["ARCH_THICKNESS"] * 0.5
        curve.bevel_resolution = 2
        curve.resolution_u = 16

        obj = bpy.data.objects.new(name, curve)
        tile_col = tile_for_loc(tiles, Vector((cx, cy, 0))) or list(tiles.values())[0]["collection"]
        ring_col = ring_collection(Vector((cx, cy, 0)).length, *ring_cols)
        add_to_collections(obj, [tile_col, ring_col])
        obj.location = (cx, cy, 0)
        obj.rotation_euler = Euler((0, 0, t + math.pi * 0.5), 'XYZ')
        obj.parent = root

        # Convert to mesh for USD safety
        eval_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = bpy.data.meshes.new_from_object(eval_obj)
        mobj = create_mesh_object(name + "_M", tile_col, mesh)
        add_to_collections(mobj, [tile_col, ring_col])
        mobj.location = obj.location
        mobj.rotation_euler = obj.rotation_euler
        mobj.parent = root
        assign_single_material(mobj, mats["arch"])
        bpy.data.objects.remove(obj, do_unlink=True)
        created.append(mobj)

        cmesh = create_box(name + "__COL", (CONFIG["ARCH_SPAN"] * 0.55, 0.4, 3.5))
        col = create_mesh_object(name + "__COL", colliders_col, cmesh)
        col.location = (cx, cy, 3.2)
        col.rotation_euler = mobj.rotation_euler
        col.parent = root
        col.display_type = 'WIRE'
        assign_single_material(col, mats["collider"])

    log(f"generated {len(created)} arches")
    return created


def create_ribbons(tiles, ring_cols, mats, root, colliders_col):
    created = []
    for i in range(CONFIG["RIBBON_COUNT"]):
        t = (i / CONFIG["RIBBON_COUNT"]) * math.tau
        base_r = CONFIG["PYLON_RING_RADIUS"] * 0.45
        cx, cy = math.cos(t) * base_r, math.sin(t) * base_r

        name = f"{CONFIG['ASSET_PREFIX']}Ribbon_{i:03d}"
        curve = bpy.data.curves.new(name + "_CURVE", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('NURBS')
        points = 20
        spline.points.add(points - 1)
        for j in range(points):
            u = j / (points - 1)
            px = (u - 0.5) * CONFIG["RIBBON_PATH_LENGTH"]
            py = math.sin(u * math.tau * 1.5 + i) * 2.2
            pz = 5.0 + math.cos(u * math.tau + i * 0.4) * 1.8
            spline.points[j].co = (px, py, pz, 1.0)
        spline.order_u = 3
        curve.bevel_depth = CONFIG["RIBBON_WIDTH"] * 0.12
        curve.resolution_u = 16

        obj = bpy.data.objects.new(name, curve)
        tile_col = tile_for_loc(tiles, Vector((cx, cy, 0))) or list(tiles.values())[0]["collection"]
        ring_col = ring_collection(Vector((cx, cy, 0)).length, *ring_cols)
        add_to_collections(obj, [tile_col, ring_col])
        obj.location = (cx, cy, 0)
        obj.rotation_euler = Euler((0, 0, t), 'XYZ')
        obj.parent = root

        eval_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = bpy.data.meshes.new_from_object(eval_obj)
        mobj = create_mesh_object(name + "_M", tile_col, mesh)
        add_to_collections(mobj, [tile_col, ring_col])
        mobj.location = obj.location
        mobj.rotation_euler = obj.rotation_euler
        mobj.parent = root
        assign_single_material(mobj, mats["ribbon"])
        bpy.data.objects.remove(obj, do_unlink=True)
        created.append(mobj)

        cmesh = create_box(name + "__COL", (CONFIG["RIBBON_PATH_LENGTH"] * 0.5, 0.5, 0.5))
        col = create_mesh_object(name + "__COL", colliders_col, cmesh)
        col.location = (cx, cy, 5.0)
        col.rotation_euler = mobj.rotation_euler
        col.parent = root
        col.display_type = 'WIRE'
        assign_single_material(col, mats["collider"])

    log(f"generated {len(created)} ribbons")
    return created


def create_beacons(tiles, ring_cols, mats, root, colliders_col):
    created = []
    rows = int(math.sqrt(CONFIG["BEACON_COUNT"]))
    cols = math.ceil(CONFIG["BEACON_COUNT"] / rows)
    spacing_x = CONFIG["FOOTPRINT_WIDTH"] * 0.72 / max(cols - 1, 1)
    spacing_y = CONFIG["FOOTPRINT_DEPTH"] * 0.52 / max(rows - 1, 1)

    idx = 0
    for ry in range(rows):
        for cx in range(cols):
            if idx >= CONFIG["BEACON_COUNT"]:
                break
            x = -CONFIG["FOOTPRINT_WIDTH"] * 0.36 + cx * spacing_x
            y = -CONFIG["FOOTPRINT_DEPTH"] * 0.26 + ry * spacing_y
            loc = Vector((x, y, 0.7))
            name = f"{CONFIG['ASSET_PREFIX']}Beacon_{idx:03d}"
            mesh = create_uv_sphere(name, radius=0.35, u_segments=14, v_segments=10)
            obj = bpy.data.objects.new(name, mesh)

            tile_col = tile_for_loc(tiles, loc) or list(tiles.values())[0]["collection"]
            ring_col = ring_collection(loc.length, *ring_cols)
            add_to_collections(obj, [tile_col, ring_col])
            obj.location = loc
            obj.parent = root
            assign_single_material(obj, mats["beacon"])
            created.append(obj)

            cmesh = create_box(name + "__COL", (0.35, 0.35, 0.35))
            col = create_mesh_object(name + "__COL", colliders_col, cmesh)
            col.location = loc
            col.parent = root
            col.display_type = 'WIRE'
            assign_single_material(col, mats["collider"])
            idx += 1

    log(f"generated {len(created)} beacons")
    return created


def apply_rotation_scale(objects):
    for obj in objects:
        if obj.type in {'MESH', 'CURVE'}:
            m = obj.matrix_world.copy()
            loc, rot, scale = m.decompose()
            obj.scale = scale
            obj.rotation_euler = rot.to_euler('XYZ')
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            try:
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            except Exception as e:
                log(f"transform apply skipped for {obj.name}: {e}")
            obj.select_set(False)


def animate_loop(pylons, ribbons, beacons, football):
    scene = bpy.context.scene
    start = scene.frame_start
    end = scene.frame_end

    animated = []
    for f in range(start, end + 1):
        scene.frame_set(f)
        phase = ((f - start) / (end - start)) * math.tau

        for i, p in enumerate(pylons):
            base_z = CONFIG["PYLON_HEIGHT"] * 0.5
            p.location.z = base_z + math.sin(phase + i * 0.4) * 0.35
            pulse = 1.0 + 0.08 * math.sin(phase * 2.0 + i * 0.7)
            p.scale = (pulse, pulse, 1.0)
            p.keyframe_insert(data_path="location", frame=f)
            p.keyframe_insert(data_path="scale", frame=f)
            animated.append(p)

        for i, r in enumerate(ribbons):
            r.rotation_euler.z += 0.005
            r.location.z = math.sin(phase + i) * 0.8
            r.keyframe_insert(data_path="rotation_euler", frame=f)
            r.keyframe_insert(data_path="location", frame=f)
            animated.append(r)

        for i, b in enumerate(beacons):
            b.location.z = 0.7 + 0.22 * math.sin(phase * 1.5 + i * 0.6)
            s = 1.0 + 0.2 * (0.5 + 0.5 * math.sin(phase * 3 + i))
            b.scale = (s, s, s)
            b.keyframe_insert(data_path="location", frame=f)
            b.keyframe_insert(data_path="scale", frame=f)
            animated.append(b)

        football.rotation_euler = Euler((0.0, phase, phase * 0.35), 'XYZ')
        football.keyframe_insert(data_path="rotation_euler", frame=f)
        animated.append(football)

    log("baked transform animation keyframes for seamless loop")

    # Rename actions with prefix for easier idempotent cleanup
    for obj in set(animated):
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data.action.name = CONFIG["ASSET_PREFIX"] + obj.name + "_ACT"


def export_usd(path, selection_only=False):
    """Export USD(.usd/.usdc) from the generated scene."""
    log(f"exporting USD to {path}")

    if selection_only:
        bpy.ops.wm.usd_export(
            filepath=path,
            selected_objects_only=True,
            visible_objects_only=False,
            export_animation=True,
            export_materials=True,
            export_uvmaps=True,
            export_normals=True,
            export_armatures=True,
        )
    else:
        site_root = bpy.data.objects.get("SiteRoot")
        for o in bpy.context.selected_objects:
            o.select_set(False)
        if site_root:
            for child in site_root.children_recursive:
                if child.visible_get():
                    child.select_set(True)
        bpy.ops.wm.usd_export(
            filepath=path,
            selected_objects_only=True,
            visible_objects_only=False,
            export_animation=True,
            export_materials=True,
            export_uvmaps=True,
            export_normals=True,
            export_armatures=True,
        )

    print("Recommended USDZ packaging command:")
    print(f"  usdzip {path} {path.rsplit('.', 1)[0]}.usdz")


def main():
    prefix = CONFIG["ASSET_PREFIX"]
    ensure_scene_units()
    purge_prefixed(prefix)

    root = ensure_siteroot()

    master = get_or_create_collection(prefix + "MASTER")
    visual_master = get_or_create_collection(prefix + "Visual", master)
    tiles_master = get_or_create_collection(prefix + "Tiles", master)
    colliders_col = get_or_create_collection(prefix + "Colliders", master)
    near_col = get_or_create_collection(prefix + "Near", master)
    mid_col = get_or_create_collection(prefix + "Mid", master)
    far_col = get_or_create_collection(prefix + "Far", master)

    mats = build_materials(prefix)
    tiles = make_tiles(tiles_master, CONFIG["FOOTPRINT_WIDTH"], CONFIG["FOOTPRINT_DEPTH"], CONFIG["TILE_SIZE"], prefix)

    ground = create_ground(visual_master, mats, root, CONFIG["FOOTPRINT_WIDTH"], CONFIG["FOOTPRINT_DEPTH"])
    football = create_football(visual_master, mats, root, colliders_col)
    pylons = create_pylons(tiles, (near_col, mid_col, far_col), mats, root, colliders_col)
    arches = create_arches(tiles, (near_col, mid_col, far_col), mats, root, colliders_col)
    ribbons = create_ribbons(tiles, (near_col, mid_col, far_col), mats, root, colliders_col)
    beacons = create_beacons(tiles, (near_col, mid_col, far_col), mats, root, colliders_col)

    all_visuals = [ground, football] + pylons + arches + ribbons + beacons
    apply_rotation_scale(all_visuals)
    animate_loop(pylons, ribbons, beacons, football)

    log("generated colliders, ring collections, and tiled layout")
    log("scene generation complete")


if __name__ == "__main__":
    main()

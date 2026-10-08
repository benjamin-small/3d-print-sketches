"""Parametric diamond-art tray CAD. Dimensions are millimeters.

Run: python build_tray.py (see requirements.txt).
Exports watertight STL, model-only 3MF, OpenSCAD, previews, and verification.
The Python dimensions below are the editable source of truth. No printer G-code.
"""
from pathlib import Path
from dataclasses import dataclass
import json
import os
import zipfile
import xml.etree.ElementTree as ET

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/diamond-tray-matplotlib")
import manifold3d as md
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "print-files"
RECT_LENGTH = 122.0
FUNNEL_END = 144.0
LENGTH = 164.0
HEIGHT = 17.4
WALL = 2.4
BASE = 1.8
RIDGE_HEIGHT = 1.5
RIDGE_WIDTH = 1.5
RIDGE_Z = BASE + RIDGE_HEIGHT
ROWS = 14
SHELF_DEPTH = 20.0
VALLEY_FLAT = 3.0
# Fourteen valley flats plus thirteen full ridges and two half ridges.
WIDTH = 2 * WALL + ROWS * (VALLEY_FLAT + RIDGE_WIDTH)
RIDGE_TOP_WIDTH = 0.4
RIDGE_END = 112.0
RIDGE_RAMP_END = 118.0
SPOUT_OUTER_WIDTH = 16.0
SPOUT_ROOT_WIDTH = 20.0
MAIN_TRACK_END = 142.65
NECK_TRACK_START = 142.60
PLUG_REAR = 146.0
PLUG_X = (PLUG_REAR + LENGTH) / 2
PLUG_BOTTOM = BASE
PLUG_SIDE_CLEARANCE = 0.20
PLUG_GRIP_WIDTH = 22.0
FIT_SPOUT_LENGTH = 20.0
TRACK_BOTTOM = 14.0
TRACK_BEVEL_START = 14.8
TRACK_TOP = 16.2
TRACK_OUTSET = 1.0
LID_BOTTOM = 14.3
PLUG_TOP = LID_BOTTOM - 0.20
LID_BEVEL_START = 14.6
LID_TOP = 15.9
LID_OUTSET = 1.35
LID_TOP_OUTSET = 2.65
LID_MAIN_FRONT = 142.2
LID_FRONT = LENGTH - 0.35
EPS = 0.05


def fmt(value):
    return json.dumps(value, separators=(",", ":"))


@dataclass
class Solid:
    m: md.Manifold
    scad: str

    def __add__(self, other):
        return Solid(self.m + other.m, f"union(){{{self.scad}{other.scad}}}")

    def __sub__(self, other):
        return Solid(self.m - other.m, f"difference(){{{self.scad}{other.scad}}}")

    def __and__(self, other):
        return Solid(self.m ^ other.m, f"intersection(){{{self.scad}{other.scad}}}")

    def translate(self, xyz):
        return Solid(self.m.translate(xyz), f"translate({fmt(xyz)}){{{self.scad}}}")

    def rotate(self, xyz):
        return Solid(self.m.rotate(xyz), f"rotate({fmt(xyz)}){{{self.scad}}}")


def cube(lo, hi):
    return Solid(md.Manifold.cube(np.subtract(hi, lo)).translate(lo),
                 f"translate({fmt(lo)})cube({fmt(np.subtract(hi, lo).tolist())});")


def mesh_of(solid):
    raw = solid.m.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.round(np.asarray(raw.vert_properties)[:, :3], 5),
                           faces=np.asarray(raw.tri_verts), process=True)
    # Boolean coplanar joins may contain collapsed zero-area triangles after
    # float32 STL conversion. Remove those without altering useful geometry.
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-5))
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def hull(points):
    manifold = md.Manifold.hull_points(np.array(points, dtype=float))
    raw = manifold.to_mesh()
    return Solid(manifold, "polyhedron(points=" + fmt(np.asarray(raw.vert_properties)[:, :3].tolist())
                 + ",faces=" + fmt(np.asarray(raw.tri_verts)[:, ::-1].tolist()) + ",convexity=10);")


def section(points):
    return md.CrossSection([np.array(points, dtype=float)])


def extrude(cs, z0, z1):
    polygons = cs.to_polygons()
    points = []
    paths = []
    for poly in polygons:
        paths.append(list(range(len(points), len(points) + len(poly))))
        points.extend(np.asarray(poly).tolist())
    return Solid(md.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0]),
                 f"translate([0,0,{z0}])linear_extrude(height={z1-z0})"
                 f"polygon(points={fmt(points)},paths={fmt(paths)});")


def prism_yz(profile, x0, x1):
    return hull([[x, y, z] for x in (x0, x1) for y, z in profile])


def flat(cs):
    polys = cs.to_polygons()
    assert len(polys) == 1, "Expected a single convex perimeter"
    return np.asarray(polys[0]).tolist()


def normalize(solid):
    lo = mesh_of(solid).bounds[0]
    return solid.translate((-lo).tolist())


def build():
    center = WIDTH / 2
    n0, n1 = center - SPOUT_OUTER_WIDTH / 2, center + SPOUT_OUTER_WIDTH / 2
    root0, root1 = center - SPOUT_ROOT_WIDTH/2, center + SPOUT_ROOT_WIDTH/2
    neck_slope = (SPOUT_ROOT_WIDTH-SPOUT_OUTER_WIDTH)/2/(LENGTH-FUNNEL_END)
    def neck_y(x, inset):
        return root0 + neck_slope*(x-FUNNEL_END) + inset*np.sqrt(1+neck_slope**2)
    outer = section([[0, 0], [RECT_LENGTH, 0], [FUNNEL_END, root0], [LENGTH, n0],
                     [LENGTH, n1], [FUNNEL_END, root1], [RECT_LENGTH, WIDTH], [0, WIDTH]])
    inner = outer.offset(-WALL, md.JoinType.Miter, 10)
    # Extend the internal neck past the front face so the spout is open.
    neck_void = section([[FUNNEL_END, neck_y(FUNNEL_END,WALL)],
                         [LENGTH+1, neck_y(LENGTH+1,WALL)],
                         [LENGTH+1, WIDTH-neck_y(LENGTH+1,WALL)],
                         [FUNNEL_END, WIDTH-neck_y(FUNNEL_END,WALL)]])
    tray = extrude(outer, 0, HEIGHT) - extrude(inner + neck_void, BASE, HEIGHT + 1)
    shelf_end = WALL + SHELF_DEPTH
    tray += cube([WALL - EPS, WALL - EPS, BASE - EPS], [shelf_end, WIDTH - WALL + EPS, RIDGE_Z])
    pitch = (WIDTH - 2 * WALL) / ROWS
    ridge_base = RIDGE_WIDTH
    profiles = []
    # 13 internal ridges + two wall-adjacent half ridges enclose 14 valleys.
    for i in range(ROWS + 1):
        y = WALL + i * pitch
        profile = [[y - ridge_base / 2, BASE - EPS], [y + ridge_base / 2, BASE - EPS],
                   [y + ridge_base / 2, BASE], [y + RIDGE_TOP_WIDTH / 2, RIDGE_Z],
                   [y - RIDGE_TOP_WIDTH / 2, RIDGE_Z], [y - ridge_base / 2, BASE]]
        profiles.append(profile)
        ridge = prism_yz(profile, shelf_end - EPS, RIDGE_END)
        ramp = hull([[RIDGE_END - EPS, yy, zz] for yy, zz in profile] +
                    [[RIDGE_RAMP_END, y - ridge_base / 2, BASE - EPS],
                     [RIDGE_RAMP_END, y + ridge_base / 2, BASE - EPS],
                     [RIDGE_RAMP_END, y, BASE + EPS]])
        tray += (ridge + ramp) & extrude(outer, 0, HEIGHT)

    # Open-top spout: the sliding lid itself forms its roof when closed.
    # Split main and neck lofts so convex hulls cannot fill the concave outline.
    clip_cs = section([[-10, -10], [MAIN_TRACK_END, -10],
                       [MAIN_TRACK_END, WIDTH + 10], [-10, WIDTH + 10]])
    groove_lo = flat(outer.offset(-TRACK_OUTSET, md.JoinType.Miter, 10) ^ clip_cs)
    groove_hi = flat(outer.offset(-WALL, md.JoinType.Miter, 10) ^ clip_cs)
    groove = hull([[x, y, z] for z in (TRACK_BOTTOM, TRACK_BEVEL_START) for x, y in groove_lo]
                  + [[x, y, TRACK_TOP] for x, y in groove_hi])
    tray -= groove
    neck_groove = hull([[x, y, z] for x in (NECK_TRACK_START, LENGTH + 1)
                       for z in (TRACK_BOTTOM, TRACK_BEVEL_START)
                       for y in (neck_y(x,TRACK_OUTSET), WIDTH-neck_y(x,TRACK_OUTSET))] +
                      [[x, y, TRACK_TOP+EPS] for x in (NECK_TRACK_START, LENGTH + 1)
                       for y in (neck_y(x,WALL+EPS), WIDTH-neck_y(x,WALL+EPS))])
    tray -= neck_groove
    # Open the back loading slot upward; no long unsupported rear crossbar.
    tray -= cube([-1, TRACK_OUTSET-EPS, TRACK_BOTTOM],
                  [WALL+EPS, WIDTH-TRACK_OUTSET+EPS, HEIGHT+1])

    lid_clip = section([[-10, -10], [LID_MAIN_FRONT, -10], [LID_MAIN_FRONT, WIDTH + 10], [-10, WIDTH + 10]])
    lid_lo = flat(outer.offset(-LID_OUTSET, md.JoinType.Miter, 10) ^ lid_clip)
    lid_hi = flat(outer.offset(-LID_TOP_OUTSET, md.JoinType.Miter, 10) ^ lid_clip)
    lid = hull([[x, y, z] for z in (LID_BOTTOM, LID_BEVEL_START) for x, y in lid_lo]
               + [[x, y, LID_TOP] for x, y in lid_hi])
    lid += hull([[x, y, z] for x in (LID_MAIN_FRONT - EPS, LID_FRONT)
                 for z in (LID_BOTTOM, LID_BEVEL_START)
                 for y in (neck_y(x,LID_OUTSET), WIDTH-neck_y(x,LID_OUTSET))] +
                [[x, y, LID_TOP] for x in (LID_MAIN_FRONT - EPS, LID_FRONT)
                 for y in (neck_y(x,LID_TOP_OUTSET), WIDTH-neck_y(x,LID_TOP_OUTSET))])
    rear_lo = [[-2, LID_OUTSET], [4, LID_OUTSET], [4, WIDTH - LID_OUTSET], [-2, WIDTH - LID_OUTSET]]
    rear_hi = [[-2, LID_TOP_OUTSET], [4, LID_TOP_OUTSET],
               [4, WIDTH - LID_TOP_OUTSET], [-2, WIDTH - LID_TOP_OUTSET]]
    lid += hull([[x, y, z] for z in (LID_BOTTOM, LID_BEVEL_START) for x, y in rear_lo]
                + [[x, y, LID_TOP] for x, y in rear_hi])
    # This underside flange stops the lid at the rear wall and forms a pull grip.
    lid += cube([-2, LID_OUTSET, 11.7], [0, WIDTH - LID_OUTSET, LID_BOTTOM + EPS])
    lid += cube([-7, center - 13, 11.7], [-1, center + 13, LID_TOP])

    def plug(extra_clearance):
        inset = WALL + PLUG_SIDE_CLEARANCE + extra_clearance
        # One flat-bottom extrusion: tapered block plus integral T grip.
        # The taper is in plan (wide toward the tray), as in the user's photos.
        profile = [[PLUG_REAR,neck_y(PLUG_REAR,inset)],
                   [LENGTH,neck_y(LENGTH,inset)],
                   [LENGTH,center-PLUG_GRIP_WIDTH/2],
                   [LENGTH+2.4,center-PLUG_GRIP_WIDTH/2],
                   [LENGTH+2.4,center+PLUG_GRIP_WIDTH/2],
                   [LENGTH,center+PLUG_GRIP_WIDTH/2],
                   [LENGTH,WIDTH-neck_y(LENGTH,inset)],
                   [PLUG_REAR,WIDTH-neck_y(PLUG_REAR,inset)]]
        return extrude(section(profile),PLUG_BOTTOM,PLUG_TOP)

    standard_plug = plug(0.0)
    relaxed_plug = plug(0.15)
    tray_coupon = tray & cube([-1, -1, -1], [18, WIDTH + 1, HEIGHT + 1])
    lid_coupon = lid & cube([-8, -1, 0], [18, WIDTH + 1, HEIGHT + 1])
    spout_coupon = tray & cube([LENGTH-FIT_SPOUT_LENGTH, root0-1, -1], [LENGTH+1,root1+1,HEIGHT+1])
    spout_lid_coupon = lid & cube([LENGTH-FIT_SPOUT_LENGTH, root0-1, 0], [LENGTH+1,root1+1,HEIGHT+1])
    parts = {
        "01_tray": tray,
        "02_sliding_lid": normalize(lid.rotate([180, 0, 0])),
        "03_spout_plug": normalize(standard_plug),
        "optional/plug_relaxed_fit": normalize(relaxed_plug),
        "optional/fit_test_tray_tracks": normalize(tray_coupon),
        "optional/fit_test_lid": normalize(lid_coupon.rotate([180, 0, 0])),
        "optional/fit_test_spout": normalize(spout_coupon),
        "optional/fit_test_spout_lid": normalize(spout_lid_coupon.rotate([180, 0, 0])),
    }
    return parts, tray, lid, standard_plug, relaxed_plug, pitch


def write_3mf(mesh, path, name):
    # Core 3MF only: portable millimeter units, no machine-specific presets.
    ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("", ns)
    el = lambda name: f"{{{ns}}}{name}"
    model = ET.Element(el("model"), unit="millimeter")
    resources = ET.SubElement(model, el("resources"))
    obj = ET.SubElement(resources, el("object"), id="1", type="model", name=name)
    mesh_xml = ET.SubElement(obj, el("mesh"))
    verts = ET.SubElement(mesh_xml, el("vertices"))
    for x, y, z in mesh.vertices:
        ET.SubElement(verts, el("vertex"), x=f"{x:.7f}", y=f"{y:.7f}", z=f"{z:.7f}")
    faces = ET.SubElement(mesh_xml, el("triangles"))
    for a, b, c in mesh.faces:
        ET.SubElement(faces, el("triangle"), v1=str(a), v2=str(b), v3=str(c))
    build_xml = ET.SubElement(model, el("build"))
    ET.SubElement(build_xml, el("item"), objectid="1")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        archive.writestr("3D/3dmodel.model", ET.tostring(model, encoding="utf-8", xml_declaration=True))


def verify(parts, tray, lid, plug, relaxed, pitch):
    result = {"units": "mm", "parts": {}, "valleys": ROWS, "valley_pitch_mm": round(pitch, 4),
              "valley_flat_mm": VALLEY_FLAT, "shelf_depth_mm": SHELF_DEPTH,
              "shelf_top_mm": RIDGE_Z, "ridge_top_mm": RIDGE_Z,
              "ridge_height_above_floor_mm": RIDGE_HEIGHT, "ridge_base_width_mm": RIDGE_WIDTH,
              "design_revision": 5, "plug_style": "plain tapered block with T grip, matching photo reference",
              "physical_print_tested": False, "bambu_studio_slice_tested": False}
    for name, solid in parts.items():
        mesh = mesh_of(solid)
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0, name
        components = len(solid.m.decompose())
        assert components == 1, f"Disconnected component in {name}: {components}"
        assert mesh.bounds[0, 2] >= -1e-4
        assert all(mesh.extents <= [180, 180, 180]), name
        # Check actual exported STL, not just the in-memory CAD object.
        disk_mesh = trimesh.load(OUT / f"{name}.stl", force="mesh")
        assert disk_mesh.is_watertight and disk_mesh.is_winding_consistent
        assert np.allclose(disk_mesh.extents, mesh.extents, atol=1e-4)
        with zipfile.ZipFile(OUT / f"{name}.3mf") as archive:
            assert archive.testzip() is None
            model = ET.fromstring(archive.read("3D/3dmodel.model"))
            assert model.attrib["unit"] == "millimeter"
            ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
            vertices_xml = model.findall(".//m:vertex", ns)
            triangles_xml = model.findall(".//m:triangle", ns)
            imported = trimesh.Trimesh(
                vertices=[[float(v.attrib[c]) for c in ("x", "y", "z")] for v in vertices_xml],
                faces=[[int(t.attrib[c]) for c in ("v1", "v2", "v3")] for t in triangles_xml])
            assert imported.is_watertight and imported.is_winding_consistent and imported.volume > 0
            assert np.allclose(imported.extents, mesh.extents, atol=1e-4)
        result["parts"][name] = {"size_mm": np.round(mesh.extents, 3).tolist(),
                                   "watertight": True, "consistent_winding": True,
                                   "connected_solids": components, "triangles": len(mesh.faces),
                                   "volume_cm3": round(mesh.volume / 1000, 3),
                                   "stl_roundtrip_verified": True, "core_3mf_roundtrip_verified": True}
    # Sample the entire removal path at 1 mm steps; all must be collision-free.
    steps = range(int(np.ceil(LID_FRONT + 7)) + 1)
    collision_volumes = [(tray.m ^ lid.m.translate([-float(d), 0, 0])).volume() for d in steps]
    plug_slide_collisions = [(plug.m ^ lid.m.translate([-float(d), 0, 0])).volume() for d in steps]
    assert max(collision_volumes) < 0.001, f"Lid hits body: {max(collision_volumes)} mm3"
    assert max(plug_slide_collisions) < 0.001, "Lid hits seated plug"
    result["lid_slide"] = {"samples": len(collision_volumes), "sample_step_mm": 1,
                           "max_collision_mm3": round(max(collision_volumes), 6),
                           "lower_edge_side_clearance_mm": LID_OUTSET - TRACK_OUTSET,
                           "bottom_clearance_mm": LID_BOTTOM - TRACK_BOTTOM,
                           "max_seated_plug_collision_mm3": round(max(plug_slide_collisions), 6)}
    result["plug_seated_interference_mm3"] = round((tray.m ^ plug.m).volume(), 6)
    result["relaxed_plug_seated_interference_mm3"] = round((tray.m ^ relaxed.m).volume(), 6)
    # The plain narrowing channel blocks complete forward withdrawal; the lid
    # blocks upward removal. With the lid retracted, the block lifts freely.
    for name, gate in [("standard", plug), ("relaxed", relaxed)]:
        assert abs((tray.m ^ gate.m).volume()) < 0.001, f"Seated {name} plug intersects tray"
        assert abs((lid.m ^ gate.m).volume()) < 0.001, f"Seated {name} plug intersects lid"
        removal = [(tray.m ^ gate.m.translate([0, 0, float(d)])).volume() for d in range(23)]
        assert max(removal) < 0.001, f"{name} plug cannot lift out"
        forward_block = (tray.m ^ gate.m.translate([8, 0, 0])).volume()
        upward_block = (lid.m ^ gate.m.translate([0, 0, 0.5])).volume()
        sideways_block = (tray.m ^ gate.m.translate([0, 1, 0])).volume()
        assert min(forward_block, upward_block, sideways_block) > 0.1, f"{name} plug not captured"
        result[f"{name}_plug_retention"] = {
            "lid_to_plug_top_clearance_mm": round(LID_BOTTOM - PLUG_TOP, 3),
            "bottom_clearance_mm": round(PLUG_BOTTOM - BASE, 3),
            "upward_removal_without_lid_max_collision_mm3": round(max(removal), 6),
            "upward_removal_samples": len(removal),
            "forward_8mm_blocked_overlap_mm3": round(forward_block, 6),
            "sideways_1mm_blocked_overlap_mm3": round(sideways_block, 6),
            "upward_half_mm_with_lid_blocked_overlap_mm3": round(upward_block, 6)}
    probe = cube([PLUG_X-0.1, WIDTH/2-0.1, BASE+EPS], [PLUG_X+0.1, WIDTH/2+0.1, HEIGHT+1])
    assert abs((tray.m ^ probe.m).volume()) < 0.001, "Spout top is not open"
    result["spout_top_open_without_lid"] = True
    spout_body = tray & cube([LENGTH-FIT_SPOUT_LENGTH, WIDTH/2-11, -1], [LENGTH+1, WIDTH/2+11, HEIGHT+1])
    spout_lid = lid & cube([LENGTH-FIT_SPOUT_LENGTH, WIDTH/2-11, 0], [LENGTH+1, WIDTH/2+11, HEIGHT+1])
    assert (spout_lid.m ^ plug.m.translate([0,0,0.5])).volume() > 0.1
    assert (spout_body.m ^ plug.m.translate([8,0,0])).volume() > 0.1
    assert abs((spout_lid.m ^ plug.m).volume()) < 0.001
    result["spout_fit_coupon_capture_verified"] = True
    # Vertical ray intersections confirm fourteen separate flat-bottom channels.
    valley_z = []
    valley_widths = []
    ridge_z = []
    ridge_widths = []
    just_above_floor = tray.m.slice(BASE+0.0001)
    for i in range(ROWS):
        yy = WALL + (i + 0.5) * pitch
        ray = cube([60, yy - 0.001, 0], [60.002, yy + 0.001, 8])
        valley_z.append(mesh_of(tray & ray).bounds[1, 2])
        clip = section([[60, yy-pitch/2], [60.002, yy-pitch/2],
                        [60.002, yy+pitch/2], [60, yy+pitch/2]])
        contours = (clip - just_above_floor).to_polygons()
        assert len(contours) == 1, f"Valley {i+1} is not one clear channel"
        ys = np.concatenate(contours)[:,1]
        valley_widths.append(float(ys.max()-ys.min()))
    for i in range(1, ROWS):
        yy = WALL + i * pitch
        ray = cube([60, yy - 0.001, 0], [60.002, yy + 0.001, 8])
        ridge_z.append(mesh_of(tray & ray).bounds[1, 2])
        # Measure the exported geometry just above the floor, excluding the
        # hidden 0.05 mm union overlap below the floor surface.
        clip = section([[60, yy-pitch/2], [60.002, yy-pitch/2],
                        [60.002, yy+pitch/2], [60, yy+pitch/2]])
        contours = (just_above_floor ^ clip).to_polygons()
        ys = np.concatenate(contours)[:,1]
        ridge_widths.append(float(ys.max()-ys.min()))
    assert np.allclose(valley_z, BASE, atol=1e-4)
    assert np.allclose(valley_widths, 3.0, atol=0.001)
    assert np.allclose(ridge_z, RIDGE_Z, atol=1e-4)
    assert np.allclose(np.array(ridge_z)-BASE, 1.5, atol=1e-4)
    assert np.allclose(ridge_widths, 1.5, atol=0.001)
    shelf_ray = cube([12, WIDTH/2 - 0.001, 0], [12.002, WIDTH/2 + 0.001, 8])
    assert abs(mesh_of(tray & shelf_ray).bounds[1, 2] - RIDGE_Z) < 1e-4
    result["measured_valley_bottoms_mm"] = np.round(valley_z, 3).tolist()
    result["measured_valley_flat_widths_mm"] = np.round(valley_widths, 4).tolist()
    result["measured_internal_ridge_tops_mm"] = np.round(ridge_z, 3).tolist()
    result["measured_ridge_base_widths_mm"] = np.round(ridge_widths, 4).tolist()
    result["measured_ridge_heights_above_floor_mm"] = np.round(np.array(ridge_z)-BASE, 3).tolist()
    return result


def render_assembly(scene, width=1500, height=1000):
    """Orthographic depth-buffer render of the actual mesh, without display/GPU."""
    from PIL import Image
    camera = np.array([np.cos(np.deg2rad(31))*np.cos(np.deg2rad(-63)),
                       np.cos(np.deg2rad(31))*np.sin(np.deg2rad(-63)), np.sin(np.deg2rad(31))])
    right = np.array([-np.sin(np.deg2rad(-63)), np.cos(np.deg2rad(-63)), 0])
    up = np.cross(camera, right)
    rotation = np.column_stack([right, up, camera])
    transformed = [(mesh_of(s), color) for s, color in scene]
    projected = np.concatenate([m.vertices @ rotation for m, _ in transformed])
    lo, hi = projected.min(axis=0), projected.max(axis=0)
    scale = min(width / (hi[0]-lo[0]), height / (hi[1]-lo[1])) * 0.88
    center = (lo + hi) / 2
    pixels = np.full((height, width, 3), [244,246,247], dtype=np.uint8)
    depth = np.full((height, width), -np.inf)
    light = np.array([-0.4,-0.6,1.0]); light /= np.linalg.norm(light)
    for mesh, color in transformed:
        rgb = np.array([int(color[i:i+2], 16) for i in (1,3,5)])
        xyz = mesh.vertices @ rotation
        xyz[:,0] = (xyz[:,0]-center[0])*scale + width/2
        xyz[:,1] = height/2 - (xyz[:,1]-center[1])*scale
        for face, normal in zip(mesh.faces, mesh.face_normals):
            if normal @ camera <= 0:
                continue
            t = xyz[face]
            x0, y0 = np.maximum(np.floor(t[:,:2].min(axis=0)), [0,0]).astype(int)
            x1, y1 = np.minimum(np.ceil(t[:,:2].max(axis=0)), [width-1,height-1]).astype(int)
            if x1 < x0 or y1 < y0:
                continue
            yy, xx = np.mgrid[y0:y1+1,x0:x1+1]
            xx, yy = xx+0.5, yy+0.5
            den = (t[1,1]-t[2,1])*(t[0,0]-t[2,0]) + (t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(den) < 1e-10:
                continue
            a = ((t[1,1]-t[2,1])*(xx-t[2,0]) + (t[2,0]-t[1,0])*(yy-t[2,1])) / den
            b = ((t[2,1]-t[0,1])*(xx-t[2,0]) + (t[0,0]-t[2,0])*(yy-t[2,1])) / den
            c = 1-a-b
            z = a*t[0,2]+b*t[1,2]+c*t[2,2]
            old = depth[y0:y1+1,x0:x1+1]
            mask = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6) & (z > old)
            old[mask] = z[mask]
            shade = 0.42 + 0.58 * max(0.0, float(normal @ light))
            pixels[y0:y1+1,x0:x1+1][mask] = np.clip(rgb*shade, 0,255).astype(np.uint8)
    return Image.fromarray(pixels)


def preview(tray, lid, plug):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 11})
    fig = plt.figure(figsize=(15, 10), facecolor="#f4f6f7")
    ax = fig.add_axes([0.01, 0.19, 0.62, 0.71])
    ax.imshow(render_assembly([(tray,"#69bbb3"),(lid.translate([-16,0,30]),"#d0dce4"),
                               (plug.translate([0,0,23]),"#df974d")]))
    ax.axis("off")
    ax2 = fig.add_axes([0.66, 0.24, 0.32, 0.64])
    mesh = mesh_of(tray)
    # Exact orthographic top surface drawing, with ridge rows visible.
    from matplotlib.collections import PolyCollection
    top = mesh.face_normals[:, 2] > 0.005
    colors = []
    for triangle in mesh.triangles[top]:
        z = triangle[:, 2].mean()
        colors.append("#b6e0d6" if z < 2 else "#5cac9e" if z < 5 else "#337c78")
    ax2.add_collection(PolyCollection(mesh.triangles[top, :, :2], facecolors=colors,
                                      edgecolors="none", antialiased=False))
    ax2.set_aspect("equal")
    ax2.set(xlim=(-4,168), ylim=(-4,WIDTH+4))
    ax2.axis("off")
    ax2.annotate("20 mm flat shelf\nlevel with ridge tops", xy=(13,WIDTH/2), xytext=(18,WIDTH+25),
                 arrowprops={"arrowstyle":"->", "color":"#34565d"}, color="#23474d")
    ax2.annotate("14 valleys · 3 mm across", xy=(70,WIDTH/2+2.25), xytext=(80,WIDTH+18),
                 arrowprops={"arrowstyle":"->", "color":"#34565d"}, color="#23474d")
    ax2.annotate("Plain open spout", xy=(155,WIDTH/2), xytext=(132,-25),
                 arrowprops={"arrowstyle":"->", "color":"#34565d"}, color="#23474d", ha="center")
    fig.text(0.04,0.94,"Diamond art sorting tray",fontsize=25,fontweight="bold",color="#123d43")
    fig.text(0.04,0.90,"Revision 5  ·  164 × 67.8 mm  ·  14 valleys, each 3 mm across",fontsize=13,color="#486269")
    fig.text(0.04,0.13,"Exploded assembly",fontsize=13,fontweight="bold",color="#123d43")
    fig.text(0.04,0.095,"Slide the lid back, then lift out the stopper using its T-shaped grip.",color="#486269")
    fig.text(0.04,0.052,"CAD preview • clearances verified digitally • physical fit requires a test print",fontsize=10,color="#687d81")
    fig.savefig(ROOT / "tray-preview.png", dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)


def spout_preview(tray, lid, plug):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    half = SPOUT_ROOT_WIDTH/2
    fixture = cube([LENGTH-FIT_SPOUT_LENGTH,WIDTH/2-half-1,-1], [LENGTH+1,WIDTH/2+half+1,HEIGHT+1])
    body, cover = tray & fixture, lid & fixture
    fig, axes = plt.subplots(1,3,figsize=(15,5), facecolor="#f4f6f7")
    scenes = [[(body,"#69bbb3"),(plug.translate([0,0,15]),"#df974d")],
              [(body,"#69bbb3"),(plug,"#df974d"),(cover,"#d0dce4")]]
    for ax, scene, title in zip(axes[:2],scenes,["1. Lid open: lower the stopper", "2. Sliding lid holds it down"]):
        ax.imshow(render_assembly(scene,width=800,height=800))
        ax.axis("off")
        ax.set_title(title, color="#123d43", fontsize=12)
    ax = axes[2]
    for solid, color in [(body,"#69bbb3"),(plug,"#df974d")]:
        mesh = mesh_of(solid)
        faces = mesh.triangles[mesh.face_normals[:,2] > 0.005]
        ax.add_collection(PolyCollection(faces[:,:,:2],facecolors=color,edgecolors="none",antialiased=False))
    ax.set(xlim=(LENGTH-FIT_SPOUT_LENGTH-3,LENGTH+6),ylim=(WIDTH/2-15,WIDTH/2+15))
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Simple tapered block · top view", color="#123d43", fontsize=12)
    ax.annotate("Wide end toward tray",xy=(PLUG_REAR+1,WIDTH/2),xytext=(PLUG_REAR+7,WIDTH/2-13),
                ha="center",fontsize=10,color="#23474d",arrowprops={"arrowstyle":"->"})
    fig.text(0.5,0.06,"One plain channel and a flat-bottom T stopper. Slide the lid back to lift it out.",
             ha="center", color="#486269", fontsize=12)
    fig.savefig(ROOT/"spout-fit-preview.png",dpi=160,facecolor=fig.get_facecolor(),bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    parts, tray, lid, plug, relaxed, pitch = build()
    for name, solid in parts.items():
        path = OUT / name
        path.parent.mkdir(exist_ok=True)
        mesh = mesh_of(solid)
        mesh.export(path.with_suffix(".stl"))
        write_3mf(mesh, path.with_suffix(".3mf"), Path(name).name)
    report = verify(parts, tray, lid, plug, relaxed, pitch)
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    source = ['// Generated CAD, millimeters. Edit build_tray.py dimensions and rebuild for parameter changes.\n',
              '// F6 render; choose part below. Export tray/lid/plug in their print orientations.\n',
              'part = "assembly"; // "tray", "lid", "plug", "assembly", "exploded"\n']
    for label, solid in [("tray", tray), ("lid_assembly", lid), ("plug_assembly", plug),
                         ("lid", parts["02_sliding_lid"]), ("plug", parts["03_spout_plug"])]:
        source.append(f"module {label}(){{{solid.scad}}}\n")
    source.append('if(part=="tray")tray(); else if(part=="lid")lid(); else if(part=="plug")plug();\n'
                  'else if(part=="assembly"){color("LightSeaGreen")tray(); color("LightGray")lid_assembly(); color("Orange")plug_assembly();}\n'
                  'else if(part=="exploded"){color("LightSeaGreen")tray(); color("LightGray")translate([-16,0,30])lid_assembly(); color("Orange")translate([0,0,23])plug_assembly();}\n')
    (ROOT / "diamond-art-tray.scad").write_text("".join(source))
    preview(tray, lid, plug)
    spout_preview(tray, lid, plug)
    with zipfile.ZipFile(ROOT / "diamond-art-tray-print-pack.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(ROOT))
        for filename in ["README.md", "build_tray.py", "requirements.txt", "diamond-art-tray.scad", "tray-preview.png", "spout-fit-preview.png", "verification.json"]:
            if (ROOT / filename).exists():
                archive.write(ROOT / filename, filename)
    # A distinct download name avoids confusing the new plug system with v1.
    (ROOT/"diamond-art-tray-v5-print-pack.zip").write_bytes((ROOT/"diamond-art-tray-print-pack.zip").read_bytes())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

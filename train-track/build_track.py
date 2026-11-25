"""Parametric straight toy-train track that mates with the user's green curve.

Dimensions are millimeters. Run: python build_track.py (see requirements.txt).
Exports watertight STL, model-only 3MF, a preview and verification.json.
No printer G-code.

Every dimension of the green piece below was estimated from two phone photos
scaled with a ruler in frame (see README.md). The estimates carry roughly
+/-1 mm of uncertainty, so print the fit-test coupon before the full straight.

Frame: x runs along the track (end faces at x=0 and x=LENGTH), y is lateral
with y=0 on the connector centerline, z is up with the bed at z=0. Looking
outward from either end, the knob is on the left and the socket on the right,
the same handedness measured on the green piece. The two ends are related by a
180 degree turn about z, so any end mates with any other end.
"""
from pathlib import Path
import json
import zipfile
import xml.etree.ElementTree as ET

import manifold3d as md
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "print-files"
REVISION = 1

# Track body. Measured green width: about 51 mm across the top and 57 mm at
# the base; running bands at about 8 mm and end blocks/rims at 10-12 mm.
LENGTH = 200.0                # end face to end face
COUPON_LENGTH = 40.0          # short fit-test piece with both connector ends
BASE_HALF = 28.5              # footprint half-width at the bed
TOP_HALF = 26.0               # half-width at the top of the sloped sides
RIM_TOP = 10.0                # low guard rims along both edges
RIM_INNER = 21.5              # rim inner edge; 43 mm clear between rims
BAND_TOP = 8.0                # running surface of the two ribbed bands
CENTER_HALF = 6.5             # recessed center channel half-width
DECK = 3.0                    # floor of the center channel
RIB_HEIGHT = 0.4
RIB_WIDTH = 1.0
RIB_PITCH = 2.4
SLOT_HALF_WIDTH = 5.0         # through-slots in the center channel
SLOT_LENGTH = 9.5
SLOT_PITCH = 19.2             # measured green slot pitch about 19 mm
SLOT_END_MARGIN = 22.0        # keep slots clear of the connector zones
END_BLOCK = 18.0              # center channel filled to band height at each end

# Connector. The green socket measured 17.2-18.3 mm across inside, with a
# 12.4-13.8 mm mouth, centered about 6 mm off the centerline and about 16 mm
# deep. A 3-3.5 mm lip on the centerline side of the mouth provides retention.
# Values below already include about 3% correction for the photo's top-plane
# magnification and deliberately err loose.
CONNECTOR_OFFSET = 6.0        # head center from the track centerline
KNOB_CENTER = 7.4             # head center beyond the end face
KNOB_SEMI_X = 7.2             # head reaches 14.6 mm beyond the face
KNOB_SEMI_Y = 8.1             # 16.2 mm head width
KNOB_NECK = (1.4, 13.0)       # neck spans these y offsets (11.6 mm)
KNOB_HEIGHT = 7.0
SOCKET_CENTER = 7.9           # socket head center inside the end face
SOCKET_SEMI_X = 8.3           # 16.2 mm deep
SOCKET_SEMI_Y = 9.0           # 18.0 mm across
SOCKET_MOUTH = (0.2, 14.0)    # mouth spans these y offsets (13.8 mm)
CIRCLE_SEGMENTS = 96

# Estimated green socket envelope used for the photo-based fit checks.
GREEN_SOCKET = {"center": 7.6, "semi_x": 7.9, "semi_y": 8.6, "offset": 5.9,
                "mouth": (0.8, 13.4)}


def ellipse(cx, cy, ax, ay):
    t = np.linspace(0, 2*np.pi, CIRCLE_SEGMENTS, endpoint=False)
    return md.CrossSection([np.c_[cx + ax*np.cos(t), cy + ay*np.sin(t)]])


def rect(x0, y0, x1, y1):
    return md.CrossSection([np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)])


def knob_shape(head_x, ax, ay, neck, offset=CONNECTOR_OFFSET):
    """Knob outline in end-local coordinates: u outward from the face, v lateral."""
    head = ellipse(head_x, offset, ax, ay)
    return head + rect(-0.6, neck[0], head_x, neck[1])


def socket_shape(center, ax, ay, mouth, offset=CONNECTOR_OFFSET):
    """Socket outline in end-local coordinates (u<0 is inside the track)."""
    head = ellipse(-center, -offset, ax, ay)
    return head + rect(-center, -mouth[1], 0.6, -mouth[0])


def knob_2d():
    return knob_shape(KNOB_CENTER, KNOB_SEMI_X, KNOB_SEMI_Y, KNOB_NECK)


def socket_2d():
    return socket_shape(SOCKET_CENTER, SOCKET_SEMI_X, SOCKET_SEMI_Y, SOCKET_MOUTH)


def green_socket_2d():
    g = GREEN_SOCKET
    return socket_shape(g["center"], g["semi_x"], g["semi_y"], g["mouth"], g["offset"])


def green_knob_2d(clearance=0.4):
    """Largest knob the estimated green socket could hold, mirrored to the knob side."""
    g = GREEN_SOCKET
    neck = (g["mouth"][0] + clearance, g["mouth"][1] - clearance)
    return knob_shape(g["center"], g["semi_x"] - clearance, g["semi_y"] - clearance,
                      neck, g["offset"])


def at_end(cs, length, end):
    """Place an end-local outline at x=length (end='far') or x=0 (end='near')."""
    if end == "far":
        return cs.translate([length, 0])
    return cs.rotate(180)


def profile():
    """Counter-clockwise (y, z) cross-section, symmetric about y=0."""
    right = [(BASE_HALF, 0), (TOP_HALF, RIM_TOP), (RIM_INNER, RIM_TOP), (RIM_INNER, BAND_TOP),
             (CENTER_HALF, BAND_TOP), (CENTER_HALF, DECK)]
    left = [(-y, z) for y, z in reversed(right)]
    return md.CrossSection([np.array(right + left, float)])


def body(length):
    # Extrude the (y, z) profile along x.
    cs = profile()
    return md.Manifold.extrude(cs, length).rotate([90, 0, 90])


def box(lo, hi):
    return md.Manifold.cube(np.subtract(hi, lo)).translate(lo)


def ribs(length):
    # Centered so both ends are identical after a 180 degree turn.
    count = int((length - 2*RIB_PITCH) // RIB_PITCH) + 1
    first = length/2 - (count - 1)*RIB_PITCH/2
    parts = []
    for i in range(count):
        x = first + i*RIB_PITCH - RIB_WIDTH/2
        for sign in (-1, 1):
            y0, y1 = sorted((sign*CENTER_HALF, sign*RIM_INNER))
            parts.append(box([x, y0, BAND_TOP - 0.01], [x + RIB_WIDTH, y1, BAND_TOP + RIB_HEIGHT]))
    return md.Manifold.batch_boolean(parts, md.OpType.Add)


def slots(length):
    usable = length - 2*SLOT_END_MARGIN
    if usable < SLOT_LENGTH:
        return None
    count = int((usable - SLOT_LENGTH) // SLOT_PITCH) + 1
    span = (count - 1)*SLOT_PITCH
    start = length/2 - span/2
    return md.Manifold.batch_boolean(
        [box([start + i*SLOT_PITCH - SLOT_LENGTH/2, -SLOT_HALF_WIDTH, -1],
             [start + i*SLOT_PITCH + SLOT_LENGTH/2, SLOT_HALF_WIDTH, DECK + 1]) for i in range(count)],
        md.OpType.Add)


def extrude2d(cs, z0, z1):
    return md.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])


def build_track(length, with_ribs=True):
    solid = body(length)
    if with_ribs:
        solid = solid + ribs(length)
    # Solid end blocks, like the green piece, give the socket lips full height.
    block = END_BLOCK if length > 2*END_BLOCK + SLOT_LENGTH else length/2
    solid = solid + box([0, -CENTER_HALF - 0.01, DECK - 0.01], [block, CENTER_HALF + 0.01, BAND_TOP])
    solid = solid + box([length - block, -CENTER_HALF - 0.01, DECK - 0.01],
                        [length, CENTER_HALF + 0.01, BAND_TOP])
    holes = slots(length)
    if holes is not None:
        solid = solid - holes
    sockets = at_end(socket_2d(), length, "far") + at_end(socket_2d(), length, "near")
    solid = solid - extrude2d(sockets, -1, RIM_TOP + 2)
    # Knob necks overlap the body by 0.6 mm so the union stays one solid.
    knobs = at_end(knob_2d(), length, "far") + at_end(knob_2d(), length, "near")
    solid = solid + extrude2d(knobs, 0, KNOB_HEIGHT)
    return solid


def build():
    return {
        "01_straight_200mm": build_track(LENGTH),
        "optional/fit_test_coupon": build_track(COUPON_LENGTH, with_ribs=False),
    }


def mesh_of(solid):
    raw = solid.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.round(np.asarray(raw.vert_properties)[:, :3], 5),
                           faces=np.asarray(raw.tri_verts), process=True)
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-5))
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def write_3mf(mesh, path, name):
    # Core 3MF only: portable millimeter units, no machine-specific presets.
    ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("", ns)
    el = lambda tag: f"{{{ns}}}{tag}"
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


def min_gap(inner, outer):
    """Smallest distance from inner's outline to outside outer; negative if inner pokes out."""
    if (inner - outer).area() > 1e-6:
        return -1.0
    lo, hi = 0.0, 5.0
    for _ in range(30):
        mid = (lo + hi)/2
        grown = inner.offset(mid, md.JoinType.Round, circular_segments=64)
        if (grown - outer).area() > 1e-6:
            hi = mid
        else:
            lo = mid
    return lo


def mate(solid_a, length_a, solid_b, pull=0.0):
    """Join B's near end (x=0) to A's far end (x=length_a); return overlap volume.

    The near end is the far end turned 180 degrees, so no extra rotation is
    needed. pull > 0 moves B outward along +x to test retention.
    """
    return (solid_a ^ solid_b.translate([length_a + pull, 0, 0])).volume()


def verify(parts):
    result = {"units": "mm", "design_revision": REVISION,
              "source": "estimated from two ruler-scaled photos of the green curve",
              "estimate_uncertainty_mm": 1.0, "parts": {},
              "physical_print_tested": False, "slicer_tested": False,
              "green_piece_fit_tested": False}
    for name, solid in parts.items():
        mesh = mesh_of(solid)
        assert mesh.is_watertight and mesh.is_winding_consistent, name
        assert len(solid.decompose()) == 1, name
        lo, hi = mesh.bounds
        assert lo[2] >= -1e-6, name
        assert hi[0] - lo[0] <= 250 and hi[1] - lo[1] <= 250, name
        result["parts"][name] = {"extents_mm": np.round(hi - lo, 3).tolist(),
                                 "volume_cm3": round(mesh.volume/1000, 2),
                                 "watertight": True, "single_body": True}
    # Compare only the parts beyond the end face; the knob neck's 0.6 mm
    # overlap into its own body is never inside a mating socket.
    outside = rect(0, -40, 40, 40)
    knob, socket = knob_2d() ^ outside, socket_2d()
    mirrored_knob = knob.rotate(180)
    printed_clearance = min_gap(mirrored_knob, socket)
    green_knob = (green_knob_2d() ^ outside).rotate(180)
    green_into_printed = min_gap(green_knob, socket)
    printed_into_green = min_gap(mirrored_knob, green_socket_2d())
    assert printed_clearance >= 0.4, printed_clearance
    assert green_into_printed >= 0.3, green_into_printed
    assert printed_into_green >= 0.2, printed_into_green
    coupon = parts["optional/fit_test_coupon"]
    straight = parts["01_straight_200mm"]
    seated = mate(straight, LENGTH, coupon)
    pulled = mate(straight, LENGTH, coupon, pull=3.0)
    assert seated < 1e-3, seated
    assert pulled > 1.0, pulled
    result["connector"] = {
        "knob_head_mm": [round(2*KNOB_SEMI_X, 2), round(2*KNOB_SEMI_Y, 2)],
        "knob_neck_width_mm": round(KNOB_NECK[1] - KNOB_NECK[0], 2),
        "knob_reach_mm": KNOB_CENTER + KNOB_SEMI_X, "knob_height_mm": KNOB_HEIGHT,
        "socket_head_mm": [round(2*SOCKET_SEMI_X, 2), round(2*SOCKET_SEMI_Y, 2)],
        "socket_mouth_width_mm": round(SOCKET_MOUTH[1] - SOCKET_MOUTH[0], 2),
        "socket_depth_mm": SOCKET_CENTER + SOCKET_SEMI_X,
        "offset_from_centerline_mm": CONNECTOR_OFFSET,
        "printed_knob_in_printed_socket_min_gap_mm": round(printed_clearance, 3),
        "estimated_green_knob_in_printed_socket_min_gap_mm": round(green_into_printed, 3),
        "printed_knob_in_estimated_green_socket_min_gap_mm": round(printed_into_green, 3),
        "seated_overlap_mm3": round(seated, 4),
        "overlap_after_3mm_pull_mm3": round(pulled, 2),
    }
    result["profile"] = {"base_width_mm": 2*BASE_HALF, "top_width_mm": 2*TOP_HALF,
                         "rim_height_mm": RIM_TOP, "rim_clear_width_mm": 2*RIM_INNER,
                         "band_height_mm": BAND_TOP, "rib_height_mm": RIB_HEIGHT,
                         "center_channel_width_mm": 2*CENTER_HALF, "deck_mm": DECK,
                         "face_to_face_length_mm": LENGTH}
    return result


def preview(parts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10})
    fig = plt.figure(figsize=(14, 8.5), facecolor="#f4f6f7")
    shades = [(DECK + 0.1, "#7fb3d5"), (BAND_TOP + 0.1, "#2e86c1"), (99, "#1b4f72")]

    def top(ax, solid, xlim):
        mesh = mesh_of(solid)
        keep = mesh.face_normals[:, 2] > 0.005
        tris = mesh.triangles[keep]
        z = tris[:, :, 2].mean(axis=1)
        order = np.argsort(z)
        colors = [next(c for limit, c in shades if zz < limit) for zz in z[order]]
        ax.add_collection(PolyCollection(tris[order, :, :2], facecolors=colors,
                                         edgecolors="none", antialiased=False))
        ax.set_xlim(*xlim)
        ax.set_ylim(-36, 36)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=8)
        ax.grid(True, lw=0.3, alpha=0.5)

    ax = fig.add_axes([0.04, 0.55, 0.92, 0.32])
    top(ax, parts["01_straight_200mm"], (-20, LENGTH + 20))
    ax.set_title("Straight, 200 mm face to face (top view, mm)", loc="left", color="#123d43")
    ax2 = fig.add_axes([0.04, 0.08, 0.42, 0.40])
    top(ax2, parts["01_straight_200mm"], (LENGTH - 22, LENGTH + 18))
    green = green_socket_2d().translate([LENGTH, 0])
    for poly in green.to_polygons():
        p = np.vstack([poly, poly[:1]])
        ax2.plot(p[:, 0], p[:, 1], "--", color="#c0392b", lw=1.2)
    ax2.set_title("Connector end. Dashed: estimated green socket", loc="left", color="#123d43")
    ax3 = fig.add_axes([0.53, 0.08, 0.43, 0.40])
    prof = np.asarray(profile().to_polygons()[0])
    prof = np.vstack([prof, prof[:1]])
    ax3.fill(prof[:, 0], prof[:, 1], color="#2e86c1")
    ax3.set_aspect("equal")
    ax3.set_xlim(-32, 32)
    ax3.set_ylim(-1, 14)
    ax3.grid(True, lw=0.3, alpha=0.5)
    ax3.tick_params(labelsize=8)
    ax3.set_title("Cross-section (mm). Ribs 0.4 mm on bands not shown", loc="left", color="#123d43")
    fig.text(0.04, 0.94, "Train track to match the green curve, revision 1", fontsize=18,
             fontweight="bold", color="#123d43")
    fig.text(0.04, 0.905, "Dimensions estimated from ruler-scaled photos (about ±1 mm). "
             "Print the 40 mm fit-test coupon first.", color="#486269")
    fig.savefig(ROOT / "track-preview.png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    parts = build()
    for name, solid in parts.items():
        path = OUT / name
        path.parent.mkdir(exist_ok=True)
        mesh = mesh_of(solid)
        mesh.export(path.with_suffix(".stl"))
        write_3mf(mesh, path.with_suffix(".3mf"), Path(name).name)
    report = verify(parts)
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    preview(parts)
    pack = ROOT / "train-track-print-pack.zip"
    with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(ROOT))
        for filename in ["README.md", "build_track.py", "requirements.txt", "track-preview.png",
                         "verification.json"]:
            if (ROOT / filename).exists():
                archive.write(ROOT / filename, filename)
    # A distinct download name identifies the current geometry revision.
    (ROOT / f"train-track-v{REVISION}-print-pack.zip").write_bytes(pack.read_bytes())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

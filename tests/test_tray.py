"""Exercise regenerated geometry and exports without changing release artifacts."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "diamond-art-tray"
spec = importlib.util.spec_from_file_location("build_tray", SOURCE / "build_tray.py")
cad = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cad
spec.loader.exec_module(cad)


class TrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.original_root, cls.original_out = cad.ROOT, cad.OUT
        cad.ROOT = Path(cls.workspace.name)
        cad.OUT = cad.ROOT / "print-files"
        cad.OUT.mkdir()
        cls.parts, cls.tray, cls.lid, cls.plug, cls.relaxed, cls.pitch = cad.build()
        for name, solid in cls.parts.items():
            path = cad.OUT / name
            path.parent.mkdir(exist_ok=True)
            mesh = cad.mesh_of(solid)
            mesh.export(path.with_suffix(".stl"))
            cad.write_3mf(mesh, path.with_suffix(".3mf"), path.name)

    @classmethod
    def tearDownClass(cls):
        cad.ROOT, cad.OUT = cls.original_root, cls.original_out
        cls.workspace.cleanup()

    def verify(self, **overrides):
        args = dict(parts=self.parts, tray=self.tray, lid=self.lid,
                    plug=self.plug, relaxed=self.relaxed, pitch=self.pitch)
        args.update(overrides)
        return cad.verify(**args)

    def test_revision_7_geometry_and_fit(self):
        report = self.verify()
        self.assertEqual(report["design_revision"], 7)
        self.assertEqual(report["valleys"], 14)
        self.assertEqual(len(report["parts"]), 8)
        np.testing.assert_allclose(report["parts"]["01_tray"]["size_mm"], [164, 67.8, 17.4])
        np.testing.assert_allclose(report["measured_valley_flat_widths_mm"], [3] * 14, atol=0.001)
        np.testing.assert_allclose(report["measured_ridge_heights_above_floor_mm"], [1] * 13)
        np.testing.assert_allclose(report["shelf_ramp_measured_channel_heights_mm"],
                                   np.repeat(np.linspace(2.8, 1.8, 5)[:, None], 14, axis=1))
        self.assertLess(report["rounded_shoulders"]["max_circle_error_mm"], 0.002)
        self.assertEqual(report["lid_slide"]["samples"], 172)
        self.assertLess(report["lid_slide"]["max_collision_mm3"], 0.001)
        self.assertTrue(report["spout_fit_coupon_capture_verified"])
        for variant in ("standard", "relaxed"):
            retention = report[f"{variant}_plug_retention"]
            self.assertLess(retention["upward_removal_without_lid_max_collision_mm3"], 0.001)
            self.assertGreater(retention["forward_8mm_blocked_overlap_mm3"], 0.1)
            self.assertGreater(retention["upward_half_mm_with_lid_blocked_overlap_mm3"], 0.1)
        self.assertFalse(report["physical_print_tested"])
        self.assertFalse(report["bambu_studio_slice_tested"])

    def test_rejects_disconnected_part(self):
        broken = self.tray + cad.cube([170, 0, 0], [171, 1, 1])
        with self.assertRaisesRegex(AssertionError, "Disconnected component"):
            self.verify(parts={"broken": broken})

    def test_rejects_oversized_part(self):
        with self.assertRaisesRegex(AssertionError, "oversized"):
            self.verify(parts={"oversized": cad.cube([0, 0, 0], [181, 1, 1])})

    def test_rejects_part_below_print_bed(self):
        with self.assertRaises(AssertionError):
            self.verify(parts={"below_bed": cad.cube([0, 0, -1], [1, 1, 1])})

    def test_rejects_lid_collision(self):
        with self.assertRaisesRegex(AssertionError, "Lid hits body"):
            self.verify(lid=self.lid.translate([0, 1, 0]))

    def test_rejects_wrong_3mf_units(self):
        path = cad.OUT / "01_tray.3mf"
        original = path.read_bytes()
        try:
            with zipfile.ZipFile(path) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            contents["3D/3dmodel.model"] = contents["3D/3dmodel.model"].replace(
                b'unit="millimeter"', b'unit="inch"')
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in contents.items():
                    archive.writestr(name, data)
            with self.assertRaises(AssertionError):
                self.verify()
        finally:
            path.write_bytes(original)

    def test_rejects_mismatched_stl(self):
        path = cad.OUT / "01_tray.stl"
        original = path.read_bytes()
        try:
            cad.mesh_of(cad.cube([0, 0, 0], [1, 1, 1])).export(path)
            with self.assertRaises(AssertionError):
                self.verify()
        finally:
            path.write_bytes(original)

    def test_published_exports_and_pack(self):
        temporary_out = cad.OUT
        try:
            cad.OUT = SOURCE / "print-files"
            report = self.verify()
        finally:
            cad.OUT = temporary_out
        published = json.loads((SOURCE / "verification.json").read_text())
        for field in ("units", "design_revision", "valleys", "valley_pitch_mm",
                      "valley_flat_mm", "shelf_depth_mm", "ridge_height_above_floor_mm",
                      "physical_print_tested", "bambu_studio_slice_tested"):
            self.assertEqual(report[field], published[field], field)
        self.assertEqual(set(report["parts"]), set(published["parts"]))
        for name, part in report["parts"].items():
            recorded = published["parts"][name]
            np.testing.assert_allclose(part["size_mm"], recorded["size_mm"], atol=0.001, rtol=0)
            self.assertAlmostEqual(part["volume_cm3"], recorded["volume_cm3"], delta=0.001)
            for field in ("watertight", "consistent_winding", "connected_solids",
                          "stl_roundtrip_verified", "core_3mf_roundtrip_verified"):
                self.assertEqual(part[field], recorded[field], f"{name}: {field}")
        # Facet counts and tiny boolean-overlap residuals can vary by platform.
        # verify() still applies the same geometry and collision tolerances.
        pack = (SOURCE / "diamond-art-tray-v7-print-pack.zip").read_bytes()
        self.assertEqual(pack, (SOURCE / "diamond-art-tray-print-pack.zip").read_bytes())
        with zipfile.ZipFile(io.BytesIO(pack)) as archive:
            self.assertIsNone(archive.testzip())
            for name in self.parts:
                for suffix in ("stl", "3mf"):
                    filename = f"print-files/{name}.{suffix}"
                    self.assertEqual(archive.read(filename), (SOURCE / filename).read_bytes())

    def test_main_generates_complete_print_pack(self):
        # Exercise rendering, generated OpenSCAD and packaging in a scratch root.
        for name in ("README.md", "requirements.txt", "build_tray.py"):
            (cad.ROOT / name).write_bytes((SOURCE / name).read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            cad.main()
        report = json.loads((cad.ROOT / "verification.json").read_text())
        self.assertEqual(len(report["parts"]), 8)
        for name in ("tray-preview.png", "spout-fit-preview.png"):
            self.assertGreater((cad.ROOT / name).stat().st_size, 1000)
        self.assertIn('part = "assembly"', (cad.ROOT / "diamond-art-tray.scad").read_text())
        generic = (cad.ROOT / "diamond-art-tray-print-pack.zip").read_bytes()
        self.assertEqual(generic, (cad.ROOT / "diamond-art-tray-v7-print-pack.zip").read_bytes())
        with zipfile.ZipFile(io.BytesIO(generic)) as archive:
            self.assertIsNone(archive.testzip())
            expected = {"README.md", "build_tray.py", "requirements.txt", "diamond-art-tray.scad",
                        "tray-preview.png", "spout-fit-preview.png", "verification.json"}
            expected.update(f"print-files/{name}.{suffix}" for name in self.parts
                            for suffix in ("stl", "3mf"))
            self.assertEqual(set(archive.namelist()), expected)
            for name in expected:
                self.assertEqual(archive.read(name), (cad.ROOT / name).read_bytes())


if __name__ == "__main__":
    unittest.main()

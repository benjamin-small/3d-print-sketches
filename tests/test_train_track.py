"""Exercise the train-track builder without changing published exports."""
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
import trimesh

SOURCE = Path(__file__).resolve().parents[1] / "train-track"
spec = importlib.util.spec_from_file_location("build_track", SOURCE / "build_track.py")
cad = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cad
spec.loader.exec_module(cad)


class TrainTrackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = cad.build()
        cls.report = cad.verify(cls.parts)

    def test_revision_1_dimensions(self):
        report = self.report
        self.assertEqual(report["design_revision"], 1)
        np.testing.assert_allclose(report["parts"]["01_straight_200mm"]["extents_mm"],
                                   [200 + 2*14.6, 57, 10])
        np.testing.assert_allclose(report["parts"]["optional/fit_test_coupon"]["extents_mm"],
                                   [40 + 2*14.6, 57, 10])
        self.assertFalse(report["physical_print_tested"])
        self.assertFalse(report["green_piece_fit_tested"])

    def test_connectors_mate_and_retain(self):
        c = self.report["connector"]
        self.assertGreaterEqual(c["printed_knob_in_printed_socket_min_gap_mm"], 0.4)
        self.assertGreaterEqual(c["estimated_green_knob_in_printed_socket_min_gap_mm"], 0.3)
        self.assertGreaterEqual(c["printed_knob_in_estimated_green_socket_min_gap_mm"], 0.2)
        self.assertLess(c["seated_overlap_mm3"], 1e-3)
        self.assertGreater(c["overlap_after_3mm_pull_mm3"], 1.0)
        straight = self.parts["01_straight_200mm"]
        # Two full straights also mate, and the ends are 180-degree symmetric.
        self.assertLess(cad.mate(straight, cad.LENGTH, straight), 1e-3)
        turned = straight.rotate([0, 0, 180]).translate([cad.LENGTH, 0, 0])
        self.assertLess((straight ^ turned).volume() - straight.volume(), 1e-3)
        self.assertGreater((straight ^ turned).volume(), straight.volume() - 1e-3)

    def test_handedness_matches_green_piece(self):
        # Looking outward from the far end (+x), the knob is on the left (+y).
        knob = cad.at_end(cad.knob_2d(), cad.LENGTH, "far")
        lo, hi = knob.bounds()[:2], knob.bounds()[2:]
        self.assertGreater((lo[1] + hi[1])/2, 0)
        socket = cad.at_end(cad.socket_2d(), cad.LENGTH, "far")
        self.assertLess(sum(socket.bounds()[1::2])/2, 0)

    def test_fit_checks_reject_bad_geometry(self):
        too_big = cad.knob_shape(cad.KNOB_CENTER, cad.KNOB_SEMI_X + 2, cad.KNOB_SEMI_Y + 2,
                                 cad.KNOB_NECK)
        self.assertEqual(cad.min_gap(too_big.rotate(180), cad.socket_2d()), -1.0)
        self.assertGreater(cad.min_gap(cad.rect(-1, -1, 0, 0), cad.rect(-5, -5, 5, 5)), 3.9)
        original = cad.SOCKET_SEMI_Y
        try:
            cad.SOCKET_SEMI_Y = cad.KNOB_SEMI_Y
            with self.assertRaises(AssertionError):
                cad.verify(self.parts)
        finally:
            cad.SOCKET_SEMI_Y = original

    def test_short_piece_has_no_slots(self):
        self.assertIsNone(cad.slots(30))
        self.assertIsNotNone(cad.slots(cad.LENGTH))

    def test_main_exports_and_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_root, original_out = cad.ROOT, cad.OUT
            cad.ROOT = Path(tmp)
            cad.OUT = cad.ROOT / "print-files"
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    cad.main()
                report = json.loads((cad.ROOT / "verification.json").read_text())
                self.assertEqual(report, json.loads(json.dumps(self.report)))
                for name in self.parts:
                    stl = trimesh.load(cad.OUT / f"{name}.stl")
                    self.assertTrue(stl.is_watertight)
                    with zipfile.ZipFile(cad.OUT / f"{name}.3mf") as archive:
                        self.assertIn('unit="millimeter"',
                                      archive.read("3D/3dmodel.model").decode())
                self.assertTrue((cad.ROOT / "track-preview.png").stat().st_size > 10000)
                generic = cad.ROOT / "train-track-print-pack.zip"
                versioned = cad.ROOT / "train-track-v1-print-pack.zip"
                self.assertEqual(generic.read_bytes(), versioned.read_bytes())
                with zipfile.ZipFile(generic) as archive:
                    self.assertIsNone(archive.testzip())
                    names = set(archive.namelist())
                self.assertIn("print-files/01_straight_200mm.3mf", names)
                self.assertIn("print-files/optional/fit_test_coupon.stl", names)
                self.assertIn("verification.json", names)
            finally:
                cad.ROOT, cad.OUT = original_root, original_out

    def test_published_exports_match_report(self):
        report = json.loads((SOURCE / "verification.json").read_text())
        self.assertEqual(report["design_revision"], cad.REVISION)
        for name, part in report["parts"].items():
            mesh = trimesh.load(SOURCE / "print-files" / f"{name}.stl")
            np.testing.assert_allclose(mesh.extents, part["extents_mm"], atol=0.01)


if __name__ == "__main__":
    unittest.main()

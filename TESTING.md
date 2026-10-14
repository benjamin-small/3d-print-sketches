# Testing

Use Python 3.14 from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
.venv/bin/python -m coverage xml
```

Measured on 2026-10-13 with Python 3.14.7 and coverage.py 7.16.2: **99.3%
statement coverage** of `diamond-art-tray/build_tray.py` (422 of 425 statements),
with **9 passing tests**. The terminal report rounds this to 99%. `.coveragerc`
requires at least 95%; CI measures the same source and uploads `coverage.xml`.
Re-run the commands and update this baseline when source or test scope changes.

## Test scope

- Regenerate all eight parts, including normalized print orientations, and run
  the builder's watertightness, winding, connectedness and build-volume checks.
- Verify revision 7's dimensions, 14 valley bottoms, 13 ridge heights, rounded
  shoulders and continuous shelf ramp.
- Check the full sampled lid-removal path, both stopper fits, vertical removal,
  closed-lid capture and small spout fixtures.
- Exercise STL and millimeter-unit core-3MF export/import, then independently
  validate committed exports and their verification report.
- Render previews, generate OpenSCAD and assemble both print-pack ZIPs. Check
  archive integrity, expected entries and byte equality with generated files.
- Reject disconnected solids, oversized or below-bed parts, lid collisions,
  wrong 3MF units and mismatched STL dimensions.

Generated test artifacts stay in temporary directories that are removed after
the suite. Tests read the published revision 7 files but do not rewrite them.

## Limits

Coverage measures executed Python statements, not proof of printability or every
possible geometry configuration. The three uncovered statements are two renderer
guards for off-screen/degenerate projected triangles and the script entrypoint.
The suite executes `main()` directly, including rendering and packaging.

Tests cover the current default dimensions. They do not validate Bambu Studio or
OrcaSlicer import/slicing, printer settings, physical fit, warping, durability,
sorting performance, or an independent OpenSCAD render. These require separate
checks. `physical_print_tested` and `bambu_studio_slice_tested` remain false.

GitHub's `CAD tests` check runs this suite on Linux/Python 3.14 for pull requests
and pushes to `main`. CodeQL analyzes Python separately; it does not analyze the
generated OpenSCAD or establish mechanical safety.

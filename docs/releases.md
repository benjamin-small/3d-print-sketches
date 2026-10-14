# Releases

Printable designs use numbered geometry revisions, currently diamond-art tray
revision 7. A geometry or fit change increments the revision in the builder,
verification report, project README, preview labels and revision-specific ZIP.
Documentation and test changes alone do not increment the geometry revision.

Release notes describe changed dimensions, clearances, behavior and which parts
must be reprinted. Explain whether older lids, plugs or fixtures are compatible.
Record slicer and physical-print evidence explicitly; digital checks establish
geometry, not print success. Never silently replace an older revision's geometry.

Before a release, run the repository's documented validation commands, confirm generated artifacts are current, and verify the release from a clean checkout.

Regenerate exports with `build_tray.py`, inspect previews and `verification.json`,
then compare the generic and revision-specific ZIPs and their contents. Publish
source, STL, model-only 3MF, generated OpenSCAD, previews and verification together.
Include the repository's MIT license when redistributing source or design files.

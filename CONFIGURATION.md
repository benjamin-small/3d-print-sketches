# Configuration

The builder and tests use Python 3.14. CAD dependencies are pinned in
`diamond-art-tray/requirements.txt`; test tooling is pinned in
`requirements-dev.txt`. No credentials, network service, or `.env` file is needed
to build the tray or run tests after installing dependencies.

Dimensions are millimeters. Edit the constants near the top of
`diamond-art-tray/build_tray.py` for tray size, valleys, shelf, spout, lid tracks,
and stopper clearances. The Python builder is the source of truth; generated
OpenSCAD does not independently parameterize these constants. See
[docs/releases.md](docs/releases.md) before changing published geometry.

The builder writes beside its source: `print-files/`, `verification.json`,
generated OpenSCAD, previews, and both current ZIPs. It replaces these outputs.
Tests redirect all generated files into disposable temporary directories.

Optional environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `MPLCONFIGDIR` | Matplotlib cache/config directory; set it to a writable location on your host. | `/private/tmp/diamond-tray-matplotlib` |
| `MPLBACKEND` | Matplotlib backend; CI selects `Agg`. The builder also selects `Agg` when rendering previews. | Builder uses `Agg`. |

For Linux or other hosts, set `MPLCONFIGDIR=/tmp/diamond-tray-matplotlib` before
building if `/private/tmp` is unavailable. CI uses its runner temporary directory.

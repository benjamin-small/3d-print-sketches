# Contributing

Open an issue before substantial changes so scope and expected behavior are clear. Keep pull requests focused and include tests or documentation for changed behavior.

## Local setup

Use Python 3.14 from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Each design belongs in its own directory with editable source, exports, previews,
dimensions, units, and validation notes. Edit `diamond-art-tray/build_tray.py` for
tray geometry; OpenSCAD and model exports are generated from it.

## Validation

```sh
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
```

See [TESTING.md](TESTING.md) for coverage and test scope. For CAD changes, also
run `../.venv/bin/python build_tray.py` from `diamond-art-tray/`, inspect previews
and `verification.json`, and include matching model exports and print packs.
Document slicer and physical-print results separately from digital verification.
Print small fit fixtures before claiming assembly fit.

Contributions to source and design files use the [MIT license](LICENSE).

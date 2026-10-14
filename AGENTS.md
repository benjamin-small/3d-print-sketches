# Agent instructions

## Purpose

Make focused, reviewable changes to 3d-print-sketches. Preserve existing behavior unless the issue or pull request explicitly authorizes a change.

## Setup

At session start, run `$poietic-harness-start`. Initial user-scope setup is authorized.
Use Jev by default for suitable bounded structured decisions; read
`/Users/bsmall/.agents/skills/jev/SKILL.md` and pass its entrypoint and authorized
execution access to subagents when delegation is requested. Use deterministic
checks for exact CAD geometry and fit.

Use Python 3.14. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Validation

```sh
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
```

The coverage gate is 95% of `diamond-art-tray/build_tray.py` statements. Tests
write into temporary directories. See `TESTING.md` for scope and limitations.

For authorized model changes, regenerate from the project directory:

```sh
cd diamond-art-tray
../.venv/bin/python build_tray.py
```

Review `verification.json`, previews, STL/3MF files and print-pack contents.
Update the revision and its documentation together. Keep the current generic
pack and revision-specific pack consistent.

## Constraints

- Do not commit credentials, generated secrets, or local environment files.
- Keep documentation and tests synchronized with behavior changes.
- Do not overwrite unrelated work in a dirty working tree.
- Preserve revision 7 exports when making documentation or test-only changes.
- Keep millimeter units and model-only 3MF output; do not add printer G-code.
- Do not claim slicer or physical print acceptance from digital geometry checks.
- Require the `CAD tests` CI check before merging. Keep automated review issues
  open until the changes land and Repository Keeper verifies them.

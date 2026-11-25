# Train track

A straight toy-train track designed to connect to a lime-green curved piece
from a commercial plastic toy-train system (2026 production). It replaces a
downloaded third-party straight that did not fit. That model's knobs are about
7 mm across, against about 17 mm on the green piece, and its body is about 13 mm
narrower.

![Track preview](track-preview.png)

**Revision 2.** It is sized from caliper measurements of the green piece,
taken on 2026-11-25. Revision 1 was sized from photos, and its coupon missed:
the green knob would not go into its socket, its knob pulled out of the green
socket, and the green piece sat higher. Print the revision 2 coupon before the
full straight.

## Print files

Download the [revision 2 print pack](train-track-v2-print-pack.zip) or use these
files directly:

| File | Part |
|---|---|
| `print-files/optional/fit_test_coupon.3mf` | 40 mm piece with both connector ends. Print this first (about 16 cm³). |
| `print-files/01_straight_200mm.3mf` | Straight, 200 mm from end face to end face (230 mm including knobs, about 73 cm³). |

Print flat, bottom down, in millimeters. The model has no overhangs, so it
needs no supports. If your printer has elephant's foot, correct it in the
slicer, because a flared first layer tightens the knob fit.

## Fitting the coupon

1. Drop the coupon's knob into the green piece's socket from above, then the
   green knob into the coupon's socket. Both should drop in with light play and
   should not pull apart.
2. Check the step at the joint. The rib tops are 7.5 mm high and the rims 10.5 mm.
3. If something is off, change the constants at the top of `build_track.py` and
   rebuild:
   - The knob won't go in: reduce `KNOB_SEMI_Y`/`KNOB_SEMI_X`, or narrow `KNOB_NECK`.
   - The green knob won't go in: increase `SOCKET_SEMI_Y`, or widen `SOCKET_MOUTH`.
   - The connectors don't line up: adjust `KNOB_OFFSET` and `SOCKET_OFFSET`.
   - The joint has a step: adjust `BAND_TOP`, `RIM_TOP` or `DECK`.

## Measurements of the green piece

Measured with calipers. Edge distances were taken from the base edge.

| Feature | Measured |
|---|---|
| Width | 46 mm across the top, 55 mm at the base |
| Ribbed bands | 10 mm wide, 7.5 mm high to the rib tops |
| Rims | 5.5 mm wide, 10.5 mm high |
| Center channel | 11.5 mm wide, with 9.1 mm slots at a 17.5 mm pitch |
| Socket | 18.16 mm across, 12.6 mm mouth, 15.7 mm deep; 12 mm from the edge to the hole, 15.2 mm from the edge to the mouth |
| Knob | 17.8 mm across the ridge tips, 13 mm neck, 16 mm reach, 7.4 mm thick, 12 mm from the edge; ridges about 1.5 mm |
| Handedness | Knob on the left, looking outward from an end |

From these, the green socket is centered 6.4 mm off the centerline and the
knob 6.6 mm. The channel floor height, slot length, curve length and the
neck's position on the knob were not measured. The model keeps 3 mm, 9.5 mm,
200 mm and an assumed neck position for those.

## Dimensions

| Feature | Value |
|---|---|
| Footprint | 55 mm wide at the base, 46 mm at the top |
| Running bands | Rib tops at 7.5 mm (7.1 mm band with 0.4 mm ribs), from 5.75 to 16 mm off center |
| Rims | 10.5 mm high, 5.5 mm flat top with a 1.5 mm bevel to the edge, 32 mm clear width |
| Center channel | 11.5 mm wide, 3 mm floor, 9.1 × 9.5 mm slots at a 17.5 mm pitch |
| Knob | 17.5 mm wide head, 12 mm neck, reaches 15.1 mm, 7.2 mm high, 6.4 mm off center |
| Socket | 18.9 mm wide, 14.3 mm mouth, 16.8 mm deep, 6.6 mm off center, through the full height |

`verification.json` records the digital checks:

- Every part is a single watertight solid.
- Minimum clearances, from the knob's outline to the socket's:
  - printed knob in printed socket: 0.32 mm
  - measured green knob in printed socket: 0.32 mm
  - printed knob in measured green socket: 0.30 mm
- Pulled 2 mm back out, each knob catches on the lip of the socket it sits in.
- A seated joint has zero overlap, and pulling it 3 mm apart collides with the
  lip.

Physical fit, slicing and the fit to the real green piece are untested.

## Rebuild

From this directory:

```sh
../.venv/bin/python build_track.py
```

This rewrites `print-files/`, `verification.json`, `track-preview.png` and both
print packs.

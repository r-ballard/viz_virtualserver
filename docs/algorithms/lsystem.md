# L-system geometry and pen layers

This implementation uses L-system/turtle *semantics* only. It does not use a turtle graphics
library and does not draw while interpreting commands. Each generation is expanded, converted
into numeric points, and accumulated into connected polylines. Rendering happens afterward.

## Geometry commands

- `F` draws forward by default. Additional drawing symbols can be supplied with `draw_symbols`.
- `f` moves forward without drawing by default. Additional move symbols can be supplied with
  `move_symbols`.
- `+` rotates counterclockwise by `angle` degrees.
- `-` rotates clockwise by `angle` degrees.
- `|` rotates 180 degrees.
- `[` saves position and heading and begins a branch.
- `]` closes the branch and restores the saved state.
- Other symbols participate in rewriting but are ignored by geometry generation.

Branch boundaries intentionally split paths. This avoids introducing false line segments when a
branch returns to its parent and lets SVG/HPGL exporters operate on connected polyline runs.

## API

Generate JSON geometry:

```bash
curl -sS http://localhost:5699/LSystem \
  -H 'content-type: application/json' \
  --data @examples/lsystems/plant.json
```

Generate stroke-only SVG:

```bash
curl -sS 'http://localhost:5699/LSystemSvg?padding=10&stroke_width=1' \
  -H 'content-type: application/json' \
  --data @examples/lsystems/plant.json \
  > plant.svg
```

The SVG contains one top-level `<g>` per physical pen with a unique stroke color and
`data-pen` metadata. Within each pen group, geometry remains tagged by generation.

## Pen assignment

The DPX-3300 has eight physical pen positions, so API pen numbers are constrained to 1-8.
If `pen_layers` is omitted, generations are divided as evenly as possible among up to eight
pens. For generations 0 through 16, the automatic ranges are:

```text
pen 1: 0-1
pen 2: 2-3
pen 3: 4-5
pen 4: 6-7
pen 5: 8-9
pen 6: 10-11
pen 7: 12-13
pen 8: 14-16
```

Explicit assignments can be supplied when the actual pens/colors in the carousel differ:

```json
"pen_layers": [
  {"pen": 1, "start_generation": 0, "end_generation": 1, "color": "#000000"},
  {"pen": 2, "start_generation": 2, "end_generation": 3, "color": "#D62728"},
  {"pen": 3, "start_generation": 4, "end_generation": 5, "color": "#1F77B4"}
]
```

Explicit layers must cover every requested generation exactly once.

## Expansion limit

Rewriting can grow exponentially. `max_symbols` defaults to 1,000,000 and is checked while each
new generation is assembled, before the oversized string is created. Only the current expanded
generation is retained; previous generation strings are discarded after their geometry is built.

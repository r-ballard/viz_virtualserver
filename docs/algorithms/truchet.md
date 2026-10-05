# Truchet tiles

`truchet` generates a seeded square-tile pattern as connected vector curves,
clipped to each target polygon. It implements the non-overlapping square subset
of Walter, Ligler, and Gursoy's [Truchet Tile Grammar](https://doi.org/10.1007/s00004-024-00779-8).
Tile construction, complementary region matching, and motif substitution are
separate operations; this is a compiled grammar rather than a rule interpreter.

## Generate artwork

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-classic.json --output-dir output/truchet-classic
```

Open `design.svg` or an SVG under `surfaces/`. Use `truchet-asymmetric.json` for
independent corner curvature, or `truchet-polygon-targets.json` for square,
triangle, and concave canvases. Monochrome examples emit `truchet-curves`.
Declare one or more curve layers; their IDs must be unique and nonblank.

## Controls

| Parameter | Default | Range and meaning |
| --- | --- | --- |
| `tile_size` | 10 | Positive finite square side length, in domain units |
| `arc_a` | 0.20710678118654757 | First corner's signed sagitta/chord ratio; [-0.20710678118654757, 0.45] |
| `arc_b` | 0.20710678118654757 | Opposite corner's ratio; same range |
| `curve_tolerance` | 0.02 | Positive finite maximum arc-to-chord error, in domain units |

Positive curvature bows toward the tile center; negative curvature bows toward
the corner. Zero produces straight diagonal connections. Classic defaults give
quarter circles. Independent arc values give asymmetric motifs. An outward arc
beyond the negative quarter-circle limit would escape its square and is rejected.
Unknown fields, numeric strings, booleans, and nonfinite numbers are rejected.

The grid begins at each polygon's minimum x and y and covers its bounding
rectangle with whole tiles. Tiles have compatible region identities on shared
edges, even though output contains only their boundary curves. Complementary
states exchange regions without changing geometry. Rotations remain distinct
so each corner retains its own arc control. The seed comes from the existing job,
pass, and domain seed contract. Changing curvature or tolerance preserves the
symbolic tile arrangement. Domains generate independently, including overlapping
domains, and composition transforms are handled by the existing bundle workflow.

Interior tile endpoints join into open chains or closed loops before clipping.
No tile borders or polygon perimeter are added by default. Clipping can split chains and
open loops; exterior gaps are never bridged. Arbitrary curvature guarantees
endpoint continuity, but can produce kinks at joins. Classic defaults give smooth
ordinary tile joins. Sampling estimates are capped at 2,000,000 points per domain;
bounding grids above 100,000 tiles fail before allocation.

## Multi-scale curves

`truchet-multiscale` adds recursively subdivided squares and a fixed winged motif
with two connections per edge, at one-third and two-thirds. It is a separate
algorithm; the classic controls and defaults above remain available.

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-multiscale.json --output-dir output/truchet-multiscale
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-multiscale-polygons.json --output-dir output/truchet-multiscale-polygons
```

| Parameter | Default | Range and meaning |
| --- | --- | --- |
| `base_tile_size` | 40 | Positive finite largest square side, in domain units |
| `max_depth` | 3 | Strict integer 0–6; minimum side is base size divided by 2 to this power |
| `split_probability` | 0.45 | Finite 0–1 chance of subdividing each eligible square |
| `curve_tolerance` | 0.02 | Positive finite maximum sampling error, in domain units |

Depth zero or probability zero yields a uniform tiling; probability one yields
all minimum-size tiles. Intermediate values permit mixed sizes, without forcing
a split. The examples use seeded mixed arrangements. Tile orientation and
subdivision use independent stable hash streams from the existing domain seed;
changing tolerance preserves the arrangement. `tile_size`, `arc_a`, and `arc_b`
are not parameters of this fixed circular motif family.

The implementation independently adapts the winged-region construction described
in Carlson's [Multi-Scale Truchet Patterns](https://christophercarlson.com/portfolio/multi-scale-truchet-patterns/)
and [Bridges paper](https://archive.bridgesmathart.org/2018/bridges2018-39.pdf).
Regions extend beyond each content square and are composited from coarse to fine,
inverting their identity with depth. Only the resulting boundaries are exported;
regions are internal geometry, with optional hatching described below. Equal-depth operations are
batched after verifying equivalence with sequential painting. Shared circles use
a common angular sampling mesh to prevent artificial seams.

Each polygon generates independently in a frame anchored to its minimum x/y.
A full base-tile halo supplies wing interactions before clipping. Extracting
boundaries before polygon clipping avoids introducing polygon perimeter strokes.
Open curves end at the target boundary; closed curves remain loops. Exact tangent
contacts that contain no linework are discarded. The default examples use `truchet-curves`.

For topology, effective tolerance is capped at the smallest leaf side / 100.
Composition uses base-tile units and a precision grid of
`min(effective_normalized_tolerance / 16, smallest_normalized_side / 1024)`.
Three quarters of the error budget goes to arc sampling; snapping and coordinate
round trips fit within the remaining quarter. Requests below reliable floating
resolution fail explicitly. The 10,000-leaf limit includes the halo and is lower
than classic tracing because polygon Boolean operations cost more. Sampling is
preflighted against 2,000,000 points per domain before motif allocation.

Immutable internal leaf records retain root indices, quadrant addresses, parents,
bounds, depth and orientation for future placement work. They are not a persisted
tile catalog. Shared-coordinate generation, separating individual tile leaves,
and physical imposition remain future work. Separating individual leaves
will require a decision about cross-tile wings and clipping.

## Polygon outlines and artwork inset

Both generators support optional borders and clearance inside each target polygon.
The target polygons remain independent artwork surfaces; these options do not
separate the individual square tiles or change their placement.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `artwork_inset` | 0 | Nonnegative finite inward clipping distance, in SVG design units |
| `outline_layer_id` | null | ID of a declared logical layer used only for polygon outlines in this pass |

For one artwork channel and a border, declare:

```json
"parameters": {"artwork_inset": 5.0, "outline_layer_id": "polygon-border"},
"logical_layers": [
  {"id": "truchet-curves", "label": "Curves"},
  {"id": "polygon-border", "label": "Polygon borders"}
]
```

At least one curve channel must remain besides outline and hatch layers. The outline
layer is excluded from seeded curve-color assignment, wherever it occurs in the
declared list. Adding a border therefore does not recolor the existing curves.
The CLI automatically publishes a neutral bundle for curves plus outlines, even
when the artwork has only one color. Border paths expose `polygon-outline` as
their semantic feature role and can be mapped to a separate physical pen downstream.

The generator first builds the same seeded arrangement and curves for the original
domain, then clips the artwork inward. Insets do not rescale, regenerate, or reseed
the pattern, and every surviving fragment retains its original color. Polygon
offsets use straight miter joins (with GEOS's default miter limit of 5). Concave
insets may split into multiple regions; those regions are clipped independently
without connecting across gaps. An inset that removes the entire polygon area,
or is too small to represent reliably at the domain coordinates, fails explicitly
without publishing a bundle. A surviving inset region need not contain any curves.

The border is one closed path following the original polygon vertices, emitted
once per target domain per opted-in pass. It stays at the original edge; the inset
boundary is not plotted. With multiple passes on the same polygon, enable its
outline in only one pass to avoid duplicate border strokes.

Generate the square, triangle, and concave panel example:

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-bordered-polygons.json --output-dir output/truchet-bordered-polygons
```

Its composition transforms demonstrate separated polygons and a five-unit artwork
inset. These distances are SVG design units, not millimeters. Page placement,
physical spacing, pen width allowances, and conversion to millimeters belong to
the downstream imposition workflow. Omitting both options preserves existing output.

## Multicolor curve channels

Both generators accept any ordered list of unique, nonblank curve-layer IDs.
After excluding optional outline and hatch layers, one curve layer keeps the monochrome
behavior. Multiple curve layers assign each complete
curve or loop to one channel using a stable hash of its component index and the
existing domain seed. Declare, for example:

```json
"logical_layers": [
  {"id": "curve-blue", "label": "Blue channel"},
  {"id": "curve-orange", "label": "Orange channel"},
  {"id": "curve-green", "label": "Green channel"}
]
```

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-multicolor.json --output-dir output/truchet-multicolor
```

This example places classic and multi-scale artwork side by side. Assignment
happens before polygon clipping, so separated fragments of the same curve keep
one channel. It uses an independent hash stream and does not change subdivision,
orientation, curvature, or linework. Repeating a job gives the same assignments;
renaming channels preserves assignment by their ordered positions. Colors are
seeded, without balancing stroke length or guaranteeing every channel is used
in a small drawing. Geometry/tolerance changes can change component indexing;
these IDs are internal and are not a persistent curve catalog.

When any Truchet pass declares multiple channels, a Truchet-only job exports the
existing `viz-logical-layers/v1` neutral contract automatically. Its audit contains
the ordered channel catalog and per-surface inventory; SVG paths carry semantic
IDs and channel provenance. Shared channel IDs across passes must have consistent
labels. Unused channels are omitted from the catalog. All-single-channel jobs keep
their legacy export format. A multi-channel Truchet job mixed with other generator
families is rejected explicitly; export those families separately for now.

Neutral SVG groups receive the existing preview palette, so the generated SVG is
already colored for inspection. These preview colors are not physical pen
assignments. Map channel IDs to actual pen slots using the downstream neutral-layer
workflow. Layer labels do not imply ink colors. No new palette, seed, projection,
or color-count job parameter is needed: the declared layers are the channels.
Colored solid SVG fills remain separate future work.

## Plotter hatching of multiscale regions

Hatching uses the [shared fill-effects library](../reference/fill-effects.md),
which other generators can call with their own composed polygon regions.
Truchet retains responsibility for region selection, frames, and logical layers.

`truchet-multiscale` can render a composed region as parallel or crosshatched open strokes.
Curves remain present and can have their existing single or multiple color channels.
Hatching is opt-in through a separate declared hatch layer:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `hatch_layer_id` | null | Declared logical layer used only for hatching in this pass; null disables hatching |
| `hatch_effect` | parallel-hatch | `parallel-hatch` uses one family; `crosshatch` adds a perpendicular family with the same spacing |
| `hatch_spacing` | 2 | Positive finite perpendicular distance between hatch rows, in SVG design units |
| `hatch_angle` | 45 | Finite angle in degrees; 0 is horizontal, 90 vertical, positive rotates clockwise in SVG coordinates |
| `hatch_region` | painted | `painted` selects the final composed region; `unpainted` selects its complement inside the polygon |

The hatch layer must differ from the outline layer, and at least one curve layer
must remain. Like outlines, the hatch layer is excluded from seeded curve-color
assignment. Enabling or changing hatching does not alter tile subdivision,
orientation, boundary curves, or their color assignments. Effect, spacing, angle, and
region controls are validated but do not affect output while `hatch_layer_id`
is null. These controls are specific to `truchet-multiscale`; classic region
reconstruction has not yet been implemented.

The generator composes and unions all tile regions before hatching, using the
same depth-parity painting as the boundary curves. It does not hatch each tile
individually. Scan strokes cross tile joins without seams and split at region
holes, disconnected pieces, and polygon gaps; those gaps never receive connecting
strokes. Tangent point contacts and fragments that collapse after coordinate
conversion are discarded. Each stroke is open, with no solid
SVG fill. Hatches expose the semantic role `truchet-hatch` in the existing neutral
bundle, so their channel can be mapped or omitted independently downstream.

Hatch rows use a regular lattice anchored to each polygon's minimum x/y, in the
same independent frame as tile placement. Angles repeat every 180 degrees. The
artwork inset clips hatches as well as curves without moving the lattice; the
polygon border remains at its original edge. A large spacing can leave a small
region with no hatch strokes, in which case its unused layer is omitted from the
export catalog. Generation rejects more than 100,000 scan rows or 2,000,000 hatch
points per domain, combined across both families for crosshatch, and spacing below
reliable floating-point resolution in
either normalized or domain coordinates fails
explicitly. Hatch points have their own limit in addition to the motif sampling
limit. These guards fail without publishing a partial bundle.

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-hatching.json --output-dir output/truchet-hatching
uv run --locked viz-domain-bundle examples/domain-jobs/truchet-crosshatching.json --output-dir output/truchet-crosshatching
```

The example hatches the painted region of a square and the unpainted region of
a triangle, with separate boundaries, hatch strokes, and polygon borders. The
crosshatching example uses perpendicular families at 4-unit spacing. Its
`hatch_angle` specifies the first family; the second is 90 degrees clockwise.
Both families share the hatch layer and existing `truchet-hatch` provenance;
crossings remain separate strokes. SVG
preview colors are not physical pen assignments. Spacing is measured between
stroke centerlines; pen-width compensation and conversion to millimeters remain
downstream concerns. Stippling, dithering, and stroke-order
optimization remain future work.

## Later work

- More multi-scale motif families and spatial subdivision controls.
- Classic filled regions: reconstruct and union matching regions. Multiscale
  parallel hatching and crosshatching are available; stippling and dithering remain
  future work. Python is the preferred reproducible
  route; consider Inkscape extensions or scripted finishing as another option.
- Overlapping motifs and the paper's R7 third region field.
- Triangle and hexagon tile grammars. A triangular target polygon currently
  clips square tiles; it does not select triangular tiles.
- Additional arrangement policies and derivation inspection.
- Numerical improvement: extraordinarily small curvature/tolerance combinations
  (for example `arc_a=1e-310`, `curve_tolerance=1e-312`) can overflow the radius
  calculation and incorrectly report a sampling limit. Ordinary near-straight
  curves use a stable straight-segment shortcut. A future dimensionless sampler
  can support these extreme inputs.

### Triangular reference

The user supplied [this Processing Python sketch](https://pastebin.com/NQuAnL2S)
as additional context. It starts with six equilateral triangles in a hexagonal
field, recursively splits each triangle into four half-scale children, and draws
concentric corner arc families. The middle child reverses triangle orientation;
line counts halve while global line spacing stays fixed. These ideas can inform
future multi-scale triangular work, but are not used in this square grammar.
Porting should review its recursion loop: during mandatory subdivision iterations
it also performs the probabilistic subdivision pass, potentially duplicating
children. Processing drawing, masking, and border behavior also need explicit
vector equivalents rather than a direct source transplant.

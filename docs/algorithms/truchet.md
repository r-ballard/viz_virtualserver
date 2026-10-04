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
triangle, and concave canvases. All examples emit the `truchet-curves` layer.
The domain pass must declare exactly that logical layer.

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
No tile borders or polygon perimeter are added. Clipping can split chains and
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
regions are internal geometry, with no plotted fills. Equal-depth operations are
batched after verifying equivalence with sequential painting. Shared circles use
a common angular sampling mesh to prevent artificial seams.

Each polygon generates independently in a frame anchored to its minimum x/y.
A full base-tile halo supplies wing interactions before clipping. Extracting
boundaries before polygon clipping avoids introducing polygon perimeter strokes.
Open curves end at the target boundary; closed curves remain loops. Exact tangent
contacts that contain no linework are discarded. All output uses `truchet-curves`.

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
tile catalog. Shared-coordinate generation, separated polygon panels, margins,
borders and physical imposition remain future work. Separating individual leaves
will require a decision about cross-tile wings and clipping.

## Later work

- More multi-scale motif families and spatial subdivision controls.
- Filled regions: reconstruct and union matching regions, then generate hatching,
  crosshatching, stippling, or dithering. Python is the preferred reproducible
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

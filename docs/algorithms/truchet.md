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

## Later work

- Mixed tile sizes: Carlson-style connection rules and scale transitions.
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

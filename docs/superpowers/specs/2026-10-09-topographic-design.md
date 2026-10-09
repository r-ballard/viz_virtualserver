# Synthetic topographic artwork

## Status and intent

Concept approved October 9, 2026; this written spec awaits user review.
The user wants natural-looking topographic artwork in the existing polygon
and plotter workflow, inspired by the geometric drawing application's terrain
generator. Synthetic terrain comes first. Smoothing is configurable.

This is an architectural addition: introduce reusable scalar-field sampling
and contour extraction, then a `topographic` domain algorithm. Preserve the
existing concentric generators and their output. Each polygon initially receives
independent artwork, consistent with the user's imposition preference.

Success means deterministic natural terrain, continuous contour paths, useful
smoothing controls, convex/concave polygon clipping, distinct major/intermediate
logical channels, and ordinary bundles accepted by plotter-workflow.

## Reference and alternatives

Reference sources inspected on October 9:

- [Terrain generator](https://github.com/jarvisar/geometric/blob/master/web/geometric-web-app/src/generators/topo.js),
  source SHA `2d6255ab07aac5939d9b059b72a4899eb8b5adbc`.
- [Contour extraction](https://github.com/jarvisar/geometric/blob/master/web/geometric-web-app/src/lib/contours.js),
  source SHA `ed57f1a671a439fb529d66519c92af2a22d61291`.

The reference builds synthetic fractal terrain, optionally warps its coordinates,
samples heights, and stitches marching-squares segments into continuous paths.
It also offers index contours, smoothing, and decorative contour thinning.
Implement these mathematical ideas independently in Python; do not copy or
bundle reference code, assets, GUI, or physical pen settings.

Chosen approach: contours of one shared height field. Unlike independently
distorted concentric rings, this represents interacting hills, valleys, ridges,
and saddles coherently. Real elevation rasters would fit the sampling boundary
later, but geographic import and coordinate systems add unnecessary first-release
scope. Summed radial hills are another future field source, not the initial preset.

## Scope

Include seeded natural terrain, coordinate warping, field smoothing, evenly
spaced normalized elevation levels, index contours, conservative simplification,
polygon clipping, strict validation, bounded resource use, CLI registration,
documentation, and a visually inspected example sheet.

Defer actual geographic elevation data, elevation-band regions/fills, contour
labels, GUI controls, physical pen widths, automatic thinning for pen clearance,
shared terrain across imposed polygons, rounded-hill presets, and terrain-gradient
adapters for vector-field marks. No plotter-workflow code changes are required.
Existing text and physical imposition remain downstream operations.

## Components and contracts

Create `viz_virtualserver/scalar_fields/` with focused field, sampling, and contour
modules, and `viz_virtualserver/generators/topographic/` with parameters and service.
Exact module splits belong in the implementation plan.

1. A scalar-field protocol exposes `sample(x, y) -> float`. Values must be finite;
   coordinates use the current intrinsic design space. It carries no polygon,
   SVG, logical layer, or physical pen knowledge. Keep it separate from the
   existing vector-field protocol rather than changing that interface.
2. A seeded terrain evaluator implements deterministic gradient noise and a
   normalized fractal sum. Fixed octave frequency multiplier is 2; `roughness`
   controls octave amplitude decay. Independent seed-derived low-frequency
   fields displace coordinates for optional domain warping. No global RNG state
   or process-randomized Python hash participates in generation.
3. An immutable sampled-field record holds origin, grid dimensions, x/y step,
   finite heights, and range. Uniform grid spacing fits the expanded bounding
   rectangle exactly. Gaussian filtering works on sampled heights before their
   final normalization; existing SciPy is sufficient and no dependency is added.
4. Contour extraction consumes a sampled field and explicit levels, returning
   elevation-associated continuous polylines with an explicit closed flag.
   It has no styling or domain ownership responsibilities.
5. `TopographicDomainAlgorithm` adapts these components to existing
   `DomainAlgorithm`, `AlgorithmContext`, `DesignResult`, and `VectorPath` contracts.
   Register `topographic` in `viz_virtualserver/cli/domain_bundle.py`.

Return domain-frame paths and no derived domains. Use the existing per-domain
seed. Do not add job schema fields or alter bundle contracts. Generation is
independent of target ordering and other passes. Translating the same polygon,
with the same domain identity and seed, translates its artwork without changing
its intrinsic pattern. Local noise coordinates start at the polygon bounds origin.
Explicit shared composition-frame terrain is outside this version; reject that
mode with a clear error rather than accidentally generating separate aligned maps.

## Parameters

All lengths are intrinsic domain units, not millimeters. Defaults target a
roughly 100-by-100 example domain; other scales should tune the length parameters.

| Parameter | Default | Contract |
| --- | --- | --- |
| `terrain_scale` | 30.0 | Finite positive base noise wavelength |
| `octaves` | 5 | Strict integer, 1 through 8 |
| `roughness` | 0.45 | Finite value in [0, 1], octave amplitude decay |
| `warp_strength` | 0.35 | Finite value in [0, 1], displacement relative to terrain scale |
| `terrain_smoothing` | 1.0 | Finite nonnegative Gaussian sigma in domain units |
| `sample_spacing` | 0.5 | Finite positive maximum grid step in domain units |
| `contour_count` | 30 | Strict integer, 1 through 120 |
| `index_every` | 5 | Strict integer, 1 through 120 |
| `simplify_tolerance` | 0.02 | Finite nonnegative geometric error in domain units; zero disables |

Reject unknown parameters, numeric strings, boolean numbers, and nonfinite values.
No independent seed parameter. No silent coarsening of the requested grid.
The actual terrain is normalized to [0, 1] over samples covering the target's
unexpanded bounding rectangle, after smoothing. Halo samples use that same
normalization and may fall outside [0, 1]. Do not clamp them: clamping can change
boundary topology. A zero or numerically negligible range yields an empty result,
not division by zero or invented terrain. Treat a range at or below
`64 * machine_epsilon * max(1, abs(minimum), abs(maximum))` as negligible
and cover constant-field behavior with tests.

Generate levels `i / (contour_count + 1)`, for `i` from 1 through `contour_count`.
Index levels have `i % index_every == 0`; numbering starts at one.
Levels are normalized artistic elevations, not meters. `contour_count` therefore
sets interval spacing explicitly without competing interval/count parameters.

Require exactly two logical layers, in order: the first receives intermediate
contours and the second index contours. Both remain declared if empty.
Examples use `topographic-contours` and `topographic-index`. `index_every=1`
places every contour on the index channel; values above the contour count leave
the index channel empty. Physical colors, pens, and heavier line treatment are
assigned downstream; index contours are not duplicated or offset strokes.

## Generation and geometry

1. Resolve polygon bounds and domain seed. Evaluate in a zero-origin local frame,
   then restore the bounds origin for returned points.
2. Expand the sampling rectangle by at least one grid cell plus the Gaussian
   filter support of four sigma on each side. Calculate dimensions and all
   resource costs before allocating. Anchor grid nodes to the unexpanded bounds
   endpoints, with integer extra rows/columns for the halo. Filter the halo-backed grid, avoiding
   edge artifacts at the target boundary.
3. Normalize as specified, then extract the requested levels from the shared grid.
   Edge intersections are shared by grid-edge identity, not approximate coordinate
   matching. Resolve ambiguous saddle cells with the bilinear asymptotic decider
   and a documented deterministic tie rule. Handle exact-level vertices using a
   consistent symbolic tie policy, without random perturbation. Avoid zero-length
   segments and stitch open chains and closed loops deterministically.
4. Simplify conservatively, then clip against the true polygon using the existing
   Shapely geometry conventions. Preserve actual closed loops and mark clipped
   fragments open; never join separate fragments across excluded space. Preserve
   winding-independent clipping and support simple concave polygons.
5. Emit stable path ordering by level and canonical geometric order. Closed-loop
   starting vertices and open-chain direction must be canonical to avoid unstable
   SVG/audit output. Carry closedness through the existing `VectorPath` contract.

Terrain smoothing changes the shared height field and is the main aesthetic
control. It can remove small peaks and alter topology intentionally. There is
no per-contour Chaikin smoothing: independent curve movement can cause crossings.

Simplification must stay within the requested error relative to sampled contour
polylines, preserve closed/open status, retain loops, and introduce no intersections
between previously disjoint contours or new self-intersections. Check proposed
simplifications spatially and revert affected paths to their original geometry
when unsafe. Check topology again after clipping. Existing degeneracies in the
raw field are not grounds for silently changing elevation levels. A closed loop
must retain at least three distinct vertices. Zero tolerance keeps original
contour geometry. No short-loop deletion or invented bridging across contour gaps.

`sample_spacing` controls approximation of terrain, while `simplify_tolerance`
controls additional geometric error. Documentation must distinguish these;
simplification tolerance alone is not an error guarantee against the unsampled
continuous terrain. Contour clearance depends on terrain slope and eventual
physical scaling, so this version makes no minimum pen-gap guarantee.

## Resource limits and errors

Per domain, cap total halo-backed samples at 250,000 and the sample-count times
contour-count workload at 12,000,000. Cap extracted segment count at 1,000,000
and final plotted vertices at 1,000,000 per pass, including all targeted domains.
These are internal safety limits rather than user parameters. Abort clearly on
excess cost, invalid heights, or invalid geometry; identify the parameter/domain
and suggest increasing spacing or reducing smoothing extent or contour count.
Do not silently drop contours, change grid resolution, or emit partial bundles.
Reuse the CLI's existing error handling and atomic bundle publication.

## Validation and deliverables

Tests cover seeded repeatability, translation and target-order invariance, no
global RNG mutation, strict parameters, and resource checks before allocation.
Analytic sampled fixtures cover a plane, radial hill, two hills with a saddle,
constant field, exact-level vertices, ambiguous saddle cells, boundary chains,
and closed loops. Verify continuous stitching and level assignment without
depending solely on visual snapshots.

Smoothing tests check zero-sigma identity, reduced high-frequency variation, and
halo behavior. Simplification tests include close neighboring contours and loops
that require fallback. Clipping tests cover convex and concave domains, boundary
contacts, reversed winding, and preservation of closedness. Test empty channels,
index numbering, multiple domains, CLI bundles, and downstream neutral-layer
validation. Existing concentric and Truchet regression checks must keep passing.

Provide a tuning sheet comparing the same seed with smoothing zero, default,
and stronger smoothing, plus a second seed and a concave polygon example. Inspect
rendered SVGs for natural terrain, distinguishable index contours, clipping,
absence of introduced crossings, and manageable plotting detail. Run appropriate
tests and Ruff before completion; record observed results rather than predictions.

Documentation explains length units, normalized elevations, layer assignment,
smoothing versus sampling versus simplification, cost limits, and the ordinary
CLI-to-bundle-to-imposition workflow. No GUI or plotter transport changes.

## Future extension boundaries

Other scalar sources can implement the same sample protocol. Raster elevation
import will additionally need interpolation, nodata, coordinate-system, and
physical-scale policies. Elevation-band fills need region extraction and stable
band identities. Gradient/curl vector adapters can drive the existing field-mark
renderer without changing its vector interface. Shared-coordinate terrain needs
an explicit seed and frame policy, not merely reuse of independent domain fields.
These are backlog boundaries, not hidden first-release requirements.

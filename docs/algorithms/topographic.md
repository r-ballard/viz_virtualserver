# Synthetic topographic artwork

`topographic` generates natural-looking synthetic terrain and extracts continuous
elevation contours. It produces vector strokes for plotting, not geographic maps
or measured elevations. Existing concentric algorithms keep their original behavior.

```powershell
python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-tuning.json --output-dir output/topographic-tuning
```

Open `output/topographic-tuning/design.svg` to inspect the contours. Optional colored
review previews are generated separately and are not part of the CLI bundle.
Use `surfaces/*.svg` and `design.json` for the existing plotter-workflow handoff.
The bundle also includes the monochrome design SVG and audit metadata.

## Parameters

| Parameter | Default | Meaning and range |
| --- | --- | --- |
| `terrain_scale` | 30.0 | Positive base noise wavelength; larger gives broader terrain |
| `octaves` | 5 | Integer 1–8; additional finer-scale noise layers |
| `roughness` | 0.45 | 0–1; amplitude decay between octaves |
| `warp_strength` | 0.35 | 0–1; coordinate displacement relative to terrain scale |
| `terrain_smoothing` | 1.0 | Nonnegative Gaussian sigma; zero disables filtering |
| `sample_spacing` | 0.5 | Positive maximum grid spacing; smaller resolves more detail |
| `contour_count` | 30 | Integer 1–120; normalized elevation interval is 1/(count+1) |
| `index_every` | 5 | Integer 1–120; every Nth elevation level is an index contour |
| `simplify_tolerance` | 0.02 | Nonnegative additional polyline error; zero disables simplification |

All lengths are **intrinsic domain units**. Defaults suit an approximately
100-by-100 domain. Scale length parameters together for similarly detailed larger
or smaller artwork. Unknown parameters, numeric strings, booleans as numbers,
and nonfinite values are rejected.

For contour-only artwork, declare exactly two distinct logical layers in order: intermediate contours,
then index contours. Example IDs are `topographic-contours` and `topographic-index`.
Index numbering starts at one. With `index_every=1`, every contour uses the second
channel; with `index_every>contour_count`, it is unused. Both channels remain
declared in the audit's `logical_layers` catalog, even when empty. SVGs omit empty
groups. Colors and physical pen treatment are assigned downstream; major contours
are not artificially widened or duplicated by this generator.

## Smoothing and geometry

Terrain smoothing filters a shared height field before extracting contours.
Increase it to soften fine terrain and remove small peaks. It can intentionally
change topology. Curves are not independently smoothed, which avoids introducing
crossings through separate curve movement.

Sampling determines the resolution of the terrain approximation. Simplification
reduces vertices within its additional error tolerance and falls back to original
geometry when it would create intersections, self-intersections, or erase a loop.
The simplification tolerance is not an error bound against unsampled terrain.

Each simple convex or concave polygon receives independent, domain-local artwork
using the existing derived domain seed. Composition transforms place that artwork
in the preview without making it shared terrain. A pass requesting
`coordinate_frame: "composition"` is rejected. Reordering targets does not change
their artwork. Translating a polygon with the same identity translates its pattern.

Heights are normalized over each polygon's bounding rectangle after filtering;
levels lie strictly between zero and one. They are artistic elevations, not meters.
Constant or numerically negligible fields produce no contours. Clipping retains
closed loops inside the polygon and open fragments at the boundary; it does not
bridge excluded regions or delete small loops.

The tuning job's panels use smoothing 0, 1, and 3, a second terrain realization,
and a concave target. CLI pass and domain identities derive independent seeds,
so its panels compare settings on different terrains. For a controlled comparison,
hold the same domain ID, geometry, and effective domain seed while changing only
smoothing through the Python service; this comparison is part of visual validation.

## Limits and plotting

Per domain, the halo-backed grid is limited to 250,000 samples, its sample count
times contour count to 12,000,000, and extracted segments to 1,000,000. Final
vertices across a pass are limited to 1,000,000. Excessive costs fail clearly
before publishing a bundle; increase sampling spacing or reduce contour count or
smoothing extent. Resolution is never silently reduced.

Steep slopes can produce close contours. This version does not thin contours for
minimum pen clearance. Judge spacing after physical scaling and pen assignment in
plotter-workflow. Text labels remain a downstream Inkscape operation.

Future extensions include actual elevation rasters, rounded-hill field sources,
shared-coordinate terrain and slope-dependent mark density.

## Elevation-band fills

Run `python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-band-fills.json --output-dir output/topographic-band-fills` for alternating stroke dots, mixed dots/hatching, a concave target, and circle rings. Each panel has independent terrain.

Add optional `band_fills` rules to the pass parameters:

```json
"band_fills": [
  {"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots",
   "parameters": {"spacing": 3, "mark_length": 0.5}, "layer_id": "terrain-dots"}
]
```

For N contours there are N+1 bands numbered 0 through N, from low to high. Band 0 lies below the first level; band N lies above the last. Empty bands keep their indices. Unselected bands remain unfilled. Each rule unions its selected bands before rendering, so adjacent selected bands have no artificial internal clipping seam. Different rules cannot select the same band; they may share a fill layer.

The first two logical layers remain intermediate and index contours. Additional layer IDs must exactly match those referenced by fill rules and cannot alias either contour layer. Empty channels remain declared in the audit catalog and have no SVG group. Fill paths carry the `topographic-fill` feature role; physical pens and colors are assigned downstream.

All five [catalogue effects](../reference/fill-effects.md) are available, with the same controls and defaults. Rules and controls are validated before terrain sampling, including selections that eventually contain no area. Omit `band_fills` or use an empty array to retain contour-only output.

Regions use the same normalized sampled terrain and levels as the contours, before contour simplification. Changing `simplify_tolerance` does not change fills. Holes and disconnected islands are retained; clipped strokes never bridge excluded regions. Equality at a level belongs to the lower band. Constant or numerically negligible normalized terrain produces neither contours nor fills.

Fill lattices use the polygon's bounds-local coordinate frame. Translating the same domain translates its artwork without changing lattice phase. Composition placement does not create shared terrain between polygons.

Region extraction additionally limits cell-level work to 12,000,000 and cumulative intermediate polygon coordinates to 1,000,000 per domain. Contours and fills share the final 1,000,000-vertex pass limit, alongside each effect's own limits. Excessive cost or inadequate coordinate precision fails before publishing a bundle; increase spacing or reduce contour count rather than relying on silent coarsening.

## Terrain-gradient marks

Use `effect: "field-marks"` in a band-fill rule and explicitly set `field_direction` to `"slope"` or `"contour"`. Other effects must omit this field. For example:

```json
{"bands": [0, 2, 4, 6, 8], "effect": "field-marks",
 "field_direction": "contour", "layer_id": "terrain-marks",
 "parameters": {"spacing": 3, "mark_length": 1.5, "angle": 0}}
```

Slope marks follow the uphill/downhill axis; they are undirected strokes, not arrows. Contour marks rotate that axis 90 degrees. `angle` rotates the placement lattice independently of terrain direction. Spacing and length are fixed; flat areas omit marks. Rules retain ordinary band union, clipping, channel and unfilled-region behavior.

Directions come from central differences of the same smoothed, normalized sampled terrain, with one-sided differences at the outer grid edge. Raw x/y derivatives are bilinearly interpolated before normalization. This approximates terrain directions; it is not an exact tangent to marching-square segments. Contour simplification does not affect marks.

The numerical flatness floor is `64 * float_epsilon * max(1, max(abs(heights))) / min(dx, dy)` in normalized height per input unit. No extra artistic smoothing or flatness setting is applied. The full sampled halo supplies directions around boundaries. Centres outside that rectangle omit marks without extrapolation, including possible fragments whose centres lie beyond the halo.

```powershell
python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-gradient-marks.json --output-dir output/topographic-gradient-marks
```

The example shows slope marks, contour marks, and a concave selected-band panel. Each uses independent terrain, so it is not a controlled orientation comparison. Hold the effective domain seed and geometry constant in the Python service to compare orientations on identical terrain.

Gradient storage uses the existing sample cap and is shared per domain. The common field renderer limits each call to 100,000 candidate marks and 2,000,000 clipped points. Contours and all fill rules retain a combined 1,000,000-vertex pass limit; subsequent rules stop on excess. Dense marks can overlap at a chosen physical scale: inspect spacing and pen assignment downstream.

## Seeded component fill choices

A band-fill rule may use `component_choices` instead of a single effect. Selected bands are unioned first, then each polygon member receives one deterministic weighted choice. Holes stay attached; point-touching MultiPolygon members remain separate. Unselected bands and blank choices stay empty.

```json
{"bands": [0, 2, 4, 6, 8], "component_seed": 0,
 "component_choices": [
   {"id": "blank", "weight": 2, "effect": null},
   {"id": "dots", "weight": 3, "effect": "stroke-dots",
    "parameters": {"spacing": 3}, "layer_id": "terrain-dots"},
   {"id": "marks", "weight": 1, "effect": "field-marks",
    "field_direction": "contour", "layer_id": "terrain-marks"}
 ]}
```

Each choice needs a unique, nonblank, case-sensitive ID and an integer weight from 1 to 1,000,000. There must be 1 through 32 choices. A blank choice requires explicit `effect: null` and must omit rendering controls. Nonblank choices use catalogue parameters and layers, including the existing field-direction rules. Choice rules must omit top-level effect/parameters/layer/direction; old rules must omit component fields. Every possible choice is validated before terrain sampling.

The effective domain seed and optional integer component_seed drive a versioned hash of each canonical full-precision local polygon and selected band indices. Choice order, winding, hole order and unrelated components do not change an unchanged component's assignment. Changing only component_seed changes assignments without changing terrain; weights do not promise exact proportions in a small drawing. Shape or palette-ID/weight changes can change assignments.

Exactly equivalent bounds-local geometry retains assignments under translation or composition placement. No quantization hides numerical changes: translations that lose local precision may change IDs. Tiny islands are retained. Component effects share the original domain lattice origin, not their own bounding origins.

Declare the first two contour layers followed by the exact set of every potential nonblank choice layer, including choices not selected in this drawing. Empty channels remain in the audit and have no SVG group. All-blank palettes need only contour layers. Mixed old and choice rules still require disjoint band selections. Existing single-effect rules retain their output.

Component selection caps each union at 100,000 components and 1,000,000 polygon coordinates. A choice rule has an aggregate 100,000 scan-row/lattice-position budget across rendered components; crosshatch counts both families. The catalogue uses the same planning arithmetic for estimates and rendering. Individual effect limits and combined pass vertices still apply; excessive cost fails rather than dropping geometry.

```powershell
python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-component-choices.json --output-dir output/topographic-component-choices
```

The example mixes blank, dots, hatching and contour-oriented marks on independent square and concave terrains. The audit retains supplied palettes and seeds; this release does not export a per-component decision manifest or support manual overrides.

## Deterministic mark density

`stroke-dots`, `vortex-marks` and `field-marks` accept numeric `density` from 0 through 1 in their parameters (default 1). A separate optional `density_seed` belongs on the ordinary rule or component-choice entry and is a strict signed 64-bit integer (default 0).

```json
{"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots",
 "parameters": {"spacing": 3, "mark_length": 0.7, "density": 0.3},
 "density_seed": 7, "layer_id": "terrain-dots"}
```

Density retains a reproducible subset of candidate marks; it does not change spacing, mark length or vector direction. Increasing it adds marks without moving survivors. Coverage is statistical, not an exact count or calibrated ink area. Full density preserves existing output. Zero density emits no marks but retains its declared channel and validates controls, field availability and full candidate costs. Rejected field marks do not evaluate terrain gradients; zero density does not allocate gradient arrays.

The effective domain seed and density_seed derive a shared mask from lattice row/column indices. Component IDs, choice IDs, bands, layers and effect IDs do not enter this seed. Changing density_seed changes thinning without changing terrain or component assignments. Equivalent local lattices use the same mask when clipped separately or as a union. Changing spacing/angle moves the lattice; its index decisions stay fixed. All fragments from a clipped candidate share one decision.

Hatches and rings reject density controls. Blank choices must omit density_seed and all other rendering fields. Truchet has no new density controls in this release; standalone catalogue calls support the same mark effects with an explicit density_seed.

```powershell
python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-mark-density.json --output-dir output/topographic-mark-density
```

The example uses independent sparse-dot, field-mark and concave terrains. Hold domain geometry and effective seed fixed in the Python service for a controlled comparison of densities 0,.25,.5,.75,1. Low density never bypasses the full planned lattice's per-effect or aggregate candidate limits; final emitted vertices remain subject to the existing pass cap.

## Elevation-driven density

Mark styles and nonblank component choices may supply `density_source` alongside numeric parameters:

```json
{"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots",
 "parameters": {"spacing": 3, "mark_length": 0.7, "density": 1},
 "density_seed": 7,
 "density_source": {"type": "elevation", "minimum": 0.1,
                    "maximum": 0.8, "invert": false},
 "layer_id": "terrain-dots"}
```

Type is required and must be `elevation`. Minimum defaults to 0, maximum to 1, and inversion to false. Bounds are finite real values in [0,1] with minimum <= maximum; equal bounds are valid. Invert requires a boolean. Explicit null, unsupported sources/effects and unknown keys are errors, even for unused choices. Blank choices must omit the source. Keep the source outside numeric parameters.

The same smoothed, normalized height field supplies bilinear elevation h at each candidate centre. Inside the sampled rectangle, clamp h to [0,1], optionally use 1-h, then map linearly between minimum and maximum. The existing numeric density multiplies this mapped value. The seeded lattice mask stays fixed: pointwise-increased coverage adds marks without moving survivors, while inversion redistributes dense areas.

The halo can extend outside normalized interior elevations, which explains the height clamp. Centres outside the full sampled rectangle get zero density without extrapolation, even with nonzero minimum or constant mappings; long marks can therefore lose fragments whose centres exceed the halo. Terrain is never renormalized over individual bands/components. Constant or negligible fields still produce no artwork.

Source controls change only retention: terrain, component choices, mark directions, spacing, clipping, layer ownership and contour simplification remain independent. Missing source preserves prior fixed-density output. Density-only dots allocate no gradients; rejected field candidates do not evaluate vectors. Full lattice budgets still apply, including maximum-zero mappings. Such mappings retain declared empty channels and can pass an exhausted emitted-vertex allowance after validation and candidate reservation.

```powershell
python -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/topographic-elevation-density.json --output-dir output/topographic-elevation-density
```

The example shows normal dots, inverted contour-oriented marks and component choices on a concave target. Its panels have independent terrain. Use the same effective seed/domain in Python to compare normal and inverted mapping on identical terrain. Coverage is approximate mark retention, not calibrated ink coverage. Slope/raster sources and new Truchet controls remain future work.

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

Declare exactly two distinct logical layers in order: intermediate contours,
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
elevation-band fill effects, gradient-driven marks, and shared-coordinate terrain.

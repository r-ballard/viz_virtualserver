# Recursive Voronoi cell artwork

The `voronoi-cells` domain algorithm subdivides each convex polygon with seeded Voronoi sites. Each generation partitions its parent cell, so the unstyled leaves cover the domain. A small inward offset separates the drawn cell contours; sampled quadratic corners soften them. The output is neutral vector geometry in a single logical layer, `cell-contours`.

Generate the example bundle:

```powershell
uv run --frozen python scripts/generate_domain_bundle.py examples/domain-jobs/voronoi-three-polygons.json --output-dir output/voronoi-three-polygons
```

Inspect `output/voronoi-three-polygons/design.svg` and the SVGs in `surfaces/`. The JSON job is reusable: change `seed` for another composition, or tune `branch` (2–5), `depth` (1–7), `inset_ratio`, `corner_radius_ratio`, and `curve_segments`. The two ratios use the smaller bounding-box dimension of each domain, so they are independent of plotter units. `max_cells` and `max_path_length_ratio` bound large jobs; a too-large request fails with a clear error.

The algorithm accepts convex polygons, including triangles and pentagons, and seeds each domain independently. `viz_virtualserver` exports design paths. Paper placement, pen assignment, HP-GL conversion, and the physical send remain in `plotter-workflow`.

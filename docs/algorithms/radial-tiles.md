# Radial Tiles

`radial-tiles` generates plotter-native fields of overlapping concentric motifs
inside arbitrary polygon domains. Each motif combines drifting ring centers,
irregular angular tiles, omissions, and small geometric perturbations. The
result is orderly at a distance and visibly imperfect at close range without
using fills or raster effects.

The algorithm runs independently for every target domain. Its output remains in
domain coordinates; polygon placement and physical imposition belong to the
downstream workflow.

## Generate the three-polygon example

From Git Bash in `viz_virtualserver`, set `workspace_root` to the portable
workspace that contains `.tools/`, then run:

```bash
: "${workspace_root:?set workspace_root to the portable workspace root}"

"$workspace_root/.tools/uv.exe" run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/radial-tiles-three-polygons.json \
  --output-dir "$workspace_root/artifacts/radial-tiles-three-polygons"
```

Add `--overwrite` only after reviewing the exact output directory and deciding
to replace the existing bundle. The command writes `design.json`, `design.svg`,
and one intrinsic SVG under `surfaces/` for each declared surface. It does not
impose, convert, preflight, transmit HPGL, or operate a plotter.

## Required logical layers

Every `radial-tiles` pass declares these layers in this order:

1. `structural-rings` — complete ring outlines that establish the large form;
2. `primary-tiles` — most segmented band outlines;
3. `accent-tiles` — a deterministic subset of tile outlines for another pen or
   visual treatment.

Keeping the layers logical allows a later workflow to map them to physical pens.

## Parameters

| Parameter | Default | Range | Effect |
| --- | ---: | ---: | --- |
| `motif_count` | `3` | 1–20 | Concentric structures generated per polygon |
| `ring_count` | `4` | 1–20 | Bands generated per structure |
| `tile_density` | `18` | 3–120 | Approximate tiles in the innermost band; outer bands increase slightly |
| `center_drift` | `0.06` | 0–0.5 | Ring-to-ring center movement as a fraction of band spacing |
| `angular_jitter` | `0.12` | 0–0.45 | Variation in tile start and end angles |
| `radial_jitter` | `0.08` | 0–0.45 | Variation in ring radii and tile depths |
| `omission_rate` | `0.12` | 0–0.9 | Probability that a tile position is left empty |
| `closed_tiles` | `true` | Boolean | Closed quadrilaterals when true; open three-segment marks when false |

All randomness comes from the job's stable per-domain seed. Repeating the same
job produces identical paths. Adding or reordering other domains does not alter
a named domain's design.

## Tuning for small folded surfaces

Begin with `motif_count` 1–3, `ring_count` 2–4, and `tile_density` 8–18. Reduce
those values before reducing jitter when a triangular or reveal surface becomes
too dense. Increase `omission_rate` to create breathing room without changing
the overall radial structure.

The surface SVG includes a defensive polygon clip. Some motif centers and rings
intentionally extend beyond the domain so that cropped arcs enter from an edge.
Always inspect the per-surface SVGs before imposition.

## Creating another polygon set

Copy the example job and replace the `domains` and `surfaces` arrays. Each
surface references one domain, and a single pass may target one or many domain
IDs. Keep polygon coordinates intrinsic: do not encode sheet positions,
rotations, physical pens, HPGL settings, or plotter commands in this job.

Change the top-level `seed` to explore a new deterministic composition. Change
parameters to alter density and character. Preserve the three required logical
layers unless the algorithm contract itself is deliberately revised.

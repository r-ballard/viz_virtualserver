# Concentric-point generator

The concentric-point generator consumes generic polygon-domain geometry through its design
adapter. The adapter receives domains owned by `viz_canvas`, invokes the existing concentric
algorithm for a supported target, and returns neutral canvas-coordinate vector paths internally.
The generic polygon model is not owned by the concentric package; see [CANVAS.md](CANVAS.md) for
the shared domain grammar, semantics, metadata, and repository boundaries.

The generator is intentionally canvas-aware. A triangular source is generated as a triangular
composition rather than as rectangular artwork that is cropped only during imposition.

The adapter declares the algorithm's actual capability: it supports simple convex polygon
domains and does not claim support for concave polygons. When invoked through the generic
design-pass executor, unsupported geometry is rejected before the algorithm runs. The
compatibility wrappers preserve the established JSON response and SVG surface, including circles
and top-level physical `pen-N` groups, while the internal `DesignResult` remains independent of
HTTP models and plotter-slot assignment.

## API

Generate JSON geometry:

```bash
curl -sS http://localhost:5699/ConcentricPoints \
  -H 'content-type: application/json' \
  --data @examples/concentric/triangle-organic.json
```

Generate SVG:

```bash
curl --fail-with-body -sS \
  -o triangle-concentric.svg \
  -H 'content-type: application/json' \
  --data-binary @examples/concentric/triangle-organic.json \
  'http://localhost:5699/ConcentricPointsSvg?stroke_width=1'
```

The SVG keeps the intrinsic canvas metadata established by `viz_canvas`, adds the versioned
polygon-domain metadata described in [CANVAS.md](CANVAS.md), defines the same polygonal clip under
`<defs>`, and places all drawable geometry in a top-level strict `pen-N` group for downstream
`plotter-workflow` compatibility. These are compatibility guarantees of the public endpoint; the
adapter's neutral internal paths use logical layers instead of physical pen groups.

## Request fields

`canvas` is a normal `CanvasSpec`. The remaining fields are algorithm-specific.

### Center count and placement

- `seed`: deterministic PRNG seed.
- `point_count`: exact number of sampled centers. This remains the backward-compatible default.
- `point_count_range`: optional inclusive `[minimum, maximum]` range. When supplied, one count is
  deterministically selected from the range using `seed`; it takes precedence over `point_count`.
- `center_margin`: minimum distance from a sampled center to the canvas boundary.
- `min_center_spacing`: minimum Euclidean distance between sampled centers.
- `center_bias`: `uniform`, `centroid`, `boundary`, or `vertices`.
- `center_bias_strength`: value from `0` to `1` controlling interpolation toward the selected
  geometric target. Zero is equivalent to uniform sampling. Strong bias can conflict with
  `center_margin` or `min_center_spacing`, in which case sampling fails explicitly.
- `max_sampling_attempts`: rejection-sampling safety limit.

Bias is a generative preference, not a new canvas definition. All accepted centers must still
satisfy the intrinsic polygon and all spacing/margin constraints.

### Ring count and spacing

- `ring_count`: exact number of rings emitted for every center.
- `ring_spacing`: `linear`, `progressive`, or `random`.
- `ring_spacing_power`: exponent used by `progressive` spacing. Values above `1` place rings more
  tightly toward the center and increase gaps outward; values below `1` do the reverse.
- `min_ring_radius`: optional absolute lower bound for the first ring.
- `max_ring_radius`: optional absolute cap on the outer ring.

`linear` preserves the original evenly spaced behavior. `random` samples deterministic radial
positions and sorts them, always retaining the outermost ring at the effective maximum radius.
`progressive` uses a power curve while also retaining the effective maximum radius.

### Radius and overlap behavior

- `boundary_mode`: `inscribed` or `clip`.
- `radius_scale`: multiplier in `(0, 1]` applied to each center's available radius.
- `radius_variation`: deterministic per-center reduction in `[0, 1)`. A value of `0.35` gives each
  center an outer-radius multiplier sampled from `[0.65, 1.0]`.
- `overlap_mode`: `allow` or `avoid`.

For `avoid`, each center's outer radius is additionally capped at half the distance to its nearest
neighbor. Therefore the outer rings of neighboring centers cannot intersect. This is most useful
for isolated motifs. `allow` is the better default for dense, clipped triangle-filling artwork.

### Plotter metadata

- `pen`: logical/physical pen number encoded as a top-level `pen-N` SVG group.
- `color`: six-digit SVG stroke color.

## Boundary modes

### `inscribed`

The available radius for each center is its distance to the intrinsic canvas boundary. Every ring
is therefore geometrically contained by the canvas before SVG clipping is applied.

This mode is useful for isolated motifs and compositions where the canvas edge should remain
visually quiet.

### `clip`

The available radius is the farthest distance from the center to any canvas vertex. The largest
ring can therefore span the complete polygon and is clipped by the intrinsic canvas clip path.

This mode deliberately creates edge interaction and is the recommended starting point for
triangle-filling cootie-catcher selector/reveal artwork.

Final SVG clipping is retained for both modes as a defensive export boundary.

## Determinism

All random decisions use one `random.Random(seed)` stream, including count-range selection,
center placement, per-center radius variation, and random ring spacing. Repeating the same request
under the same Python runtime reproduces the JSON and SVG geometry.

Requests that cannot satisfy center placement or leave no usable radius above `min_ring_radius`
fail explicitly rather than silently reducing the requested content.

## Examples

- `triangle-fill.json`: original dense clipped triangle with linear rings.
- `triangle-organic.json`: count range, progressive rings, per-center radius variation, and vertex
  bias for a less mechanically regular clipped composition.
- `triangle-nonoverlap.json`: inscribed, randomized rings with non-overlapping center motifs.
- `square-inscribed.json`: original square inscribed example.

## Relationship to `plotter-workflow`

`viz-virtualserver` owns the logical shape and the generative response to that shape. The SVG
therefore contains:

- the intrinsic polygon and `up_vector` metadata;
- shape-aware center placement and ring radii;
- a canvas clip path; and
- top-level `pen-N` drawing groups.

`plotter-workflow` remains responsible for physical scaling, rotation into an imposition panel,
final defensive clipping, pen-plan resolution, HP-GL conversion, and DPX-3300 transport.

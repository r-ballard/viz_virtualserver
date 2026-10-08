# Reusable fill effects

`viz_virtualserver.fill_effects` converts composed polygon regions into explicit
vector strokes. Generators choose the regions, frame, ownership, and logical
layers. The library returns geometry without domain IDs, semantic roles, pen
assignments, or styling.

## Catalogue and standalone use

```python
from shapely.geometry import box
from viz_virtualserver.fill_effects import list_fill_effects, render_fill_effect

effects = list_fill_effects()
strokes = render_fill_effect(
    box(1, 1, 9, 9),
    effect="parallel-hatch",
    parameters={"spacing": 2, "angle": 0},
)
print(tuple(stroke.points for stroke in strokes))
```

The result is four open strokes:

```text
(((1.0, 2.0), (9.0, 2.0)), ((1.0, 4.0), (9.0, 4.0)),
 ((1.0, 6.0), (9.0, 6.0)), ((1.0, 8.0), (9.0, 8.0)))
```

`list_fill_effects()` returns an ordered tuple of frozen descriptors with `id`,
`name`, `description`, and a tuple of `parameters`. Each parameter exposes `name`,
`default`, `unit`, and `exclusive_minimum`. Rendering uses those same declarations.
The public API does not expose mutable registration state.

| Effect | Control | Default | Meaning |
| --- | --- | --- | --- |
| `parallel-hatch` | `spacing` | 2 | Positive distance between scan rows in input units |
| `parallel-hatch` | `angle` | 45 | Finite degrees, positive clockwise in SVG coordinates |
| `crosshatch` | `spacing` | 2 | Positive row spacing within each of two perpendicular families |
| `crosshatch` | `angle` | 45 | First family angle; the second is 90 degrees clockwise from it |
| `circle-rings` | `spacing` | 8 | Positive centre spacing of a square lattice |
| `circle-rings` | `radius` | 2 | Positive circle radius, independent of centre spacing |
| `circle-rings` | `angle` | 0 | Clockwise rotation of the centre lattice |
| `circle-rings` | `curve_tolerance` | 0.02 | Positive maximum chord deviation in input units |
| `stroke-dots` | `spacing` | 8 | Positive centre spacing of a square lattice |
| `stroke-dots` | `mark_length` | 0.5 | Positive length of each uncut short stroke |
| `stroke-dots` | `angle` | 0 | Clockwise rotation of both the centre lattice and marks |
| `vortex-marks` | `spacing` | 8 | Positive centre spacing of a square lattice |
| `vortex-marks` | `mark_length` | 0.5 | Positive fixed length of each uncut mark |
| `vortex-marks` | `angle` | 0 | Clockwise rotation of the placement lattice only |
| `vortex-marks` | `center_x`, `center_y` | 0 | Vortex centre in the input coordinate frame |

Select `effect="crosshatch"` in the same Python call for two perpendicular families.
Both use the same coordinate-zero phase, spacing and region clipping. Crossing
strokes remain separate open paths; intersections do not become joins. The
combined output is sorted deterministically. Orientation repeats every 90 degrees
for crosshatch, because both families use the same spacing.

Select `effect="circle-rings"` for repeated circle outlines. Circle centres use
the same coordinate-zero origin; angle rotates their square lattice. Sampling
uses at least eight vertices and a multiple of four, with chord deviation bounded
by `curve_tolerance`. Complete rings are closed strokes without a repeated end
vertex. Boundary and hole clipping yields open arcs, joining contiguous fragments
across a ring's sampling seam. Separate rings and gaps are never joined. Centres
outside the selected region are included when their outlines can enter it.
Radius and spacing are independent, so overlapping rings are allowed.

Select `effect="stroke-dots"` for short, nonzero line segments centred on a square
lattice anchored at coordinate zero. Angle rotates both the lattice and the mark
direction; orientation repeats every 180 degrees. Clipping can shorten or split a
mark, but never joins different marks or bridges holes. Centres outside the
region are considered when their marks can enter it. Marks longer than centre
spacing may overlap deliberately and still remain separate paths.

The dot-like appearance depends on the selected physical pen. This effect returns
open two-point paths, not filled disks, zero-length points, pen taps or dwell
commands. Pen width and ink coverage remain downstream concerns. Larger solid
dot effects using spirals or hatched disks remain future work.

Select `effect="vortex-marks"` to turn those short marks according to a local
field. Each mark is tangent to a circle around the configured centre. Direction
varies with position while uncut mark length stays fixed. The centre is explicit,
not inferred from the selected region's bounding box, so changing a painted or
unpainted mask does not recenter the flow. A zero vector at the vortex centre,
including positions indistinguishable within coordinate-rounding resolution,
omits its mark. Open segments have no arrowheads; their geometry displays the
tangent orientation rather than the sign of circulation.

### Field and renderer abstraction

`vector_fields.VectorField` specifies `sample(x, y) -> VectorSample`. A frozen
sample retains raw `dx` and `dy`, with separate `direction` and `magnitude`
properties. Direction normalization is stable for large and subnormal components;
an unrepresentable magnitude raises `ValueError` when requested. Field evaluators
are expected to be pure and have no knowledge of masks, layers, pens or placement.
Raw components allow future blending or convolution before normalization.

`field_marks.render_field_marks` owns placement, precision/budget checks, and
individual clipping. It uses sample direction only, skipping zero vectors. Its
fixed-length marks do not vary with magnitude. The `vortex-marks` catalogue entry
combines this renderer with `VortexField`; future radial, wave, noise or blended
fields can consume the same boundary without changing clipping code.

```python
from shapely.geometry import box
from viz_virtualserver.fill_effects.field_marks import render_field_marks
from viz_virtualserver.fill_effects.vector_fields import VortexField

strokes = render_field_marks(
    box(0, 0, 80, 80), spacing=8, mark_length=0.5, angle=0,
    field=VortexField(center_x=40, center_y=40),
)
```

This evaluates clockwise raw vectors `(-(y-center_y), x-center_x)` in SVG
coordinates, resolving the centre within a small combined-ULP rounding envelope.
That singularity policy belongs to the vortex evaluator; the renderer does not
apply an arbitrary magnitude threshold to other fields. Longer integrated
streamlines and magnitude-based mark sizing
remain separate extensions.

Omitted parameters use defaults. Controls accept real numeric values, excluding
booleans; strings, unknown controls, unknown effect IDs, and non-finite values
raise `ValueError`. Validation also occurs for empty regions.

## Geometry and frames

Supply valid `Polygon`, `MultiPolygon`, or recursively polygonal
`GeometryCollection` input. Empty polygonal geometry returns `()`. Invalid
polygons and non-polygonal inputs raise `ValueError`; the engine does not repair
geometry or reconstruct regions from tile curves. Union adjacent regions first
if their seams should disappear.

Hatch angles repeat every 180 degrees: 0 is horizontal and 90 is vertical. Rows lie on
a lattice anchored at coordinate zero in the supplied frame. Translating a
region changes its relationship to that lattice; the library never silently
recenters it. Spacing has the same units as the coordinates, with no implied
millimetres or physical pen width.

Clipping produces a separate stroke for each fragment. Strokes do not bridge
holes or disconnected polygons, and point-only tangent contacts produce no
stroke. Endpoints and strokes have deterministic ordering. Hatch rendering rejects
more than 100,000 scan rows, more than 2,000,000 sampled points, or spacing that
cannot be reliably represented at the projected coordinates. Clipping failures
raise `ValueError`.

For crosshatch, both families share those budgets. The complete scan-row budget
is checked before clipping either family; the point budget is enforced as
fragments are produced. Switching to crosshatch does not double the limits.

Circle rings have a preflight limit of 100,000 candidate centres in the rotated,
radius-padded bounding rectangle and 2,000,000 sampled vertices across those
candidates. This conservative budget includes candidates whose outlines later
clip away. Clipped output also has a 2,000,000-vertex limit, since intersections
can introduce new vertices. Unrepresentable spacing, radius or tolerance fails
with `ValueError` before drawing; parameters are not silently enlarged or relaxed.
Sampling reserves a coordinate-rounding allowance before choosing its vertex
count. Truchet additionally reserves error for conversion to design coordinates.
If rounding exhausts the requested tolerance, generation fails explicitly.

Stroke dots have a preflight limit of 100,000 candidate marks and 2,000,000 source
endpoints, plus a 2,000,000 clipped-endpoint limit. Candidates come from the
rotated bounding rectangle padded by half the mark length along its direction.
Both spacing and mark length must be reliably representable at the input and
Truchet design coordinates. Point-only tangencies and fragments collapsed by
coordinate conversion are discarded; no zero-length strokes are returned.
An empty lattice dimension returns immediately rather than traversing the
other dimension when no marks can be drawn.

Field marks use the same 100,000-candidate and 2,000,000 source/clipped-endpoint
limits. Their candidate rectangle is padded by half the mark length on both
lattice axes, because a local field can point in any direction. Guards run before
field evaluation; empty lattice dimensions return immediately. Each mark clips
independently, with no bridges at holes or joins across separate marks.

`FillStroke` contains immutable `points` and `closed` values. Coordinates must
be finite 2D values, with at least two distinct vertices for open strokes and
three for closed strokes. If a caller scales or translates the result, it must
discard collapsed fragments and validate the transformed geometry.

## Generator and export integration

A generator selects its composed region, calls the effect, then converts strokes
to its own path type and attaches domain ownership, feature roles, and logical
layers. Export preserves those assignments. Physical scaling, pens, ink
compensation, device commands, and plotting order belong downstream.

[Multiscale Truchet](../algorithms/truchet.md#plotter-hatching-of-multiscale-regions)
uses this engine in its normalized frame. It retains painted/unpainted selection,
world-coordinate spacing checks, post-transform canonicalization, insets, curve
colors, borders, and neutral provenance. Its existing `hatch_*` job controls
retain their meaning, with `hatch_effect` selecting `parallel-hatch` (default),
`crosshatch`, `circle-rings`, `stroke-dots`, or `vortex-marks`. Rings additionally use `hatch_radius` (default 0.5)
and `hatch_curve_tolerance` (default 0.02), in design units. Truchet retains its
existing spacing and angle defaults (2 and 45), so its ring defaults differ from
the standalone catalogue defaults. `generators.truchet.hatching.parallel_hatches`
remains a compatibility adapter returning `CurvePath` values, with the old limit
names still importable.

Stroke dots use `hatch_mark_length` (default 0.5), measured in design units and
normalized with centre spacing before shared rendering. Existing effects ignore
this control after validation. Truchet's spacing/angle defaults remain 2 and 45
for dots as well, while standalone dot catalogue defaults are 8 and 0.

Vortex marks use `hatch_field_center_x` and `hatch_field_center_y` (both default
0), measured in design units relative to each polygon's minimum x/y. Classic
passes these coordinates into its near-origin frame; multiscale divides them by
its tile scale alongside spacing and mark length. Nonzero centres lost during
normalization fail explicitly. Centre controls are validated but ignored by
other effects. Truchet retains its spacing/angle defaults of 2 and 45.

[Classic Truchet](../algorithms/truchet.md#plotter-fills-of-classic-regions) supports
the same effects and validated `hatch_*` controls. It reconstructs grammar
fields from the same sampled arcs used for its boundary curves, unions matching
regions across tiles, and draws in design units near the domain origin before
translating output back. `painted` selects region 1; `unpainted` selects the
complement inside the polygon. A null hatch layer leaves both fields unfilled.
Its sampling, color assignment, borders and insets retain their existing behavior.

## Future effects and Patternfills

[Patternfills](https://github.com/iros/patternfills) is a reference collection
for motif families. Its SVG/CSS pattern assets need adaptation to explicit,
clipped plotter geometry. No Patternfills assets are bundled here. When copying
its source or assets, retain the notices required by its
[MIT license](https://github.com/iros/patternfills/blob/master/LICENSE).

| Motif | Proposed native geometry | Status |
| --- | --- | --- |
| Horizontal, vertical, diagonal stripes | Parallel hatch with angle/spacing | Available |
| Crosshatch | Two perpendicular clipped hatch families | Available |
| Circles | Repeated rings sampled with a stated curve tolerance | Available |
| Stroke dots | Short, individually clipped lattice marks | Available |
| Vortex marks | Fixed marks driven by an independent vector field | Available |
| Larger filled dots | Spirals or hatched disks, with explicit fill density | Future |
| Houndstooth and filled motifs | Repeating polygon regions with outlines or another fill effect | Future |

Only implemented effects appear in the catalogue. Independent per-field and
per-component fill selection, dithering, arbitrary SVG/image import, a generic fill CLI, and
plugin discovery remain separate work.

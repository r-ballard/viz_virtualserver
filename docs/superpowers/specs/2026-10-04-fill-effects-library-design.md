# Shared fill-effects library

Linear: [HAR-43](https://linear.app/hardcase/issue/HAR-43/extract-a-reusable-fill-effects-library-from-truchet-hatching)

Status: proposed written design, awaiting review. The user approved the conceptual
separation of generator regions, reusable effects, and export, and requested this
ticket and implementation. This document makes the shared API concrete.

## Purpose and scope

Make the existing parallel-hatching behavior reusable by generators beyond
Truchet. A generator constructs and selects composed regions; a fill effect
converts region geometry into vector strokes; the generator attaches ownership
and logical layers before the existing export workflow. Physical scaling, pens,
device commands, and stroke-order optimization remain downstream responsibilities.

This first increment extracts the implementation from PR #14, supplies an explicit
catalogue, and routes multiscale Truchet through it. It adds no new fill styles.
Classic-region reconstruction will use this library in a subsequent feature.

## Approach

Use a small Python package with a static effect registry. This provides discovery
and validation while preserving the existing geometry flow.

A direct-function-only extraction would share code but leave catalogue metadata
and parameter validation to each caller. Dynamic plugin discovery would add
installation and registration behavior without a current consumer. Neither is
needed for the accepted explicit catalogue approach.

## Public contract

Add `viz_virtualserver.fill_effects` with these entry points:

- `list_fill_effects()` returns the catalogue's ordered effect descriptors.
- `render_fill_effect(region, *, effect, parameters=None)` returns an immutable
  tuple of `FillStroke` geometry values.

The initial effect ID is `parallel-hatch`. Each descriptor exposes an ID, display
name, description, and supported parameter schema, including defaults and units.
The catalogue describes implemented effects only. Registry entries are explicit
and callers cannot mutate global registration state through the public API.

`FillStroke` contains immutable points and a closed flag, with finite coordinates
and enough distinct vertices for its open or closed geometry. It carries no
generator identity, domain ID, logical layer, semantic provenance, or pen slot.
The shared package must not import Truchet modules or `CurvePath`.

Parallel-hatch parameters are strict, finite numeric values: `spacing` defaults
to 2 and must be positive; `angle` defaults to 45 degrees. Unknown fields and
unknown effect IDs raise clear `ValueError` failures. Catalogue discovery and
rendering use the same parameter definitions.

## Geometry and coordinate responsibilities

The caller supplies already-composed valid polygonal geometry in one coordinate
frame. Polygon, multipolygon, and polygonal geometry collections retain the
existing scanner's clipping behavior; empty geometry returns no strokes.
The engine does not repair invalid polygons or reconstruct generator regions.

Spacing uses the input geometry's units, and angles follow SVG coordinates:
0 degrees horizontal, 90 vertical, positive clockwise, repeating every 180.
Hatch rows remain on the current lattice anchored at coordinate zero in the
supplied frame. Callers normalize or translate geometry to establish their own
origin; the API does not silently recenter it.

Preserve the current scanner, clipping, endpoint order, tangent handling,
normalized precision guard, 100,000-row guard, and 2,000,000 sampled-point guard.
Each clipped fragment is a separate open stroke; holes and disconnected pieces
receive no joining strokes. Additional transformations may collapse fragments,
so callers must validate and canonicalize geometry after converting coordinates.
Truchet retains its world-coordinate spacing check and final canonicalization.

## Truchet integration and compatibility

Multiscale Truchet calls the shared registry for `parallel-hatch`, converting its
spacing to the existing normalized frame. It continues to compose once for curves
and hatches. Painted/unpainted selection, seeds, subdivision, tolerance, artwork
insets, curve colors, border channels, and semantic roles remain in Truchet.

Keep `generators.truchet.hatching.parallel_hatches` as a thin compatibility adapter
that returns the original `CurvePath` values. Preserve its existing limit constant
imports. The shared scanner has one implementation, used by the adapter and the
registry; the multiscale compositor uses the shared entry point directly.

No job-schema or CLI changes are introduced. Existing `hatch_*` job fields retain
their meaning. For identical inputs in the installed environment, the generated
SVGs, neutral metadata, path order, and hashes remain byte-for-byte unchanged.

## Verification and documentation

Test the shared entry point independently on literal rectangles, holes, disjoint
polygons, angled rows, empty geometry, parameter errors, and resource guards.
Verify catalogue declarations match actual defaults and accepted controls.
Retain the existing translated-spacing, collapsed-fragment, concave-inset,
channel-preservation, and neutral-export regressions.

Capture the existing hatching example's audit, combined SVG, and both surface SVGs
before extraction; compare bytes afterward. Run the full test suite, lint, and
whitespace checks. Render and inspect the example and validate its neutral bundle
with the existing downstream contract validator. Request one independent final
review and address substantive findings before opening the PR.

Document the catalogue and a standalone Python usage example, the coordinate
contract, and how a generator adds layers and ownership. Update the Truchet guide
to identify its shared implementation.

## Deferred work and delivery

### Patternfills reference and effect roadmap

Use [iros/patternfills](https://github.com/iros/patternfills) as a motif reference
for subsequent catalogue additions. Its SVG collection groups circles, diagonal
stripes, dots, horizontal stripes, vertical stripes, and other motifs, including
crosshatch and houndstooth. The repository distributes SVG/CSS pattern assets;
our library must generate explicit clipped strokes for plotters.

| Reference family | Native approach | Priority after extraction |
| --- | --- | --- |
| Horizontal, vertical, diagonal stripes | Existing parallel hatch with angle and spacing | Covered initially |
| Crosshatch | Combine two independently clipped hatch families | First new effect |
| Circles | Generate rings on a lattice, approximate curves with a documented tolerance, then clip | Subsequent effect |
| Filled dots | Define a plotted mark such as rings, spirals, or short strokes; preserve a separate density control | Subsequent design |
| Houndstooth and other filled motifs | Construct repeating polygon regions, then apply outlines or a selected fill effect | Later design |

Do not introduce an arbitrary SVG importer or an npm runtime dependency in this
extraction. Preserve catalogue space for these effects without advertising them
as implemented. Patternfills uses the [MIT license](https://github.com/iros/patternfills/blob/master/LICENSE);
retain its copyright and license notice if later implementations copy its assets
or substantial source. No reference assets are bundled in this increment.

Crosshatching, stippling, dithering, new region sources, classic Truchet region
reconstruction, image input, a generic fill CLI/job schema, dynamic plugins,
physical ink compensation, and path-order optimization remain separate features.

Use native implementation in `.worktrees/har43-fill-effects` after written-spec
review, a written implementation plan, and approval of that plan. Follow the
existing push-and-PR preference. PR #14 is currently open, so this branch builds
on its head; target its branch if it remains open, or `main` after it merges.

# Orbital-concentric generator

`orbital-concentric` generates simplified, plotter-native orbital diagrams inside one or more
polygon domains. It is a sibling of `concentric-points`; the existing algorithm and its HTTP/SVG
compatibility behavior remain unchanged.

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/orbital-concentric-three-polygons.json \
  --output-dir artifacts/orbital-concentric
```

The algorithm emits neutral `VectorPath` geometry in three required logical layers, in order:
`orbits`, `primary-bodies`, and `accent-bodies`. Each target domain is generated independently
from its domain seed, and the generic exporter performs final polygon clipping. Convex simple
polygons are supported; concave domains are rejected by the capability check.

## Parameters

- `system_count`: systems per domain. One uses the centroid; additional systems use the existing
  polygon-aware center sampler.
- `orbit_count`, `ring_spacing`, `ring_spacing_power`: orbit count and radial distribution.
- `boundary_mode`, `radius_scale`, `center_margin`, `min_center_spacing`: established concentric
  boundary and placement controls.
- `orbit_eccentricity`: mathematical ellipse eccentricity; zero creates circles.
- `orbit_eccentricity_variation`: deterministic per-orbit deviation from the base eccentricity.
- `orbit_rotation`, `orbit_rotation_variation`: base and per-orbit axis angles in radians.
- `bodies_per_orbit_range`: inclusive body-count range.
- `body_radius_range`, `central_body_radius`: radii in domain units.
- `accent_probability`: probability that an orbiting body uses the accent layer.
- `minimum_body_separation`: minimum angular separation in radians; zero permits clustering.
- `orbit_gaps`: split orbit lines around bodies; defaults to `true`.
- `gap_clearance`: additional domain-unit clearance around each body.

Set both ellipse variation parameters to zero to share eccentricity and orientation across all
orbits. An impossible body count/separation combination fails explicitly. SVG stroke width is
preview styling; physical HP-GL line width remains determined by the installed plotter pen.

## Starting-point presets

The committed `circular` and `elliptical` jobs are deterministic starting-point examples, not
global algorithm defaults. Both use the same seed, square/triangle/pentagon domains, body and gap
settings, and eight orbits; the circular job fixes all ellipse values to zero, while the elliptical
job uses subtle eccentricity and deterministic axis variation.

Generate the circular example into its own directory:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/orbital-concentric-circular.json \
  --output-dir artifacts/orbital-concentric-circular
```

Generate the elliptical example into a separate directory:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/orbital-concentric-elliptical.json \
  --output-dir artifacts/orbital-concentric-elliptical
```

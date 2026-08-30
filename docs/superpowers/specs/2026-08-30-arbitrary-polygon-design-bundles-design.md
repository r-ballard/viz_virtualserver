# Arbitrary Polygon Design Bundles

## Status

Approved architecture specification. This document defines a general-purpose,
placement-independent workflow for generating one or many intrinsic polygon
artworks from a single design job.

## Context

`viz_virtualserver` already provides polygon-domain geometry, semantic surfaces,
ordered groups, typed relations, design passes, neutral vector results, logical
layers, and versioned SVG domain metadata. `plotter-workflow` separately owns
physical placement, imposition, clipping, pen assignment, HP-GL conversion, and
hardware transport.

The cootie-catcher workflow demonstrates the intended boundary: twenty intrinsic
panel SVGs are generated independently, then `cootie_impose.py` scales, rotates,
places, and clips those sources into the twenty physical sheet slots. The new
workflow generalizes artwork generation without replacing that imposition.

## Goals

- Accept an ordered set of one or more arbitrary simple polygon domains.
- Generate an ordered set of intrinsic surface designs from one job.
- Preserve stable IDs, deterministic output, and input order.
- Support independent per-domain passes and explicitly coordinated multi-domain
  passes.
- Export a canonical multi-domain design plus one intrinsic SVG projection per
  declared surface.
- Keep intrinsic artwork generation independent of physical sheet placement.
- Allow the cootie-catcher's twenty panels to be expressed as a preset rather
  than as a special case in the general runner.

## Non-goals

- General physical sheet layout, packing, nesting, or imposition.
- Replacing `cootie_impose.py` or `booklet_impose.py`.
- Assigning logical design layers to physical plotter slots.
- HP-GL generation or plotter transport.
- Inferring semantic relations solely from polygon contact, proximity, overlap,
  or list position.
- Guaranteeing that every registered algorithm supports concave polygons.

## Coordinate frames

The design distinguishes three coordinate frames.

### Domain-local frame

Each polygon's authoritative geometry is expressed in its own reusable local
frame. Algorithms that operate independently use only this frame. Translation,
rotation, or scale in another context must not change an independent domain's
generated design.

### Composition frame

A domain may optionally declare an explicit transform into a shared intrinsic
composition frame. Only passes that require coordinated cross-domain geometry
use this frame. Relative positions in this frame express intrinsic design
relationships, not physical sheet placement.

Absence of a composition transform means that relative distance or direction
between that domain and other domains is undefined. Cross-domain passes that
require a shared frame must reject targets that cannot be resolved into one.

### Physical placement frame

Physical placement belongs exclusively to `plotter-workflow`. Placement
transforms may scale, rotate, translate, and defensively clip exported intrinsic
surface SVGs. Physical transforms are not written back into the design job or
used as algorithm inputs.

## Job model

A domain artwork job contains:

- a schema version;
- a job-level deterministic seed;
- an ordered collection of unique polygon domains;
- optional surfaces that each reference exactly one domain;
- optional ordered groups of surfaces;
- optional typed domain or feature relations;
- optional composition transforms;
- an ordered sequence of design passes and their algorithm-specific parameters;
  and
- export options that do not encode physical placement.

A conceptual document has this shape:

```json
{
  "schema_version": 1,
  "seed": 42,
  "domains": [
    {
      "id": "polygon-a",
      "vertices": [[0, 0], [1, 0], [0, 1]]
    }
  ],
  "surfaces": [
    {"id": "surface-a", "domain_id": "polygon-a"}
  ],
  "groups": [],
  "relations": [],
  "composition_transforms": [],
  "passes": [
    {
      "id": "pass-1",
      "algorithm": "contour-field",
      "target_domain_ids": ["polygon-a"],
      "parameters": {}
    }
  ]
}
```

The concrete request types should reuse existing domain, surface, group,
relation, `DesignPass`, `DesignResult`, and logical-layer concepts rather than
introducing parallel representations.

When `surfaces` is omitted, the runner creates one implicit surface per source
domain in domain order, using the domain ID as the surface ID. An explicitly
empty `surfaces` collection is invalid because a bundle must project at least
one surface.

## One-to-many cardinality

One job accepts `N >= 1` domains and produces projections for every declared
surface. The general runner must not assume a fixed polygon count, shape,
dimension, naming scheme, or template.

The following invariants apply:

- Domain and surface IDs are non-empty and unique in their respective scopes.
- Input domain, surface, group-member, pass, result, and projection order is
  preserved.
- Each declared surface produces exactly one intrinsic projection, including
  surfaces whose valid result contains no drawable paths.
- Projection filenames derive from stable surface IDs rather than list indices.
- Missing, duplicate, or unexpected projection IDs are errors.
- The job publishes no bundle if validation, generation, or projection fails.

The cootie-catcher preset declares four square outer surfaces, eight triangular
selector surfaces, and eight triangular reveal surfaces. It therefore produces
twenty intrinsic SVG projections, which remain ordinary inputs to the existing
cootie-catcher manifest and imposition workflow.

## Determinism and seeds

Independent per-domain generation derives its random stream from the job seed,
algorithm/pass identity, and stable domain ID. It must not derive randomness
from the domain's list index.

Consequently, inserting or reordering unrelated domains does not change an
existing independent domain's paths. A coordinated multi-domain pass derives a
group stream from the job seed, pass identity, and ordered target IDs because
target order may be meaningful for that pass.

Repeated execution of the same validated job with the same registered
algorithms must produce semantically identical bundle content.

## Pass execution

A design pass may target one domain, a subset, or the complete set. Before an
algorithm runs, the executor validates target existence and the algorithm's
declared geometry capabilities.

Independent passes receive domain-local geometry. Coordinated passes receive
the ordered targets, declared relations, and resolved composition transforms
they request. Algorithms must not infer semantic adjacency or correspondence
merely because polygons touch or overlap.

Each pass returns neutral vector paths in logical layers through `DesignResult`.
Operations that create geometry domains return new immutable derived domains
with provenance. Algorithms do not assign physical pens.

Every returned path must be associated with exactly one source or derived
domain ID. The current neutral `VectorPath` representation does not yet carry
that association, so implementation must extend the neutral result contract
rather than infer path ownership from pass targets or geometric containment.
This association is required for deterministic surface projection, especially
when one pass targets multiple overlapping domains.

## Canonical bundle

A successful job produces a directory-level bundle:

```text
design.json
design.svg
surfaces/
  <surface-id>.svg
```

`design.json` is the machine-readable audit record. It contains the validated
job identity, schema version, seed, ordered IDs, pass summaries, algorithm
identities, derived-domain provenance, output paths, and deterministic content
digests. It contains no physical placement data.

`design.svg` is the canonical multi-domain visualization. It retains
`viz-domain/v1` metadata and neutral logical layers.

Each file under `surfaces/` is an intrinsic projection for one declared
surface. Its view box is local to that surface's domain, its geometry is rebased
consistently, its intrinsic orientation metadata is explicit, and it retains
the logical layers and provenance relevant to that surface. A defensive polygon
clip may be included, but algorithms remain responsible for shape-aware
generation.

The exporter must sanitize stable surface IDs for filenames deterministically
and reject collisions after sanitization.

## Projection semantics

Projection does not rerun an algorithm. It selects the paths associated with a
surface's referenced domain from the completed neutral result, maps them into
the surface's domain-local frame, writes intrinsic canvas metadata, and
serializes logical layers.

A coordinated pass may generate geometry that crosses several composition-frame
domains. Projection clips or partitions that geometry into the relevant local
surface outputs while preserving common pass and provenance identifiers. The
canonical multi-domain result remains the authoritative record of the
coordinated design.

## Placement integration

Placement consumes only exported surface SVGs and a separate placement
manifest. For the cootie catcher, the manifest maps each semantic slot to its
corresponding projection:

```json
{"slot": "selector-1", "source": "surfaces/selector-1.svg"}
```

`plotter-workflow` remains responsible for target polygon geometry, margins,
fit mode, rotation, clipping, physical sheet coordinates, pen planning,
conversion, preflight, and sending. No physical placement transform becomes
part of the canonical design bundle.

## Validation and failure behavior

Validation occurs before output publication and rejects:

- malformed, non-finite, self-intersecting, or zero-area polygons;
- duplicate or empty IDs;
- unknown domain, surface, group, relation, or pass references;
- composition transforms that are non-finite or non-invertible;
- passes whose algorithms do not support the target geometry;
- coordinated passes lacking required composition-frame information;
- algorithms returning paths for undeclared targets;
- duplicate, missing, or unexpected surface projections; and
- filename collisions after ID sanitization.

Bundle creation is atomic. Files are first produced in a temporary sibling
directory, fully validated, and then published as a complete bundle. A failed
job must not replace a previously valid bundle or expose a partial new one.

## Testing strategy

Development follows strict task-by-task TDD. Tests cover:

- one polygon and one surface;
- two heterogeneous polygons;
- convex and concave domain validation independent of algorithm capability;
- the twenty cootie-catcher surfaces;
- an arbitrary larger set with no fixed-count assumptions;
- stable domain results after unrelated insertion or reordering;
- preserved declared ordering throughout the bundle;
- independent and coordinated pass execution;
- selector/reveal edge correspondence through explicit relations;
- optional composition-frame resolution and missing-frame rejection;
- empty but valid surface artwork;
- per-surface projection, rebasing, clipping, orientation, and logical layers;
- duplicate IDs, unknown references, output mismatches, and sanitized filename
  collisions;
- atomic failure without partial publication; and
- deterministic bundle regeneration.

Existing single-domain HTTP behavior, legacy SVG metadata, concentric endpoint
compatibility, and `plotter-workflow` imposition tests remain regression
requirements.

## Repository boundaries

`viz_virtualserver` owns the job schema, validation, intrinsic coordinate
frames, pass execution, deterministic generation, neutral results, and bundle
projection/export.

`plotter-workflow` owns template-driven physical placement, source fitting,
physical clipping, orientation resolution, construction guides,
logical-to-physical pen planning, HP-GL conversion, preflight, and transport.

Neither repository silently assumes responsibilities assigned to the other.

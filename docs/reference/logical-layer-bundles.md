# Neutral logical-layer bundles

The domain-bundle CLI accepts an optional top-level `projection` field for
`orbital-concentric`-only jobs. A string selects a shipped preset; a projection
object declares ordered `match` rules with exactly one `layer` or `group`. Job
files without `projection` keep the existing legacy bundle behavior, except
Truchet-only jobs with multiple curve channels or a separate polygon outline layer:
those automatically use
the neutral contract described in the [Truchet guide](../algorithms/truchet.md).
A `match`
can select `feature_role`, `domain_id`, or declared orbital attributes; list
values on attributes express membership. Dynamic `group_by` keys may also include
`domain_id`.

Generate the per-body example from Git Bash:

```bash
uv run --locked viz-domain-bundle \
  "examples/domain-jobs/orbital-per-body.json" \
  --output-dir ".artifacts/orbital-per-body"
```

Inspect `design.json` for `logical_layer_contract`, the normalized `projection`,
the ordered `logical_layers` catalog, and each surface's layer inventory. Neutral
surface SVGs repeat the contract on the root as `data-viz-layer-contract`; layer
groups expose `data-viz-layer-id`, `data-viz-layer-ordinal`, and
`data-viz-layer-label`, while paths retain semantic provenance attributes.

Logical layers are not physical pens. The producer permits any finite layer
count and never allocates pen slots. A bundle with more than eight included
layers, including this per-body example, requires an explicit merge or multi-pass
plan in the downstream plotter workflow before plotting.

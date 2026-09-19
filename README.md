# viz_virtualserver

See [RADIAL_TILES.md](RADIAL_TILES.md) for the plotter-native radial tile field
algorithm and its runnable three-polygon example.
See [ORBITAL_CONCENTRIC.md](ORBITAL_CONCENTRIC.md) for simplified orbital diagrams
with independently seeded polygon surfaces and three logical layers.
A Python 3 virtual server using fastapi and gunicorn to render graphs with Python 3 using Processing Python Mode

## L-system lineage layers

Set `lineage_policy` on `LSystemRequest` (or in its JSON input) to choose how
replacement symbols inherit birth-generation labels:

| Policy | Replacement rule |
| --- | --- |
| `inherit_all` (C, default) | All children matching the parent symbol retain its birth; different symbols receive the current generation. |
| `rewrite` (B) | Every child of an explicit production receives the current generation, including `F -> F`. |
| `inherit_first` (A) | The first child matching the parent symbol retains its birth; all other children receive the current generation. |

Symbols with no production always retain their birth. These are lineage labels,
not the first appearance of geometry at a coordinate. The default preserves the
multicolor plant-booklet behavior in `examples/lsystems/plant-booklet.json`.

```python
from lsystem.models import LSystemRequest
from lsystem.service import generate_lsystem_design, generate_lsystem_growth_pages

request = LSystemRequest(
    axiom="X", rules={"X": "FX", "F": "FF"}, generations=4,
    lineage_policy="inherit_all", growth_mode="cumulative",
)
design = generate_lsystem_design(request, domain_id="page-4")
pages = generate_lsystem_growth_pages(request, generation_numbers=(1, 2, 3, 4))
```

Neutral designs use native logical IDs such as `generation-1` and `generation-4`;
growth pages retain the legacy pen mapping. Each page uses its selected generation's
geometry. `cumulative` includes its present birth groups from 1 through N; `delta`
includes only birth N. Missing groups are omitted, and delta can be empty. For
example, with C, `X -> F` followed by `F -> FF` leaves both segments at birth 1,
so delta 2 is empty. Birth 0 is unplotted: axiom `F` with `F -> FF` remains
unplotted under C. Policy changes can therefore change the selected strokes,
even though the underlying turtle geometry is the same.

Lineage policies apply to neutral semantic designs and growth pages. The ordinary
`generate_lsystem()` service and `/LSystem` and `/LSystemSvg` endpoints continue to
render complete generation snapshots grouped by generation, independently of this
policy. Use `result_to_generation_svgs()` for separate complete-generation pages;
lineage layers do not overlay earlier snapshots.

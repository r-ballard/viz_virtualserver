from collections import defaultdict

import pytest
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.generators.truchet.multiscale_composition import render_multiscale_components
from viz_virtualserver.generators.truchet.multiscale_models import MultiscaleParameters
from viz_virtualserver.generators.truchet.multiscale_service import TruchetMultiscaleDomainAlgorithm
from viz_virtualserver.generators.truchet.multiscale_subdivision import assemble_multiscale
from viz_virtualserver.generators.truchet.service import TruchetDomainAlgorithm

CHANNELS = ("curve-blue", "curve-orange", "curve-green")
SQUARE = ((0, 0), (80, 0), (80, 80), (0, 80))
ALGORITHMS = (TruchetDomainAlgorithm(), TruchetMultiscaleDomainAlgorithm())


def generate(algorithm, vertices=SQUARE, layers=CHANNELS, *, seed=31):
    domain = PolygonDomain("panel", vertices)
    canvas = CanvasGeometry("square", 80, 80, SQUARE, "edge:0")
    design_pass = DesignPass("tiles", algorithm.name, (domain.id,), {},
                             tuple(LogicalLayer(i) for i in layers))
    return algorithm.generate(canvas=canvas, domains=(domain,), design_pass=design_pass,
        context=AlgorithmContext(1, 2, {domain.id: seed}, (), (), (), {}))


def linework(result):
    return unary_union([LineString(p.points + (p.points[:1] if p.closed else ()))
                        for p in result.paths])


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_three_channels_are_reproducible_and_preserve_monochrome_linework(algorithm):
    color = generate(algorithm)
    mono = generate(algorithm, layers=("truchet-curves",))
    assert color == generate(algorithm)
    assert {p.layer_id for p in color.paths} == set(CHANNELS)
    assert linework(color).symmetric_difference(linework(mono)).length < 1e-9
    assert not color.derived_domains
    assert all(p.domain_id == "panel" and p.producing_pass_id == "tiles" for p in color.paths)
    assert all(Polygon(SQUARE).covers(LineString(p.points + (p.points[:1] if p.closed else ())))
               for p in color.paths)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_ordered_channel_names_can_be_changed_without_changing_assignment(algorithm):
    a = generate(algorithm)
    b = generate(algorithm, layers=("pen-cyan", "pen-magenta", "pen-yellow"))
    assert tuple(p.points for p in a.paths) == tuple(p.points for p in b.paths)
    mapping = dict(zip(CHANNELS, ("pen-cyan", "pen-magenta", "pen-yellow")))
    assert tuple(mapping[p.layer_id] for p in a.paths) == tuple(p.layer_id for p in b.paths)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("layers", [(), ("a", "a"), ("",), (" ",)])
def test_missing_duplicate_or_blank_channels_reject(algorithm, layers):
    with pytest.raises(ValueError, match="curve layer"):
        generate(algorithm, layers=layers)


def test_multiscale_fragments_keep_their_preclip_component_channel():
    vertices = ((0,0), (80,0), (80,80), (50,80), (50,15), (30,15), (30,80), (0,80))
    domain = PolygonDomain("panel", vertices)
    a = assemble_multiscale((0,0,80,80), parameters=MultiscaleParameters(), seed=31)
    components = render_multiscale_components(a, domain, curve_tolerance=.02)
    groups = defaultdict(list)
    for component_id, path in components:
        groups[component_id].append(path)
    assert any(len(paths) > 1 for paths in groups.values())
    result = generate(TruchetMultiscaleDomainAlgorithm(), vertices)
    by_geometry = {(p.points, p.closed): p.layer_id for p in result.paths}
    for paths in groups.values():
        assert len({by_geometry[p.points, p.closed] for p in paths}) == 1


def test_classic_fragments_keep_their_preclip_component_channel():
    from viz_virtualserver.generators.truchet.assembly import assemble_grid
    from viz_virtualserver.generators.truchet.geometry import clip_paths, render_arrangement
    from viz_virtualserver.generators.truchet.models import TruchetParameters
    vertices = ((0,0), (80,0), (80,80), (50,80), (50,15), (30,15), (30,80), (0,80))
    domain = PolygonDomain("panel", vertices)
    a = assemble_grid((0,0,80,80), tile_size=10, seed=31)
    groups = [clip_paths((path,), domain) for path in render_arrangement(a, TruchetParameters())]
    assert any(len(paths) > 1 for paths in groups)
    result = generate(TruchetDomainAlgorithm(), vertices)
    by_geometry = {(p.points, p.closed): p.layer_id for p in result.paths}
    for paths in groups:
        assert len({by_geometry[p.points, p.closed] for p in paths}) <= 1

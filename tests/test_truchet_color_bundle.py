import xml.etree.ElementTree as ET

import pytest

from viz_virtualserver.canvas.bundle import write_neutral_bundle
from viz_virtualserver.canvas.job_io import load_domain_artwork_job
from viz_virtualserver.canvas.runner import run_domain_artwork_job
from viz_virtualserver.cli.domain_bundle import ALGORITHMS
from viz_virtualserver.generators.truchet.color_bundle import (
    project_truchet_color_paths,
    truchet_color_projection,
)


def job(layers_a, layers_b=None, *, parameters=None):
    passes = [{"id":"a", "algorithm":"truchet", "target_domain_ids":["p"],
               "parameters": parameters or {}, "logical_layers":layers_a}]
    if layers_b is not None:
        passes.append({"id":"b", "algorithm":"truchet-multiscale",
                       "target_domain_ids":["p"], "parameters":{"max_depth":0},
                       "logical_layers":layers_b})
    return load_domain_artwork_job({"schema_version":1, "seed":31,
        "domains":[{"id":"p", "vertices":[[0,0],[40,0],[40,40],[0,40]]}], "passes":passes})


def test_projection_unifies_shared_channels_and_preserves_pass_path_identity():
    j = job([{"id":"blue", "label":"Blue"}, {"id":"orange", "label":"Orange"}],
            [{"id":"green", "label":"Green"}, {"id":"blue", "label":"Blue"}])
    projection = truchet_color_projection(j)
    assert [rule.fixed.id for rule in projection.rules] == ["blue", "orange", "green"]
    state = run_domain_artwork_job(j, ALGORITHMS)
    design = project_truchet_color_paths(state, projection)
    originals = [p for result in state.results for p in result.paths]
    assert [(p.points, p.closed, p.domain_id, p.layer_id) for p in design.paths] == [
        (p.points, p.closed, p.domain_id, p.layer_id) for p in originals]
    assert len({p.semantic_path.path_id for p in design.paths}) == len(design.paths)


def test_single_channel_job_retains_legacy_export_and_mixed_passes_use_neutral():
    assert truchet_color_projection(job([{"id":"truchet-curves"}])) is None
    j = job([{"id":"outline-like-channel"}], [{"id":"a"}, {"id":"b"}])
    projection = truchet_color_projection(j)
    state = run_domain_artwork_job(j, ALGORITHMS)
    design = project_truchet_color_paths(state, projection)
    assert any(p.layer_id == "outline-like-channel" for p in design.paths)


def test_conflicting_shared_labels_reject_before_generation():
    j = job([{"id":"a", "label":"Blue"}, {"id":"b"}],
            [{"id":"a", "label":"Red"}, {"id":"b"}])
    with pytest.raises(ValueError, match="conflicting.*label"):
        truchet_color_projection(j)


def test_empty_geometry_can_project_without_inventing_strokes():
    j = job([{"id":"a"}, {"id":"b"}], parameters={"tile_size":10000})
    projection = truchet_color_projection(j)
    state = run_domain_artwork_job(j, ALGORITHMS)
    assert not state.results[0].paths
    design = project_truchet_color_paths(state, projection)
    assert not design.paths and not design.catalog.entries


def test_unused_channels_are_omitted_and_empty_bundle_still_publishes(tmp_path):
    j = job([{"id":f"color-{i}"} for i in range(100)])
    projection = truchet_color_projection(j)
    design = project_truchet_color_paths(run_domain_artwork_job(j, ALGORITHMS), projection)
    used = {p.layer_id for p in design.paths}
    assert 0 < len(used) < 100
    assert {entry.id for entry in design.catalog.entries} == used
    bundle = write_neutral_bundle(j, design, tmp_path / "used", projection=projection)
    root = ET.fromstring(bundle.design_svg_path.read_text())
    assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"

    empty_job = job([{"id":"a"}, {"id":"b"}], parameters={"tile_size":10000})
    empty_projection = truchet_color_projection(empty_job)
    empty = project_truchet_color_paths(run_domain_artwork_job(empty_job, ALGORITHMS),
                                       empty_projection)
    bundle = write_neutral_bundle(empty_job, empty, tmp_path / "empty",
                                 projection=empty_projection)
    root = ET.fromstring(bundle.surface_paths[0].read_text())
    assert not root.findall("{http://www.w3.org/2000/svg}g")

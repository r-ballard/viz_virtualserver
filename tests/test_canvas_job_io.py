from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from viz_canvas.job_io import load_domain_artwork_job, read_domain_artwork_job

TWO_DOMAIN_PAYLOAD: dict[str, object] = {
    "schema_version": 1,
    "seed": 42,
    "domains": [
        {
            "id": "triangle",
            "vertices": [[0, 0], [10, 0], [5, 10]],
        },
        {
            "id": "square",
            "vertices": [[20, 0], [30, 0], [30, 10], [20, 10]],
        },
    ],
    "surfaces": [
        {
            "id": "front",
            "domain_id": "triangle",
            "feature_aliases": {
                "apex": {
                    "domain_id": "triangle",
                    "feature_type": "vertex",
                    "index": 2,
                },
                "base": {
                    "domain_id": "triangle",
                    "feature_type": "edge",
                    "index": 0,
                },
            },
        },
        {
            "id": "back",
            "domain_id": "square",
            "feature_aliases": {
                "top": {
                    "domain_id": "square",
                    "feature_type": "edge",
                    "index": 0,
                },
                "left": {
                    "domain_id": "square",
                    "feature_type": "edge",
                    "index": 1,
                },
            },
        },
    ],
    "groups": [
        {
            "id": "paired",
            "surface_ids": ["back", "front"],
            "seed": 7,
            "metadata": {"purpose": "paired artwork"},
        },
        {
            "id": "paired-reverse",
            "surface_ids": ["front", "back"],
            "seed": 8,
            "metadata": {"purpose": "reverse pair"},
        },
    ],
    "relations": [
        {
            "id": "topology",
            "relation_type": "corresponds_to",
            "source": {
                "domain_id": "triangle",
                "feature_type": "vertex",
                "index": 2,
            },
            "target": {"domain_id": "square"},
            "metadata": {"weight": 1},
        },
        {
            "id": "reverse-topology",
            "relation_type": "corresponds_to",
            "source": {"domain_id": "square"},
            "target": {
                "domain_id": "triangle",
                "feature_type": "vertex",
                "index": 0,
            },
            "metadata": {"weight": 2},
        },
    ],
    "composition_transforms": [
        {"domain_id": "triangle", "matrix": [1, 0, 0, 1, 3, 4]},
        {"domain_id": "square", "matrix": [2, 0, 0, 2, 5, 6]},
    ],
    "passes": [
        {
            "id": "paired-lines",
            "algorithm": "record",
            "target_domain_ids": ["triangle", "square"],
            "parameters": {"spacing": 2, "style": {"dash": [3, 1]}},
            "logical_layers": [
                {"id": "underlay", "label": "Underlay"},
                {"id": "ink", "label": "Ink"},
            ],
            "group_context_ids": ["paired"],
            "relation_context_ids": ["topology"],
            "depends_on": [],
        },
        {
            "id": "finishing",
            "algorithm": "record-final",
            "target_domain_ids": ["square", "triangle"],
            "parameters": {"color": "black", "width": 2},
            "logical_layers": [
                {"id": "highlight", "label": "Highlight"},
                {"id": "outline", "label": "Outline"},
            ],
            "group_context_ids": ["paired-reverse", "paired"],
            "relation_context_ids": ["reverse-topology", "topology"],
            "depends_on": ["paired-lines"],
        },
    ],
}


def test_loader_builds_ordered_two_domain_job() -> None:
    job = load_domain_artwork_job(TWO_DOMAIN_PAYLOAD)

    assert [domain.id for domain in job.domains] == ["triangle", "square"]
    assert [
        (surface.id, surface.domain_id) for surface in job.resolved_surfaces
    ] == [("front", "triangle"), ("back", "square")]
    assert [
        (alias, reference.domain_id, reference.feature_type.value, reference.index)
        for surface in job.resolved_surfaces
        for alias, reference in surface.feature_aliases.items()
    ] == [
        ("apex", "triangle", "vertex", 2),
        ("base", "triangle", "edge", 0),
        ("top", "square", "edge", 0),
        ("left", "square", "edge", 1),
    ]
    assert [group.id for group in job.groups] == ["paired", "paired-reverse"]
    assert [
        (group.surface_ids, group.seed, dict(group.metadata)) for group in job.groups
    ] == [
        (("back", "front"), 7, {"purpose": "paired artwork"}),
        (("front", "back"), 8, {"purpose": "reverse pair"}),
    ]
    assert [relation.id for relation in job.relations] == [
        "topology",
        "reverse-topology",
    ]
    assert job.relations[0].source.feature_type.value == "vertex"
    assert job.relations[0].source.index == 2
    assert job.relations[0].target.domain_id == "square"
    assert job.relations[0].relation_type.value == "corresponds_to"
    assert dict(job.relations[0].metadata) == {"weight": 1}
    assert job.relations[1].source.domain_id == "square"
    assert job.relations[1].target.feature_type.value == "vertex"
    assert job.relations[1].target.index == 0
    assert job.relations[1].relation_type.value == "corresponds_to"
    assert dict(job.relations[1].metadata) == {"weight": 2}
    assert [
        (
            transform.domain_id,
            transform.transform.a,
            transform.transform.b,
            transform.transform.c,
            transform.transform.d,
            transform.transform.e,
            transform.transform.f,
        )
        for transform in job.composition_transforms
    ] == [
        ("triangle", 1.0, 0.0, 0.0, 1.0, 3.0, 4.0),
        ("square", 2.0, 0.0, 0.0, 2.0, 5.0, 6.0),
    ]
    assert [
        (layer.id, layer.label) for layer in job.passes[0].logical_layers
    ] == [("underlay", "Underlay"), ("ink", "Ink")]
    assert (job.passes[0].id, job.passes[0].algorithm) == ("paired-lines", "record")
    assert job.passes[0].target_domain_ids == ("triangle", "square")
    assert job.passes[0].group_context_ids == ("paired",)
    assert job.passes[0].relation_context_ids == ("topology",)
    assert job.passes[0].depends_on == ()
    assert job.passes[0].parameters == {"spacing": 2, "style": {"dash": [3, 1]}}
    assert [(design_pass.id, design_pass.algorithm) for design_pass in job.passes] == [
        ("paired-lines", "record"),
        ("finishing", "record-final"),
    ]
    assert job.passes[1].target_domain_ids == ("square", "triangle")
    assert [
        (layer.id, layer.label) for layer in job.passes[1].logical_layers
    ] == [("highlight", "Highlight"), ("outline", "Outline")]
    assert job.passes[1].group_context_ids == ("paired-reverse", "paired")
    assert job.passes[1].relation_context_ids == ("reverse-topology", "topology")
    assert job.passes[1].depends_on == ("paired-lines",)
    assert job.passes[1].parameters == {"color": "black", "width": 2}
    assert [
        (
            design_pass.id,
            design_pass.group_context_ids,
            design_pass.relation_context_ids,
            design_pass.depends_on,
            list(design_pass.parameters.items()),
        )
        for design_pass in job.passes
    ] == [
        (
            "paired-lines",
            ("paired",),
            ("topology",),
            (),
            [("spacing", 2), ("style", {"dash": [3, 1]})],
        ),
        (
            "finishing",
            ("paired-reverse", "paired"),
            ("reverse-topology", "topology"),
            ("paired-lines",),
            [("color", "black"), ("width", 2)],
        ),
    ]


def test_reader_loads_versioned_json_job(tmp_path: Path) -> None:
    path = tmp_path / "job.json"
    path.write_text(json.dumps(TWO_DOMAIN_PAYLOAD), encoding="utf-8")

    job = read_domain_artwork_job(path)

    assert job.seed == 42
    assert [design_pass.id for design_pass in job.passes] == [
        "paired-lines",
        "finishing",
    ]


def test_loader_rejects_unsupported_schema_version() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["schema_version"] = 2

    with pytest.raises(ValueError, match="unsupported schema version: 2"):
        load_domain_artwork_job(payload)


def test_loader_rejects_boolean_schema_version() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["schema_version"] = True

    with pytest.raises(ValidationError, match="schema_version"):
        load_domain_artwork_job(payload)


def test_loader_rejects_malformed_relation_endpoint() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["relations"][0]["source"] = {  # type: ignore[index]
        "domain_id": "triangle",
        "feature_type": "vertex",
    }

    with pytest.raises(ValidationError, match="index"):
        load_domain_artwork_job(payload)


def test_loader_rejects_null_feature_type_in_relation_endpoint() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["relations"][0]["source"] = {  # type: ignore[index]
        "domain_id": "triangle",
        "feature_type": None,
        "index": 2,
    }

    with pytest.raises(ValidationError, match="feature_type"):
        load_domain_artwork_job(payload)


def test_loader_rejects_missing_domains() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    del payload["domains"]

    with pytest.raises(ValidationError, match="domains"):
        load_domain_artwork_job(payload)


def test_loader_rejects_nonnumeric_affine_matrix() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["composition_transforms"][0]["matrix"][4] = "right"  # type: ignore[index]

    with pytest.raises(ValidationError, match="matrix"):
        load_domain_artwork_job(payload)


def test_loader_rejects_boolean_affine_matrix_entry() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["composition_transforms"][0]["matrix"][4] = True  # type: ignore[index]

    with pytest.raises(ValidationError, match="matrix"):
        load_domain_artwork_job(payload)


def test_loader_rejects_unknown_fields() -> None:
    payload = deepcopy(TWO_DOMAIN_PAYLOAD)
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="unexpected"):
        load_domain_artwork_job(payload)

from __future__ import annotations

import dataclasses
import json
import xml.etree.ElementTree as ET

from .design import DesignResult, DesignState, VectorPath
from .frames import AffineTransform, resolve_composition_transforms
from .geometry import CanvasGeometry
from .jobs import DomainArtworkJob
from .models import PolygonDomain
from .projection import SurfaceProjection

SVG_NS = "http://www.w3.org/2000/svg"
CLIP_ID = "viz-canvas-clip"
ET.register_namespace("", SVG_NS)


def canvas_root_attributes(canvas: CanvasGeometry) -> dict[str, str]:
    """Return SVG-root metadata that makes the logical canvas self-describing."""

    up_x, up_y = canvas.up_vector
    return {
        "viewBox": f"0 0 {_fmt(canvas.width)} {_fmt(canvas.height)}",
        "width": _fmt(canvas.width),
        "height": _fmt(canvas.height),
        "data-viz-canvas-version": "1",
        "data-viz-canvas-shape": canvas.shape,
        "data-viz-canvas-coordinate-system": "svg-y-down",
        "data-viz-canvas-up-anchor": canvas.up_anchor,
        "data-viz-canvas-up-vector": f"{_fmt(up_x)},{_fmt(up_y)}",
        "data-viz-canvas-polygon": _polygon_points(canvas),
        "data-viz-canvas-clip-id": CLIP_ID,
    }


def append_canvas_clip(root: ET.Element, canvas: CanvasGeometry) -> str:
    """Add the canonical user-space clip path and return its SVG URL value.

    Exporters apply the returned value directly to their own drawable groups.
    In particular, strict ``pen-N`` groups must remain top-level SVG children.
    """

    defs = ET.SubElement(root, _tag("defs"))
    clip = ET.SubElement(
        defs,
        _tag("clipPath"),
        {"id": CLIP_ID, "clipPathUnits": "userSpaceOnUse"},
    )
    ET.SubElement(clip, _tag("path"), {"d": canvas_path_data(canvas)})
    return f"url(#{CLIP_ID})"


def canvas_to_svg(
    canvas: CanvasGeometry,
    *,
    include_boundary: bool = False,
    boundary_stroke_width: float = 1.0,
) -> str:
    """Serialize an empty, metadata-bearing SVG drawing canvas.

    ``include_boundary`` is intended for visual/debug templates. The boundary
    is real drawable geometry when enabled and should not be confused with the
    non-rendering clip path in ``<defs>``.
    """

    if boundary_stroke_width <= 0:
        raise ValueError("boundary_stroke_width must be positive")

    root = ET.Element(_tag("svg"), canvas_root_attributes(canvas))
    append_canvas_clip(root, canvas)

    if include_boundary:
        guide = ET.SubElement(
            root,
            _tag("g"),
            {
                "id": "canvas-guide",
                "data-viz-role": "canvas-guide",
                "fill": "none",
                "stroke": "#000000",
                "stroke-width": _fmt(boundary_stroke_width),
            },
        )
        ET.SubElement(guide, _tag("path"), {"d": canvas_path_data(canvas)})

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    )


def build_domain_metadata_payload(canvas: CanvasGeometry) -> dict[str, object]:
    """Build canonical, versioned metadata for every declared polygon domain."""

    domains: list[dict[str, object]] = []
    for domain in canvas.domains:
        provenance = domain.provenance
        domains.append(
            {
                "id": domain.id,
                "vertices": [[float(x), float(y)] for x, y in domain.vertices],
                "provenance": (
                    None
                    if provenance is None
                    else {
                        "source_domain_ids": list(provenance.source_domain_ids),
                        "generating_pass_id": provenance.generating_pass_id,
                        "operation": provenance.operation,
                    }
                ),
            }
        )
    return {"schema": "viz-domain/v1", "domains": domains}


def serialize_design_result_svg(
    *,
    canvas: CanvasGeometry,
    results: tuple[DesignResult, ...],
    view_box: tuple[float, float, float, float] | None = None,
) -> str:
    """Serialize neutral design paths with domain metadata and logical layers."""

    root_attributes = canvas_root_attributes(canvas)
    if view_box is not None:
        min_x, min_y, width, height = view_box
        root_attributes["viewBox"] = " ".join(
            _fmt(value) for value in (min_x, min_y, width, height)
        )
    root = ET.Element(_tag("svg"), root_attributes)
    clip_value = append_canvas_clip(root, canvas)
    _append_domain_metadata(root, canvas)

    layers: dict[str, ET.Element] = {}
    for result in results:
        for path in result.paths:
            layer = layers.get(path.layer_id)
            if layer is None:
                layer = ET.SubElement(
                    root,
                    _tag("g"),
                    {
                        "id": path.layer_id,
                        "data-viz-role": "logical-layer",
                        "data-viz-layer": path.layer_id,
                        "clip-path": clip_value,
                        "fill": "none",
                        "stroke": "#000000",
                        "stroke-width": "1",
                        "stroke-linecap": "round",
                        "stroke-linejoin": "round",
                    },
                )
                layers[path.layer_id] = layer
            ET.SubElement(layer, _tag("path"), {"d": _vector_path_data(path)})

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    )


def canonical_design_to_svg(job: DomainArtworkJob, state: DesignState) -> str:
    """Serialize completed paths in the job's explicitly declared canonical frame."""

    transforms = resolve_composition_transforms(job.domains, job.composition_transforms)
    canonical_domains = tuple(
        _transform_domain(domain, transforms.get(domain.id))
        for domain in (*state.source_domains, *state.derived_domains)
    )
    canonical_results = tuple(
        dataclasses.replace(
            result,
            paths=tuple(
                dataclasses.replace(
                    path,
                    points=(
                        tuple(transforms[path.domain_id].apply(point) for point in path.points)
                        if path.coordinate_frame == "domain" and path.domain_id in transforms
                        else path.points
                    ),
                    coordinate_frame="composition",
                )
                for path in result.paths
            ),
        )
        for result in state.results
    )
    points = tuple(
        point
        for domain in canonical_domains
        for point in domain.vertices
    ) + tuple(
        point
        for result in canonical_results
        for path in result.paths
        for point in path.points
    )
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_x = max(x for x, _ in points)
    max_y = max(y for _, y in points)
    canvas = CanvasGeometry(
        shape="rectangle",
        width=max_x - min_x,
        height=max_y - min_y,
        polygon=((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)),
        up_anchor="edge:0",
        domains=canonical_domains,
    )
    return serialize_design_result_svg(
        canvas=canvas,
        results=canonical_results,
        view_box=(min_x, min_y, max_x - min_x, max_y - min_y),
    )


def _transform_domain(
    domain: PolygonDomain, transform: AffineTransform | None
) -> PolygonDomain:
    if transform is None:
        return domain
    return dataclasses.replace(
        domain,
        vertices=tuple(transform.apply(point) for point in domain.vertices),
    )


def surface_projection_to_svg(projection: SurfaceProjection) -> str:
    """Serialize one rebased surface projection as an intrinsic polygon SVG."""

    min_x, min_y, max_x, max_y = projection.bounds
    canvas = CanvasGeometry(
        shape="polygon",
        width=max_x - min_x,
        height=max_y - min_y,
        polygon=projection.domain.vertices,
        up_anchor=projection.up_anchor,
        domains=(projection.domain,),
    )
    root = ET.Element(_tag("svg"), canvas_root_attributes(canvas))
    clip_value = append_canvas_clip(root, canvas)
    _append_domain_metadata(root, canvas)

    layer_ids = [layer.id for layer in projection.layers]
    known = set(layer_ids)
    for path in projection.paths:
        if path.layer_id not in known:
            known.add(path.layer_id)
            layer_ids.append(path.layer_id)
    for layer_id in layer_ids:
        paths = tuple(path for path in projection.paths if path.layer_id == layer_id)
        if not paths:
            continue
        layer = ET.SubElement(
            root,
            _tag("g"),
            _logical_layer_attributes(layer_id, clip_value),
        )
        for path in paths:
            ET.SubElement(layer, _tag("path"), {"d": _vector_path_data(path)})

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    )


def _append_domain_metadata(root: ET.Element, canvas: CanvasGeometry) -> None:
    metadata = ET.SubElement(root, _tag("metadata"), {"id": "viz-domain-metadata"})
    metadata.text = json.dumps(
        build_domain_metadata_payload(canvas), separators=(",", ":"), sort_keys=False
    )


def _logical_layer_attributes(layer_id: str, clip_value: str) -> dict[str, str]:
    return {
        "id": layer_id,
        "data-viz-role": "logical-layer",
        "data-viz-layer": layer_id,
        "clip-path": clip_value,
        "fill": "none",
        "stroke": "#000000",
        "stroke-width": "1",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }


def canvas_path_data(canvas: CanvasGeometry) -> str:
    points = list(canvas.polygon)
    first_x, first_y = points[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def _vector_path_data(path: VectorPath) -> str:
    first_x, first_y = path.points[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in path.points[1:])
    if path.closed:
        commands.append("Z")
    return " ".join(commands)


def _polygon_points(canvas: CanvasGeometry) -> str:
    return " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in canvas.polygon)


def _tag(local_name: str) -> str:
    return f"{{{SVG_NS}}}{local_name}"


def _fmt(value: float) -> str:
    text = f"{float(value):.9f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"

"""Completed-state validation shared by execution and publication boundaries."""

from __future__ import annotations

from .design import DesignPass, DesignState
from .jobs import DomainArtworkJob


def validate_completed_design_state(
    job: DomainArtworkJob,
    state: DesignState,
) -> None:
    """Require a completed state to satisfy the job's schema-v1 contracts."""

    if state.source_domains != job.domains:
        raise ValueError("design state source domains do not match the job")
    expected_pass_ids = tuple(design_pass.id for design_pass in job.passes)
    result_pass_ids = tuple(result.producing_pass_id for result in state.results)
    if result_pass_ids != expected_pass_ids:
        raise ValueError("design state results do not match declared pass order")
    result_derived = tuple(
        domain for result in state.results for domain in result.derived_domains
    )
    if state.derived_domains != result_derived:
        raise ValueError("design state derived domains do not match result provenance")
    domain_ids = {domain.id for domain in (*state.source_domains, *state.derived_domains)}
    if len(domain_ids) != len(state.source_domains) + len(state.derived_domains):
        raise ValueError("design state contains duplicate domain ids")

    prior_derived_ids: set[str] = set()
    for design_pass, result in zip(job.passes, state.results, strict=True):
        coordinated = _is_coordinated(design_pass)
        if coordinated:
            for domain_id in design_pass.target_domain_ids:
                if domain_id in prior_derived_ids:
                    raise ValueError(
                        "composition frame is unavailable for derived target domain: "
                        f"{domain_id}"
                    )

        new_derived_ids = {domain.id for domain in result.derived_domains}
        for domain in result.derived_domains:
            provenance = domain.provenance
            if provenance is None:  # pragma: no cover - DesignResult validates this
                raise ValueError("derived domain requires provenance")
            for source_domain_id in provenance.source_domain_ids:
                if source_domain_id not in design_pass.target_domain_ids:
                    raise ValueError(
                        f"derived domain {domain.id} provenance source is not a pass "
                        f"target: {source_domain_id}"
                    )

        allowed_owners = {*design_pass.target_domain_ids, *new_derived_ids}
        for path in result.paths:
            if path.domain_id not in domain_ids:
                raise ValueError(f"design path references unknown domain: {path.domain_id}")
            if path.domain_id not in allowed_owners:
                raise ValueError(
                    f"design path owner {path.domain_id!r} is not a target or derived "
                    f"domain of producing pass {result.producing_pass_id!r}"
                )
            if coordinated and path.domain_id in new_derived_ids:
                raise ValueError(
                    "coordinated pass cannot return a path owned by derived "
                    f"domain without a declared composition transform: {path.domain_id}"
                )

            expected_frame = "composition" if coordinated else "domain"
            if path.coordinate_frame != expected_frame:
                pass_kind = "composition" if coordinated else "domain-local"
                raise ValueError(
                    f"{pass_kind} pass returned non-{expected_frame} path: "
                    f"{path.domain_id}"
                )

        prior_derived_ids.update(new_derived_ids)


def _is_coordinated(design_pass: DesignPass) -> bool:
    coordinate_frame = design_pass.parameters.get("coordinate_frame", "domain")
    if coordinate_frame not in {"domain", "composition"}:
        raise ValueError("coordinate_frame must be exactly 'domain' or 'composition'")
    return coordinate_frame == "composition"

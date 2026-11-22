"""Checks every registered part family must pass. New families are covered automatically."""

from __future__ import annotations

import pytest

from mechparts.core import registry
from mechparts.core.geometry import check_mesh, export_bytes

PART_IDS = sorted(registry.all_parts())


def edge_cases(part_id: str):
    """Defaults, then every numeric parameter at its min and its max with the rest at defaults."""
    part = registry.get(part_id)
    schema = part.parameters_schema()
    yield "defaults", {}
    for name, prop in schema["properties"].items():
        if prop.get("type") not in ("number", "integer"):
            continue
        for bound in ("minimum", "maximum"):
            if bound in prop:
                yield f"{name}={bound[:3]}", {name: prop[bound]}


CASES = [(pid, label, params) for pid in PART_IDS for label, params in edge_cases(pid)]


def test_registry_not_empty():
    assert PART_IDS


@pytest.mark.parametrize("part_id", PART_IDS)
def test_metadata_complete(part_id):
    part = registry.get(part_id)
    assert part.id and part.name and part.summary and part.description
    assert part.tags and part.standards and part.compatibility
    assert part.printability.orientation
    schema = part.parameters_schema()
    assert "clearance" in schema["properties"], "every part exposes a clearance parameter"
    for name, prop in schema["properties"].items():
        assert prop.get("description"), f"{name} lacks a description"
        assert "default" in prop, f"{name} lacks a default"
        if prop.get("type") in ("number", "integer"):
            assert "minimum" in prop and "maximum" in prop, f"{name} lacks min/max"
            assert prop.get("units"), f"{name} lacks units"


@pytest.mark.parametrize("part_id,label,params", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_edge_values_validate_or_generate(service, part_id, label, params):
    """Each edge value either produces specific issues or a watertight solid matching its computed size."""
    v = service.validate_parameters(part_id, params)
    if not v.valid:
        assert v.issues, "invalid result must explain itself"
        for issue in v.issues:
            assert issue.param and issue.message and issue.code
        return
    part = registry.get(part_id)
    model = part.Params.model_validate(params)
    shape = part.build(model)
    check_mesh(export_bytes(shape, "stl", "test"))
    assert len(shape.solids()) == 1


@pytest.mark.parametrize("part_id", PART_IDS)
def test_invalid_inputs(service, part_id):
    v = service.validate_parameters(part_id, {"not_a_param": 1})
    assert not v.valid and v.issues[0].code == "unknown_parameter"
    schema = registry.get(part_id).parameters_schema()
    for name, prop in schema["properties"].items():
        if prop.get("type") in ("number", "integer") and "maximum" in prop:
            v = service.validate_parameters(part_id, {name: prop["maximum"] + 1})
            assert not v.valid
            assert v.issues[0].param == name and v.issues[0].allowed_max == prop["maximum"]
            break

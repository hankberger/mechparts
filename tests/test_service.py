import hashlib

import pytest

from mechparts.core.hashing import geometry_hash
from mechparts.service import InvalidFormat, InvalidParameters, NotFound, UnknownPart


def test_search(service):
    assert [p.id for p in service.search_parts("involute gear")][0] == "spur_gear"
    assert service.search_parts("", standard="module 1")[0].id == "spur_gear"
    assert service.search_parts("", tags=["gear"])
    assert service.search_parts("zzzz-no-match") == []
    assert len(service.search_parts()) >= 1


def test_get_part(service):
    d = service.get_part("spur_gear")
    assert d.parameters_schema["properties"]["module"]["units"] == "mm"
    assert d.license == "CC0-1.0"
    with pytest.raises(UnknownPart):
        service.get_part("nope")


def test_validate_fills_defaults(service):
    v = service.validate_parameters("spur_gear", {"teeth": 30})
    assert v.valid and v.resolved_params["module"] == 1.0
    assert v.computed["pitch_diameter"] == 30


def test_generate_and_cache(fresh_service):
    s = fresh_service
    r1 = s.generate_part("spur_gear", {"teeth": 16}, "stl")
    assert not r1.cached and r1.watertight
    assert r1.bounding_box.size[2] == pytest.approx(6)
    assert r1.license == "CC0-1.0"
    r2 = s.generate_part("spur_gear", {"teeth": 16, "module": 1}, "stl")  # same after defaults
    assert r2.cached and r2.hash == r1.hash and r2.file_sha256 == r1.file_sha256
    f = s.download(r1.hash, "stl")
    assert hashlib.sha256(f.data).hexdigest() == r1.file_sha256
    # Another format for a known hash is produced on demand.
    step = s.download(r1.hash, "step")
    assert step.data.startswith(b"ISO-10303-21") and step.result.format == "step"


@pytest.mark.parametrize("fmt", ["stl", "step", "3mf"])
def test_outputs_are_byte_reproducible(tmp_path, fmt):
    from mechparts.config import Settings
    from mechparts.service import PartService

    a = PartService(Settings(data_dir=tmp_path / "a", workers=0)).generate_part("spur_gear", {"teeth": 11}, fmt)
    b = PartService(Settings(data_dir=tmp_path / "b", workers=0)).generate_part("spur_gear", {"teeth": 11}, fmt)
    assert a.file_sha256 == b.file_sha256


def test_hash_is_format_independent_and_normalized():
    a = geometry_hash("x", "1", {"a": 1.0, "b": 2})
    assert a == geometry_hash("x", "1", {"b": 2, "a": 1})
    assert a != geometry_hash("x", "2", {"a": 1.0, "b": 2})


def test_errors(service):
    with pytest.raises(InvalidParameters) as e:
        service.generate_part("spur_gear", {"bore_diameter": 50})
    assert e.value.details["issues"][0]["param"] == "bore_diameter"
    with pytest.raises(InvalidFormat):
        service.generate_part("spur_gear", {}, "obj")
    with pytest.raises(NotFound):
        service.download("0" * 32, "stl")
    with pytest.raises(NotFound):
        service.download("../etc", "stl")

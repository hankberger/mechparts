import pytest
from fastapi.testclient import TestClient

from mechparts.http import create_app


@pytest.fixture(scope="module")
def client(service):
    with TestClient(create_app(service)) as c:
        yield c


def test_openapi_lists_operations(client):
    spec = client.get("/openapi.json").json()
    ops = {op["operationId"] for path in spec["paths"].values() for op in path.values()}
    assert {"search_parts", "get_part", "validate_parameters", "generate_part", "download"} <= ops


def test_flow(client):
    assert client.get("/v1/parts", params={"query": "gear"}).json()[0]["id"] == "spur_gear"
    detail = client.get("/v1/parts/spur_gear").json()
    assert "teeth" in detail["parameters_schema"]["properties"]
    v = client.post("/v1/parts/spur_gear/validate", json={"params": {"teeth": 24}}).json()
    assert v["valid"]
    g = client.post("/v1/parts/spur_gear/generate", json={"params": {"teeth": 24}, "format": "stl"})
    assert g.status_code == 200
    body = g.json()
    assert body["download_url"].endswith(f"/v1/download/{body['hash']}/stl")
    d = client.get(f"/v1/download/{body['hash']}/stl")
    assert d.status_code == 200 and d.headers["content-type"] == "model/stl"
    assert d.headers["x-content-sha256"] == body["file_sha256"]


def test_errors(client):
    r = client.get("/v1/parts/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_part"
    r = client.post("/v1/parts/spur_gear/generate", json={"params": {"bore_diameter": 40}})
    assert r.status_code == 422
    assert r.json()["error"]["issues"][0]["param"] == "bore_diameter"
    r = client.get("/v1/download/" + "0" * 32 + "/stl")
    assert r.status_code == 404

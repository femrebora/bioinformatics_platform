"""Tests for the /api/v1/pipelines endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_pipelines_requires_auth(client):
    resp = await client.get("/api/v1/pipelines")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_pipelines_empty(client, auth_headers):
    resp = await client.get("/api/v1/pipelines", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_save_and_load_pipeline(client, auth_headers):
    """Create a pipeline, list it, load it, delete it."""
    graph = {
        "nodes": [
            {"id": "input-1", "type": "inputFile", "position": {"x": 0, "y": 0},
             "data": {"label": "Input", "fileType": "fastq"}},
        ],
        "edges": [],
    }

    # Save
    resp = await client.post(
        "/api/v1/pipelines",
        json={"name": "Test Pipeline", "graph": graph},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["pipeline_id"]
    assert pid

    # List — should include our pipeline
    list_resp = await client.get("/api/v1/pipelines", headers=auth_headers)
    assert list_resp.status_code == 200
    names = [p["name"] for p in list_resp.json()]
    assert "Test Pipeline" in names

    # Get by ID
    get_resp = await client.get(f"/api/v1/pipelines/{pid}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Test Pipeline"

    # Update name
    update_resp = await client.post(
        "/api/v1/pipelines",
        json={"name": "Updated Pipeline", "graph": graph, "pipeline_id": pid},
        headers=auth_headers,
    )
    assert update_resp.status_code in (200, 201)

    # Delete
    del_resp = await client.delete(f"/api/v1/pipelines/{pid}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Gone
    gone_resp = await client.get(f"/api/v1/pipelines/{pid}", headers=auth_headers)
    assert gone_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_pipeline(client, auth_headers):
    resp = await client.get("/api/v1/pipelines/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404

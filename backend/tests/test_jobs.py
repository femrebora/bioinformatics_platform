"""Tests for the /api/v1/jobs endpoints."""
import pytest
from unittest.mock import patch, MagicMock  # noqa: F401


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_job_body(**kwargs):
    return {
        "storage_key": "uploads/test/sample.fastq.gz",
        "file_type": "fastq",
        "tier": "low",
        "estimated_cost_usd": 0.5,
        **kwargs,
    }


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_requires_auth(client):
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_empty(client, auth_headers, test_user):
    resp = await client.get("/api/v1/jobs", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_job(client, auth_headers):
    """Creating a job should enqueue a Celery task and return 201."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-abc123"

    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(),
            headers=auth_headers,
        )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["tier"] == "low"
    assert "job_id" in data
    mock_pipeline.delay.assert_called_once()


@pytest.mark.asyncio
async def test_create_job_with_pipeline_id(client, auth_headers):
    mock_task = MagicMock()
    mock_task.id = "celery-task-def456"

    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(pipeline_id="rnaseq"),
            headers=auth_headers,
        )

    assert resp.status_code == 201
    assert resp.json()["pipeline_id"] == "rnaseq"


@pytest.mark.asyncio
async def test_get_job_not_found(client, auth_headers):
    resp = await client.get("/api/v1/jobs/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job(client, auth_headers):
    mock_task = MagicMock()
    mock_task.id = "celery-task-ghi789"

    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        create_resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(),
            headers=auth_headers,
        )

    job_id = create_resp.json()["job_id"]
    get_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_cancel_pending_job(client, auth_headers):
    mock_task = MagicMock()
    mock_task.id = "celery-task-cancel-test"

    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        create_resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(),
            headers=auth_headers,
        )

    job_id = create_resp.json()["job_id"]

    # Cancel — Celery revoke and Batch terminate are wrapped in try/except
    # so they won't raise even without real Redis/Celery/AWS in tests
    cancel_resp = await client.delete(
        f"/api/v1/jobs/{job_id}",
        headers=auth_headers,
    )
    assert cancel_resp.status_code == 204

    # Verify job is now cancelled
    get_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_retry_job(client, auth_headers):
    """Retry a cancelled job should create a new pending job."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-retry-src"

    # Create + cancel original job
    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        create_resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(pipeline_id="snakemake"),
            headers=auth_headers,
        )
    job_id = create_resp.json()["job_id"]

    await client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)

    # Retry
    mock_task2 = MagicMock()
    mock_task2.id = "celery-task-retry-new"
    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline2:
        mock_pipeline2.delay.return_value = mock_task2
        retry_resp = await client.post(
            f"/api/v1/jobs/{job_id}/retry",
            headers=auth_headers,
        )

    assert retry_resp.status_code == 201, retry_resp.text
    retry_data = retry_resp.json()
    assert retry_data["status"] == "pending"
    assert retry_data["pipeline_id"] == "snakemake"
    assert retry_data["job_id"] != job_id  # new job ID


@pytest.mark.asyncio
async def test_retry_active_job_fails(client, auth_headers):
    """Retrying a still-pending job should fail with 409."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-active"

    with patch("app.api.v1.jobs.run_pipeline") as mock_pipeline:
        mock_pipeline.delay.return_value = mock_task
        create_resp = await client.post(
            "/api/v1/jobs",
            json=_make_job_body(),
            headers=auth_headers,
        )
    job_id = create_resp.json()["job_id"]

    retry_resp = await client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=auth_headers,
    )
    assert retry_resp.status_code == 409

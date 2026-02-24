import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse, JobListResponse
from app.tasks.pipeline import run_pipeline

router = APIRouter()


def _serialize_job(job: Job) -> JobResponse:
    result = job.result
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            result = None

    return JobResponse(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        tier=job.tier,
        estimated_cost_usd=job.estimated_cost_usd,
        pipeline_id=job.pipeline_id,
        created_at=job.created_at,
        result=result,
        error=job.error,
    )


def _serialize_job_list(job: Job) -> JobListResponse:
    return JobListResponse(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        tier=job.tier,
        estimated_cost_usd=job.estimated_cost_usd,
        pipeline_id=job.pipeline_id,
        created_at=job.created_at,
    )


@router.get("", response_model=list[JobListResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Job).order_by(desc(Job.created_at)).limit(50)
    )
    return [_serialize_job_list(job) for job in result.scalars().all()]


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(
        id=str(uuid.uuid4()),
        status="pending",
        stage=None,
        file_type=body.file_type.lower(),
        storage_key=body.storage_key,
        tier=body.tier,
        estimated_cost_usd=body.estimated_cost_usd,
        pipeline_id=body.pipeline_id or None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = run_pipeline.delay(job.id)
    job.celery_task_id = task.id
    await db.commit()

    return _serialize_job(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _serialize_job(job)

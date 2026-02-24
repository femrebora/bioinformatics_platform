import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse
from app.tasks.pipeline import run_hla_pipeline

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
        result=result,
        error=job.error,
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    file_type = body.file_type.lower()
    if file_type not in ("fastq", "bam"):
        raise HTTPException(status_code=422, detail="file_type must be 'fastq' or 'bam'.")

    job = Job(
        id=str(uuid.uuid4()),
        status="pending",
        stage=None,
        file_type=file_type,
        storage_key=body.storage_key,
        tier=body.tier,
        estimated_cost_usd=body.estimated_cost_usd,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = run_hla_pipeline.delay(job.id)
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

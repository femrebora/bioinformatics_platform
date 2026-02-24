import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.pipeline import Pipeline
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineListItem,
)

router = APIRouter()


def _serialize_pipeline(pipeline: Pipeline) -> PipelineResponse:
    return PipelineResponse(
        pipeline_id=pipeline.id,
        name=pipeline.name,
        graph=pipeline.graph,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


@router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(body: PipelineCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    pipeline = Pipeline(
        id=str(uuid.uuid4()),
        name=body.name,
        graph=body.graph.model_dump(),
        created_at=now,
        updated_at=now,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return _serialize_pipeline(pipeline)


@router.get("", response_model=list[PipelineListItem])
async def list_pipelines(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pipeline).order_by(Pipeline.created_at.desc()))
    pipelines = result.scalars().all()
    return [
        PipelineListItem(
            pipeline_id=p.id,
            name=p.name,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in pipelines
    ]


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    return _serialize_pipeline(pipeline)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str, body: PipelineUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    if body.name is not None:
        pipeline.name = body.name
    if body.graph is not None:
        pipeline.graph = body.graph.model_dump()
    pipeline.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(pipeline)
    return _serialize_pipeline(pipeline)


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    await db.delete(pipeline)
    await db.commit()

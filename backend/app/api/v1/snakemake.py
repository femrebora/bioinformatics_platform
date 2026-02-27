from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.snakemake_wrapper import SnakemakeWrapper
from app.models.snakemake_workflow import SnakemakeWorkflow
from app.schemas.snakemake import (
    SnakemakeWrapperOut,
    SnakemakeWorkflowOut,
    SnakemakeCatalogStatus,
)

router = APIRouter()


@router.get("/wrappers", response_model=list[SnakemakeWrapperOut])
async def list_wrappers(
    q: str = "",
    category: str = "",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SnakemakeWrapper).where(SnakemakeWrapper.fetched_at.isnot(None))
    if q:
        stmt = stmt.where(
            or_(
                SnakemakeWrapper.id.ilike(f"%{q}%"),
                SnakemakeWrapper.tool.ilike(f"%{q}%"),
                SnakemakeWrapper.description.ilike(f"%{q}%"),
            )
        )
    if category:
        stmt = stmt.where(SnakemakeWrapper.category == category)
    stmt = stmt.order_by(SnakemakeWrapper.id).limit(min(limit, 200))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/wrapper-categories", response_model=list[dict])
async def list_wrapper_categories(db: AsyncSession = Depends(get_db)):
    """Return wrapper categories with counts, sorted by count desc."""
    stmt = (
        select(SnakemakeWrapper.category, func.count(SnakemakeWrapper.id).label("count"))
        .where(SnakemakeWrapper.fetched_at.isnot(None))
        .group_by(SnakemakeWrapper.category)
        .order_by(func.count(SnakemakeWrapper.id).desc())
    )
    result = await db.execute(stmt)
    return [{"category": row.category, "count": row.count} for row in result]


@router.get("/workflows", response_model=list[SnakemakeWorkflowOut])
async def list_workflows(
    q: str = "",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SnakemakeWorkflow)
    if q:
        stmt = stmt.where(
            or_(
                SnakemakeWorkflow.name.ilike(f"%{q}%"),
                SnakemakeWorkflow.description.ilike(f"%{q}%"),
            )
        )
    stmt = stmt.order_by(SnakemakeWorkflow.stars.desc()).limit(min(limit, 200))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/status", response_model=SnakemakeCatalogStatus)
async def snakemake_status(db: AsyncSession = Depends(get_db)):
    n_wrappers = (
        await db.execute(
            select(func.count(SnakemakeWrapper.id)).where(
                SnakemakeWrapper.fetched_at.isnot(None)
            )
        )
    ).scalar() or 0
    n_workflows = (
        await db.execute(select(func.count(SnakemakeWorkflow.id)))
    ).scalar() or 0
    return SnakemakeCatalogStatus(
        wrappers=n_wrappers,
        workflows=n_workflows,
        ready=n_wrappers > 0,
    )


@router.post("/refresh", status_code=202)
async def refresh_snakemake():
    from app.tasks.scrape_snakemake import scrape_snakemake_catalog
    scrape_snakemake_catalog.delay(force=True)
    return {"message": "Snakemake catalog refresh started in background"}

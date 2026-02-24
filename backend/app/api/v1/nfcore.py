from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.nfcore_pipeline import NfCorePipeline
from app.models.nfcore_module import NfCoreModule

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PipelineOut(BaseModel):
    id: str
    full_name: str
    description: Optional[str]
    topics: Optional[list]
    html_url: str
    stars: int
    input_formats: Optional[list] = None
    model_config = {"from_attributes": True}


class ModuleOut(BaseModel):
    id: str
    tool: str
    subcommand: Optional[str]
    description: Optional[str]
    keywords: Optional[list]
    category: str
    inputs: Optional[list]
    outputs: Optional[list]
    model_config = {"from_attributes": True}


class CatalogStatus(BaseModel):
    pipelines: int
    modules: int
    ready: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pipelines", response_model=list[PipelineOut])
async def list_pipelines(q: str = "", db: AsyncSession = Depends(get_db)):
    stmt = select(NfCorePipeline)
    if q:
        stmt = stmt.where(
            or_(
                NfCorePipeline.full_name.ilike(f"%{q}%"),
                NfCorePipeline.description.ilike(f"%{q}%"),
            )
        )
    stmt = stmt.order_by(NfCorePipeline.stars.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/modules", response_model=list[ModuleOut])
async def list_modules(
    q: str = "",
    category: str = "",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NfCoreModule).where(NfCoreModule.fetched_at.isnot(None))
    if q:
        stmt = stmt.where(
            or_(
                NfCoreModule.id.ilike(f"%{q}%"),
                NfCoreModule.description.ilike(f"%{q}%"),
            )
        )
    if category:
        stmt = stmt.where(NfCoreModule.category == category)
    stmt = stmt.order_by(NfCoreModule.id).limit(min(limit, 200))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/categories", response_model=list[dict])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return categories with module counts, sorted by count desc."""
    stmt = (
        select(NfCoreModule.category, func.count(NfCoreModule.id).label("count"))
        .where(NfCoreModule.fetched_at.isnot(None))
        .group_by(NfCoreModule.category)
        .order_by(func.count(NfCoreModule.id).desc())
    )
    result = await db.execute(stmt)
    return [{"category": row.category, "count": row.count} for row in result]


@router.get("/status", response_model=CatalogStatus)
async def catalog_status(db: AsyncSession = Depends(get_db)):
    n_pip = (await db.execute(select(func.count(NfCorePipeline.id)))).scalar() or 0
    n_mod = (
        await db.execute(
            select(func.count(NfCoreModule.id)).where(
                NfCoreModule.fetched_at.isnot(None)
            )
        )
    ).scalar() or 0
    return CatalogStatus(pipelines=n_pip, modules=n_mod, ready=n_pip > 0)


def _extract_module_ids(data: dict) -> list[str]:
    """Extract module IDs from modules.json — handles old and new formats."""
    # New format: {"repos": {"<url>": {"modules": {"nf-core": {<id>: {...}}}}}}
    for repo_data in data.get("repos", {}).values():
        nfcore = repo_data.get("modules", {}).get("nf-core", {})
        if nfcore:
            return list(nfcore.keys())
    # Old format: {"nf-core": {<id>: {...}}}
    nfcore = data.get("nf-core", {})
    if nfcore:
        return list(nfcore.keys())
    return []


@router.get("/pipelines/{pipeline_id}/modules", response_model=list[ModuleOut])
async def get_pipeline_modules(
    pipeline_id: str, db: AsyncSession = Depends(get_db)
):
    """
    Return all nf-core modules used by a specific pipeline.
    Fetches the pipeline's modules.json from GitHub raw (no token needed),
    then cross-references our local module catalog for full port metadata.
    """
    pipeline = (
        await db.execute(
            select(NfCorePipeline).where(NfCorePipeline.id == pipeline_id)
        )
    ).scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    url = f"https://raw.githubusercontent.com/nf-core/{pipeline_id}/master/modules.json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Could not fetch pipeline modules from GitHub",
        )

    module_ids = _extract_module_ids(data)
    if not module_ids:
        return []

    stmt = (
        select(NfCoreModule)
        .where(NfCoreModule.id.in_(module_ids))
        .where(NfCoreModule.fetched_at.isnot(None))
        .order_by(NfCoreModule.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/refresh", status_code=202)
async def refresh_catalog():
    from app.tasks.scrape_nfcore import scrape_nfcore_catalog
    scrape_nfcore_catalog.delay(force=True)
    return {"message": "Catalog refresh started in background"}

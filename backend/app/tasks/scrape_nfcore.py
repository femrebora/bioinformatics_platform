"""
Celery task: scrape the nf-core catalog and persist to PostgreSQL.

Uses psycopg2 (sync) + raw SQL — same pattern as pipeline.py,
avoids importing the async-engine-backed ORM models.

Runs once on app startup; subsequent runs skip unless forced.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.config import settings
from app.services.nfcore.scraper import run_scrape, parse_meta_yml

logger = logging.getLogger(__name__)

_sync_url = (
    settings.DATABASE_URL
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("postgresql://", "postgresql+psycopg2://")
)
_engine = create_engine(_sync_url, pool_pre_ping=True)


def _is_already_loaded() -> bool:
    try:
        with _engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM nfcore_modules WHERE fetched_at IS NOT NULL")
            ).scalar()
            return (count or 0) > 100
    except Exception:
        return False


def _save_pipelines(pipelines: list, now: datetime) -> int:
    saved = 0
    with _engine.begin() as conn:
        for p in pipelines:
            pid = p.get("name", "")
            if not pid:
                continue
            input_formats = p.get("input_formats")
            conn.execute(
                text("""
                    INSERT INTO nfcore_pipelines
                        (id, full_name, description, topics, html_url, stars,
                         last_updated, fetched_at, input_formats)
                    VALUES
                        (:id, :full_name, :description, :topics, :html_url, :stars,
                         :last_updated, :fetched_at, :input_formats)
                    ON CONFLICT (id) DO UPDATE SET
                        full_name    = EXCLUDED.full_name,
                        description  = EXCLUDED.description,
                        topics       = EXCLUDED.topics,
                        html_url     = EXCLUDED.html_url,
                        stars        = EXCLUDED.stars,
                        last_updated = EXCLUDED.last_updated,
                        fetched_at   = EXCLUDED.fetched_at,
                        input_formats = EXCLUDED.input_formats
                """),
                {
                    "id": pid,
                    "full_name": p.get("full_name", f"nf-core/{pid}"),
                    "description": (p.get("description") or "")[:500],
                    "topics": json.dumps(p.get("topics") or []),
                    "html_url": p.get("html_url", ""),
                    "stars": p.get("stargazers_count", 0),
                    "last_updated": _parse_dt(p.get("updated_at")),
                    "fetched_at": now,
                    "input_formats": json.dumps(input_formats) if input_formats is not None else None,
                },
            )
            saved += 1
    return saved


def _save_module_batch(batch: list[dict], now: datetime) -> None:
    with _engine.begin() as conn:
        for m in batch:
            conn.execute(
                text("""
                    INSERT INTO nfcore_modules
                        (id, tool, subcommand, description, keywords, category,
                         inputs, outputs, fetched_at)
                    VALUES
                        (:id, :tool, :subcommand, :description, :keywords, :category,
                         :inputs, :outputs, :fetched_at)
                    ON CONFLICT (id) DO UPDATE SET
                        tool        = EXCLUDED.tool,
                        subcommand  = EXCLUDED.subcommand,
                        description = EXCLUDED.description,
                        keywords    = EXCLUDED.keywords,
                        category    = EXCLUDED.category,
                        inputs      = EXCLUDED.inputs,
                        outputs     = EXCLUDED.outputs,
                        fetched_at  = EXCLUDED.fetched_at
                """),
                {
                    "id": m["id"],
                    "tool": m["tool"],
                    "subcommand": m["subcommand"],
                    "description": m["description"],
                    "keywords": json.dumps(m["keywords"] or []),
                    "category": m["category"],
                    "inputs": json.dumps(m["inputs"] or []),
                    "outputs": json.dumps(m["outputs"] or []),
                    "fetched_at": now,
                },
            )


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


@celery_app.task(name="app.tasks.scrape_nfcore.scrape_nfcore_catalog")
def scrape_nfcore_catalog(force: bool = False) -> dict:
    if not force and _is_already_loaded():
        logger.info("[nfcore] Catalog already loaded — skipping scrape")
        return {"status": "skipped"}

    logger.info("[nfcore] Starting catalog scrape (force=%s)", force)
    now = datetime.now(timezone.utc)

    try:
        pipelines_raw, module_results = asyncio.run(run_scrape())
    except Exception as exc:
        logger.error("[nfcore] Scrape failed: %s", exc)
        raise

    n_pipelines = _save_pipelines(pipelines_raw, now)
    logger.info("[nfcore] Saved %d pipelines", n_pipelines)

    batch: list[dict] = []
    n_modules = 0
    for path, content in module_results:
        if not content:
            continue
        parsed = parse_meta_yml(path, content)
        if not parsed:
            continue
        batch.append(parsed)
        if len(batch) >= 50:
            _save_module_batch(batch, now)
            n_modules += len(batch)
            logger.info("[nfcore] %d modules saved…", n_modules)
            batch = []
    if batch:
        _save_module_batch(batch, now)
        n_modules += len(batch)

    logger.info("[nfcore] Done — %d pipelines, %d modules", n_pipelines, n_modules)
    return {"status": "ok", "pipelines": n_pipelines, "modules": n_modules}

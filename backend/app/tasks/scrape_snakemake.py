"""
Celery task: scrape the Snakemake wrappers + workflow catalog and persist to PostgreSQL.

Uses psycopg2 (sync) + raw SQL — same pattern as scrape_nfcore.py.
Runs once on app startup; subsequent runs skip unless forced.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.config import settings
from app.services.snakemake_scraper import (
    run_scrape_wrappers,
    run_scrape_workflows,
    _parse_wrapper_meta,
)

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
                text("SELECT COUNT(*) FROM snakemake_wrappers WHERE fetched_at IS NOT NULL")
            ).scalar()
            return (count or 0) > 50
    except Exception:
        return False


def _save_wrapper_batch(batch: list[dict], now: datetime) -> None:
    with _engine.begin() as conn:
        for w in batch:
            conn.execute(
                text("""
                    INSERT INTO snakemake_wrappers
                        (id, tool, subcommand, name, description, authors,
                         input_names, output_names, category, fetched_at)
                    VALUES
                        (:id, :tool, :subcommand, :name, :description, :authors,
                         :input_names, :output_names, :category, :fetched_at)
                    ON CONFLICT (id) DO UPDATE SET
                        tool         = EXCLUDED.tool,
                        subcommand   = EXCLUDED.subcommand,
                        name         = EXCLUDED.name,
                        description  = EXCLUDED.description,
                        authors      = EXCLUDED.authors,
                        input_names  = EXCLUDED.input_names,
                        output_names = EXCLUDED.output_names,
                        category     = EXCLUDED.category,
                        fetched_at   = EXCLUDED.fetched_at
                """),
                {
                    "id":           w["id"],
                    "tool":         w["tool"],
                    "subcommand":   w["subcommand"],
                    "name":         w["name"],
                    "description":  w["description"],
                    "authors":      json.dumps(w["authors"] or []),
                    "input_names":  json.dumps(w["input_names"] or []),
                    "output_names": json.dumps(w["output_names"] or []),
                    "category":     w["category"],
                    "fetched_at":   now,
                },
            )


def _save_workflows(workflows: list[dict], now: datetime) -> int:
    saved = 0
    with _engine.begin() as conn:
        for wf in workflows:
            wf_id = wf.get("full_name") or wf.get("id") or ""
            if not wf_id:
                continue
            name = wf_id.split("/")[-1]
            conn.execute(
                text("""
                    INSERT INTO snakemake_workflows
                        (id, name, description, topics, html_url, stars, fetched_at)
                    VALUES
                        (:id, :name, :description, :topics, :html_url, :stars, :fetched_at)
                    ON CONFLICT (id) DO UPDATE SET
                        name        = EXCLUDED.name,
                        description = EXCLUDED.description,
                        topics      = EXCLUDED.topics,
                        html_url    = EXCLUDED.html_url,
                        stars       = EXCLUDED.stars,
                        fetched_at  = EXCLUDED.fetched_at
                """),
                {
                    "id":          wf_id,
                    "name":        name,
                    "description": (wf.get("description") or "")[:500],
                    "topics":      json.dumps(wf.get("topics") or []),
                    "html_url":    wf.get("html_url", ""),
                    "stars":       wf.get("stargazers_count", 0),
                    "fetched_at":  now,
                },
            )
            saved += 1
    return saved


@celery_app.task(name="app.tasks.scrape_snakemake.scrape_snakemake_catalog")
def scrape_snakemake_catalog(force: bool = False) -> dict:
    if not force and _is_already_loaded():
        logger.info("[snakemake] Catalog already loaded — skipping scrape")
        return {"status": "skipped"}

    logger.info("[snakemake] Starting catalog scrape (force=%s)", force)
    now = datetime.now(timezone.utc)

    # ── Wrappers ──────────────────────────────────────────────────────────
    try:
        wrapper_results = asyncio.run(run_scrape_wrappers())
    except Exception as exc:
        logger.error("[snakemake] Wrapper scrape failed: %s", exc)
        wrapper_results = []

    batch: list[dict] = []
    n_wrappers = 0
    for path, content in wrapper_results:
        if not content:
            continue
        parsed = _parse_wrapper_meta(path, content)
        if not parsed:
            continue
        batch.append(parsed)
        if len(batch) >= 50:
            _save_wrapper_batch(batch, now)
            n_wrappers += len(batch)
            logger.info("[snakemake] %d wrappers saved…", n_wrappers)
            batch = []
    if batch:
        _save_wrapper_batch(batch, now)
        n_wrappers += len(batch)
    logger.info("[snakemake] Saved %d wrappers", n_wrappers)

    # ── Workflows ─────────────────────────────────────────────────────────
    try:
        raw_workflows = asyncio.run(run_scrape_workflows())
    except Exception as exc:
        logger.error("[snakemake] Workflow scrape failed: %s", exc)
        raw_workflows = []

    n_workflows = _save_workflows(raw_workflows, now)
    logger.info("[snakemake] Saved %d workflows", n_workflows)

    return {"status": "ok", "wrappers": n_wrappers, "workflows": n_workflows}

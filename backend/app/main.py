from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create any tables not yet in the DB (idempotent; Alembic handles schema changes)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))
    except Exception:
        pass  # tables already exist from a previous migration run
    # Kick off nf-core catalog scrape in background (skips if already loaded)
    try:
        from app.tasks.scrape_nfcore import scrape_nfcore_catalog
        scrape_nfcore_catalog.delay()
    except Exception:
        pass  # worker may not be ready yet; catalog can be refreshed via POST /nfcore/refresh
    yield
    await engine.dispose()


app = FastAPI(
    title="Bioinformatics Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}

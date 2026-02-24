from fastapi import APIRouter
from app.api.v1 import uploads, jobs, pipelines, nfcore

router = APIRouter(prefix="/api/v1")
router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
router.include_router(nfcore.router, prefix="/nfcore", tags=["nfcore"])

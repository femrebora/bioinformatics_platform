import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.config import settings
from app.schemas.upload import PresignRequest, PresignResponse
from app.services.cost_estimator import estimate
from app.services.storage.base import get_storage_backend

router = APIRouter()


@router.post("/presign", response_model=PresignResponse)
async def presign_upload(body: PresignRequest):
    ext = os.path.splitext(body.filename)[1].lower() or ".fastq"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_key = f"uploads/{unique_name}"

    storage = get_storage_backend()
    upload_url = storage.generate_upload_url(storage_key)

    tier_est = estimate(body.file_size_bytes)

    return PresignResponse(
        upload_url=upload_url,
        storage_key=storage_key,
        recommended_tier=tier_est.tier,
        estimated_cost_usd=tier_est.cost_usd,
        tier_rationale=tier_est.rationale,
    )


@router.put("/local/{filename}")
async def upload_local(filename: str, request: Request):
    """Mock S3 endpoint: receives raw file bytes and saves to the uploads volume."""
    safe_filename = os.path.basename(filename)
    dest_path = os.path.join(settings.UPLOADS_DIR, safe_filename)

    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body.")

    with open(dest_path, "wb") as f:
        f.write(body)

    return Response(status_code=200)

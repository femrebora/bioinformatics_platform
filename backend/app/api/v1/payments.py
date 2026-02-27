"""
Stripe payment endpoints.

Flow:
  1. POST /checkout      → create Stripe Checkout session → return checkout_url
  2. Browser             → redirect to checkout_url → user pays on Stripe
  3. Stripe              → POST /webhook (checkout.session.completed)
  4. Webhook handler     → create Job + dispatch Celery task
  5. Browser             → GET /session/{session_id} → poll until job_id appears

workflow_config can be large (Snakemake wrapper lists, BioScript scripts), so it
is stored in Redis under a temporary key and only the key is placed in Stripe
metadata (which has a 500-char per-value limit).
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis as redis_lib
import stripe
import stripe.error
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.job import Job
from app.models.user import User
from app.tasks.pipeline import run_pipeline

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Redis client (lazy) ───────────────────────────────────────────────────

_redis_client: Optional[redis_lib.Redis] = None


def _redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(
            settings.CELERY_BROKER_URL, decode_responses=True
        )
    return _redis_client


# ── Stripe config (lazy) ──────────────────────────────────────────────────

def _configure_stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment processing is not configured yet.")
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ── Request / response schemas ────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    storage_key: str
    file_type: str
    tier: str
    pipeline_id: Optional[str] = None
    estimated_cost_usd: float
    n_samples: int = 1
    storage_key_r2: Optional[str] = None
    workflow_config: Optional[Any] = None
    job_name: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session. Returns the hosted payment URL."""
    _configure_stripe()

    # Stripe requires minimum 50 cents
    amount_cents = max(50, round(body.estimated_cost_usd * 100))
    pipeline_label = body.pipeline_id or "HLA typing"

    # Store workflow_config in Redis (avoids Stripe's 500-char metadata limit)
    workflow_config_ref = ""
    if body.workflow_config:
        workflow_config_ref = str(uuid.uuid4())
        _redis().setex(
            f"wfcfg:{workflow_config_ref}",
            86400,  # 24-hour TTL (prevents expiry on delayed Stripe webhooks)
            json.dumps(body.workflow_config),
        )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Pipeline: {pipeline_label}",
                        "description": f"{body.n_samples} sample(s) · {body.tier} tier",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{settings.APP_BASE_URL}/?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_BASE_URL}/",
        metadata={
            "storage_key":          body.storage_key,
            "file_type":            body.file_type,
            "tier":                 body.tier,
            "pipeline_id":          body.pipeline_id or "",
            "user_id":              current_user.id,
            "estimated_cost_usd":   str(body.estimated_cost_usd),
            "storage_key_r2":       body.storage_key_r2 or "",
            "workflow_config_ref":  workflow_config_ref,
            "job_name":             (body.job_name or "")[:200],
        },
    )

    logger.info("[stripe] checkout session %s created for user %s", session.id, current_user.id)
    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe calls this after successful payment.
    NOT JWT-protected — Stripe signature is verified instead.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured.")
    _configure_stripe()

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})

        # Retrieve workflow_config from Redis if present
        workflow_config = None
        wfcfg_ref = meta.get("workflow_config_ref", "")
        if wfcfg_ref:
            raw = _redis().get(f"wfcfg:{wfcfg_ref}")
            if raw:
                workflow_config = json.loads(raw)
                _redis().delete(f"wfcfg:{wfcfg_ref}")  # consume once

        job = Job(
            id=str(uuid.uuid4()),
            status="pending",
            stage=None,
            file_type=meta.get("file_type", "fastq"),
            storage_key=meta["storage_key"],
            tier=meta.get("tier", "small"),
            estimated_cost_usd=float(meta.get("estimated_cost_usd", 0)),
            pipeline_id=meta.get("pipeline_id") or None,
            storage_key_r2=meta.get("storage_key_r2") or None,
            workflow_config=workflow_config,
            job_name=meta.get("job_name") or None,
            user_id=meta.get("user_id"),
            stripe_session_id=session["id"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        task = run_pipeline.delay(job.id)
        job.celery_task_id = task.id
        await db.commit()

        logger.info("[stripe] job %s created for session %s", job.id, session["id"])

    return {"ok": True}


@router.get("/session/{session_id}")
async def get_session_job(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Frontend polls this after Stripe redirects back to the app.
    Returns job_id once the webhook has created the job (usually < 2s).
    Returns {job_id: null} while waiting.
    """
    result = await db.execute(
        select(Job).where(
            Job.stripe_session_id == session_id,
            Job.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()
    return {"job_id": job.id if job else None}

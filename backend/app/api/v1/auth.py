import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.deps import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.services.audit import log_audit, _ip, _ua
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter()


# ── Schemas (small, auth-only — no separate file needed) ──────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(User.email == body.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower().strip(),
        hashed_password=hash_password(body.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_audit("auth.register", user_id=user.id, resource_type="user", resource_id=user.id,
                    ip_address=_ip(request), user_agent=_ua(request))
    return user


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == form.username.lower().strip())
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        await log_audit("auth.login_failed", ip_address=_ip(request), user_agent=_ua(request),
                        meta={"email": form.username.lower().strip()})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await log_audit("auth.login", user_id=user.id, resource_type="user", resource_id=user.id,
                    ip_address=_ip(request), user_agent=_ua(request))
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GDPR right-to-erasure: delete the current user and all associated data.

    Deletes the user row (which cascades to jobs via application logic),
    then queues background deletion of all S3 objects owned by the user.
    """
    from sqlalchemy import delete as sa_delete
    from app.models.job import Job

    # Collect all storage keys before deletion so we can clean up S3
    jobs_result = await db.execute(
        select(Job.storage_key, Job.storage_key_r2)
        .where(Job.user_id == current_user.id)
    )
    storage_keys = []
    for row in jobs_result:
        if row.storage_key:
            storage_keys.append(row.storage_key)
        if row.storage_key_r2:
            storage_keys.append(row.storage_key_r2)

    # Delete jobs first (no FK cascade on user_id by design)
    await db.execute(sa_delete(Job).where(Job.user_id == current_user.id))
    # Delete user
    await db.delete(current_user)
    await db.commit()

    # Queue S3 cleanup task (best-effort, non-blocking)
    if storage_keys:
        try:
            from app.tasks.cleanup import delete_storage_keys
            delete_storage_keys.delay(storage_keys)
        except Exception:
            pass  # non-fatal — keys can be cleaned up manually

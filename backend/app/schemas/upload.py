from pydantic import BaseModel


class PresignRequest(BaseModel):
    filename: str
    file_size_bytes: int


class PresignResponse(BaseModel):
    upload_url: str
    storage_key: str
    recommended_tier: str
    estimated_cost_usd: float
    tier_rationale: str

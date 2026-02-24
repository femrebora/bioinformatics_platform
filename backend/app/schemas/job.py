from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class JobCreate(BaseModel):
    storage_key: str
    file_type: str        # fastq | bam
    tier: str             # small | medium | large
    estimated_cost_usd: float


class HLAAllele(BaseModel):
    gene: str
    allele_1: str
    allele_2: str


class JobResult(BaseModel):
    hla_alleles: list[HLAAllele]
    instance_type: str
    runtime_seconds: int


class JobResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str]
    tier: str
    estimated_cost_usd: float
    result: Optional[Any]
    error: Optional[str]

    model_config = {"from_attributes": True}

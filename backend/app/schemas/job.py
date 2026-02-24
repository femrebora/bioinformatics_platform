from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class JobCreate(BaseModel):
    storage_key: str
    file_type: str              # fastq | bam (or any nf-core-accepted format)
    tier: str                   # small | medium | large
    estimated_cost_usd: float
    pipeline_id: Optional[str] = None   # None → HLA pipeline; set → nf-core pipeline


# ── Result schemas ────────────────────────────────────────────────────────


class HLAAllele(BaseModel):
    gene: str
    allele_1: str
    allele_2: str


class VcfVariant(BaseModel):
    chrom: str
    pos: Any
    id: str
    ref: str
    alt: str
    qual: Any
    filter: str
    info: str


class ResultFile(BaseModel):
    name: str
    path: str
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    description: Optional[str] = None


class JobResult(BaseModel):
    """Generalised result payload.

    The ``type`` field is used by the frontend ResultsPanel to select
    the appropriate renderer.  All payload fields are optional to allow
    partial results and future extension.
    """

    type: Optional[str] = None          # "hla_alleles" | "table" | "vcf" | "html_report" | "text" | "files"

    # HLA alleles (type="hla_alleles")
    hla_alleles: Optional[list[HLAAllele]] = None

    # Generic table / count matrix (type="table")
    columns: Optional[list[str]] = None
    rows: Optional[list[dict[str, Any]]] = None

    # VCF variants (type="vcf")
    variants: Optional[list[VcfVariant]] = None

    # HTML report, e.g. MultiQC (type="html_report")
    html: Optional[str] = None

    # Plain text (type="text")
    content: Optional[str] = None

    # File list (type="files")
    files: Optional[list[ResultFile]] = None

    # Common metadata (always present)
    instance_type: str = ""
    runtime_seconds: int = 0


# ── Job response ──────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str]
    tier: str
    estimated_cost_usd: float
    pipeline_id: Optional[str] = None
    created_at: Optional[datetime] = None
    result: Optional[Any]
    error: Optional[str]

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str]
    tier: str
    estimated_cost_usd: float
    pipeline_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

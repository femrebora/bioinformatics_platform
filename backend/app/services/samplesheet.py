"""nf-core samplesheet generator.

Generates CSV (or text) samplesheets that nf-core pipelines consume
via their ``--input`` parameter.  Each pipeline expects a specific
column layout; this module encodes those layouts and returns the
samplesheet as a UTF-8 string ready to be written to a file.

Usage::

    from app.services.samplesheet import SampleInput, generate_samplesheet

    sheet = generate_samplesheet(
        pipeline_id="rnaseq",
        inputs=[
            SampleInput("SAMPLE1", "s3://bucket/sample1_R1.fastq.gz",
                        "s3://bucket/sample1_R2.fastq.gz"),
        ],
    )
    # → "sample,fastq_1,fastq_2,strandedness\\nSAMPLE1,s3://…,s3://…,auto\\n"
"""
import csv
import io
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SampleInput:
    """Represents one sample for samplesheet generation."""

    sample_name: str
    fastq_1: str                        # primary file path / storage key
    fastq_2: Optional[str] = None       # second read (paired-end); None for SE
    extra: dict = field(default_factory=dict)  # pipeline-specific extra fields


# ── Per-pipeline generators ───────────────────────────────────────────────


def _rnaseq(inputs: list[SampleInput]) -> str:
    """nf-core/rnaseq: sample, fastq_1, fastq_2, strandedness."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["sample", "fastq_1", "fastq_2", "strandedness"])
    for s in inputs:
        w.writerow([s.sample_name, s.fastq_1, s.fastq_2 or "", "auto"])
    return out.getvalue()


def _sarek(inputs: list[SampleInput]) -> str:
    """nf-core/sarek: patient, sample, lane, fastq_1, fastq_2."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["patient", "sample", "lane", "fastq_1", "fastq_2"])
    for i, s in enumerate(inputs):
        patient = s.extra.get("patient", f"PATIENT{i + 1}")
        w.writerow([patient, s.sample_name, "lane1", s.fastq_1, s.fastq_2 or ""])
    return out.getvalue()


def _atacseq_methylseq(inputs: list[SampleInput]) -> str:
    """nf-core/atacseq and nf-core/methylseq: sample, fastq_1, fastq_2."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["sample", "fastq_1", "fastq_2"])
    for s in inputs:
        w.writerow([s.sample_name, s.fastq_1, s.fastq_2 or ""])
    return out.getvalue()


def _ampliseq(inputs: list[SampleInput]) -> str:
    """nf-core/ampliseq: sampleID, forwardReads, reverseReads, run."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["sampleID", "forwardReads", "reverseReads", "run"])
    for i, s in enumerate(inputs):
        run_id = s.extra.get("run", f"run{i + 1}")
        w.writerow([s.sample_name, s.fastq_1, s.fastq_2 or "", run_id])
    return out.getvalue()


def _chipseq(inputs: list[SampleInput]) -> str:
    """nf-core/chipseq: sample, fastq_1, fastq_2, antibody, control."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["sample", "fastq_1", "fastq_2", "antibody", "control"])
    for s in inputs:
        antibody = s.extra.get("antibody", "H3K27AC")
        control  = s.extra.get("control", "")
        w.writerow([s.sample_name, s.fastq_1, s.fastq_2 or "", antibody, control])
    return out.getvalue()


def _fetchngs(inputs: list[SampleInput]) -> str:
    """nf-core/fetchngs: plain text with one SRA/ENA accession per line."""
    return "\n".join(s.fastq_1 for s in inputs) + "\n"


def _generic(inputs: list[SampleInput]) -> str:
    """Fallback: sample, fastq_1, fastq_2."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["sample", "fastq_1", "fastq_2"])
    for s in inputs:
        w.writerow([s.sample_name, s.fastq_1, s.fastq_2 or ""])
    return out.getvalue()


_GENERATORS: dict[str, Callable[[list[SampleInput]], str]] = {
    "rnaseq":    _rnaseq,
    "sarek":     _sarek,
    "atacseq":   _atacseq_methylseq,
    "methylseq": _atacseq_methylseq,
    "ampliseq":  _ampliseq,
    "chipseq":   _chipseq,
    "fetchngs":  _fetchngs,
}


# ── Public API ────────────────────────────────────────────────────────────


def generate_samplesheet(pipeline_id: str, inputs: list[SampleInput]) -> str:
    """Generate and return the samplesheet CSV string.

    Args:
        pipeline_id: nf-core pipeline ID, e.g. ``"rnaseq"`` or ``"nf-core/rnaseq"``.
        inputs:      List of sample inputs (at least one required).

    Returns:
        Samplesheet content as a string.  The format varies by pipeline.
    """
    if not inputs:
        raise ValueError("At least one SampleInput is required.")

    pid = pipeline_id.lower().removeprefix("nf-core/")
    generator = _GENERATORS.get(pid, _generic)
    return generator(inputs)


def samplesheet_filename(pipeline_id: str) -> str:
    """Return the conventional filename for the generated samplesheet."""
    pid = pipeline_id.lower().removeprefix("nf-core/")
    if pid == "fetchngs":
        return "ids.txt"
    return "samplesheet.csv"

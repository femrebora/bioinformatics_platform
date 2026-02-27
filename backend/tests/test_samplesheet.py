"""Unit tests for the samplesheet generator."""
import csv
import io
import pytest
from app.services.samplesheet import (
    SampleInput,
    generate_samplesheet,
    samplesheet_filename,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    """Return (headers, rows) from CSV text."""
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    headers = list(reader.fieldnames or [])
    return headers, rows


SE = SampleInput("S1", "s3://bucket/S1_R1.fastq.gz")
PE = SampleInput("S1", "s3://bucket/S1_R1.fastq.gz", "s3://bucket/S1_R2.fastq.gz")


# ── generate_samplesheet — error cases ───────────────────────────────────


def test_empty_inputs_raises():
    with pytest.raises(ValueError, match="At least one"):
        generate_samplesheet("rnaseq", [])


# ── rnaseq ────────────────────────────────────────────────────────────────


class TestRnaseq:
    def test_header(self):
        text = generate_samplesheet("rnaseq", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["sample", "fastq_1", "fastq_2", "strandedness"]

    def test_single_end_fastq_2_empty(self):
        _, rows = _parse_csv(generate_samplesheet("rnaseq", [SE]))
        assert rows[0]["fastq_2"] == ""

    def test_paired_end_fastq_2_filled(self):
        _, rows = _parse_csv(generate_samplesheet("rnaseq", [PE]))
        assert rows[0]["fastq_2"] == "s3://bucket/S1_R2.fastq.gz"

    def test_strandedness_is_auto(self):
        _, rows = _parse_csv(generate_samplesheet("rnaseq", [SE]))
        assert rows[0]["strandedness"] == "auto"

    def test_multiple_samples(self):
        s2 = SampleInput("S2", "s3://bucket/S2_R1.fastq.gz")
        _, rows = _parse_csv(generate_samplesheet("rnaseq", [SE, s2]))
        assert len(rows) == 2
        assert rows[1]["sample"] == "S2"

    def test_nf_core_prefix_stripped(self):
        text = generate_samplesheet("nf-core/rnaseq", [SE])
        headers, _ = _parse_csv(text)
        assert "strandedness" in headers


# ── sarek ─────────────────────────────────────────────────────────────────


class TestSarek:
    def test_header(self):
        text = generate_samplesheet("sarek", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["patient", "sample", "lane", "fastq_1", "fastq_2"]

    def test_default_patient_name(self):
        _, rows = _parse_csv(generate_samplesheet("sarek", [SE]))
        assert rows[0]["patient"] == "PATIENT1"

    def test_custom_patient_from_extra(self):
        s = SampleInput("TUMOR", "s3://bucket/t.fastq.gz", extra={"patient": "PT007"})
        _, rows = _parse_csv(generate_samplesheet("sarek", [s]))
        assert rows[0]["patient"] == "PT007"

    def test_lane_is_lane1(self):
        _, rows = _parse_csv(generate_samplesheet("sarek", [SE]))
        assert rows[0]["lane"] == "lane1"


# ── atacseq ───────────────────────────────────────────────────────────────


class TestAtacseq:
    def test_header(self):
        text = generate_samplesheet("atacseq", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["sample", "fastq_1", "fastq_2"]

    def test_paired_end(self):
        _, rows = _parse_csv(generate_samplesheet("atacseq", [PE]))
        assert rows[0]["fastq_2"] == "s3://bucket/S1_R2.fastq.gz"


# ── methylseq ─────────────────────────────────────────────────────────────


class TestMethylseq:
    def test_same_format_as_atacseq(self):
        atac_text  = generate_samplesheet("atacseq",   [SE])
        methyl_text = generate_samplesheet("methylseq", [SE])
        assert atac_text == methyl_text


# ── chipseq ───────────────────────────────────────────────────────────────


class TestChipseq:
    def test_header(self):
        text = generate_samplesheet("chipseq", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["sample", "fastq_1", "fastq_2", "antibody", "control"]

    def test_default_antibody(self):
        _, rows = _parse_csv(generate_samplesheet("chipseq", [SE]))
        assert rows[0]["antibody"] == "H3K27AC"

    def test_custom_antibody(self):
        s = SampleInput("IP", "s3://b/ip.fastq.gz", extra={"antibody": "H3K4ME3"})
        _, rows = _parse_csv(generate_samplesheet("chipseq", [s]))
        assert rows[0]["antibody"] == "H3K4ME3"

    def test_control_empty_by_default(self):
        _, rows = _parse_csv(generate_samplesheet("chipseq", [SE]))
        assert rows[0]["control"] == ""


# ── ampliseq ──────────────────────────────────────────────────────────────


class TestAmpliseq:
    def test_header(self):
        text = generate_samplesheet("ampliseq", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["sampleID", "forwardReads", "reverseReads", "run"]

    def test_default_run_id(self):
        _, rows = _parse_csv(generate_samplesheet("ampliseq", [SE]))
        assert rows[0]["run"] == "run1"

    def test_custom_run_id(self):
        s = SampleInput("S1", "s3://b/s1.fastq.gz", extra={"run": "plate3"})
        _, rows = _parse_csv(generate_samplesheet("ampliseq", [s]))
        assert rows[0]["run"] == "plate3"


# ── fetchngs ──────────────────────────────────────────────────────────────


class TestFetchngs:
    def test_plain_text_one_per_line(self):
        s1 = SampleInput("S1", "SRR123456")
        s2 = SampleInput("S2", "SRR654321")
        text = generate_samplesheet("fetchngs", [s1, s2])
        lines = [l for l in text.splitlines() if l.strip()]
        assert lines == ["SRR123456", "SRR654321"]

    def test_no_csv_header(self):
        s = SampleInput("S1", "SRR000001")
        text = generate_samplesheet("fetchngs", [s])
        assert "," not in text.splitlines()[0]


# ── fallback (generic) ────────────────────────────────────────────────────


class TestGenericFallback:
    def test_unknown_pipeline_uses_generic_header(self):
        text = generate_samplesheet("some-unknown-pipeline", [SE])
        headers, _ = _parse_csv(text)
        assert headers == ["sample", "fastq_1", "fastq_2"]


# ── samplesheet_filename ──────────────────────────────────────────────────


class TestSamplesheetFilename:
    def test_fetchngs_returns_ids_txt(self):
        assert samplesheet_filename("fetchngs") == "ids.txt"

    def test_rnaseq_returns_csv(self):
        assert samplesheet_filename("rnaseq") == "samplesheet.csv"

    def test_nf_core_prefix_stripped(self):
        assert samplesheet_filename("nf-core/sarek") == "samplesheet.csv"

    def test_unknown_returns_csv(self):
        assert samplesheet_filename("my-custom-pipeline") == "samplesheet.csv"

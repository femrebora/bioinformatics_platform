"""Unit tests for the mock pipeline runners.

All ``time.sleep`` calls are patched so tests finish instantly.
The mock runners are deterministic (seeded by storage_key) so
result shapes are stable across repeated runs.
"""
import pytest
from unittest.mock import patch


STORAGE_KEY = "uploads/user123/sample.fastq.gz"
FILE_TYPE   = "fastq"
JOB_ID      = "test-job-001"


# ── Helper ────────────────────────────────────────────────────────────────

def _no_sleep(seconds):
    """Replacement for time.sleep that does nothing."""
    pass


# ── MockNextflowRunner ────────────────────────────────────────────────────


class TestMockNextflowRunner:
    @pytest.fixture
    def runner(self):
        from app.services.nextflow.mock import MockNextflowRunner
        return MockNextflowRunner()

    def _run(self, runner, pipeline_id):
        with patch("app.services.nextflow.mock.time.sleep", _no_sleep):
            return runner.run(pipeline_id, STORAGE_KEY, FILE_TYPE, job_id=JOB_ID)

    def test_rnaseq_returns_table(self, runner):
        result = self._run(runner, "rnaseq")
        assert result["type"] == "table"
        assert "columns" in result
        assert "rows" in result
        assert len(result["rows"]) > 0

    def test_rnaseq_has_de_columns(self, runner):
        result = self._run(runner, "rnaseq")
        assert "log2FoldChange" in result["columns"]
        assert "padj" in result["columns"]

    def test_sarek_returns_vcf(self, runner):
        result = self._run(runner, "sarek")
        assert result["type"] == "vcf"
        assert "variants" in result
        assert len(result["variants"]) > 0

    def test_sarek_variant_has_required_fields(self, runner):
        result = self._run(runner, "sarek")
        v = result["variants"][0]
        for field in ("chrom", "pos", "ref", "alt", "filter"):
            assert field in v, f"Missing variant field: {field!r}"

    def test_atacseq_returns_files(self, runner):
        result = self._run(runner, "atacseq")
        assert result["type"] == "files"
        assert len(result["files"]) > 0

    def test_chipseq_returns_files(self, runner):
        result = self._run(runner, "chipseq")
        assert result["type"] == "files"

    def test_ampliseq_returns_table(self, runner):
        result = self._run(runner, "ampliseq")
        assert result["type"] == "table"
        assert "phylum" in result["columns"]

    def test_fetchngs_returns_files(self, runner):
        result = self._run(runner, "fetchngs")
        assert result["type"] == "files"
        names = [f["name"] for f in result["files"]]
        assert any(n.endswith(".fastq.gz") for n in names)

    def test_default_pipeline_returns_files(self, runner):
        result = self._run(runner, "unknown-pipeline-xyz")
        assert result["type"] == "files"

    def test_result_includes_instance_type(self, runner):
        result = self._run(runner, "rnaseq")
        assert "instance_type" in result

    def test_result_includes_runtime_seconds(self, runner):
        result = self._run(runner, "rnaseq")
        assert "runtime_seconds" in result

    def test_deterministic_for_same_storage_key(self, runner):
        r1 = self._run(runner, "rnaseq")
        r2 = self._run(runner, "rnaseq")
        # Same gene names and padj values
        assert r1["rows"][0]["gene_name"] == r2["rows"][0]["gene_name"]
        assert r1["rows"][0]["padj"] == r2["rows"][0]["padj"]

    def test_nf_core_prefix_handled(self, runner):
        result = self._run(runner, "nf-core/rnaseq")
        assert result["type"] == "table"


# ── MockSnakemakeRunner ───────────────────────────────────────────────────


class TestMockSnakemakeRunner:
    @pytest.fixture
    def runner(self):
        from app.services.snakemake.mock import MockSnakemakeRunner
        return MockSnakemakeRunner()

    def _run(self, runner, workflow_config=None):
        with patch("app.services.snakemake.mock.time.sleep", _no_sleep):
            return runner.run(
                "snakemake",
                STORAGE_KEY,
                FILE_TYPE,
                job_id=JOB_ID,
                workflow_config=workflow_config,
            )

    def test_returns_files_type(self, runner):
        result = self._run(runner)
        assert result["type"] == "files"

    def test_has_bam_file(self, runner):
        result = self._run(runner)
        names = [f["name"] for f in result["files"]]
        assert any(".bam" in n for n in names)

    def test_has_vcf_file(self, runner):
        result = self._run(runner)
        names = [f["name"] for f in result["files"]]
        assert any(".vcf" in n for n in names)

    def test_has_multiqc_report(self, runner):
        result = self._run(runner)
        names = [f["name"] for f in result["files"]]
        assert any("multiqc" in n.lower() for n in names)

    def test_each_file_has_required_fields(self, runner):
        result = self._run(runner)
        for f in result["files"]:
            assert "name" in f
            assert "path" in f
            assert "size_bytes" in f
            assert "mime_type" in f

    def test_instance_type_present(self, runner):
        result = self._run(runner)
        assert "instance_type" in result

    def test_runtime_seconds_present(self, runner):
        result = self._run(runner)
        assert "runtime_seconds" in result

    def test_deterministic_for_same_storage_key(self, runner):
        r1 = self._run(runner)
        r2 = self._run(runner)
        assert r1["files"][0]["name"] == r2["files"][0]["name"]


# ── MockBioScriptRunner ───────────────────────────────────────────────────


class TestMockBioScriptRunner:
    @pytest.fixture
    def runner(self):
        from app.services.bioscript.mock import MockBioScriptRunner
        return MockBioScriptRunner()

    def _run(self, runner, script="# qc and align"):
        with patch("app.services.bioscript.mock.time.sleep", _no_sleep):
            return runner.run(
                STORAGE_KEY,
                FILE_TYPE,
                job_id=JOB_ID,
                workflow_config={"script": script},
            )

    def test_returns_files_type(self, runner):
        result = self._run(runner)
        assert result["type"] == "files"

    def test_always_includes_bam(self, runner):
        result = self._run(runner)
        names = [f["name"] for f in result["files"]]
        assert any(".bam" in n for n in names)

    def test_always_includes_multiqc(self, runner):
        result = self._run(runner)
        names = [f["name"] for f in result["files"]]
        assert any("multiqc" in n.lower() for n in names)

    def test_script_keyword_vcf_adds_vcf_output(self, runner):
        result = self._run(runner, script="bcftools call -mv")
        names = [f["name"] for f in result["files"]]
        assert any(".vcf" in n for n in names)

    def test_script_keyword_counts_adds_counts(self, runner):
        result = self._run(runner, script="featurecounts -a annotation.gtf")
        names = [f["name"] for f in result["files"]]
        assert any("count" in n.lower() for n in names)

    def test_script_preserved_in_outputs(self, runner):
        script = "#!/bin/bash\necho hello"
        result = self._run(runner, script=script)
        names = [f["name"] for f in result["files"]]
        assert "script.sh" in names

    def test_instance_type_present(self, runner):
        result = self._run(runner)
        assert "instance_type" in result

    def test_no_workflow_config_uses_defaults(self, runner):
        with patch("app.services.bioscript.mock.time.sleep", _no_sleep):
            result = runner.run(STORAGE_KEY, FILE_TYPE, job_id=JOB_ID)
        assert result["type"] == "files"


# ── MockCustomRunner ──────────────────────────────────────────────────────


CUSTOM_TOOLS = ["spades", "kraken2", "prokka", "iqtree", "flye"]


class TestMockCustomRunner:
    @pytest.fixture
    def runner(self):
        from app.services.custom.mock import MockCustomRunner
        return MockCustomRunner()

    def _run(self, runner, tool):
        with patch("app.services.custom.mock.time.sleep", _no_sleep):
            return runner.run(tool, STORAGE_KEY, FILE_TYPE, job_id=JOB_ID)

    @pytest.mark.parametrize("tool", CUSTOM_TOOLS)
    def test_returns_files_type(self, runner, tool):
        result = self._run(runner, tool)
        assert result["type"] == "files"

    @pytest.mark.parametrize("tool", CUSTOM_TOOLS)
    def test_returns_nonempty_files(self, runner, tool):
        result = self._run(runner, tool)
        assert len(result["files"]) > 0

    def test_spades_has_contigs(self, runner):
        result = self._run(runner, "spades")
        names = [f["name"] for f in result["files"]]
        assert "contigs.fasta" in names

    def test_kraken2_has_taxonomy_report(self, runner):
        result = self._run(runner, "kraken2")
        names = [f["name"] for f in result["files"]]
        assert "taxonomy_report.tsv" in names

    def test_prokka_has_gff(self, runner):
        result = self._run(runner, "prokka")
        names = [f["name"] for f in result["files"]]
        assert "genome.gff" in names

    def test_iqtree_has_newick_tree(self, runner):
        result = self._run(runner, "iqtree")
        names = [f["name"] for f in result["files"]]
        assert "tree.nwk" in names

    def test_flye_has_assembly(self, runner):
        result = self._run(runner, "flye")
        names = [f["name"] for f in result["files"]]
        assert "assembly.fasta" in names

    def test_unknown_tool_falls_back_to_spades(self, runner):
        result = self._run(runner, "not-a-tool")
        assert result["type"] == "files"
        # falls back to spades outputs
        names = [f["name"] for f in result["files"]]
        assert "contigs.fasta" in names

    def test_each_file_has_s3_path(self, runner):
        result = self._run(runner, "spades")
        for f in result["files"]:
            assert f["path"].startswith("s3://")

    def test_each_file_has_mime_type(self, runner):
        result = self._run(runner, "spades")
        for f in result["files"]:
            assert "mime_type" in f
            assert f["mime_type"]  # not empty

    def test_instance_type_present(self, runner):
        result = self._run(runner, "spades")
        assert result["instance_type"] == "t3.xlarge"

    def test_deterministic_for_same_key_and_tool(self, runner):
        r1 = self._run(runner, "spades")
        r2 = self._run(runner, "spades")
        assert r1["files"][0]["size_bytes"] == r2["files"][0]["size_bytes"]

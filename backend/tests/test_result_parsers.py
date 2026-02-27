"""Unit tests for result_parsers.py — all pure functions, no I/O."""
import pytest
from app.services.result_parsers import (
    parse_vcf,
    parse_count_matrix,
    parse_multiqc_html,
    parse_file_list,
    parse_text,
    detect_and_parse,
)


# ── VCF ───────────────────────────────────────────────────────────────────


VCF_CONTENT = """\
##fileformat=VCFv4.2
##FILTER=<ID=PASS,Description="All filters passed">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t925952\t.\tG\tA\t112.0\tPASS\tDP=30;GQ=99
chr7\t117548628\t.\tT\tC\t250.0\tPASS\tDP=55;GQ=99
chr17\t41276045\trs28897672\tC\tT\t60.0\tLowQual\tDP=12;GQ=40
"""


class TestParseVcf:
    def test_returns_vcf_type(self):
        result = parse_vcf(VCF_CONTENT)
        assert result["type"] == "vcf"

    def test_parses_all_data_rows(self):
        result = parse_vcf(VCF_CONTENT)
        assert len(result["variants"]) == 3

    def test_skips_header_lines(self):
        result = parse_vcf(VCF_CONTENT)
        # No header rows should appear in variants
        for v in result["variants"]:
            assert not v["chrom"].startswith("#")

    def test_variant_fields(self):
        result = parse_vcf(VCF_CONTENT)
        v = result["variants"][0]
        assert v["chrom"] == "chr1"
        assert v["pos"] == 925952
        assert v["ref"] == "G"
        assert v["alt"] == "A"
        assert v["filter"] == "PASS"

    def test_max_variants_limit(self):
        many_variants = VCF_CONTENT + "\n".join(
            f"chr1\t{i}\t.\tA\tT\t100\tPASS\tDP=20"
            for i in range(1_000, 1_600)
        )
        result = parse_vcf(many_variants, max_variants=10)
        assert len(result["variants"]) == 10

    def test_empty_vcf_returns_empty_variants(self):
        result = parse_vcf("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n")
        assert result["variants"] == []

    def test_malformed_rows_skipped(self):
        bad = "chr1\t100\t.\tA\n"  # only 4 columns
        result = parse_vcf(bad)
        assert result["variants"] == []

    def test_non_integer_pos_kept_as_string(self):
        content = "chr1\tNOTANUMBER\t.\tA\tT\t.\t.\t.\n"
        result = parse_vcf(content)
        assert result["variants"][0]["pos"] == "NOTANUMBER"


# ── Count matrix ──────────────────────────────────────────────────────────


TSV_CONTENT = "gene_id\tcount\tpadj\nGENE1\t100\t0.01\nGENE2\t200\t0.05\nGENE3\t50\t0.99\n"
CSV_CONTENT = "gene_id,count,padj\nGENE1,100,0.01\nGENE2,200,0.05\n"


class TestParseCountMatrix:
    def test_tab_delimited_returns_table(self):
        result = parse_count_matrix(TSV_CONTENT)
        assert result["type"] == "table"

    def test_parses_columns(self):
        result = parse_count_matrix(TSV_CONTENT)
        assert result["columns"] == ["gene_id", "count", "padj"]

    def test_parses_rows(self):
        result = parse_count_matrix(TSV_CONTENT)
        assert len(result["rows"]) == 3

    def test_row_values(self):
        result = parse_count_matrix(TSV_CONTENT)
        assert result["rows"][0]["gene_id"] == "GENE1"
        assert result["rows"][0]["count"] == "100"

    def test_csv_delimited(self):
        result = parse_count_matrix(CSV_CONTENT)
        assert result["type"] == "table"
        assert len(result["rows"]) == 2

    def test_max_rows_limit(self):
        header = "a\tb\n"
        many   = "\n".join(f"x{i}\t{i}" for i in range(3000))
        result = parse_count_matrix(header + many, max_rows=100)
        assert len(result["rows"]) == 100


# ── MultiQC / HTML ────────────────────────────────────────────────────────


class TestParseMultiqcHtml:
    def test_returns_html_report_type(self):
        result = parse_multiqc_html("<html><body>Report</body></html>")
        assert result["type"] == "html_report"

    def test_html_preserved(self):
        html = "<html><body>Report</body></html>"
        result = parse_multiqc_html(html)
        assert result["html"] == html


# ── File list ─────────────────────────────────────────────────────────────


class TestParseFileList:
    def test_returns_files_type(self):
        files = [{"name": "a.bam", "path": "results/a.bam"}]
        result = parse_file_list(files)
        assert result["type"] == "files"

    def test_files_preserved(self):
        files = [
            {"name": "a.bam", "path": "results/a.bam", "size_bytes": 1024},
            {"name": "b.bai", "path": "results/b.bai", "size_bytes": 512},
        ]
        result = parse_file_list(files)
        assert result["files"] == files

    def test_empty_list(self):
        result = parse_file_list([])
        assert result["files"] == []


# ── Plain text ────────────────────────────────────────────────────────────


class TestParseText:
    def test_returns_text_type(self):
        result = parse_text("hello world")
        assert result["type"] == "text"

    def test_content_preserved(self):
        result = parse_text("hello world")
        assert result["content"] == "hello world"

    def test_truncated_at_max_chars(self):
        long_text = "x" * 30_000
        result = parse_text(long_text, max_chars=100)
        assert len(result["content"]) == 100


# ── Auto-detect ───────────────────────────────────────────────────────────


class TestDetectAndParse:
    def test_vcf_extension(self):
        result = detect_and_parse(VCF_CONTENT, "calls.vcf")
        assert result["type"] == "vcf"

    def test_vcf_gz_extension(self):
        result = detect_and_parse(VCF_CONTENT, "calls.vcf.gz")
        assert result["type"] == "vcf"

    def test_html_extension(self):
        result = detect_and_parse("<html/>", "report.html")
        assert result["type"] == "html_report"

    def test_htm_extension(self):
        result = detect_and_parse("<html/>", "report.htm")
        assert result["type"] == "html_report"

    def test_tsv_extension(self):
        result = detect_and_parse(TSV_CONTENT, "counts.tsv")
        assert result["type"] == "table"

    def test_csv_extension(self):
        result = detect_and_parse(CSV_CONTENT, "counts.csv")
        assert result["type"] == "table"

    def test_txt_extension(self):
        result = detect_and_parse("log text", "run.log")
        assert result["type"] == "text"

    def test_unknown_extension_falls_back_to_text(self):
        result = detect_and_parse("binary?", "data.bin")
        assert result["type"] == "text"

    def test_case_insensitive_extension(self):
        result = detect_and_parse(VCF_CONTENT, "CALLS.VCF")
        assert result["type"] == "vcf"

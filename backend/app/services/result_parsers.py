"""Result parsers for nf-core (and other) pipeline outputs.

Each parser converts raw text/bytes/dict output into a ``JobResult``-
compatible dict understood by the frontend ``ResultsPanel``.

Supported result types (matching frontend ``JobResult.type``):

* ``"table"``        — generic tabular data (gene counts, taxonomy, etc.)
* ``"vcf"``          — variant call format
* ``"html_report"``  — HTML content (e.g. MultiQC)
* ``"text"``         — plain text
* ``"files"``        — list of output files with download metadata
"""
import csv
import io
import re
from typing import Optional


# ── VCF ───────────────────────────────────────────────────────────────────


def parse_vcf(vcf_text: str, max_variants: int = 500) -> dict:
    """Parse VCF format text into ``type='vcf'`` result dict.

    Only the first ``max_variants`` data rows are included to keep the
    payload size reasonable.
    """
    variants: list[dict] = []
    for line in vcf_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        variants.append({
            "chrom":  parts[0],
            "pos":    int(parts[1]) if parts[1].isdigit() else parts[1],
            "id":     parts[2],
            "ref":    parts[3],
            "alt":    parts[4],
            "qual":   parts[5] if len(parts) > 5 else ".",
            "filter": parts[6] if len(parts) > 6 else ".",
            "info":   parts[7] if len(parts) > 7 else ".",
        })
        if len(variants) >= max_variants:
            break
    return {"type": "vcf", "variants": variants}


# ── TSV / count matrix ────────────────────────────────────────────────────


def parse_count_matrix(tsv_text: str, max_rows: int = 2000) -> dict:
    """Parse a tab-separated count / DE matrix into ``type='table'``.

    Handles both comma- and tab-delimited input by sniffing the dialect.
    """
    sample = tsv_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
    except csv.Error:
        dialect = csv.excel_tab  # type: ignore[assignment]

    reader = csv.DictReader(io.StringIO(tsv_text), dialect=dialect)
    rows: list[dict] = []
    for row in reader:
        rows.append(dict(row))
        if len(rows) >= max_rows:
            break
    columns = list(reader.fieldnames or [])
    return {"type": "table", "columns": columns, "rows": rows}


# ── MultiQC / HTML ────────────────────────────────────────────────────────


def parse_multiqc_html(html_content: str) -> dict:
    """Wrap a MultiQC (or other) HTML report as ``type='html_report'``."""
    return {"type": "html_report", "html": html_content}


# ── File list ─────────────────────────────────────────────────────────────


def parse_file_list(files: list[dict]) -> dict:
    """Convert an output file manifest into ``type='files'``.

    Each file dict should contain at minimum ``name`` and ``path``.
    Optional: ``size_bytes``, ``mime_type``, ``description``.
    """
    return {"type": "files", "files": files}


# ── Plain text ────────────────────────────────────────────────────────────


def parse_text(content: str, max_chars: int = 20_000) -> dict:
    """Wrap plain text content as ``type='text'``."""
    return {"type": "text", "content": content[:max_chars]}


# ── Auto-detect dispatcher ────────────────────────────────────────────────


_EXT_PARSERS: list[tuple[str, str]] = [
    (r"\.vcf(\.gz)?$",            "vcf"),
    (r"\.(html|htm)$",            "html_report"),
    (r"\.(tsv|csv)$",             "table"),
    (r"\.(txt|log|out)$",         "text"),
]


def detect_and_parse(
    content: str,
    filename: str,
    pipeline_id: Optional[str] = None,
) -> dict:
    """Auto-detect the result format from the filename extension.

    Falls back to plain-text for unknown extensions.
    """
    name = filename.lower()
    for pattern, kind in _EXT_PARSERS:
        if re.search(pattern, name):
            if kind == "vcf":
                return parse_vcf(content)
            if kind == "html_report":
                return parse_multiqc_html(content)
            if kind == "table":
                return parse_count_matrix(content)
            if kind == "text":
                return parse_text(content)
    return parse_text(content)

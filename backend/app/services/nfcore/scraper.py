"""
nf-core catalog scraper.

Strategy (no GitHub token needed):
  1. nf-co.re/pipelines.json     → all ~100 pipelines  (1 HTTP request)
  2. GitHub Trees API (recursive) → full repo file list (1 API request)
  3. raw.githubusercontent.com    → each meta.yml       (not API-rate-limited)

Concurrency: asyncio + semaphore (15 parallel requests for meta.yml files).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import yaml

logger = logging.getLogger(__name__)

PIPELINES_URL = "https://nf-co.re/pipelines.json"
MODULES_TREE_URL = (
    "https://api.github.com/repos/nf-core/modules/git/trees/master?recursive=1"
)
RAW_BASE = "https://raw.githubusercontent.com/nf-core/modules/master"
CONCURRENCY = 15

# ── Schema input format mapping ────────────────────────────────────────────

# Samplesheet column name → canonical format value
_COLNAME_TO_FORMAT = {
    "fastq_1": "fastq", "fastq_2": "fastq", "fastq": "fastq",
    "read1": "fastq", "read2": "fastq", "reads": "fastq",
    "bam": "bam",
    "cram": "cram",
    "sam": "sam",
    "vcf": "vcf",
    "bcf": "bcf",
    "fasta": "fasta", "genome": "fasta",
    "tiff": "tiff", "tif": "tiff",
    "ome_tiff": "ome_tiff",
    "zarr": "zarr",
    "n5": "n5",
    "png": "png",
    "czi": "czi",
    "lif": "lif",
    "nd2": "nd2",
    "svs": "svs",
    "h5ad": "h5ad",
    "loom": "loom",
    "mzml": "mzml",
    "mzxml": "mzxml",
    "raw": "raw",
    "mgf": "mgf",
    "bed": "bed",
    "gtf": "gtf",
    "gff": "gff",
    "tsv": "tsv",
    "csv": "csv",
}

# File extension appearing in a JSON schema pattern → canonical format value
_EXT_TO_FORMAT = {
    "fastq": "fastq", "fq": "fastq",
    "bam": "bam", "cram": "cram", "sam": "sam",
    "vcf": "vcf", "bcf": "bcf",
    "fa": "fasta", "fasta": "fasta", "fna": "fasta",
    "tiff": "tiff", "tif": "tiff",
    "zarr": "zarr", "n5": "n5",
    "png": "png", "czi": "czi", "lif": "lif", "nd2": "nd2", "svs": "svs",
    "h5ad": "h5ad", "loom": "loom",
    "mzml": "mzml", "mzxml": "mzxml", "raw": "raw", "mgf": "mgf",
    "bed": "bed", "gtf": "gtf", "gff": "gff",
    "tsv": "tsv", "csv": "csv", "json": "json",
}


def _parse_schema_input(schema: dict) -> list[str]:
    """
    Extract accepted file formats from a pipeline's assets/schema_input.json.

    The schema is a JSON Schema object. Column names (properties) and their
    regex patterns are both inspected to derive format values.
    """
    import re as _re

    # schema_input.json can be an array-of-objects schema
    if schema.get("type") == "array":
        properties = schema.get("items", {}).get("properties", {})
    else:
        properties = schema.get("properties", {})

    formats: set[str] = set()

    for col_name, col_def in properties.items():
        if not isinstance(col_def, dict):
            continue
        col_type = col_def.get("type", "string")
        if col_type not in ("string", ""):
            continue

        # 1. Match by column name
        fmt = _COLNAME_TO_FORMAT.get(col_name.lower())
        if fmt:
            formats.add(fmt)

        # 2. Match by regex pattern — extract extensions like \.bam or \.(bam|cram)
        pattern = col_def.get("pattern", "")
        if pattern:
            # Unescape and find all extensions
            for ext in _re.findall(r'\\?\.([a-zA-Z0-9]+)', pattern):
                fmt = _EXT_TO_FORMAT.get(ext.lower())
                if fmt:
                    formats.add(fmt)

    return sorted(formats)

# Keyword → category mapping (first match wins)
_CATEGORY_MAP = [
    ("Alignment",       ["align", "mapping", "bwa", "bowtie", "hisat", "minimap", "ngm"]),
    ("QC / Trimming",   ["quality", " qc", "fastqc", "multiqc", "trim", "fastp", "cutadapt", "bbduk"]),
    ("Variant Calling", ["variant", "snp", "indel", "gatk", "bcftools", "freebayes", "mutect", "strelka", "deepvariant"]),
    ("RNA-seq",         ["rna", "salmon", "kallisto", "featurecounts", "deseq", "transcript", "expression", "tximeta"]),
    ("Quantification",  ["quantif", "count", "htseq", "cufflinks", "stringtie"]),
    ("Assembly",        ["assembly", "spades", "trinity", "flye", "canu", "megahit", "velvet"]),
    ("Annotation",      ["annotation", "snpeff", "vep", "annovar", "functional", "predict", "interpro"]),
    ("Methylation",     ["methylation", "bismark", "bisulfite", "methyl", "wgbs"]),
    ("Phylogenetics",   ["phylogen", "tree", "msa", "muscle", "mafft", "iqtree", "raxml"]),
    ("Proteomics",      ["protein", "mass spec", "peptide", "mascot", "maxquant"]),
    ("Structural",      ["structure", "alphafold", "modeller", "rosetta", "3d"]),
    ("Conversion",      ["samtools", "convert", "sort", "index", "merge", "filter", "picard", "bedtools"]),
]


def derive_category(tool: str, keywords: list, description: str) -> str:
    text = " ".join([tool] + (keywords or []) + [description or ""]).lower()
    for category, kws in _CATEGORY_MAP:
        if any(kw in text for kw in kws):
            return category
    return "Other"


def parse_meta_yml(path: str, content: str) -> Optional[dict]:
    """
    Parse a meta.yml file into a module dict.
    path example: modules/nf-core/samtools/sort/meta.yml
    """
    try:
        meta = yaml.safe_load(content)
        if not isinstance(meta, dict):
            return None

        parts = path.split("/")
        # parts: ['modules', 'nf-core', '<tool>', '<subcmd?>', 'meta.yml']
        if len(parts) < 4:
            return None

        tool = parts[2]
        subcommand = parts[3] if parts[3] != "meta.yml" else None
        module_id = f"{tool}/{subcommand}" if subcommand else tool

        description = meta.get("description", "") or ""
        keywords = meta.get("keywords") or []

        _SKIP_NAMES = {"meta", "versions", "fasta", "fai", "dict"}

        def _extract_file_ports_from_channel(parts: list) -> list:
            """
            Extract file/directory ports from one channel represented as a list of
            {port_name: {type, description, pattern, ...}} single-key dicts.
            Skips meta maps, versions, and template names like ${prefix}.bam.
            """
            result = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                for name, details in part.items():
                    if not name or name in _SKIP_NAMES or name.startswith("${"):
                        continue
                    if not isinstance(details, dict):
                        continue
                    ptype = details.get("type", "file")
                    if ptype not in ("file", "directory"):
                        continue
                    result.append({
                        "name": name,
                        "type": ptype,
                        "description": (details.get("description") or "")[:120],
                        "pattern": details.get("pattern", ""),
                    })
            return result

        def _parse_input(items) -> list:
            result = []
            for item in (items or []):
                if isinstance(item, list):
                    # New format: channel = list of {name: details} dicts
                    result.extend(_extract_file_ports_from_channel(item))
                elif isinstance(item, dict):
                    # Old format: {name: {type, description, pattern}}
                    result.extend(_extract_file_ports_from_channel([item]))
            return result

        def _parse_output(output_data) -> list:
            result = []
            if isinstance(output_data, dict):
                # Newest format: {channel_name: [[{name: details}, ...], ...]}
                # The channel_name IS the logical port name.
                for channel_name, channel_items in output_data.items():
                    if channel_name.startswith("versions") or not isinstance(channel_items, list):
                        continue
                    # Extract the file pattern from nested content
                    pattern = ""
                    for item in channel_items:
                        inner = item if isinstance(item, list) else [item]
                        for ports in _extract_file_ports_from_channel(inner):
                            if ports.get("pattern"):
                                pattern = ports["pattern"]
                                break
                    result.append({
                        "name": channel_name,
                        "type": "file",
                        "description": "",
                        "pattern": pattern,
                    })
            elif isinstance(output_data, list):
                # Old format
                for item in output_data:
                    if isinstance(item, list):
                        result.extend(_extract_file_ports_from_channel(item))
                    elif isinstance(item, dict):
                        result.extend(_extract_file_ports_from_channel([item]))
            return result

        inputs = _parse_input(meta.get("input"))
        outputs = _parse_output(meta.get("output"))

        category = derive_category(tool, keywords, description)

        return {
            "id": module_id,
            "tool": tool,
            "subcommand": subcommand,
            "description": description[:300],
            "keywords": keywords[:20],
            "category": category,
            "inputs": inputs,
            "outputs": outputs,
        }
    except Exception as exc:
        logger.debug("Failed to parse %s: %s", path, exc)
        return None


async def _fetch_pipelines(client: httpx.AsyncClient) -> list:
    resp = await client.get(PIPELINES_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # pipelines.json returns a list of GitHub repo objects
    if isinstance(data, list):
        return data
    # some versions wrap in {"remote_workflows": [...]}
    return data.get("remote_workflows", data.get("pipelines", []))


async def _fetch_module_tree(client: httpx.AsyncClient) -> list[str]:
    resp = await client.get(MODULES_TREE_URL, timeout=60)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [
        item["path"]
        for item in tree
        if (
            item.get("type") == "blob"
            and item["path"].startswith("modules/nf-core/")
            and item["path"].endswith("/meta.yml")
        )
    ]


async def run_scrape() -> tuple[list, list]:
    """
    Returns (pipelines_raw, [(path, content_or_None), ...]).
    Called via asyncio.run() from the Celery task.
    """
    headers = {"User-Agent": "bioinformatics-platform/1.0"}

    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=30.0
    ) as client:
        # 1. Pipelines
        logger.info("[nfcore] Fetching pipeline catalog...")
        try:
            pipelines = await _fetch_pipelines(client)
            logger.info("[nfcore] Got %d pipelines", len(pipelines))
        except Exception as exc:
            logger.error("[nfcore] Pipeline fetch failed: %s", exc)
            pipelines = []

        # 1b. Fetch schema_input.json for each pipeline to get accepted input formats
        # Use a dedicated semaphore — pipelines are ~144, so 20 concurrent is fine.
        pipe_sem = asyncio.Semaphore(20)

        async def _fetch_pipeline_schema(pipeline: dict) -> None:
            pid = pipeline.get("name", "")
            if not pid:
                return
            url = (
                f"https://raw.githubusercontent.com/nf-core/{pid}"
                f"/master/assets/schema_input.json"
            )
            try:
                async with pipe_sem:
                    resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    pipeline["input_formats"] = _parse_schema_input(resp.json())
            except Exception:
                pass  # leave input_formats unset → stored as NULL

        if pipelines:
            logger.info("[nfcore] Fetching input schemas for %d pipelines…", len(pipelines))
            await asyncio.gather(*[_fetch_pipeline_schema(p) for p in pipelines])
            n_with_formats = sum(1 for p in pipelines if p.get("input_formats"))
            logger.info("[nfcore] %d pipelines have input format data", n_with_formats)

        # 2. Module file tree (1 API call)
        logger.info("[nfcore] Fetching module tree from GitHub...")
        try:
            meta_paths = await _fetch_module_tree(client)
            logger.info("[nfcore] Found %d meta.yml paths", len(meta_paths))
        except Exception as exc:
            logger.error("[nfcore] Module tree fetch failed: %s", exc)
            meta_paths = []

        # 3. Fetch all meta.yml via raw.githubusercontent.com (no API quota)
        sem = asyncio.Semaphore(CONCURRENCY)

        async def _fetch_one(path: str):
            async with sem:
                url = f"{RAW_BASE}/{path}"
                try:
                    resp = await client.get(url, timeout=15)
                    if resp.status_code == 200:
                        return path, resp.text
                except Exception:
                    pass
                return path, None

        logger.info("[nfcore] Fetching %d meta.yml files...", len(meta_paths))
        results = await asyncio.gather(*[_fetch_one(p) for p in meta_paths])
        logger.info("[nfcore] Fetch complete")

        return pipelines, list(results)

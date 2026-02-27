"""
Snakemake catalog scraper.

Wrappers:  snakemake/snakemake-wrappers GitHub repo  (bio/*/meta.yaml files)
Workflows: Snakemake Workflow Catalog JSON            (single HTTP request)

Concurrency: asyncio + semaphore (15 parallel for wrapper meta.yaml files).
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import yaml

logger = logging.getLogger(__name__)

WRAPPERS_TREE_URL = (
    "https://api.github.com/repos/snakemake/snakemake-wrappers/git/trees/master?recursive=1"
)
WRAPPERS_RAW_BASE = "https://raw.githubusercontent.com/snakemake/snakemake-wrappers/master"
WORKFLOWS_CATALOG_URL = "https://raw.githubusercontent.com/snakemake/snakemake-workflow-catalog/main/data.json"
CONCURRENCY = 15

# Reuse the same keyword category map as nf-core
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


def _derive_category(tool: str, description: str) -> str:
    text = f"{tool} {description or ''}".lower()
    for category, kws in _CATEGORY_MAP:
        if any(kw in text for kw in kws):
            return category
    return "Other"


def _parse_wrapper_meta(path: str, content: str) -> Optional[dict]:
    """
    Parse a Snakemake wrapper meta.yaml.
    path example: bio/samtools/sort/meta.yaml
    """
    try:
        meta = yaml.safe_load(content)
        if not isinstance(meta, dict):
            return None

        # Derive tool/subcommand from path: bio/<tool>/<subcommand>/meta.yaml
        parts = path.split("/")
        # parts: ['bio', '<tool>', '<subcommand?>', 'meta.yaml']
        if len(parts) < 3:
            return None

        tool = parts[1] if len(parts) >= 2 else ""
        subcommand = parts[2] if len(parts) >= 4 and parts[2] != "meta.yaml" else None

        # Build wrapper ID without file extension: "bio/samtools/sort"
        wrapper_id = "/".join(parts[:-1])  # strip meta.yaml

        name = meta.get("name") or None
        description = meta.get("description") or ""

        # Authors — various formats
        raw_authors = meta.get("authors") or []
        if isinstance(raw_authors, list):
            authors = [
                a.get("name", str(a)) if isinstance(a, dict) else str(a)
                for a in raw_authors
            ]
        else:
            authors = []

        # Input/output port names
        def _extract_names(section) -> list[str]:
            if section is None:
                return []
            if isinstance(section, dict):
                return [k for k in section.keys() if k and not k.startswith("$")]
            if isinstance(section, list):
                names = []
                for i, item in enumerate(section):
                    if isinstance(item, str):
                        names.append(f"input_{i}" if "input" in path else f"output_{i}")
                    elif isinstance(item, dict):
                        for k in item.keys():
                            if k and not k.startswith("$"):
                                names.append(k)
                return names
            return []

        input_names = _extract_names(meta.get("input"))
        output_names = _extract_names(meta.get("output"))

        category = _derive_category(tool, description)

        return {
            "id": wrapper_id,
            "tool": tool,
            "subcommand": subcommand,
            "name": name,
            "description": description[:300] if description else None,
            "authors": authors[:20],
            "input_names": input_names[:20],
            "output_names": output_names[:20],
            "category": category,
        }
    except Exception as exc:
        logger.debug("Failed to parse wrapper %s: %s", path, exc)
        return None


async def _fetch_wrapper_tree(client: httpx.AsyncClient) -> list[str]:
    resp = await client.get(WRAPPERS_TREE_URL, timeout=60)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [
        item["path"]
        for item in tree
        if (
            item.get("type") == "blob"
            and re.match(r"^bio/.+/meta\.yaml$", item["path"])
        )
    ]


async def _fetch_workflows_catalog(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(WORKFLOWS_CATALOG_URL, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    # Some versions might be wrapped
    return data.get("workflows", data.get("data", []))


async def run_scrape_wrappers() -> list[tuple[str, Optional[str]]]:
    """
    Returns list of (path, content_or_None) for all bio/*/meta.yaml files.
    Called via asyncio.run() from the Celery task.
    """
    headers = {"User-Agent": "bioinformatics-platform/1.0"}

    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=30.0
    ) as client:
        logger.info("[snakemake] Fetching wrapper tree from GitHub...")
        try:
            meta_paths = await _fetch_wrapper_tree(client)
            logger.info("[snakemake] Found %d meta.yaml paths", len(meta_paths))
        except Exception as exc:
            logger.error("[snakemake] Wrapper tree fetch failed: %s", exc)
            return []

        sem = asyncio.Semaphore(CONCURRENCY)

        async def _fetch_one(path: str):
            async with sem:
                url = f"{WRAPPERS_RAW_BASE}/{path}"
                try:
                    resp = await client.get(url, timeout=15)
                    if resp.status_code == 200:
                        return path, resp.text
                except Exception:
                    pass
                return path, None

        logger.info("[snakemake] Fetching %d meta.yaml files...", len(meta_paths))
        results = await asyncio.gather(*[_fetch_one(p) for p in meta_paths])
        logger.info("[snakemake] Wrapper fetch complete")
        return list(results)


async def run_scrape_workflows() -> list[dict]:
    """
    Fetch the Snakemake Workflow Catalog JSON.
    Returns a list of raw workflow dicts.
    """
    headers = {"User-Agent": "bioinformatics-platform/1.0"}
    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=180.0
    ) as client:
        logger.info("[snakemake] Fetching workflow catalog...")
        try:
            workflows = await _fetch_workflows_catalog(client)
            logger.info("[snakemake] Got %d workflows", len(workflows))
            return workflows
        except Exception as exc:
            logger.error("[snakemake] Workflow catalog fetch failed: %s", exc)
            return []

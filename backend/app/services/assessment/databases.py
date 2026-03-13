"""
Synchronous wrappers for mutation databases.

Priority:
  1. Franklin by Genoox (primary) — ACMG classification, gnomAD AF, HGVS
  2. ClinVar (NCBI)               — fallback / supplement
  3. dbSNP (NCBI)                 — rsID fallback
  4. CancerHotspots.org           — cancer driver hotspot overlay

All functions tolerate network failures and return empty dicts on error.
NCBI rate limit without API key: 3 req/s — callers must pace requests.
"""
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "bioplatform-assessment/1.0 (research use)"})

FRANKLIN_BASE = "https://franklin.genoox.com/api/v1"
NCBI_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HOTSPOTS_BASE = "https://www.cancerhotspots.org/api"
NCBI_TIMEOUT  = 10  # seconds
FRANKLIN_TIMEOUT = 15  # seconds


def query_franklin(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Primary annotation source — Franklin by Genoox.

    Returns {classification, gene, acmg_criteria, gnomad_af, condition, hgvs}
    on success, or {} if the API key is absent / the call fails.

    Requires FRANKLIN_API_KEY in settings.
    API: POST https://franklin.genoox.com/api/v1/variant/analyze
    Docs: https://franklin.genoox.com/clinical-db/home
    """
    from app.config import settings
    if not settings.FRANKLIN_API_KEY:
        return {}

    try:
        chrom_clean = str(chrom).lstrip("chrCHR") or chrom
        # Franklin expects chromosome without 'chr' prefix for numeric chromosomes
        payload: dict[str, Any] = {
            "chromosome":    str(chrom),
            "position":      int(pos),
            "ref_allele":    ref,
            "alt_allele":    alt,
            "genome_version": settings.FRANKLIN_GENOME,
        }
        headers = {
            "Authorization": f"Bearer {settings.FRANKLIN_API_KEY}",
            "Content-Type":  "application/json",
        }
        r = _SESSION.post(
            f"{FRANKLIN_BASE}/variant/analyze",
            json=payload,
            headers=headers,
            timeout=FRANKLIN_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        # Normalise the response — field names may vary across API versions
        classification = (
            data.get("classification")
            or data.get("acmg_classification")
            or data.get("pathogenicity")
            or ""
        )
        gene = (
            data.get("gene_symbol")
            or data.get("gene")
            or (data.get("gene_data") or {}).get("symbol", "")
        )
        gnomad_af = (
            data.get("gnomad_af")
            or data.get("gnomAD_AF")
            or (data.get("population_data") or {}).get("gnomad_af")
        )
        hgvs = (
            data.get("hgvs")
            or data.get("hgvs_c")
            or data.get("protein_change")
            or ""
        )
        condition = data.get("condition") or data.get("disease") or ""
        acmg_criteria = data.get("acmg_criteria") or data.get("criteria") or []

        return {
            "classification":  classification,
            "gene":            gene,
            "acmg_criteria":   acmg_criteria,
            "gnomad_af":       gnomad_af,
            "condition":       condition,
            "hgvs":            hgvs,
        }

    except Exception as exc:
        logger.debug(
            "Franklin query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc
        )
        return {}


def query_clinvar(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Return {rsid, significance, gene, hgvs} from ClinVar for a given variant.
    Uses NCBI E-utilities esearch + esummary.
    """
    try:
        # Normalize chromosome name (remove 'chr' prefix for NCBI)
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")

        # esearch: find ClinVar IDs by position
        search_url = f"{NCBI_BASE}/esearch.fcgi"
        params = {
            "db": "clinvar",
            "term": f"{chrom_clean}[chr]+{pos}[chrpos37]",
            "retmode": "json",
            "retmax": "5",
        }
        r = _SESSION.get(search_url, params=params, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            # Try hg38 position field
            params["term"] = f"{chrom_clean}[chr]+{pos}[chrpos]"
            r = _SESSION.get(search_url, params=params, timeout=NCBI_TIMEOUT)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return {}

        # esummary: get clinical significance for the first result
        time.sleep(0.35)
        summary_url = f"{NCBI_BASE}/esummary.fcgi"
        sr = _SESSION.get(summary_url, params={"db": "clinvar", "id": ids[0], "retmode": "json"}, timeout=NCBI_TIMEOUT)
        sr.raise_for_status()
        result_obj = sr.json().get("result", {})
        doc = result_obj.get(ids[0], {})

        sig = ""
        clin_sig = doc.get("clinical_significance", {})
        if isinstance(clin_sig, dict):
            sig = clin_sig.get("description", "")
        elif isinstance(clin_sig, str):
            sig = clin_sig

        gene_names = []
        for gs in doc.get("genes", []):
            if isinstance(gs, dict) and gs.get("symbol"):
                gene_names.append(gs["symbol"])

        return {
            "rsid":         doc.get("accession", "."),
            "significance": sig or "Unknown",
            "gene":         gene_names[0] if gene_names else "",
            "hgvs":         doc.get("title", ""),
        }

    except Exception as exc:
        logger.debug("ClinVar query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


def query_cancer_hotspots(gene: str) -> dict[str, Any]:
    """
    Return {is_hotspot, hotspot_type} from cancerhotspots.org.
    Checks whether the gene has any registered hotspot mutations.
    """
    if not gene:
        return {"is_hotspot": False}
    try:
        url = f"{HOTSPOTS_BASE}/hotspots/single"
        r = _SESSION.get(url, params={"hugoSymbol": gene}, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        hits = r.json()
        if isinstance(hits, list) and hits:
            # Any result means the gene has hotspot mutations
            hotspot_type = hits[0].get("type", "recurrent") if isinstance(hits[0], dict) else "recurrent"
            return {"is_hotspot": True, "hotspot_type": hotspot_type}
        return {"is_hotspot": False}
    except Exception as exc:
        logger.debug("CancerHotspots query failed for %s: %s", gene, exc)
        return {"is_hotspot": False}


def query_dbsnp(chrom: str, pos: int | str) -> dict[str, Any]:
    """Return {rsid} from dbSNP by chromosome position."""
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")
        search_url = f"{NCBI_BASE}/esearch.fcgi"
        params = {
            "db": "snp",
            "term": f"{chrom_clean}[CHR]+{pos}:{pos}[CHRPOS]",
            "retmode": "json",
            "retmax": "1",
        }
        r = _SESSION.get(search_url, params=params, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            return {"rsid": f"rs{ids[0]}"}
        return {}
    except Exception as exc:
        logger.debug("dbSNP query failed for %s:%s: %s", chrom, pos, exc)
        return {}

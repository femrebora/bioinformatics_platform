"""
Synchronous wrappers for public mutation databases.

Sources queried per variant:
  1. ClinVar (NCBI)      — pathogenicity classification + gene + HGVS
  2. gnomAD              — population allele frequency (ACMG BA1/BS1/PM2)
  3. CancerHotspots.org  — recurrent cancer driver mutations
  4. dbSNP (NCBI)        — rsID fallback

All functions are tolerant of network failures and return empty dicts on error.
NCBI rate limit without API key: 3 req/s — callers must pace requests.
"""
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "bioplatform-assessment/1.0 (research use)"})

NCBI_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GNOMAD_BASE   = "https://gnomad.broadinstitute.org/api"
HOTSPOTS_BASE = "https://www.cancerhotspots.org/api"
NCBI_TIMEOUT  = 10   # seconds
GNOMAD_TIMEOUT = 15  # seconds


def query_clinvar(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Return {rsid, significance, gene, hgvs} from ClinVar for a given variant.
    Uses NCBI E-utilities esearch + esummary.
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")

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

        time.sleep(0.35)
        summary_url = f"{NCBI_BASE}/esummary.fcgi"
        sr = _SESSION.get(
            summary_url,
            params={"db": "clinvar", "id": ids[0], "retmode": "json"},
            timeout=NCBI_TIMEOUT,
        )
        sr.raise_for_status()
        result_obj = sr.json().get("result", {})
        doc = result_obj.get(ids[0], {})

        sig = ""
        clin_sig = doc.get("clinical_significance", {})
        if isinstance(clin_sig, dict):
            sig = clin_sig.get("description", "")
        elif isinstance(clin_sig, str):
            sig = clin_sig

        gene_names = [
            gs["symbol"]
            for gs in doc.get("genes", [])
            if isinstance(gs, dict) and gs.get("symbol")
        ]

        return {
            "rsid":         doc.get("accession", "."),
            "significance": sig or "Unknown",
            "gene":         gene_names[0] if gene_names else "",
            "hgvs":         doc.get("title", ""),
        }

    except Exception as exc:
        logger.debug("ClinVar query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


def query_gnomad(
    chrom: str,
    pos: int | str,
    ref: str,
    alt: str,
    dataset: str = "gnomad_r4",
) -> dict[str, Any]:
    """
    Return {af, ac, an, af_popmax, gene, hgvsc, hgvsp, rsids} from gnomAD.

    Uses the gnomAD public GraphQL API (no key required).
    dataset: 'gnomad_r4' (GRCh38) or 'gnomad_r2_1' (GRCh37/hg19).
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")
        variant_id = f"{chrom_clean}-{pos}-{ref}-{alt}"

        query = """
        query VariantQuery($variantId: String!, $dataset: DatasetId!) {
          variant(variantId: $variantId, dataset: $dataset) {
            genome {
              ac
              an
              af
              populations {
                id
                af
              }
            }
            exome {
              ac
              an
              af
              populations {
                id
                af
              }
            }
            genes {
              gene_name
            }
            rsids
            hgvsc
            hgvsp
          }
        }
        """
        r = _SESSION.post(
            GNOMAD_BASE,
            json={"query": query, "variables": {"variantId": variant_id, "dataset": dataset}},
            timeout=GNOMAD_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get("data", {}).get("variant") or {}

        if not data:
            return {}

        # Prefer genome (GRCh38 r4); fall back to exome
        freq_src = data.get("genome") or data.get("exome") or {}
        af = freq_src.get("af")

        # popmax AF — highest AF across continental populations
        pops = freq_src.get("populations") or []
        pop_afs = [p["af"] for p in pops if isinstance(p.get("af"), float)]
        af_popmax = max(pop_afs) if pop_afs else None

        gene_names = [g["gene_name"] for g in (data.get("genes") or []) if g.get("gene_name")]

        return {
            "af":         af,
            "ac":         freq_src.get("ac"),
            "an":         freq_src.get("an"),
            "af_popmax":  af_popmax,
            "gene":       gene_names[0] if gene_names else "",
            "hgvsc":      data.get("hgvsc", ""),
            "hgvsp":      data.get("hgvsp", ""),
            "rsids":      data.get("rsids") or [],
        }

    except Exception as exc:
        logger.debug("gnomAD query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


def query_cancer_hotspots(gene: str) -> dict[str, Any]:
    """
    Return {is_hotspot, hotspot_type} from cancerhotspots.org.
    """
    if not gene:
        return {"is_hotspot": False}
    try:
        url = f"{HOTSPOTS_BASE}/hotspots/single"
        r = _SESSION.get(url, params={"hugoSymbol": gene}, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        hits = r.json()
        if isinstance(hits, list) and hits:
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
        r = _SESSION.get(
            f"{NCBI_BASE}/esearch.fcgi",
            params={
                "db": "snp",
                "term": f"{chrom_clean}[CHR]+{pos}:{pos}[CHRPOS]",
                "retmode": "json",
                "retmax": "1",
            },
            timeout=NCBI_TIMEOUT,
        )
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            return {"rsid": f"rs{ids[0]}"}
        return {}
    except Exception as exc:
        logger.debug("dbSNP query failed for %s:%s: %s", chrom, pos, exc)
        return {}

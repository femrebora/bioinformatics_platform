"""
Synchronous wrappers for public mutation databases.

Sources queried per variant:
  1.  ClinVar (NCBI)        — pathogenicity classification + gene + HGVS
  2.  gnomAD                — population allele frequency (ACMG BA1/BS1/PM2)
  3.  Ensembl VEP           — SIFT, PolyPhen-2, consequence terms, transcript
  4.  CADD                  — phred-scaled pathogenicity score
  5.  CancerHotspots.org    — recurrent cancer driver mutations
  6.  dbSNP (NCBI)          — rsID fallback
  7.  UniProt               — protein function description (gene-level)
  8.  OMIM                  — gene-disease relationships (requires API key)
  9.  Orphanet              — rare disease associations (requires API key)

All functions tolerate network failures and return empty dicts/defaults on error.
NCBI rate limit without key: 3 req/s — callers must pace requests.
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
VEP_BASE      = "https://rest.ensembl.org"
CADD_BASE     = "https://cadd.gs.washington.edu/api/v1.0"
UNIPROT_BASE  = "https://rest.uniprot.org/uniprotkb"
OMIM_BASE     = "https://api.omim.org/api"
ORPHANET_BASE = "https://api.orphacode.org/EN"

NCBI_TIMEOUT    = 10
GNOMAD_TIMEOUT  = 15
VEP_TIMEOUT     = 20
CADD_TIMEOUT    = 15
UNIPROT_TIMEOUT = 10
OMIM_TIMEOUT    = 10
ORPHANET_TIMEOUT = 10

# gnomAD dataset → CADD genome string
_CADD_GENOME = {
    "gnomad_r4":   "GRCh38-v1.7",
    "gnomad_r2_1": "GRCh37-v1.6",
}


# ── ClinVar ────────────────────────────────────────────────────────────────────

def query_clinvar(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Return {rsid, significance, gene, hgvs} from ClinVar.
    Uses NCBI E-utilities esearch + esummary.
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")

        search_url = f"{NCBI_BASE}/esearch.fcgi"
        params: dict[str, Any] = {
            "db": "clinvar",
            "term": f"{chrom_clean}[chr]+{pos}[chrpos37]",
            "retmode": "json",
            "retmax": "5",
        }
        r = _SESSION.get(search_url, params=params, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            params["term"] = f"{chrom_clean}[chr]+{pos}[chrpos]"
            r = _SESSION.get(search_url, params=params, timeout=NCBI_TIMEOUT)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return {}

        time.sleep(0.35)
        sr = _SESSION.get(
            f"{NCBI_BASE}/esummary.fcgi",
            params={"db": "clinvar", "id": ids[0], "retmode": "json"},
            timeout=NCBI_TIMEOUT,
        )
        sr.raise_for_status()
        doc = sr.json().get("result", {}).get(ids[0], {})

        clin_sig = doc.get("clinical_significance", {})
        sig = clin_sig.get("description", "") if isinstance(clin_sig, dict) else str(clin_sig)

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


# ── gnomAD ────────────────────────────────────────────────────────────────────

def query_gnomad(
    chrom: str,
    pos: int | str,
    ref: str,
    alt: str,
    dataset: str = "gnomad_r4",
) -> dict[str, Any]:
    """
    Return {af, ac, an, af_popmax, gene, hgvsc, hgvsp, rsids} from gnomAD.
    dataset: 'gnomad_r4' (GRCh38) or 'gnomad_r2_1' (GRCh37/hg19).
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")
        variant_id = f"{chrom_clean}-{pos}-{ref}-{alt}"

        query = """
        query VariantQuery($variantId: String!, $dataset: DatasetId!) {
          variant(variantId: $variantId, dataset: $dataset) {
            genome { ac an af populations { id af } }
            exome  { ac an af populations { id af } }
            genes  { gene_name }
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

        freq_src = data.get("genome") or data.get("exome") or {}
        pops = freq_src.get("populations") or []
        pop_afs = [p["af"] for p in pops if isinstance(p.get("af"), float)]

        gene_names = [g["gene_name"] for g in (data.get("genes") or []) if g.get("gene_name")]

        return {
            "af":        freq_src.get("af"),
            "ac":        freq_src.get("ac"),
            "an":        freq_src.get("an"),
            "af_popmax": max(pop_afs) if pop_afs else None,
            "gene":      gene_names[0] if gene_names else "",
            "hgvsc":     data.get("hgvsc", ""),
            "hgvsp":     data.get("hgvsp", ""),
            "rsids":     data.get("rsids") or [],
        }

    except Exception as exc:
        logger.debug("gnomAD query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── Ensembl VEP ───────────────────────────────────────────────────────────────

def query_ensembl_vep(
    chrom: str,
    pos: int | str,
    ref: str,
    alt: str,
    assembly: str = "GRCh38",
) -> dict[str, Any]:
    """
    Return {sift_score, sift_pred, polyphen_score, polyphen_pred,
            consequence, gene, hgvsc, hgvsp, transcript} from Ensembl VEP.
    Uses the public REST API — no key required.
    assembly: 'GRCh38' (default) or 'GRCh37'.
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")
        # VEP region format: "{chr} {pos} . {ref} {alt} . . ."
        variant_str = f"{chrom_clean} {pos} . {ref} {alt} . . ."

        base = VEP_BASE if assembly == "GRCh38" else "https://grch37.rest.ensembl.org"
        r = _SESSION.post(
            f"{base}/vep/human/region",
            json={"variants": [variant_str]},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=VEP_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return {}

        hit = results[0]
        # Pick the most severe transcript consequence (canonical preferred)
        consequences = hit.get("transcript_consequences") or []
        canon = next((c for c in consequences if c.get("canonical")), None)
        tc = canon or (consequences[0] if consequences else {})

        consequence_terms = hit.get("most_severe_consequence", "")

        return {
            "sift_score":      tc.get("sift_score"),
            "sift_pred":       tc.get("sift_prediction", ""),
            "polyphen_score":  tc.get("polyphen_score"),
            "polyphen_pred":   tc.get("polyphen_prediction", ""),
            "consequence":     consequence_terms,
            "gene":            tc.get("gene_symbol", ""),
            "hgvsc":           tc.get("hgvsc", ""),
            "hgvsp":           tc.get("hgvsp", ""),
            "transcript":      tc.get("transcript_id", ""),
        }

    except Exception as exc:
        logger.debug("Ensembl VEP query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── CADD ──────────────────────────────────────────────────────────────────────

def query_cadd(
    chrom: str,
    pos: int | str,
    ref: str,
    alt: str,
    genome: str = "GRCh38-v1.7",
) -> dict[str, Any]:
    """
    Return {cadd_raw, cadd_phred} from the CADD REST API.
    genome: 'GRCh38-v1.7' (default) or 'GRCh37-v1.6'.
    CADD phred ≥ 20 → top 1% most deleterious; ≥ 30 → top 0.1%.
    """
    try:
        chrom_clean = str(chrom).replace("chr", "").replace("Chr", "")
        url = f"{CADD_BASE}/{genome}/{chrom_clean}_{pos}_{ref}_{alt}"
        r = _SESSION.get(url, timeout=CADD_TIMEOUT)
        r.raise_for_status()

        # Response is TSV with comment header lines starting with '#'
        lines = [ln for ln in r.text.strip().splitlines() if not ln.startswith("#") and ln]
        if not lines:
            return {}

        parts = lines[0].split("\t")
        # Columns: Chrom Pos Ref Alt RawScore PHRED
        if len(parts) >= 6:
            return {
                "cadd_raw":   float(parts[4]),
                "cadd_phred": float(parts[5]),
            }
        return {}

    except Exception as exc:
        logger.debug("CADD query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── CancerHotspots ────────────────────────────────────────────────────────────

def query_cancer_hotspots(gene: str) -> dict[str, Any]:
    """Return {is_hotspot, hotspot_type} from cancerhotspots.org."""
    if not gene:
        return {"is_hotspot": False}
    try:
        r = _SESSION.get(
            f"{HOTSPOTS_BASE}/hotspots/single",
            params={"hugoSymbol": gene},
            timeout=NCBI_TIMEOUT,
        )
        r.raise_for_status()
        hits = r.json()
        if isinstance(hits, list) and hits:
            hotspot_type = hits[0].get("type", "recurrent") if isinstance(hits[0], dict) else "recurrent"
            return {"is_hotspot": True, "hotspot_type": hotspot_type}
        return {"is_hotspot": False}
    except Exception as exc:
        logger.debug("CancerHotspots query failed for %s: %s", gene, exc)
        return {"is_hotspot": False}


# ── dbSNP ─────────────────────────────────────────────────────────────────────

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
        return {"rsid": f"rs{ids[0]}"} if ids else {}
    except Exception as exc:
        logger.debug("dbSNP query failed for %s:%s: %s", chrom, pos, exc)
        return {}


# ── UniProt ───────────────────────────────────────────────────────────────────

def query_uniprot(gene: str) -> dict[str, Any]:
    """
    Return {protein_name, protein_function, uniprot_id} for a human gene.
    Uses the UniProt public REST API — no key required.
    """
    if not gene:
        return {}
    try:
        r = _SESSION.get(
            f"{UNIPROT_BASE}/search",
            params={
                "query":  f"gene:{gene} AND organism_id:9606 AND reviewed:true",
                "format": "json",
                "fields": "id,protein_name,cc_function",
                "size":   "1",
            },
            headers={"Accept": "application/json"},
            timeout=UNIPROT_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return {}

        entry = results[0]
        uniprot_id = entry.get("primaryAccession", "")
        protein_name = (
            (entry.get("proteinDescription") or {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", "")
        )
        # Function comment (may be long — take first sentence)
        func_comments = entry.get("comments") or []
        func_text = ""
        for c in func_comments:
            if c.get("commentType") == "FUNCTION":
                texts = c.get("texts") or []
                if texts:
                    full = texts[0].get("value", "")
                    func_text = full.split(".")[0] + "." if "." in full else full
                break

        return {
            "uniprot_id":       uniprot_id,
            "protein_name":     protein_name,
            "protein_function": func_text,
        }

    except Exception as exc:
        logger.debug("UniProt query failed for gene %s: %s", gene, exc)
        return {}


# ── OMIM ──────────────────────────────────────────────────────────────────────

def query_omim(gene: str) -> dict[str, Any]:
    """
    Return {omim_id, disease, inheritance} for a gene from OMIM.
    Requires OMIM_API_KEY in settings (free academic registration at omim.org).
    Returns {} silently if no key is configured.
    """
    from app.config import settings
    if not settings.OMIM_API_KEY:
        return {}
    if not gene:
        return {}
    try:
        # Search gene → MIM number
        r = _SESSION.get(
            f"{OMIM_BASE}/entry/search",
            params={
                "search":      f"gene:{gene}",
                "filter":      "geneMap",
                "format":      "json",
                "apiKey":      settings.OMIM_API_KEY,
                "start":       0,
                "limit":       1,
            },
            timeout=OMIM_TIMEOUT,
        )
        r.raise_for_status()
        entries = (
            r.json()
            .get("omim", {})
            .get("searchResponse", {})
            .get("entryList", [])
        )
        if not entries:
            return {}

        entry = entries[0].get("entry", {})
        mim_number = entry.get("mimNumber", "")
        titles = entry.get("titles", {})
        disease = titles.get("preferredTitle", "") or titles.get("includedTitles", "")

        # Extract inheritance from geneMap
        gene_map = entry.get("geneMap", {})
        inheritance = gene_map.get("phenotypes", [{}])[0].get("inheritances", [""])[0] if gene_map.get("phenotypes") else ""

        return {
            "omim_id":     str(mim_number),
            "disease":     disease,
            "inheritance": inheritance,
        }

    except Exception as exc:
        logger.debug("OMIM query failed for gene %s: %s", gene, exc)
        return {}


# ── Orphanet ──────────────────────────────────────────────────────────────────

def query_orphanet(gene: str) -> dict[str, Any]:
    """
    Return {orpha_diseases: [{name, orphacode, type}]} for a gene.
    Requires ORPHANET_API_KEY in settings (free registration at orphacode.org).
    Returns {} silently if no key is configured.
    """
    from app.config import settings
    if not settings.ORPHANET_API_KEY:
        return {}
    if not gene:
        return {}
    try:
        r = _SESSION.get(
            f"{ORPHANET_BASE}/Gene/genesymbol/{gene}/Disease",
            headers={
                "apiKey":  settings.ORPHANET_API_KEY,
                "Accept":  "application/json",
            },
            timeout=ORPHANET_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        associations = data.get("ORPHAcode") or data.get("results") or []
        diseases = []
        for item in associations[:5]:  # cap at 5
            if isinstance(item, dict):
                diseases.append({
                    "name":      item.get("Disorder", {}).get("Name", "") if isinstance(item.get("Disorder"), dict) else str(item.get("name", "")),
                    "orphacode": item.get("Disorder", {}).get("OrphaCode", "") if isinstance(item.get("Disorder"), dict) else str(item.get("orphacode", "")),
                    "type":      item.get("DisorderDisorderAssociationType", {}).get("Name", "") if isinstance(item.get("DisorderDisorderAssociationType"), dict) else "",
                })
        return {"orpha_diseases": diseases} if diseases else {}

    except Exception as exc:
        logger.debug("Orphanet query failed for gene %s: %s", gene, exc)
        return {}

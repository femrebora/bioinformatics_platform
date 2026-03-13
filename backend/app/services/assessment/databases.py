"""
Synchronous wrappers for public mutation databases.

Variant-level sources:
  1.  ClinVar (NCBI)        — pathogenicity classification + gene + HGVS
  2.  gnomAD                — population allele frequency (ACMG BA1/BS1/PM2)
  3.  Ensembl VEP           — SIFT, PolyPhen-2, consequence terms, transcript
  4.  CADD                  — phred-scaled pathogenicity score
  5.  MyVariant.info        — REVEL, MetaLR, MetaSVM, MutationTaster, GERP++, PhyloP
  6.  SpliceAI (Broad)      — splice site disruption delta scores
  7.  InterVar (WinterVar)  — ACMG/AMP criteria + auto-classification
  8.  CancerHotspots.org    — recurrent cancer driver mutations
  9.  dbSNP (NCBI)          — rsID fallback

Gene-level sources (cached per gene):
  10. UniProt               — protein name + function
  11. HGNC                  — authoritative gene symbol, locus group, Ensembl/Entrez IDs
  12. ClinGen               — gene-disease validity (Definitive/Strong/Moderate)
  13. GenCC                 — aggregated gene-disease validity (ClinGen+OMIM+Orphanet+PanelApp)
  14. HPO / Ensembl         — phenotype terms associated with gene
  15. LOVD                  — locus-specific variant count
  16. OMIM                  — gene-disease + inheritance (optional: OMIM_API_KEY)
  17. Orphanet              — rare disease associations (optional: ORPHANET_API_KEY)

All functions tolerate network failures and return empty dicts/defaults on error.
NCBI rate limit without key: 3 req/s — callers must pace requests.
"""
import logging
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Thread-local sessions — each worker thread gets its own requests.Session so
# concurrent ThreadPoolExecutor calls don't share state across threads.
_thread_local = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update({"User-Agent": "bioplatform-assessment/1.0 (research use)"})
        _thread_local.session = s
    return _thread_local.session


def _clean_chrom(chrom: str) -> str:
    """Strip 'chr'/'Chr' prefix from chromosome identifiers."""
    return str(chrom).replace("chr", "").replace("Chr", "")


NCBI_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GNOMAD_BASE   = "https://gnomad.broadinstitute.org/api"
HOTSPOTS_BASE = "https://www.cancerhotspots.org/api"
VEP_BASE      = "https://rest.ensembl.org"
CADD_BASE     = "https://cadd.gs.washington.edu/api/v1.0"
UNIPROT_BASE  = "https://rest.uniprot.org/uniprotkb"
OMIM_BASE     = "https://api.omim.org/api"
ORPHANET_BASE = "https://api.orphacode.org/EN"

MYVARIANT_BASE     = "https://myvariant.info/v1"
SPLICEAI_BASE      = "https://spliceailookup-api.broadinstitute.org"
INTERVAR_BASE      = "http://wintervar.wglab.org"
CLINGEN_EREPO_BASE = "https://erepo.clinicalgenome.org/evrepo/api/v1"
LOVD_BASE          = "https://api.lovd.nl/v1.0"
HGNC_BASE          = "https://rest.genenames.org"
GENCC_BASE         = "https://thegencc.org/api/v1"

NCBI_TIMEOUT    = 10
GNOMAD_TIMEOUT  = 15
VEP_TIMEOUT     = 20
CADD_TIMEOUT    = 15
UNIPROT_TIMEOUT = 10
OMIM_TIMEOUT    = 10
ORPHANET_TIMEOUT = 10

MYVARIANT_TIMEOUT         = 15
SPLICEAI_TIMEOUT          = 15
INTERVAR_TIMEOUT          = 20
CLINGEN_TIMEOUT           = 12
LOVD_TIMEOUT              = 12
HGNC_TIMEOUT              = 10
GENCC_TIMEOUT             = 12
ENSEMBL_PHENOTYPE_TIMEOUT = 12


# ── ClinVar ────────────────────────────────────────────────────────────────────

def query_clinvar(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Return {rsid, significance, gene, hgvs} from ClinVar.
    Uses NCBI E-utilities esearch + esummary.
    """
    try:
        chrom_clean = _clean_chrom(chrom)

        search_url = f"{NCBI_BASE}/esearch.fcgi"
        params: dict[str, Any] = {
            "db": "clinvar",
            "term": f"{chrom_clean}[chr]+{pos}[chrpos37]",
            "retmode": "json",
            "retmax": "5",
        }
        session = _get_session()
        r = session.get(search_url, params=params, timeout=NCBI_TIMEOUT)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            params["term"] = f"{chrom_clean}[chr]+{pos}[chrpos]"
            r = session.get(search_url, params=params, timeout=NCBI_TIMEOUT)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return {}

        time.sleep(0.35)  # NCBI rate limit: pace between esearch and esummary
        sr = session.get(
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
        chrom_clean = _clean_chrom(chrom)
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
        r = _get_session().post(
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
        chrom_clean = _clean_chrom(chrom)
        # VEP region format: "{chr} {pos} . {ref} {alt} . . ."
        variant_str = f"{chrom_clean} {pos} . {ref} {alt} . . ."

        base = VEP_BASE if assembly == "GRCh38" else "https://grch37.rest.ensembl.org"
        r = _get_session().post(
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
        chrom_clean = _clean_chrom(chrom)
        url = f"{CADD_BASE}/{genome}/{chrom_clean}_{pos}_{ref}_{alt}"
        r = _get_session().get(url, timeout=CADD_TIMEOUT)
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
        r = _get_session().get(
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
        chrom_clean = _clean_chrom(chrom)
        r = _get_session().get(
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
        r = _get_session().get(
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
    if not settings.OMIM_API_KEY or not gene:
        return {}
    try:
        # Search gene → MIM number
        r = _get_session().get(
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
    if not settings.ORPHANET_API_KEY or not gene:
        return {}
    try:
        r = _get_session().get(
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


# ── MyVariant.info ─────────────────────────────────────────────────────────────

def query_myvariant(chrom: str, pos: int | str, ref: str, alt: str) -> dict[str, Any]:
    """
    Return {revel, metalr, metasvm, mutation_taster_pred, mutation_taster_score,
            gerp_rs, phylop} from MyVariant.info (free, no key).
    Aggregates dbNSFP scores including REVEL, MetaLR, MetaSVM, MutationTaster, GERP++, PhyloP.
    """
    try:
        chrom_clean = _clean_chrom(chrom)
        # HGVS ID for SNVs: chrN:g.POSREF>ALT
        hgvs_id = f"chr{chrom_clean}:g.{pos}{ref}>{alt}"
        fields = "dbnsfp.revel,dbnsfp.metalr,dbnsfp.metasvm,dbnsfp.mutationtaster,cadd.gerp,cadd.phylop"
        r = _get_session().get(
            f"{MYVARIANT_BASE}/variant/{hgvs_id}",
            params={"fields": fields},
            timeout=MYVARIANT_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            return {}

        dbnsfp = data.get("dbnsfp") or {}
        cadd   = data.get("cadd") or {}

        def _first(val: Any) -> Any:
            """Take first element if list."""
            return val[0] if isinstance(val, list) else val

        revel = _first(
            (dbnsfp.get("revel") or {}).get("score")
            if isinstance(dbnsfp.get("revel"), dict)
            else dbnsfp.get("revel")
        )

        metalr = _first(
            (dbnsfp.get("metalr") or {}).get("score")
            if isinstance(dbnsfp.get("metalr"), dict)
            else dbnsfp.get("metalr")
        )

        metasvm = _first(
            (dbnsfp.get("metasvm") or {}).get("score")
            if isinstance(dbnsfp.get("metasvm"), dict)
            else dbnsfp.get("metasvm")
        )

        mt = dbnsfp.get("mutationtaster") or {}
        mt_pred  = _first(mt.get("pred"))  if isinstance(mt, dict) else ""
        mt_score = _first(mt.get("score")) if isinstance(mt, dict) else None

        gerp_rs  = (cadd.get("gerp") or {}).get("rs") if isinstance(cadd.get("gerp"), dict) else cadd.get("gerp")
        phylop   = cadd.get("phylop")

        return {
            "revel":                 revel,
            "metalr":                metalr,
            "metasvm":               metasvm,
            "mutation_taster_pred":  mt_pred  or "",
            "mutation_taster_score": mt_score,
            "gerp_rs":               gerp_rs,
            "phylop":                phylop,
        }
    except Exception as exc:
        logger.debug("MyVariant query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── SpliceAI ───────────────────────────────────────────────────────────────────

def query_spliceai(chrom: str, pos: int | str, ref: str, alt: str, hg: str = "38") -> dict[str, Any]:
    """
    Return {spliceai_ds_max, spliceai_ds_ag, spliceai_ds_al, spliceai_ds_dg, spliceai_ds_dl}
    from the Broad Institute SpliceAI lookup (free, no key).
    spliceai_ds_max >= 0.2 is considered a meaningful splice effect.
    """
    try:
        chrom_clean = _clean_chrom(chrom)
        variant = f"chr{chrom_clean}-{pos}-{ref}-{alt}"
        r = _get_session().get(
            f"{SPLICEAI_BASE}/spliceai/",
            params={"hg": hg, "variant": variant},
            timeout=SPLICEAI_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        scores = data.get("scores") or {}
        if not scores:
            return {}

        ds_ag = scores.get("ds_ag") or scores.get("DS_AG", 0.0)
        ds_al = scores.get("ds_al") or scores.get("DS_AL", 0.0)
        ds_dg = scores.get("ds_dg") or scores.get("DS_DG", 0.0)
        ds_dl = scores.get("ds_dl") or scores.get("DS_DL", 0.0)

        return {
            "spliceai_ds_max": max(ds_ag, ds_al, ds_dg, ds_dl),
            "spliceai_ds_ag":  ds_ag,
            "spliceai_ds_al":  ds_al,
            "spliceai_ds_dg":  ds_dg,
            "spliceai_ds_dl":  ds_dl,
        }
    except Exception as exc:
        logger.debug("SpliceAI query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── InterVar ───────────────────────────────────────────────────────────────────

def query_intervar(chrom: str, pos: int | str, ref: str, alt: str, build: str = "hg38") -> dict[str, Any]:
    """
    Return {intervar_class, acmg_criteria} from WinterVar (InterVar web API, free).
    Applies ACMG/AMP 2015 guidelines automatically.
    acmg_criteria: list of met criteria e.g. ['PM2', 'PP3']
    """
    try:
        chrom_clean = _clean_chrom(chrom)
        r = _get_session().get(
            f"{INTERVAR_BASE}/api2.php",
            params={
                "queryType": "position",
                "chr":       chrom_clean,
                "pos":       str(pos),
                "ref":       ref,
                "alt":       alt,
                "build":     build,
            },
            timeout=INTERVAR_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        intervar_class = data.get("intervar") or data.get("Intervar") or ""

        # Collect met ACMG criteria (value == 1 means met)
        criteria_keys = [
            "PVS1",
            "PS1", "PS2", "PS3", "PS4",
            "PM1", "PM2", "PM3", "PM4", "PM5", "PM6",
            "PP1", "PP2", "PP3", "PP4", "PP5",
            "BA1",
            "BS1", "BS2", "BS3", "BS4",
            "BP1", "BP2", "BP3", "BP4", "BP5", "BP6", "BP7",
        ]
        met = [k for k in criteria_keys if data.get(k) == 1 or data.get(k.lower()) == 1]

        return {
            "intervar_class": intervar_class,
            "acmg_criteria":  met,
        }
    except Exception as exc:
        logger.debug("InterVar query failed for %s:%s %s>%s: %s", chrom, pos, ref, alt, exc)
        return {}


# ── ClinGen ────────────────────────────────────────────────────────────────────

def query_clingen(gene: str) -> dict[str, Any]:
    """
    Return {clingen_classifications: [{disease, moi, classification, url}]}
    from ClinGen Evidence Repository (free, no key).
    Classification strength: Definitive > Strong > Moderate > Limited > No Known Disease.
    """
    if not gene:
        return {}
    try:
        r = _get_session().get(
            f"{CLINGEN_EREPO_BASE}/classifications",
            params={"gene_symbol": gene, "limit": 10},
            headers={"Accept": "application/json"},
            timeout=CLINGEN_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", []) or data.get("results", [])

        results = []
        for item in items[:5]:
            disease = (
                (item.get("disease") or {}).get("label", "")
                if isinstance(item.get("disease"), dict)
                else str(item.get("disease", ""))
            )
            moi = (
                (item.get("modeOfInheritance") or {}).get("label", "")
                if isinstance(item.get("modeOfInheritance"), dict)
                else str(item.get("modeOfInheritance", ""))
            )
            classification = (
                (item.get("classification") or {}).get("label", "")
                if isinstance(item.get("classification"), dict)
                else str(item.get("classification", ""))
            )
            if disease or classification:
                results.append({"disease": disease, "moi": moi, "classification": classification})

        return {"clingen_classifications": results} if results else {}
    except Exception as exc:
        logger.debug("ClinGen query failed for gene %s: %s", gene, exc)
        return {}


# ── LOVD ───────────────────────────────────────────────────────────────────────

def query_lovd(gene: str) -> dict[str, Any]:
    """
    Return {lovd_variant_count, lovd_pathogenic_count} from LOVD (free, no key).
    LOVD (Leiden Open Variation Database) hosts locus-specific variant databases.
    """
    if not gene:
        return {}
    try:
        r = _get_session().get(
            f"{LOVD_BASE}/variants/{gene}",
            params={"format": "application/json", "limit": "0"},
            headers={"Accept": "application/json"},
            timeout=LOVD_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        total = data.get("total") or data.get("n_total") or 0
        # Try to count pathogenic from entries if available
        entries = data.get("data") or data.get("variants") or []
        pathogenic = sum(
            1 for e in entries
            if isinstance(e, dict) and "pathogenic" in str(e.get("classification", "") or e.get("effect", "")).lower()
        )

        return {
            "lovd_variant_count":    int(total),
            "lovd_pathogenic_count": pathogenic,
        }
    except Exception as exc:
        logger.debug("LOVD query failed for gene %s: %s", gene, exc)
        return {}


# ── HGNC ───────────────────────────────────────────────────────────────────────

def query_hgnc(gene: str) -> dict[str, Any]:
    """
    Return {hgnc_id, locus_group, locus_type, entrez_id, ensembl_id, gene_family}
    from HGNC (HUGO Gene Nomenclature Committee, free, no key).
    """
    if not gene:
        return {}
    try:
        r = _get_session().get(
            f"{HGNC_BASE}/fetch/symbol/{gene}",
            headers={"Accept": "application/json"},
            timeout=HGNC_TIMEOUT,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        if not docs:
            return {}
        doc = docs[0]
        families = doc.get("gene_family") or []
        return {
            "hgnc_id":     doc.get("hgnc_id", ""),
            "locus_group": doc.get("locus_group", ""),
            "locus_type":  doc.get("locus_type", ""),
            "entrez_id":   doc.get("entrez_id", ""),
            "ensembl_id":  doc.get("ensembl_gene_id", ""),
            "gene_family": families[0] if families else "",
        }
    except Exception as exc:
        logger.debug("HGNC query failed for gene %s: %s", gene, exc)
        return {}


# ── GenCC ──────────────────────────────────────────────────────────────────────

def query_gencc(gene: str) -> dict[str, Any]:
    """
    Return {gencc_diseases: [{disease, classification, submitter}]}
    from GenCC (aggregates ClinGen, OMIM, Orphanet, PanelApp — free, no key).
    """
    if not gene:
        return {}
    try:
        r = _get_session().get(
            f"{GENCC_BASE}/classifications-search",
            params={"gene_symbol": gene},
            headers={"Accept": "application/json"},
            timeout=GENCC_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("data", []) or data.get("classifications", []) or (data if isinstance(data, list) else [])

        results = []
        for item in items[:8]:
            disease        = (item.get("disease") or {}).get("title", "") if isinstance(item.get("disease"), dict) else str(item.get("disease_title", "") or item.get("disease", ""))
            classification = (item.get("classification") or {}).get("title", "") if isinstance(item.get("classification"), dict) else str(item.get("classification_title", "") or item.get("classification", ""))
            submitter      = (item.get("submitter") or {}).get("title", "") if isinstance(item.get("submitter"), dict) else str(item.get("submitter_title", "") or item.get("submitter", ""))
            if disease or classification:
                results.append({"disease": disease, "classification": classification, "submitter": submitter})

        return {"gencc_diseases": results} if results else {}
    except Exception as exc:
        logger.debug("GenCC query failed for gene %s: %s", gene, exc)
        return {}


# ── HPO / Ensembl phenotype ────────────────────────────────────────────────────

def query_hpo(gene: str) -> dict[str, Any]:
    """
    Return {hpo_terms: [{term, description, source}]} via Ensembl phenotype/gene endpoint.
    Includes HPO, OMIM, and Orphanet phenotype terms associated with the gene.
    """
    if not gene:
        return {}
    try:
        r = _get_session().get(
            f"{VEP_BASE}/phenotype/gene/homo_sapiens/{gene}",
            params={"include_associated": "1"},
            headers={"Accept": "application/json"},
            timeout=ENSEMBL_PHENOTYPE_TIMEOUT,
        )
        r.raise_for_status()
        entries = r.json()
        if not isinstance(entries, list):
            return {}

        # Collect HPO / phenotype terms (deduplicated)
        seen: set[str] = set()
        terms = []
        for e in entries:
            desc = e.get("description") or e.get("trait") or ""
            source = e.get("source") or ""
            if desc and desc not in seen:
                seen.add(desc)
                terms.append({"term": desc, "source": source})
            if len(terms) >= 10:
                break

        return {"hpo_terms": terms} if terms else {}
    except Exception as exc:
        logger.debug("HPO/Ensembl phenotype query failed for gene %s: %s", gene, exc)
        return {}

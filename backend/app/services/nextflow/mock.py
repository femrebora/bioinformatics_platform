"""Mock Nextflow runner.

Simulates pipeline execution and returns realistic mock results for
each supported nf-core pipeline.  The per-pipeline result shapes match
the frontend ``ResultsPanel`` renderers:

* rnaseq   → ``type="table"``  (DESeq2-style DE results)
* sarek    → ``type="vcf"``    (germline SNP/indel calls)
* atacseq  → ``type="files"``  (peak + bigWig files)
* chipseq  → ``type="files"``  (peak + bigWig files)
* methylseq→ ``type="files"``  (bismark coverage files)
* ampliseq → ``type="table"``  (taxonomy counts)
* fetchngs → ``type="files"``  (downloaded FASTQ + samplesheet)
* default  → ``type="files"``  (generic output directory listing)
"""
import hashlib
import random
import time

from app.services.nextflow.base import NextflowRunner

TIER_INSTANCE_MAP = {
    "small":  "t3.small",
    "medium": "t3.medium",
    "large":  "c5.2xlarge",
}

# ── Mock data pools ───────────────────────────────────────────────────────

_HUMAN_GENES = [
    ("ENSG00000141736", "ERBB2"),
    ("ENSG00000012048", "BRCA1"),
    ("ENSG00000139618", "BRCA2"),
    ("ENSG00000141510", "TP53"),
    ("ENSG00000146648", "EGFR"),
    ("ENSG00000136997", "MYC"),
    ("ENSG00000105173", "CCNE1"),
    ("ENSG00000170280", "CDK6"),
    ("ENSG00000196549", "MME"),
    ("ENSG00000111276", "CDKN1B"),
    ("ENSG00000197386", "HTT"),
    ("ENSG00000110092", "CCND1"),
    ("ENSG00000168036", "CTNNB1"),
    ("ENSG00000012048", "AKT1"),
    ("ENSG00000177885", "VEGFA"),
    ("ENSG00000136244", "IL6"),
    ("ENSG00000232810", "TNF"),
    ("ENSG00000075624", "ACTB"),
    ("ENSG00000111640", "GAPDH"),
    ("ENSG00000026508", "CD44"),
    ("ENSG00000153563", "CD8A"),
    ("ENSG00000049768", "FOXP3"),
    ("ENSG00000188389", "PDCD1"),
    ("ENSG00000120217", "CD274"),
    ("ENSG00000163599", "CTLA4"),
    ("ENSG00000168610", "STAT3"),
    ("ENSG00000142208", "AKT1"),
    ("ENSG00000100030", "MAPK1"),
    ("ENSG00000197728", "RPS26"),
    ("ENSG00000116670", "RAD51"),
]

_TAXA = [
    ("Bacteroidetes", "Bacteroidia", "Bacteroidales", "Bacteroidaceae", "Bacteroides"),
    ("Firmicutes",    "Clostridia",  "Clostridiales",  "Lachnospiraceae","Blautia"),
    ("Proteobacteria","Gammaproteobacteria","Enterobacterales","Enterobacteriaceae","Escherichia"),
    ("Firmicutes",    "Bacilli",     "Lactobacillales", "Lactobacillaceae","Lactobacillus"),
    ("Actinobacteria","Actinomycetia","Bifidobacteriales","Bifidobacteriaceae","Bifidobacterium"),
    ("Verrucomicrobia","Verrucomicrobiae","Verrucomicrobiales","Akkermansiaceae","Akkermansia"),
    ("Firmicutes",    "Clostridia",  "Clostridiales",  "Ruminococcaceae","Ruminococcus"),
    ("Proteobacteria","Betaproteobacteria","Burkholderiales","Comamonadaceae","Comamonas"),
]


def _seed(storage_key: str) -> random.Random:
    digest = hashlib.md5(storage_key.encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


# ── Per-pipeline mock generators ─────────────────────────────────────────


def _mock_rnaseq(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """DESeq2-style differential expression table."""
    genes = rng.sample(_HUMAN_GENES, min(20, len(_HUMAN_GENES)))
    rows = []
    for gene_id, gene_name in genes:
        base_mean  = round(rng.uniform(10, 5000), 2)
        lfc        = round(rng.uniform(-4.0, 4.0), 4)
        lfc_se     = round(rng.uniform(0.1, 0.8), 4)
        stat       = round(lfc / lfc_se, 4)
        pval       = round(rng.uniform(1e-10, 0.99), 6)
        padj       = round(min(pval * rng.uniform(1, 20), 1.0), 6)
        rows.append({
            "gene_id":        gene_id,
            "gene_name":      gene_name,
            "baseMean":       base_mean,
            "log2FoldChange": lfc,
            "lfcSE":          lfc_se,
            "stat":           stat,
            "pvalue":         pval,
            "padj":           padj,
        })
    # Sort by padj (most significant first)
    rows.sort(key=lambda r: float(r["padj"]))
    return {
        "type":    "table",
        "columns": ["gene_id", "gene_name", "baseMean",
                    "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"],
        "rows":    rows,
        "instance_type":    instance_type,
        "runtime_seconds":  runtime,
    }


def _mock_sarek(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """Germline variant calls (SNPs and small indels)."""
    chroms = ["chr1", "chr3", "chr7", "chr11", "chr17", "chr22", "chrX"]
    bases  = ["A", "C", "G", "T"]
    filter_vals = ["PASS", "PASS", "PASS", "LowQual", "SnpCluster"]
    variants = []
    for _ in range(rng.randint(8, 18)):
        ref = rng.choice(bases)
        alt_choices = [b for b in bases if b != ref] + [
            ref + rng.choice(bases),         # insertion
            ref[0] if len(ref) > 1 else ".",  # deletion
        ]
        alt = rng.choice(alt_choices[:4])
        dp  = rng.randint(15, 200)
        gq  = rng.randint(20, 99)
        variants.append({
            "chrom":  rng.choice(chroms),
            "pos":    rng.randint(100_000, 250_000_000),
            "id":     ".",
            "ref":    ref,
            "alt":    alt,
            "qual":   round(rng.uniform(30, 600), 1),
            "filter": rng.choice(filter_vals),
            "info":   f"DP={dp};GQ={gq}",
        })
    variants.sort(key=lambda v: (v["chrom"], v["pos"]))
    return {
        "type":     "vcf",
        "variants": variants,
        "instance_type":   instance_type,
        "runtime_seconds": runtime,
    }


def _mock_atacseq(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """ATAC-seq peak files + QC."""
    sample = f"SAMPLE{rng.randint(1, 9)}"
    files = [
        {"name": f"{sample}.macs3_peaks.narrowPeak",    "path": f"results/peak_calling/{sample}.narrowPeak",    "size_bytes": rng.randint(50_000, 500_000),  "mime_type": "text/plain",       "description": "MACS3 narrow peaks"},
        {"name": f"{sample}.bigWig",                     "path": f"results/bigwig/{sample}.bigWig",              "size_bytes": rng.randint(5_000_000, 50_000_000), "mime_type": "application/octet-stream", "description": "ATAC-seq signal track"},
        {"name": f"{sample}.filtered.bam",               "path": f"results/bwa/mergedLibrary/{sample}.bam",      "size_bytes": rng.randint(200_000_000, 2_000_000_000), "mime_type": "application/octet-stream", "description": "Filtered alignment (BAM)"},
        {"name": "multiqc_report.html",                  "path": "results/multiqc/multiqc_report.html",          "size_bytes": rng.randint(2_000_000, 8_000_000),  "mime_type": "text/html",       "description": "MultiQC quality report"},
        {"name": "multiqc_data.json",                    "path": "results/multiqc/multiqc_data.json",            "size_bytes": rng.randint(100_000, 500_000),  "mime_type": "application/json", "description": "MultiQC raw data"},
        {"name": "frip_score.txt",                       "path": f"results/peak_calling/{sample}_frip.txt",      "size_bytes": 128,                               "mime_type": "text/plain",       "description": "Fraction of reads in peaks"},
    ]
    return {"type": "files", "files": files, "instance_type": instance_type, "runtime_seconds": runtime}


def _mock_chipseq(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """ChIP-seq peak files + QC."""
    antibody = rng.choice(["H3K27AC", "H3K4ME3", "H3K27ME3", "H3K9ME2"])
    sample   = f"IP_{antibody}"
    files = [
        {"name": f"{sample}.macs3_peaks.broadPeak",   "path": f"results/peak_calling/{sample}.broadPeak",     "size_bytes": rng.randint(30_000, 300_000),   "mime_type": "text/plain",           "description": f"{antibody} broad peaks"},
        {"name": f"{sample}.bigWig",                   "path": f"results/bigwig/{sample}.bigWig",              "size_bytes": rng.randint(5_000_000, 40_000_000), "mime_type": "application/octet-stream", "description": "ChIP-seq signal track"},
        {"name": f"{sample}.filtered.bam",             "path": f"results/bowtie2/{sample}.bam",               "size_bytes": rng.randint(100_000_000, 1_500_000_000), "mime_type": "application/octet-stream", "description": "Filtered alignment"},
        {"name": "multiqc_report.html",                "path": "results/multiqc/multiqc_report.html",          "size_bytes": rng.randint(2_000_000, 8_000_000),  "mime_type": "text/html",           "description": "MultiQC quality report"},
        {"name": "consensus_peaks.bed",                "path": "results/consensus_peaks/consensus_peaks.bed",  "size_bytes": rng.randint(10_000, 100_000),   "mime_type": "text/plain",           "description": "Consensus peak set across replicates"},
    ]
    return {"type": "files", "files": files, "instance_type": instance_type, "runtime_seconds": runtime}


def _mock_methylseq(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """Bisulfite sequencing coverage files."""
    sample = f"SAMPLE{rng.randint(1, 9)}"
    pct_meth = round(rng.uniform(55, 85), 1)
    files = [
        {"name": f"{sample}_bismark_bt2.deduplicated.bismark.cov.gz",
         "path": f"results/bismark/{sample}.cov.gz",
         "size_bytes": rng.randint(1_000_000, 20_000_000),
         "mime_type": "application/gzip", "description": "Bismark CpG coverage file"},
        {"name": f"{sample}.CpG_report.txt.gz",
         "path": f"results/bismark/{sample}.CpG_report.txt.gz",
         "size_bytes": rng.randint(50_000_000, 200_000_000),
         "mime_type": "application/gzip", "description": "Full CpG methylation report"},
        {"name": f"{sample}_bismark_bt2.deduplicated.bam",
         "path": f"results/bismark/{sample}.bam",
         "size_bytes": rng.randint(500_000_000, 5_000_000_000),
         "mime_type": "application/octet-stream", "description": "Deduplicated alignment (BAM)"},
        {"name": "multiqc_report.html",
         "path": "results/multiqc/multiqc_report.html",
         "size_bytes": rng.randint(2_000_000, 7_000_000),
         "mime_type": "text/html", "description": "MultiQC report"},
        {"name": "methylation_summary.txt",
         "path": "results/summary/methylation_summary.txt",
         "size_bytes": 512,
         "mime_type": "text/plain",
         "description": f"Global CpG methylation rate: {pct_meth}%"},
    ]
    return {"type": "files", "files": files, "instance_type": instance_type, "runtime_seconds": runtime}


def _mock_ampliseq(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """16S amplicon taxonomy counts table."""
    taxa_sample = rng.sample(_TAXA, min(8, len(_TAXA)))
    rows = []
    total_reads = rng.randint(50_000, 200_000)
    for phylum, cls, order, family, genus in taxa_sample:
        species  = f"{genus[0].lower()}. {rng.choice(['muciniphila','fragilis','thetaiotaomicron','breve','longum','reuteri','gnavus'])}"
        count    = rng.randint(100, total_reads // 3)
        rel_abun = round(count / total_reads * 100, 2)
        rows.append({
            "phylum":           phylum,
            "class":            cls,
            "order":            order,
            "family":           family,
            "genus":            genus,
            "species":          species,
            "read_count":       count,
            "relative_abundance": rel_abun,
        })
    rows.sort(key=lambda r: -r["read_count"])  # type: ignore[arg-type]
    return {
        "type":    "table",
        "columns": ["phylum", "class", "order", "family", "genus",
                    "species", "read_count", "relative_abundance"],
        "rows":    rows,
        "instance_type":   instance_type,
        "runtime_seconds": runtime,
    }


def _mock_fetchngs(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """Downloaded FASTQ files and samplesheet."""
    n_samples = rng.randint(2, 6)
    files = []
    for i in range(1, n_samples + 1):
        srr = f"SRR{rng.randint(10_000_000, 99_999_999)}"
        files += [
            {"name": f"{srr}_1.fastq.gz",
             "path": f"results/fastq/{srr}_1.fastq.gz",
             "size_bytes": rng.randint(200_000_000, 2_000_000_000),
             "mime_type": "application/gzip", "description": f"{srr} read 1"},
            {"name": f"{srr}_2.fastq.gz",
             "path": f"results/fastq/{srr}_2.fastq.gz",
             "size_bytes": rng.randint(200_000_000, 2_000_000_000),
             "mime_type": "application/gzip", "description": f"{srr} read 2"},
        ]
    files.append({
        "name": "samplesheet.csv",
        "path": "results/samplesheet.csv",
        "size_bytes": 256 * n_samples,
        "mime_type": "text/csv",
        "description": "Auto-generated nf-core samplesheet",
    })
    return {"type": "files", "files": files, "instance_type": instance_type, "runtime_seconds": runtime}


def _mock_default(rng: random.Random, instance_type: str, runtime: int) -> dict:
    """Generic output directory listing."""
    files = [
        {"name": "pipeline_info/execution_report.html",
         "path": "results/pipeline_info/execution_report.html",
         "size_bytes": rng.randint(500_000, 3_000_000),
         "mime_type": "text/html", "description": "Nextflow execution report"},
        {"name": "pipeline_info/execution_trace.txt",
         "path": "results/pipeline_info/execution_trace.txt",
         "size_bytes": rng.randint(10_000, 100_000),
         "mime_type": "text/plain", "description": "Per-process timing trace"},
        {"name": "multiqc/multiqc_report.html",
         "path": "results/multiqc/multiqc_report.html",
         "size_bytes": rng.randint(1_000_000, 5_000_000),
         "mime_type": "text/html", "description": "MultiQC quality report"},
        {"name": "output.tar.gz",
         "path": "results/output.tar.gz",
         "size_bytes": rng.randint(100_000_000, 2_000_000_000),
         "mime_type": "application/gzip", "description": "All output files (compressed)"},
    ]
    return {"type": "files", "files": files, "instance_type": instance_type, "runtime_seconds": runtime}


_MOCK_GENERATORS = {
    "rnaseq":    _mock_rnaseq,
    "sarek":     _mock_sarek,
    "atacseq":   _mock_atacseq,
    "chipseq":   _mock_chipseq,
    "methylseq": _mock_methylseq,
    "ampliseq":  _mock_ampliseq,
    "fetchngs":  _mock_fetchngs,
}


# ── Runner class ──────────────────────────────────────────────────────────


class MockNextflowRunner(NextflowRunner):
    """Simulates an nf-core pipeline run with a realistic delay and
    deterministic (but randomised) mock result data."""

    def run(self, pipeline_id: str, storage_key: str, file_type: str) -> dict:
        start = time.time()

        # Simulate pipeline execution time (longer than HLA mock)
        delay = random.uniform(5.0, 12.0)
        time.sleep(delay)
        runtime = int(time.time() - start)

        pid        = pipeline_id.lower().removeprefix("nf-core/")
        rng        = _seed(storage_key)
        tier_guess = "medium"
        instance   = TIER_INSTANCE_MAP.get(tier_guess, "t3.medium")

        generator = _MOCK_GENERATORS.get(pid, _mock_default)
        result    = generator(rng, instance, runtime)
        return result

"""Mock custom pipeline runner — deterministic per-tool fake outputs."""
import hashlib
import random
import time
from typing import Optional

from app.services.custom.base import CustomPipelineRunner


def _rng(key: str) -> random.Random:
    digest = hashlib.md5(key.encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


def _size(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


_MOCK_FILES: dict[str, list[dict]] = {
    "spades": [
        {"name": "contigs.fasta",        "ext": "fasta", "lo": 500_000,  "hi": 5_000_000,   "desc": "SPAdes assembled contigs"},
        {"name": "scaffolds.fasta",       "ext": "fasta", "lo": 400_000,  "hi": 4_000_000,   "desc": "SPAdes scaffolds"},
        {"name": "assembly_graph.fastg",  "ext": "fastg", "lo": 50_000,   "hi": 500_000,     "desc": "Assembly graph (Bandage-compatible)"},
        {"name": "quast_report.html",     "ext": "html",  "lo": 200_000,  "hi": 600_000,     "desc": "QUAST assembly QC report"},
        {"name": "assembly_stats.txt",    "ext": "txt",   "lo": 1_000,    "hi": 5_000,       "desc": "Assembly statistics summary"},
    ],
    "kraken2": [
        {"name": "taxonomy_report.tsv",   "ext": "tsv",   "lo": 10_000,   "hi": 200_000,     "desc": "Kraken2 taxonomy classification"},
        {"name": "bracken_report.tsv",    "ext": "tsv",   "lo": 5_000,    "hi": 50_000,      "desc": "Bracken species abundance estimates"},
        {"name": "krona.html",            "ext": "html",  "lo": 100_000,  "hi": 500_000,     "desc": "Krona interactive taxonomy chart"},
        {"name": "classified.fastq.gz",   "ext": "gz",    "lo": 50_000_000, "hi": 200_000_000, "desc": "Classified reads"},
        {"name": "unclassified.fastq.gz", "ext": "gz",    "lo": 10_000_000, "hi": 80_000_000,  "desc": "Unclassified reads"},
    ],
    "prokka": [
        {"name": "genome.gff",    "ext": "gff",  "lo": 1_000_000, "hi": 10_000_000, "desc": "GFF3 gene annotation"},
        {"name": "genome.gbk",    "ext": "gbk",  "lo": 2_000_000, "hi": 15_000_000, "desc": "GenBank format annotation"},
        {"name": "proteins.faa",  "ext": "faa",  "lo": 500_000,   "hi": 3_000_000,  "desc": "Predicted protein sequences (FASTA)"},
        {"name": "genes.ffn",     "ext": "ffn",  "lo": 800_000,   "hi": 5_000_000,  "desc": "Nucleotide gene sequences (FASTA)"},
        {"name": "prokka.log",    "ext": "log",  "lo": 10_000,    "hi": 50_000,     "desc": "Prokka run log"},
        {"name": "stats.txt",     "ext": "txt",  "lo": 500,       "hi": 2_000,      "desc": "Annotation statistics"},
    ],
    "iqtree": [
        {"name": "aligned.fasta",    "ext": "fasta", "lo": 100_000, "hi": 2_000_000, "desc": "MAFFT multiple sequence alignment"},
        {"name": "tree.nwk",         "ext": "nwk",   "lo": 1_000,   "hi": 20_000,   "desc": "Maximum-likelihood tree (Newick)"},
        {"name": "tree.nwk.svg",     "ext": "svg",   "lo": 10_000,  "hi": 100_000,  "desc": "Tree visualisation (SVG)"},
        {"name": "iqtree.iqtree",    "ext": "txt",   "lo": 50_000,  "hi": 200_000,  "desc": "IQ-TREE full log + model info"},
        {"name": "iqtree.log",       "ext": "log",   "lo": 5_000,   "hi": 30_000,   "desc": "IQ-TREE progress log"},
    ],
    "flye": [
        {"name": "assembly.fasta",    "ext": "fasta", "lo": 2_000_000, "hi": 50_000_000, "desc": "Flye assembled genome"},
        {"name": "assembly_info.txt", "ext": "txt",   "lo": 2_000,     "hi": 10_000,     "desc": "Contig length / coverage table"},
        {"name": "assembly_graph.gfa","ext": "gfa",   "lo": 1_000_000, "hi": 20_000_000, "desc": "Assembly graph (Bandage-compatible)"},
        {"name": "nanostat.txt",      "ext": "txt",   "lo": 3_000,     "hi": 10_000,     "desc": "NanoStat read QC summary"},
        {"name": "flye.log",          "ext": "log",   "lo": 20_000,    "hi": 100_000,    "desc": "Flye run log"},
    ],
}

_MIME: dict[str, str] = {
    "fasta": "text/plain",
    "fastg": "text/plain",
    "gfa":   "text/plain",
    "html":  "text/html",
    "tsv":   "text/tab-separated-values",
    "txt":   "text/plain",
    "log":   "text/plain",
    "gz":    "application/gzip",
    "gff":   "text/plain",
    "gbk":   "text/plain",
    "faa":   "text/plain",
    "ffn":   "text/plain",
    "nwk":   "text/plain",
    "svg":   "image/svg+xml",
}


class MockCustomRunner(CustomPipelineRunner):
    def run(
        self,
        tool: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        storage_key_r2: Optional[str] = None,
    ) -> dict:
        rng = _rng(storage_key + tool)
        delay = rng.uniform(5.0, 14.0)
        start = time.time()
        time.sleep(delay)
        runtime = int(time.time() - start)

        specs = _MOCK_FILES.get(tool, _MOCK_FILES["spades"])
        prefix = f"custom-output/{job_id or 'job'}/"

        files = [
            {
                "name": s["name"],
                "path": f"s3://mock-bucket/{prefix}{s['name']}",
                "size_bytes": _size(rng, s["lo"], s["hi"]),
                "mime_type": _MIME.get(s["ext"], "application/octet-stream"),
                "description": s["desc"],
            }
            for s in specs
        ]

        return {
            "type": "files",
            "files": files,
            "instance_type": "t3.xlarge",
            "runtime_seconds": runtime,
            "_mock": True,
        }

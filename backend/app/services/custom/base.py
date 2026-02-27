"""
Custom Linux Pipeline runners.

Supported tools (not available as nf-core pipelines or Snakemake wrappers):
  spades   — De Novo Assembly (SPAdes + QUAST)
  kraken2  — Metagenome Profiling (Kraken2 + Bracken)
  prokka   — Prokaryote Annotation (Prokka)
  iqtree   — Phylogenomics (MAFFT + IQ-TREE 2)
  flye     — Long-read Assembly (Flye + NanoStat)
"""
from abc import ABC, abstractmethod
from typing import Optional


TOOL_METADATA: dict[str, dict] = {
    "spades": {
        "name": "De Novo Assembly",
        "description": "SPAdes genome assembler + QUAST quality assessment",
        "input_label": "FASTQ reads (short-read, paired or single)",
        "output_labels": ["contigs.fasta", "scaffolds.fasta", "quast_report.html", "assembly_stats.txt"],
    },
    "kraken2": {
        "name": "Metagenome Profiling",
        "description": "Kraken2 taxonomic classification + Bracken abundance estimation",
        "input_label": "FASTQ reads",
        "output_labels": ["taxonomy_report.tsv", "bracken_report.tsv", "krona.html"],
    },
    "prokka": {
        "name": "Prokaryote Annotation",
        "description": "Prokka rapid prokaryotic genome annotation",
        "input_label": "FASTA assembly (contigs / scaffolds)",
        "output_labels": ["genome.gff", "genome.gbk", "proteins.faa", "genes.ffn", "prokka.log"],
    },
    "iqtree": {
        "name": "Phylogenomics",
        "description": "MAFFT multiple alignment + IQ-TREE 2 maximum-likelihood tree",
        "input_label": "Multi-FASTA sequences",
        "output_labels": ["aligned.fasta", "tree.nwk", "iqtree.log"],
    },
    "flye": {
        "name": "Long-read Assembly",
        "description": "Flye assembler (Nanopore / PacBio) + NanoStat QC",
        "input_label": "Long reads FASTQ (Nanopore or PacBio)",
        "output_labels": ["assembly.fasta", "assembly_info.txt", "nanostat.txt"],
    },
}


class CustomPipelineRunner(ABC):
    @abstractmethod
    def run(
        self,
        tool: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        storage_key_r2: Optional[str] = None,
    ) -> dict:
        """Run the named custom pipeline and return a result dict."""


def get_custom_runner() -> CustomPipelineRunner:
    from app.config import settings

    backend = getattr(settings, "CUSTOM_BACKEND", "mock")
    if backend == "awsbatch":
        from app.services.custom.batch import AWSBatchCustomRunner
        return AWSBatchCustomRunner()

    from app.services.custom.mock import MockCustomRunner
    return MockCustomRunner()

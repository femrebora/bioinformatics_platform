#!/usr/bin/env bash
# bioplatform_helpers.sh — shell library pre-loaded in the BioScript Docker image.
#
# Usage in user scripts:
#   . /usr/local/lib/bio_helpers.sh
#   bioplatform_qc input.fastq.gz results/qc
#   bioplatform_align results/qc/input_trimmed.fastq.gz genome.fa results/align
#   bioplatform_call results/align/output.bam genome.fa results/variants

set -euo pipefail

# ── Logging helpers ──────────────────────────────────────────────────────────

bp_log()  { echo "[bioplatform] $(date +%T) $*" >&2; }
bp_step() { echo "[bioplatform] ── $* ──────────────────────────" >&2; }
bp_done() { echo "[bioplatform] DONE: $*" >&2; }
bp_fail() { echo "[bioplatform] FAIL: $*" >&2; exit 1; }

# ── Resource detection ───────────────────────────────────────────────────────

bp_threads() {
    # Return number of CPU threads to use (leave 1 for OS)
    local n
    n=$(nproc 2>/dev/null || echo 1)
    echo $(( n > 1 ? n - 1 : 1 ))
}

bp_mem_gb() {
    # Return ~80% of total RAM in GB (safe for tools that reserve memory)
    local total_kb
    total_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 8388608)
    echo $(( total_kb * 8 / 10 / 1048576 ))
}

# ── S3 helpers ───────────────────────────────────────────────────────────────

bp_s3_get() {
    local s3_uri=$1 local_path=$2
    bp_log "s3 get: $s3_uri → $local_path"
    mkdir -p "$(dirname "$local_path")"
    aws s3 cp "$s3_uri" "$local_path"
}

bp_s3_put() {
    local local_path=$1 s3_uri=$2
    bp_log "s3 put: $local_path → $s3_uri"
    aws s3 cp "$local_path" "$s3_uri"
}

bp_s3_sync_out() {
    local local_dir=$1 s3_prefix=$2
    bp_log "s3 sync: $local_dir → $s3_prefix"
    aws s3 sync "$local_dir" "$s3_prefix" --exclude "*.tmp"
}

# ── Quality control ──────────────────────────────────────────────────────────

# bioplatform_qc <input.fastq.gz> <outdir> [r2.fastq.gz]
bioplatform_qc() {
    local input=$1 outdir=$2 r2=${3:-}
    bp_step "QC / Adapter trimming (fastp)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    if [[ -n "$r2" ]]; then
        fastp -i "$input" -I "$r2" \
              -o "$outdir/r1_trimmed.fastq.gz" \
              -O "$outdir/r2_trimmed.fastq.gz" \
              -j "$outdir/fastp.json" \
              -h "$outdir/fastp.html" \
              --thread "$threads"
    else
        fastp -i "$input" \
              -o "$outdir/trimmed.fastq.gz" \
              -j "$outdir/fastp.json" \
              -h "$outdir/fastp.html" \
              --thread "$threads"
    fi
    bp_done "QC complete → $outdir"
}

# ── Alignment ────────────────────────────────────────────────────────────────

# bioplatform_align <reads.fastq.gz> <genome.fa> <outdir> [r2.fastq.gz]
bioplatform_align() {
    local reads=$1 genome=$2 outdir=$3 r2=${4:-}
    bp_step "Alignment (BWA-MEM2 → samtools sort)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)
    local sample="sample_$(date +%s)"

    # Index genome if not already indexed
    if [[ ! -f "${genome}.bwt" && ! -f "${genome}.0123" ]]; then
        bp_log "Indexing reference genome…"
        bwa-mem2 index "$genome" 2>/dev/null || bwa index "$genome"
    fi

    local bam_out="$outdir/aligned.bam"
    if [[ -n "$r2" ]]; then
        bwa mem -t "$threads" -R "@RG\tID:${sample}\tSM:${sample}\tPL:ILLUMINA" \
            "$genome" "$reads" "$r2" \
            | samtools sort -@ "$threads" -o "$bam_out"
    else
        bwa mem -t "$threads" -R "@RG\tID:${sample}\tSM:${sample}\tPL:ILLUMINA" \
            "$genome" "$reads" \
            | samtools sort -@ "$threads" -o "$bam_out"
    fi
    samtools index "$bam_out"
    bp_done "Alignment complete → $bam_out"
}

# ── STAR alignment (RNA-seq) ─────────────────────────────────────────────────

# bioplatform_star_align <reads.fastq.gz> <star_index_dir> <outdir> [r2.fastq.gz]
bioplatform_star_align() {
    local reads=$1 index=$2 outdir=$3 r2=${4:-}
    bp_step "Alignment (STAR)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)
    local mem_bytes; mem_bytes=$(( $(bp_mem_gb) * 1073741824 ))

    STAR \
        --runThreadN "$threads" \
        --genomeDir "$index" \
        --readFilesIn "$reads" ${r2:+"$r2"} \
        --readFilesCommand zcat \
        --outSAMtype BAM SortedByCoordinate \
        --outSAMattributes NH HI AS NM MD \
        --outFileNamePrefix "$outdir/" \
        --limitBAMsortRAM "$mem_bytes" \
        --quantMode GeneCounts

    samtools index "$outdir/Aligned.sortedByCoord.out.bam"
    bp_done "STAR alignment complete → $outdir"
}

# ── Variant calling ───────────────────────────────────────────────────────────

# bioplatform_call <input.bam> <genome.fa> <outdir>
bioplatform_call() {
    local bam=$1 genome=$2 outdir=$3
    bp_step "Variant calling (bcftools mpileup + call)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    # Index genome if needed
    [[ -f "${genome}.fai" ]] || samtools faidx "$genome"

    bcftools mpileup \
        --threads "$threads" \
        -f "$genome" \
        --output-type u \
        "$bam" \
    | bcftools call \
        --threads "$threads" \
        --multiallelic-caller \
        --variants-only \
        --output-type z \
        --output "$outdir/variants.vcf.gz"

    tabix -p vcf "$outdir/variants.vcf.gz"
    bp_done "Variant calling complete → $outdir/variants.vcf.gz"
}

# ── MultiQC aggregate report ─────────────────────────────────────────────────

# bioplatform_multiqc <results_dir> <outdir>
bioplatform_multiqc() {
    local results_dir=$1 outdir=$2
    bp_step "MultiQC aggregate report"
    mkdir -p "$outdir"
    multiqc "$results_dir" --outdir "$outdir" --filename "multiqc_report.html"
    bp_done "MultiQC report → $outdir/multiqc_report.html"
}

# ── Feature counting (RNA-seq) ────────────────────────────────────────────────

# bioplatform_featurecount <bam> <gtf> <outdir>
bioplatform_featurecount() {
    local bam=$1 gtf=$2 outdir=$3
    bp_step "Feature counting (featureCounts)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    featureCounts \
        -T "$threads" \
        -a "$gtf" \
        -o "$outdir/counts.txt" \
        "$bam"

    bp_done "Feature counts → $outdir/counts.txt"
}

# ── Custom pipeline helpers ───────────────────────────────────────────────────

# bioplatform_spades <input.fastq.gz> <outdir> [r2.fastq.gz]
#   De novo genome assembly with SPAdes + QUAST quality report.
bioplatform_spades() {
    local reads=$1 outdir=$2 r2=${3:-}
    bp_step "De novo assembly (SPAdes)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)
    local mem;    mem=$(bp_mem_gb)

    if [[ -n "$r2" ]]; then
        python3 /opt/spades/bin/spades.py \
            -1 "$reads" -2 "$r2" \
            -o "$outdir/spades" \
            -t "$threads" -m "$mem"
    else
        python3 /opt/spades/bin/spades.py \
            -s "$reads" \
            -o "$outdir/spades" \
            -t "$threads" -m "$mem"
    fi

    # QUAST quality report on the contigs
    bp_step "Assembly QC (QUAST)"
    quast.py \
        "$outdir/spades/contigs.fasta" \
        -o "$outdir/quast" \
        --threads "$threads"

    # Symlink primary outputs to outdir top-level for easy discovery
    [[ -f "$outdir/spades/contigs.fasta" ]] && \
        cp "$outdir/spades/contigs.fasta"  "$outdir/contigs.fasta"
    [[ -f "$outdir/spades/scaffolds.fasta" ]] && \
        cp "$outdir/spades/scaffolds.fasta" "$outdir/scaffolds.fasta"
    [[ -f "$outdir/quast/report.html" ]] && \
        cp "$outdir/quast/report.html" "$outdir/quast_report.html"

    bp_done "SPAdes assembly complete → $outdir"
}

# bioplatform_kraken2 <input.fastq.gz> <db_dir> <outdir>
#   Metagenomics classification with Kraken2 + Bracken abundance re-estimation.
#   DB_DIR defaults to $KRAKEN2_DB env var (must be pre-downloaded).
bioplatform_kraken2() {
    local reads=$1 db_dir=${2:-${KRAKEN2_DB:-/data/kraken2_db}} outdir=$3
    bp_step "Metagenomics classification (Kraken2)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    kraken2 \
        --db "$db_dir" \
        --threads "$threads" \
        --report "$outdir/taxonomy_report.tsv" \
        --output "$outdir/kraken2_output.txt" \
        --gzip-compressed \
        "$reads"

    bp_step "Abundance estimation (Bracken)"
    bracken \
        -d "$db_dir" \
        -i "$outdir/taxonomy_report.tsv" \
        -o "$outdir/bracken_report.tsv" \
        -l S || bp_log "Bracken skipped (DB may lack required files)"

    bp_step "Krona HTML report"
    ktImportTaxonomy \
        -t 5 -m 3 \
        "$outdir/taxonomy_report.tsv" \
        -o "$outdir/krona.html" || bp_log "KronaTools not available — skipping Krona plot"

    bp_done "Kraken2 classification complete → $outdir"
}

# bioplatform_prokka <assembly.fasta> <outdir> [prefix]
#   Prokaryote genome annotation with Prokka.
bioplatform_prokka() {
    local fasta=$1 outdir=$2 prefix=${3:-genome}
    bp_step "Prokaryote annotation (Prokka)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    prokka \
        --outdir "$outdir" \
        --prefix "$prefix" \
        --cpus "$threads" \
        --force \
        "$fasta"

    bp_done "Prokka annotation complete → $outdir"
}

# bioplatform_iqtree <sequences.fasta> <outdir>
#   Multiple sequence alignment (MAFFT) + phylogenetic tree (IQ-TREE 2).
bioplatform_iqtree() {
    local fasta=$1 outdir=$2
    bp_step "Multiple sequence alignment (MAFFT)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)

    mafft --auto --thread "$threads" "$fasta" > "$outdir/aligned.fasta"

    bp_step "Phylogenetic tree inference (IQ-TREE 2)"
    iqtree2 \
        -s "$outdir/aligned.fasta" \
        -T "$threads" \
        --prefix "$outdir/tree" \
        -B 1000 \
        --redo

    [[ -f "$outdir/tree.treefile" ]] && cp "$outdir/tree.treefile" "$outdir/tree.nwk"

    bp_done "Phylogenomics complete → $outdir"
}

# bioplatform_flye <reads.fastq.gz> <outdir> [read_type: nano-hq|nano-raw|pacbio-raw|pacbio-hifi]
#   Long-read genome assembly (Flye) + NanoStat quality report.
bioplatform_flye() {
    local reads=$1 outdir=$2 read_type=${3:-nano-hq}
    bp_step "Long-read assembly (Flye)"
    mkdir -p "$outdir"
    local threads; threads=$(bp_threads)
    local mem;    mem=$(bp_mem_gb)

    flye \
        "--${read_type}" "$reads" \
        --out-dir "$outdir/flye" \
        --threads "$threads"

    bp_step "Read QC (NanoStat)"
    NanoStat \
        --fastq "$reads" \
        --outdir "$outdir" \
        --name  nanostat.txt \
        --threads "$threads" || \
    NanoStat --fastq "$reads" > "$outdir/nanostat.txt" 2>&1 || \
        bp_log "NanoStat failed — skipping"

    [[ -f "$outdir/flye/assembly.fasta" ]] && \
        cp "$outdir/flye/assembly.fasta"      "$outdir/assembly.fasta"
    [[ -f "$outdir/flye/assembly_info.txt" ]] && \
        cp "$outdir/flye/assembly_info.txt"   "$outdir/assembly_info.txt"

    bp_done "Flye long-read assembly complete → $outdir"
}

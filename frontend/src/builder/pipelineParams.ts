/**
 * Per-pipeline parameter definitions that drive the ParameterPanel side drawer.
 * Each entry maps a nextflow --param_name to a typed UI control.
 */

export type ParamType = "select" | "boolean" | "number" | "text";

export interface PipelineParam {
  key: string;
  label: string;
  type: ParamType;
  options?: string[];
  default: unknown;
  hint?: string;
}

export const PIPELINE_PARAMS: Record<string, PipelineParam[]> = {
  rnaseq: [
    {
      key: "aligner", label: "Aligner", type: "select",
      options: ["star_salmon", "star_rsem", "hisat2"], default: "star_salmon",
      hint: "Primary alignment algorithm",
    },
    {
      key: "pseudo_aligner", label: "Pseudo-aligner", type: "select",
      options: ["", "salmon", "kallisto"], default: "",
      hint: "Run alongside main aligner for count quantification",
    },
    {
      key: "skip_trimming", label: "Skip adapter trimming", type: "boolean", default: false,
      hint: "Skip fastp / Trim Galore step",
    },
    {
      key: "skip_qc", label: "Skip QC steps", type: "boolean", default: false,
    },
    {
      key: "min_mapped_reads", label: "Min mapped reads (%)", type: "number", default: 5,
      hint: "Samples below this threshold are excluded",
    },
    {
      key: "deseq2_vst", label: "VST normalisation (DESeq2)", type: "boolean", default: false,
      hint: "Use VST instead of rlog (faster for large n)",
    },
    {
      key: "save_align_intermeds", label: "Save alignment intermediates", type: "boolean", default: false,
    },
    {
      key: "extra_star_align_args", label: "Extra STAR args", type: "text", default: "",
      hint: "e.g. --outFilterMismatchNmax 2",
    },
  ],
  sarek: [
    {
      key: "tools", label: "Variant callers", type: "text", default: "haplotypecaller",
      hint: "Comma-separated: haplotypecaller, mutect2, strelka2, deepvariant",
    },
    {
      key: "wes", label: "WES mode", type: "boolean", default: false,
      hint: "Whole-exome sequencing — requires intervals file",
    },
    {
      key: "joint_germline", label: "Joint germline calling", type: "boolean", default: false,
      hint: "Run GATK joint genotyping across all samples",
    },
    {
      key: "dbsnp", label: "dbSNP VCF (s3:// path)", type: "text", default: "",
      hint: "Known sites for BQSR — leave blank to skip",
    },
    {
      key: "intervals", label: "Target intervals BED (s3:// path)", type: "text", default: "",
      hint: "Required for WES mode",
    },
    {
      key: "skip_tools", label: "Skip steps", type: "text", default: "",
      hint: "e.g. markduplicates,baserecalibrator",
    },
    {
      key: "no_intervals", label: "No intervals (WGS no BQSR)", type: "boolean", default: false,
    },
  ],
  atacseq: [
    {
      key: "narrow_peak", label: "Narrow peaks (MACS3)", type: "boolean", default: true,
      hint: "Narrow for TF, broad for histone marks",
    },
    {
      key: "skip_qc", label: "Skip QC", type: "boolean", default: false,
    },
    {
      key: "min_trimmed_reads", label: "Min trimmed reads", type: "number", default: 10000,
    },
    {
      key: "save_align_intermeds", label: "Save alignment intermediates", type: "boolean", default: false,
    },
    {
      key: "macs_gsize", label: "MACS effective genome size", type: "text", default: "hs",
      hint: "hs = human, mm = mouse, ce = C.elegans, dm = fly",
    },
  ],
  chipseq: [
    {
      key: "narrow_peak", label: "Narrow peaks (MACS3)", type: "boolean", default: false,
      hint: "True for TF ChIP, False for histone ChIP",
    },
    {
      key: "skip_qc", label: "Skip QC", type: "boolean", default: false,
    },
    {
      key: "min_reps_consensus", label: "Min replicates for consensus", type: "number", default: 1,
    },
    {
      key: "save_align_intermeds", label: "Save alignment intermediates", type: "boolean", default: false,
    },
    {
      key: "macs_gsize", label: "MACS effective genome size", type: "text", default: "hs",
    },
  ],
  methylseq: [
    {
      key: "aligner", label: "Aligner", type: "select",
      options: ["bismark", "bwameth"], default: "bismark",
    },
    {
      key: "cytosine_context", label: "Cytosine context", type: "select",
      options: ["CpG", "CHG", "CHH", "CpHpG", "CpHpH"], default: "CpG",
    },
    {
      key: "skip_deduplication", label: "Skip deduplication", type: "boolean", default: false,
      hint: "For RRBS or amplicon data",
    },
    {
      key: "save_align_intermeds", label: "Save alignment intermediates", type: "boolean", default: false,
    },
    {
      key: "comprehensive", label: "Comprehensive report", type: "boolean", default: false,
      hint: "Extract all cytosine contexts (large output)",
    },
  ],
  ampliseq: [
    {
      key: "trunclenf", label: "DADA2 truncate forward (bp)", type: "number", default: 0,
      hint: "0 = auto-detect from quality plots",
    },
    {
      key: "trunclenr", label: "DADA2 truncate reverse (bp)", type: "number", default: 0,
      hint: "0 = auto-detect",
    },
    {
      key: "min_samples", label: "Min samples", type: "number", default: 1,
    },
    {
      key: "classifier", label: "Taxonomic classifier", type: "select",
      options: ["qiime2", "sintax", "kraken2"], default: "qiime2",
    },
    {
      key: "skip_dada2", label: "Skip DADA2", type: "boolean", default: false,
    },
  ],
  fetchngs: [
    {
      key: "nf_core_pipeline", label: "Downstream pipeline", type: "select",
      options: ["", "rnaseq", "sarek", "atacseq", "chipseq", "methylseq"], default: "",
      hint: "Auto-generate samplesheet for this pipeline",
    },
    {
      key: "force_sratools_download", label: "Force SRA tools", type: "boolean", default: false,
      hint: "Use sra-tools instead of AWS S3 (slower)",
    },
  ],
};

export const IGENOMES: { value: string; label: string; organism: string }[] = [
  { value: "GRCh38", label: "GRCh38 / hg38", organism: "Human" },
  { value: "GRCh37", label: "GRCh37 / hg19", organism: "Human" },
  { value: "GRCm39", label: "GRCm39 / mm39", organism: "Mouse" },
  { value: "GRCm38", label: "GRCm38 / mm10", organism: "Mouse" },
  { value: "BDGP6", label: "BDGP6 / dm6", organism: "Drosophila" },
  { value: "WBcel235", label: "WBcel235 / ce11", organism: "C. elegans" },
  { value: "R64-1-1", label: "R64-1-1 / sacCer3", organism: "Yeast" },
  { value: "GRCz10", label: "GRCz10 / danRer10", organism: "Zebrafish" },
  { value: "EquCab3", label: "EquCab3.0", organism: "Horse" },
  { value: "Mmul_10", label: "Mmul_10", organism: "Macaque" },
  { value: "custom", label: "Custom (FASTA + GTF)", organism: "" },
];

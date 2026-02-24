export interface NfCoreIOPort {
  name: string;
  type: string;
  description: string;
  pattern: string;
}

export interface NfCoreModule {
  id: string;           // "samtools/sort"
  tool: string;         // "samtools"
  subcommand: string | null;
  description: string | null;
  keywords: string[] | null;
  category: string;
  inputs: NfCoreIOPort[] | null;
  outputs: NfCoreIOPort[] | null;
}

export interface NfCorePipeline {
  id: string;                     // "rnaseq"
  full_name: string;              // "nf-core/rnaseq"
  description: string | null;
  topics: string[] | null;
  html_url: string;
  stars: number;
  input_formats: string[] | null; // e.g. ["bam","cram","fastq","vcf"]
}

export interface CatalogCategory {
  category: string;
  count: number;
}

export interface CatalogStatus {
  pipelines: number;
  modules: number;
  ready: boolean;
}

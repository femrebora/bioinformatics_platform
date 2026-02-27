export interface SnakemakeWrapper {
  id: string;
  tool: string;
  subcommand: string | null;
  name: string | null;
  description: string | null;
  input_names: string[] | null;
  output_names: string[] | null;
  category: string;
}

export interface SnakemakeWorkflow {
  id: string;
  name: string;
  description: string | null;
  topics: string[] | null;
  html_url: string;
  stars: number;
}

export interface SnakemakeCatalogStatus {
  wrappers: number;
  workflows: number;
  ready: boolean;
}

export interface SnakemakeCatalogCategory {
  category: string;
  count: number;
}

import axios from "axios";
import type {
  SnakemakeWrapper,
  SnakemakeWorkflow,
  SnakemakeCatalogStatus,
  SnakemakeCatalogCategory,
} from "../types/snakemake";

const http = axios.create({ baseURL: "/api/v1" });

export async function fetchWrappers(
  q?: string,
  category?: string,
  limit = 50
): Promise<SnakemakeWrapper[]> {
  const params: Record<string, string | number> = { limit };
  if (q) params.q = q;
  if (category) params.category = category;
  const { data } = await http.get<SnakemakeWrapper[]>("/snakemake/wrappers", { params });
  return data;
}

export async function fetchWrapperCategories(): Promise<SnakemakeCatalogCategory[]> {
  const { data } = await http.get<SnakemakeCatalogCategory[]>("/snakemake/wrapper-categories");
  return data;
}

export async function fetchWorkflows(
  q?: string,
  limit = 50
): Promise<SnakemakeWorkflow[]> {
  const params: Record<string, string | number> = { limit };
  if (q) params.q = q;
  const { data } = await http.get<SnakemakeWorkflow[]>("/snakemake/workflows", { params });
  return data;
}

export async function fetchSnakemakeStatus(): Promise<SnakemakeCatalogStatus> {
  const { data } = await http.get<SnakemakeCatalogStatus>("/snakemake/status");
  return data;
}

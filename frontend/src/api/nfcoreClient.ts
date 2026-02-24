import axios from "axios";
import type {
  NfCoreModule,
  NfCorePipeline,
  CatalogCategory,
  CatalogStatus,
} from "../types/nfcore";

const http = axios.create({ baseURL: "/api/v1" });

export async function fetchNfcorePipelines(q?: string): Promise<NfCorePipeline[]> {
  const { data } = await http.get<NfCorePipeline[]>("/nfcore/pipelines", {
    params: q ? { q } : undefined,
  });
  return data;
}

export async function fetchNfcoreModules(
  q?: string,
  category?: string,
  limit = 50
): Promise<NfCoreModule[]> {
  const params: Record<string, string | number> = { limit };
  if (q) params.q = q;
  if (category) params.category = category;
  const { data } = await http.get<NfCoreModule[]>("/nfcore/modules", { params });
  return data;
}

export async function fetchNfcoreCategories(): Promise<CatalogCategory[]> {
  const { data } = await http.get<CatalogCategory[]>("/nfcore/categories");
  return data;
}

export async function fetchNfcoreStatus(): Promise<CatalogStatus> {
  const { data } = await http.get<CatalogStatus>("/nfcore/status");
  return data;
}

export async function fetchPipelineModules(
  pipelineId: string
): Promise<NfCoreModule[]> {
  const { data } = await http.get<NfCoreModule[]>(
    `/nfcore/pipelines/${encodeURIComponent(pipelineId)}/modules`
  );
  return data;
}

import { useState, useCallback } from "react";
import {
  fetchNfcoreStatus,
  fetchNfcoreCategories,
  fetchNfcorePipelines,
} from "../api/nfcoreClient";
import type { NfCorePipeline, CatalogCategory, CatalogStatus } from "../types/nfcore";

export function useNfcoreModules() {
  const [status, setStatus] = useState<CatalogStatus | null>(null);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [pipelines, setPipelines] = useState<NfCorePipeline[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchCatalogMeta = useCallback(async () => {
    setLoading(true);
    try {
      const [s, cats, pipes] = await Promise.all([
        fetchNfcoreStatus(),
        fetchNfcoreCategories(),
        fetchNfcorePipelines(),
      ]);
      setStatus(s);
      setCategories(cats);
      setPipelines(pipes);
    } catch {
      // silently fail — catalog loads in background on first startup
    } finally {
      setLoading(false);
    }
  }, []);

  return { status, categories, pipelines, loading, fetchCatalogMeta };
}

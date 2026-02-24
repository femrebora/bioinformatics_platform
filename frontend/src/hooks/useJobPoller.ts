import { useEffect, useRef, useState } from "react";
import { getJob } from "../api/client";
import type { Job } from "../types/job";

const POLL_INTERVAL_MS = 2000;
const MAX_CONSECUTIVE_ERRORS = 5;

export function useJobPoller(jobId: string | null): Job | null {
  const [job, setJob] = useState<Job | null>(null);
  const errorCount = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }

    let active = true;

    async function poll() {
      if (!active) return;

      try {
        const updated = await getJob(jobId!);
        errorCount.current = 0;
        if (active) setJob(updated);

        if (updated.status === "completed" || updated.status === "failed") {
          return; // stop polling
        }
      } catch {
        errorCount.current += 1;
        if (errorCount.current >= MAX_CONSECUTIVE_ERRORS) {
          return; // give up
        }
      }

      if (active) {
        timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();

    return () => {
      active = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [jobId]);

  return job;
}

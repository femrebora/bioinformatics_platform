import { useState, useEffect } from "react";
import { UploadForm } from "./components/UploadForm";
import { TierConfirm } from "./components/TierConfirm";
import { JobProgress } from "./components/JobProgress";
import { ResultViewer } from "./components/ResultViewer";
import { ResultsPanel } from "./components/ResultsPanel";
import { JobHistory } from "./components/JobHistory";
import { AuthGate } from "./components/AuthGate";
import { PipelineBuilder } from "./builder/PipelineBuilder";
import { createJob, getSessionJob } from "./api/client";
import { getStoredToken, clearToken, getMe } from "./api/authClient";
import { useJobPoller } from "./hooks/useJobPoller";
import type { PresignResponse, Tier } from "./types/job";
import type { AuthUser } from "./types/auth";

type AppState =
  | { phase: "idle" }
  | { phase: "uploading" }
  | { phase: "confirming"; presign: PresignResponse; filename: string; fileType: string }
  | { phase: "awaiting_payment"; sessionId: string }
  | { phase: "processing"; jobId: string }
  | { phase: "done"; jobId: string }
  | { phase: "error"; message: string }
  | { phase: "builder" }
  | { phase: "history" }
  | {
      phase: "builder-confirming";
      presign: PresignResponse;
      filename: string;
      fileType: string;
      pipelineId: string | null;
      storageKeyR2: string | null;
      workflowConfig: unknown | null;
      nSamples: number;
    };

export default function App() {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [state, setState] = useState<AppState>({ phase: "builder" });
  const [panelOpen, setPanelOpen] = useState(false);

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setAuthChecked(true);
      return;
    }
    getMe(token)
      .then((user) => {
        setCurrentUser(user);
        setAuthChecked(true);
        // Check if Stripe redirected back with a session_id
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get("session_id");
        if (sessionId) {
          window.history.replaceState({}, "", "/"); // clean URL
          setState({ phase: "awaiting_payment", sessionId });
        }
      })
      .catch(() => {
        clearToken();
        setAuthChecked(true);
      });
  }, []);

  const jobId =
    state.phase === "processing" || state.phase === "done"
      ? state.jobId
      : null;

  const job = useJobPoller(jobId);

  // Transition processing → done when job completes or is cancelled
  useEffect(() => {
    if (
      state.phase === "processing" &&
      job &&
      (job.status === "completed" || job.status === "failed" || job.status === "cancelled")
    ) {
      setState({ phase: "done", jobId: state.jobId });
    }
  }, [job, state.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-open results panel when job finishes
  useEffect(() => {
    if (job?.status === "completed" || job?.status === "failed") {
      setPanelOpen(true);
    }
  }, [job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll for job after Stripe redirect
  useEffect(() => {
    if (state.phase !== "awaiting_payment") return;
    const { sessionId } = state;
    const interval = setInterval(async () => {
      try {
        const { job_id } = await getSessionJob(sessionId);
        if (job_id) {
          clearInterval(interval);
          setState({ phase: "processing", jobId: job_id });
        }
      } catch {
        // keep polling
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [state.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for ResultsNode "View Results" button click
  useEffect(() => {
    function handler() { setPanelOpen(true); }
    window.addEventListener("openResultsPanel", handler);
    return () => window.removeEventListener("openResultsPanel", handler);
  }, []);

  function handlePresigned(presign: PresignResponse, file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    const fileType = ext === "bam" ? "bam" : "fastq";
    setState({ phase: "confirming", presign, filename: file.name, fileType });
  }

  async function handleConfirm(tier: Tier, estimatedCostUsd: number) {
    if (state.phase !== "confirming") return;

    try {
      const newJob = await createJob(
        state.presign.storage_key,
        state.fileType,
        tier,
        estimatedCostUsd
      );
      setState({ phase: "processing", jobId: newJob.job_id });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create job.";
      setState({ phase: "error", message: msg });
    }
  }

  function handleBuilderRunRequested(
    presign: PresignResponse,
    filename: string,
    fileType: string,
    pipelineId: string | null,
    storageKeyR2?: string | null,
    workflowConfig?: unknown | null,
    nSamples?: number,
  ) {
    setState({
      phase: "builder-confirming",
      presign,
      filename,
      fileType,
      pipelineId,
      storageKeyR2: storageKeyR2 ?? null,
      workflowConfig: workflowConfig ?? null,
      nSamples: nSamples ?? 1,
    });
  }

  async function handleBuilderConfirm(tier: Tier, estimatedCostUsd: number) {
    if (state.phase !== "builder-confirming") return;
    try {
      const newJob = await createJob(
        state.presign.storage_key,
        state.fileType,
        tier,
        estimatedCostUsd,
        state.pipelineId,
        state.storageKeyR2,
        state.workflowConfig,
      );
      setState({ phase: "processing", jobId: newJob.job_id });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create job.";
      setState({ phase: "error", message: msg });
    }
  }

  function handleReset() {
    setState({ phase: "idle" });
  }

  function handleSignOut() {
    clearToken();
    setCurrentUser(null);
    setState({ phase: "builder" });
  }

  // Show nothing while we check the stored token
  if (!authChecked) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ color: "#64748b", fontSize: 14 }}>Loading…</span>
      </div>
    );
  }

  // Show auth wall if not signed in
  if (!currentUser) {
    return <AuthGate onAuthenticated={(token) => {
      getMe(token).then(setCurrentUser);
    }} />;
  }

  const isBuilderPhase =
    state.phase === "builder" ||
    state.phase === "builder-confirming" ||
    state.phase === "awaiting_payment";
  const isHistoryPhase = state.phase === "history";

  const confirmingState =
    state.phase === "builder-confirming"
      ? {
          presign: state.presign,
          filename: state.filename,
          pipelineId: state.pipelineId,
          storageKeyR2: state.storageKeyR2,
          workflowConfig: state.workflowConfig,
          nSamples: state.nSamples,
        }
      : null;

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <span style={styles.logo}>🧬</span>
        <span style={styles.brand}>Bioinformatics Platform</span>
        <nav style={styles.nav}>
          <button
            style={{
              ...styles.navBtn,
              ...(isBuilderPhase ? styles.navBtnActive : {}),
            }}
            onClick={() => setState({ phase: "builder" })}
          >
            Pipeline Builder
          </button>
          <button
            style={{
              ...styles.navBtn,
              ...(state.phase === "idle" || state.phase === "confirming"
                ? styles.navBtnActive
                : {}),
            }}
            onClick={() => setState({ phase: "idle" })}
          >
            Quick Run
          </button>
          <button
            style={{
              ...styles.navBtn,
              ...(isHistoryPhase ? styles.navBtnActive : {}),
            }}
            onClick={() => setState({ phase: "history" })}
          >
            History
          </button>
          {job && (job.status === "completed" || job.status === "failed") && (
            <button
              style={{ ...styles.navBtn, background: panelOpen ? "rgba(255,255,255,0.2)" : "#16a34a", borderColor: "#16a34a" }}
              onClick={() => setPanelOpen((o) => !o)}
              title="Toggle results panel"
            >
              📊 Results
            </button>
          )}
          <div style={styles.userInfo}>
            <span style={styles.userEmail}>{currentUser.email}</span>
            <button style={styles.signOutBtn} onClick={handleSignOut}>
              Sign Out
            </button>
          </div>
        </nav>
      </header>

      {isHistoryPhase ? (
        <main style={styles.main}>
          <JobHistory />
        </main>
      ) : state.phase === "awaiting_payment" ? (
        <main style={styles.main}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 36, marginBottom: 16 }}>⏳</div>
            <h2 style={{ fontWeight: 700, marginBottom: 8 }}>Confirming payment…</h2>
            <p style={{ color: "#6b7280", fontSize: 14 }}>
              Your payment was received. Starting the pipeline in a moment.
            </p>
          </div>
        </main>
      ) : isBuilderPhase ? (
        <PipelineBuilder
          onRunRequested={handleBuilderRunRequested}
          confirmingState={confirmingState}
          TierConfirmComponent={TierConfirm}
          onConfirm={handleBuilderConfirm}
          onCancelConfirm={() => setState({ phase: "builder" })}
          job={job}
        />
      ) : (
        <main style={styles.main}>
          {state.phase === "idle" && (
            <UploadForm onPresigned={handlePresigned} />
          )}

          {state.phase === "confirming" && (
            <TierConfirm
              presign={state.presign}
              filename={state.filename}
              pipelineId={null}
              onConfirm={handleConfirm}
              onCancel={handleReset}
            />
          )}

          {state.phase === "processing" && (
            <JobProgress
              job={job}
              onCancelled={() => { if (job) setState({ phase: "done", jobId: job.job_id }); }}
            />
          )}

          {state.phase === "done" && job && job.status === "completed" && (
            <ResultViewer job={job} onReset={handleReset} />
          )}

          {state.phase === "done" && job && job.status === "cancelled" && (
            <div style={styles.errorCard}>
              <h2 style={{ ...styles.errorTitle, color: "#6b7280" }}>Job Cancelled</h2>
              <p style={styles.errorMsg}>The pipeline was cancelled before completing.</p>
              <button style={styles.retryBtn} onClick={handleReset}>
                Back
              </button>
            </div>
          )}

          {state.phase === "done" && job && job.status === "failed" && (
            <div style={styles.errorCard}>
              <h2 style={styles.errorTitle}>Pipeline Failed</h2>
              <p style={styles.errorMsg}>{job.error ?? "Unknown error"}</p>
              <button style={styles.retryBtn} onClick={handleReset}>
                Try Again
              </button>
            </div>
          )}

          {state.phase === "error" && (
            <div style={styles.errorCard}>
              <h2 style={styles.errorTitle}>Error</h2>
              <p style={styles.errorMsg}>{state.message}</p>
              <button style={styles.retryBtn} onClick={handleReset}>
                Try Again
              </button>
            </div>
          )}
        </main>
      )}
      {/* Results panel — always rendered so transitions are smooth */}
      {job && job.result && (
        <ResultsPanel
          job={job}
          isOpen={panelOpen}
          onClose={() => setPanelOpen(false)}
          onReset={handleReset}
        />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", flexDirection: "column" },
  header: {
    height: 60,
    padding: "0 32px",
    background: "#1e3a5f",
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexShrink: 0,
  },
  logo: { fontSize: 28 },
  brand: { color: "#fff", fontWeight: 700, fontSize: 18, letterSpacing: "-0.3px" },
  nav: { marginLeft: "auto", display: "flex", gap: 4, alignItems: "center" },
  navBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid rgba(255,255,255,0.3)",
    background: "transparent",
    color: "#fff",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  navBtnActive: { background: "rgba(255,255,255,0.15)" },
  userInfo: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginLeft: 8,
    paddingLeft: 12,
    borderLeft: "1px solid rgba(255,255,255,0.2)",
  },
  userEmail: { color: "rgba(255,255,255,0.7)", fontSize: 12 },
  signOutBtn: {
    padding: "4px 10px",
    borderRadius: 5,
    border: "1px solid rgba(255,255,255,0.3)",
    background: "transparent",
    color: "rgba(255,255,255,0.8)",
    cursor: "pointer",
    fontSize: 12,
  },
  main: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "48px 24px",
  },
  errorCard: {
    maxWidth: 480,
    textAlign: "center",
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #fca5a5",
    padding: "32px 24px",
  },
  errorTitle: { fontSize: 20, fontWeight: 700, color: "#dc2626", marginBottom: 8 },
  errorMsg: { color: "#374151", marginBottom: 20 },
  retryBtn: {
    padding: "10px 24px",
    borderRadius: 8,
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
};

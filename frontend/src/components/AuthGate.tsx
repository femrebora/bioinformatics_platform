import { useState } from "react";
import { login, register, storeToken } from "../api/authClient";

interface Props {
  onAuthenticated: (token: string) => void;
}

type Tab = "login" | "register";

export function AuthGate({ onAuthenticated }: Props) {
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setLoading(true);
    try {
      if (tab === "register") {
        await register(email, password);
        setSuccessMsg("Account created! Signing you in…");
      }
      const tokenRes = await login(email, password);
      storeToken(tokenRes.access_token);
      onAuthenticated(tokenRes.access_token);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err instanceof Error ? err.message : "Something went wrong.");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.backdrop}>
      <div style={s.card}>
        <div style={s.logoRow}>
          <span style={s.logoEmoji}>🧬</span>
          <span style={s.brand}>Bioinformatics Platform</span>
        </div>

        <div style={s.tabs}>
          <button
            style={{ ...s.tab, ...(tab === "login" ? s.tabActive : {}) }}
            onClick={() => { setTab("login"); setError(null); setSuccessMsg(null); }}
          >
            Sign In
          </button>
          <button
            style={{ ...s.tab, ...(tab === "register" ? s.tabActive : {}) }}
            onClick={() => { setTab("register"); setError(null); setSuccessMsg(null); }}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit} style={s.form}>
          <label style={s.label}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            style={s.input}
            placeholder="you@example.com"
          />

          <label style={s.label}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={tab === "register" ? "new-password" : "current-password"}
            style={s.input}
            placeholder="••••••••"
          />

          {error && <div style={s.error}>{error}</div>}
          {successMsg && <div style={s.success}>{successMsg}</div>}

          <button type="submit" disabled={loading} style={s.submitBtn}>
            {loading ? "Please wait…" : tab === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <p style={s.hint}>
          {tab === "login" ? (
            <>Don't have an account?{" "}
              <button style={s.switchLink} onClick={() => setTab("register")}>Create one</button>
            </>
          ) : (
            <>Already have an account?{" "}
              <button style={s.switchLink} onClick={() => setTab("login")}>Sign in</button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  backdrop: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f1f5f9",
  },
  card: {
    background: "#fff",
    borderRadius: 14,
    border: "1px solid #e2e8f0",
    padding: "36px 40px 28px",
    width: 380,
    boxShadow: "0 4px 24px rgba(0,0,0,0.07)",
  },
  logoRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 28,
    justifyContent: "center",
  },
  logoEmoji: { fontSize: 28 },
  brand: { fontWeight: 700, fontSize: 18, color: "#1e3a5f" },
  tabs: {
    display: "flex",
    borderBottom: "1px solid #e2e8f0",
    marginBottom: 24,
    gap: 0,
  },
  tab: {
    flex: 1,
    padding: "8px 0",
    border: "none",
    background: "none",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 500,
    color: "#64748b",
    borderBottom: "2px solid transparent",
    transition: "color 0.15s",
  },
  tabActive: {
    color: "#1e3a5f",
    borderBottom: "2px solid #1e3a5f",
  },
  form: { display: "flex", flexDirection: "column", gap: 8 },
  label: { fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 2 },
  input: {
    padding: "9px 12px",
    borderRadius: 7,
    border: "1px solid #d1d5db",
    fontSize: 14,
    outline: "none",
    marginBottom: 8,
  },
  error: {
    background: "#fef2f2",
    border: "1px solid #fca5a5",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#dc2626",
    fontSize: 13,
    marginTop: 4,
  },
  success: {
    background: "#f0fdf4",
    border: "1px solid #86efac",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#16a34a",
    fontSize: 13,
    marginTop: 4,
  },
  submitBtn: {
    marginTop: 8,
    padding: "11px 0",
    borderRadius: 8,
    border: "none",
    background: "#1e3a5f",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  hint: { textAlign: "center", fontSize: 13, color: "#64748b", marginTop: 16, marginBottom: 0 },
  switchLink: {
    background: "none",
    border: "none",
    color: "#2563eb",
    cursor: "pointer",
    fontSize: 13,
    padding: 0,
    textDecoration: "underline",
  },
};

import { FormEvent, useEffect, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

type Simulation = {
  original_request: string;
  planned_command: string;
  command_explanation: string;
  risk_level: string;
  risk_score: number;
  risk_reasons: string[];
  warnings: string[];
  files_affected: Array<{ path: string; action: string; size_bytes: number }>;
  total_files_count: number;
  total_size_bytes: number;
  processes_affected: Array<{ name: string; impact: string }>;
  is_reversible: boolean;
  safer_alternative: string;
  safer_command: string;
  simulation_confidence: string;
  requires_approval: boolean;
};

type SandboxResult = {
  command: string;
  target_path: string;
  target_exists: boolean;
  before_file_count: number;
  after_file_count: number;
  data_destroyed_readable: string;
  destruction_percentage: number;
  is_catastrophic: boolean;
  impact_summary: string;
  files_deleted: Array<{ path: string; name: string; size_bytes: number }>;
  files_survived: Array<{ path: string }>;
};

type HistoryItem = {
  timestamp: string;
  action: string;
  command: string;
  risk_level: string;
};

type DemoScenario = {
  scenario: string;
  description: string;
  command: string;
  category: string;
  danger_level: string;
  action_taken: string;
  sandbox: {
    files_before: number;
    files_after: number;
    files_deleted: number;
    data_destroyed: string;
    is_catastrophic: boolean;
    impact: string;
  };
};

type AgentChatResponse = {
  original_prompt: string;
  intent: string;
  steps_completed: string[];
  message: string;
  code_result?: {
    code: string;
    filename: string;
    language: string;
    explanation?: string;
    saved_to?: string;
    folder?: string;
  } | null;
  storage_analysis?: {
    target_path: string;
    scanned_files_count: number;
    total_size_readable: string;
    trash: {
      count: number;
      readable: string;
      reclaim_percentage: number;
      items: Array<{ name: string; size_readable: string; reason: string; path: string }>;
    };
    review: {
      count: number;
      readable: string;
      items: Array<{ name: string; size_readable: string; reason: string }>;
    };
    essential: {
      count: number;
      readable: string;
    };
    clean_result?: {
      cleaned_count: number;
      freed_readable: string;
    };
  } | null;
  file_resolution?: {
    query: string;
    best_match?: {
      name: string;
      relative_path: string;
      size_readable: string;
      modified: string;
      match_type: string;
      score: number;
    };
    matches: Array<any>;
  } | null;
  github_data?: {
    status?: {
      authenticated: boolean;
      user?: { login: string; public_repos: number; avatar_url: string; html_url: string };
    };
    repositories?: Array<{ name: string; nameWithOwner: string; isPrivate: boolean; url: string; updatedAt: string; description: string }>;
    recent_commits?: Array<{ sha: string; message: string; author: string; date: string }>;
    active_repo?: string;
  } | null;
  simulation?: Simulation | null;
  sandbox?: SandboxResult | null;
  requires_approval: boolean;
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function riskColor(level: string) {
  return { CRITICAL: "#dc2626", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e" }[level] ?? "#6b7280";
}

// ─── Shared Components ────────────────────────────────────────────────────────

function Button({ children, className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props}>{children}</button>;
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">B</span>
      <span>BashGuard</span>
    </div>
  );
}

// ─── Login Component ──────────────────────────────────────────────────────────

function Login({ onLogin }: { onLogin: () => void }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusChecked, setStatusChecked] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/auth/status`)
      .then((r) => r.json())
      .then((data) => {
        if (!data.is_registered) {
          setIsRegister(true);
        }
        setStatusChecked(true);
      })
      .catch(() => {
        setStatusChecked(true);
      });
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }

    if (isRegister && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const endpoint = isRegister ? "/auth/register" : "/auth/login";
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password: password.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed");
      }

      if (isRegister) {
        const loginRes = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim(), password: password.trim() }),
        });
        const loginData = await loginRes.json();
        if (loginData.token) {
          localStorage.setItem("bashguard-session", loginData.token);
          localStorage.setItem("bashguard-user", loginData.username);
        }
      } else if (data.token) {
        localStorage.setItem("bashguard-session", data.token);
        localStorage.setItem("bashguard-user", data.username);
      }

      onLogin();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  if (!statusChecked) {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: "center" }}>
          <p className="muted">Connecting to BashGuard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-brand">
        <Brand />
        <p>Simulation first. Execution only with consent.</p>
      </div>
      <div className="login-card">
        <div>
          <p className="eyebrow">{isRegister ? "First-time setup" : "Welcome back"}</p>
          <h1>{isRegister ? "Create admin account" : "Log in to BashGuard"}</h1>
          <p className="muted">
            {isRegister
              ? "Set your credentials. Only this account will have access to system execution."
              : "Enter your credentials to access the safety agent."}
          </p>
        </div>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
          <label>
            User ID
            <input
              type="text"
              placeholder="e.g. admin or username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              autoComplete={isRegister ? "new-password" : "current-password"}
            />
          </label>
          {isRegister && (
            <label>
              Confirm password
              <input
                type="password"
                placeholder="Re-enter password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={loading}
                autoComplete="new-password"
              />
            </label>
          )}
          {error && <p className="form-error" style={{ color: "#dc2626" }}>{error}</p>}
          <Button className="primary login-button" type="submit" disabled={loading}>
            {loading ? "Processing..." : isRegister ? "Create account & proceed →" : "Log in →"}
          </Button>
          {!isRegister && (
            <p className="fine-print">
              Need a fresh setup? Delete <code>bashguard_auth.db</code> and reload.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ─── Demo Page Component ──────────────────────────────────────────────────────

function DemoPage() {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/demo`)
      .then((r) => r.json())
      .then((data) => setScenarios(data.scenarios || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="demo-section" style={{ padding: "48px 0 96px" }}>
      <div className="section-heading" style={{ marginBottom: 32 }}>
        <div>
          <p className="eyebrow">Judge evaluation</p>
          <h2>Live Pre-Built Scenarios</h2>
          <p className="muted" style={{ marginTop: 8 }}>
            Evaluated consequence simulations showing how BashGuard halts catastrophic commands and provides safer alternatives.
          </p>
        </div>
      </div>
      {loading ? (
        <p className="muted">Loading benchmark scenarios...</p>
      ) : (
        <div className="demo-grid">
          {scenarios.map((s, idx) => (
            <div key={idx} className="demo-card">
              <div className="demo-card-header">
                <div>
                  <span className="demo-category">{s.category}</span>
                  <h3>{s.scenario}</h3>
                </div>
                <span className="demo-action-badge" style={{ borderColor: riskColor(s.danger_level), color: riskColor(s.danger_level) }}>
                  {s.action_taken}
                </span>
              </div>
              <code className="demo-command">{s.command}</code>
              <p className="muted" style={{ fontSize: 13, margin: 0 }}>{s.description}</p>
              <div className="demo-sandbox-row">
                <span>Before: <strong>{s.sandbox.files_before}</strong></span>
                <span>After: <strong>{s.sandbox.files_after}</strong></span>
                <span>Destroyed: <strong style={{ color: "#dc2626" }}>{s.sandbox.data_destroyed}</strong></span>
              </div>
              <p className="demo-impact">{s.sandbox.impact}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ─── MAIN DASHBOARD (ONE UNIFIED WORKSPACE FOR ALL 3 CAPABILITIES) ────────────

type Tab = "workspace" | "terminal" | "demo";

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("workspace");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [result, setResult] = useState<AgentChatResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [decisionMsg, setDecisionMsg] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const samplePrompts = [
    "create a folder called test_game and write a snake game in python inside it",
    "simulate rm -rf /",
    "judge what files on my laptop are necessary and what are trash in Downloads",
    "clean trash in my downloads",
    "find file server and show me what's inside",
    "fetch my github repositories and recent commits"
  ];

  useEffect(() => {
    fetch(`${API_URL}/`).then((r) => { if (r.ok) setApiOnline(true); }).catch(() => setApiOnline(false));
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const res = await fetch(`${API_URL}/history?limit=8`);
      if (res.ok) setHistory(await res.json());
    } catch { /* offline */ }
  }

  async function handleUnifiedSubmit(e: FormEvent | null, customPrompt?: string) {
    if (e) e.preventDefault();
    const query = (customPrompt || prompt).trim();
    if (!query) return;
    setLoading(true);
    setError("");
    setDecisionMsg("");
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: query }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: AgentChatResponse = await res.json();
      setResult(data);
      await loadHistory();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed. Verify server is running.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(action: "execute" | "reject", useSafer = false) {
    if (!result?.simulation) return;
    const plannedCmd = (useSafer && result.simulation.safer_command) ? result.simulation.safer_command : result.simulation.planned_command;
    try {
      const res = await fetch(`${API_URL}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "execute"
            ? {
                command: plannedCmd,
                risk_level: result.simulation.risk_level,
                use_safer: useSafer,
                safer_command: result.simulation.safer_command,
              }
            : {
                command: plannedCmd,
                reason: "Rejected by user in unified workspace",
              }
        ),
      });
      const data = await res.json();
      setDecisionMsg(
        action === "execute"
          ? (data.was_blocked ? "Permanently blocked by BashGuard hard-block rules." : (data.success ? `✓ Executed: ${plannedCmd}` : data.error))
          : "Command rejected. Nothing executed."
      );
      await loadHistory();
    } catch {
      setError("Failed to execute decision.");
    }
  }

  async function handleCleanTrash() {
    if (!result?.storage_analysis?.trash?.items?.length) return;
    setCleaning(true);
    try {
      const paths = result.storage_analysis.trash.items.map((i) => i.path);
      const res = await fetch(`${API_URL}/intel/clean-trash`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_paths: paths, quarantine: true }),
      });
      if (!res.ok) throw new Error();
      const cleanData = await res.json();
      setResult((prev) => {
        if (!prev || !prev.storage_analysis) return prev;
        return {
          ...prev,
          storage_analysis: {
            ...prev.storage_analysis,
            clean_result: {
              cleaned_count: cleanData.cleaned_count,
              freed_readable: cleanData.freed_readable,
            },
          },
        };
      });
      await loadHistory();
    } catch {
      setError("Failed to clean trash.");
    } finally {
      setCleaning(false);
    }
  }

  function copyCode() {
    if (!result?.code_result?.code) return;
    navigator.clipboard.writeText(result.code_result.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header>
        <Brand />
        <nav aria-label="Primary navigation">
          <a href="#" onClick={() => setTab("workspace")} className={tab === "workspace" ? "nav-active" : ""}>
            Unified Workspace
          </a>
          <a href="#" onClick={() => setTab("terminal")} className={tab === "terminal" ? "nav-active" : ""}>
            Terminal Hook
          </a>
          <a href="#" onClick={() => setTab("demo")} className={tab === "demo" ? "nav-active" : ""}>
            Demo
          </a>
          <a href="https://github.com/cypher07-ai/BASHGUARD" rel="noreferrer" target="_blank">
            GitHub
          </a>
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="api-status-dot" style={{ background: apiOnline ? "#22c55e" : "#ef4444" }} title={apiOnline ? "API Online" : "API Offline"} />
          <Button className="secondary" onClick={async () => {
            const token = localStorage.getItem("bashguard-session");
            if (token) {
              await fetch(`${API_URL}/auth/logout`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token }),
              }).catch(() => {});
            }
            localStorage.removeItem("bashguard-session");
            localStorage.removeItem("bashguard-user");
            onLogout();
          }}>Log out</Button>
        </div>
      </header>

      <main>
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 1: UNIFIED WORKSPACE (OMNI AGENT + SIMULATOR + CODER IN ONE)    */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {tab === "workspace" && (
          <section style={{ padding: "40px 0 96px" }}>
            {/* Hero / Header */}
            <div className="section-heading" style={{ marginBottom: 24 }}>
              <div>
                <p className="eyebrow">All-in-One Autonomous AI Safety & Execution Layer</p>
                <h1 style={{ fontSize: "clamp(32px, 5vw, 56px)", letterSpacing: "-.04em", margin: "10px 0 14px", lineHeight: 1.05 }}>
                  Simulate, Code, Clean & Execute.
                </h1>
                <p className="muted" style={{ fontSize: 17, maxWidth: 800, margin: 0 }}>
                  One single workspace for everything: simulate dangerous commands before execution, synthesize code and scaffold project folders, judge trash vs necessary files, fuzzy-search files, and inspect GitHub.
                </p>
              </div>
            </div>

            {/* Omnibar Input Card */}
            <form className="omni-prompt-card" onSubmit={(e) => handleUnifiedSubmit(e)}>
              <textarea
                className="omni-textarea"
                placeholder="Type anything: 'rm -rf /', 'create a folder called test_game and write a snake game in python inside it', 'judge what files in Downloads are trash vs necessary', or 'find server'..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={loading}
                rows={3}
              />

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14 }}>
                <div className="quick-pills">
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--body)", alignSelf: "center" }}>Quick Prompts:</span>
                  {samplePrompts.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="quick-pill"
                      onClick={() => {
                        setPrompt(p);
                        handleUnifiedSubmit(null, p);
                      }}
                    >
                      {p.length > 36 ? p.substring(0, 36) + "…" : p}
                    </button>
                  ))}
                </div>

                <Button className="primary" type="submit" disabled={loading || !prompt.trim()} style={{ minWidth: 170 }}>
                  {loading ? "Agent Processing…" : "Run & Simulate →"}
                </Button>
              </div>
            </form>

            {error && <div className="notice error-notice" style={{ marginTop: 24 }}>{error}</div>}

            {/* ── Results Stream ── */}
            {result && (
              <div style={{ marginTop: 36, display: "grid", gap: 24 }}>
                {/* Workflow Step Badges */}
                {result.steps_completed && result.steps_completed.length > 0 && (
                  <div className="step-timeline">
                    <span style={{ fontSize: 12, fontWeight: 700, alignSelf: "center", marginRight: 8, color: "#0369a1" }}>WORKFLOW STEPS:</span>
                    {result.steps_completed.map((st, i) => (
                      <span key={i} className="step-badge">
                        ✓ Step {i + 1}: {st}
                      </span>
                    ))}
                  </div>
                )}

                {/* Explanation Banner */}
                <div className="notice" style={{ background: "var(--soft)", color: "var(--ink)", border: "1px solid var(--pressed)" }}>
                  <p style={{ margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.6, fontSize: 15 }}>
                    {result.message}
                  </p>
                </div>

                {/* 1. Command Consequence Simulation & Blast Radius (The Simulator) */}
                {result.simulation && (
                  <article className="result-main">
                    <div className="command-preview">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                        <span>Consequence & Blast Radius Simulation</span>
                        <span className="risk-pill" style={{ background: riskColor(result.simulation.risk_level), color: "#fff" }}>
                          {result.simulation.risk_level} Risk ({result.simulation.risk_score}/100)
                        </span>
                      </div>
                      <code>{result.simulation.planned_command}</code>
                    </div>

                    <p className="explanation" style={{ margin: 0, padding: "18px 24px" }}>
                      {result.simulation.command_explanation}
                    </p>

                    <div className="impact-stats">
                      <div><strong>{result.simulation.total_files_count}</strong><span>Files affected</span></div>
                      <div><strong>{formatBytes(result.simulation.total_size_bytes)}</strong><span>Data affected</span></div>
                      <div><strong>{result.simulation.is_reversible ? "Yes" : "No"}</strong><span>Reversible</span></div>
                      <div><strong>{result.simulation.simulation_confidence}</strong><span>Confidence</span></div>
                    </div>

                    {/* Safer Alternative */}
                    {result.simulation.safer_command && (
                      <div style={{ padding: "16px 24px", background: "#f0fdf4", borderTop: "1px solid #bbf7d0", borderBottom: "1px solid #bbf7d0" }}>
                        <span className="eyebrow" style={{ color: "#16a34a" }}>Proactive Safer Alternative Suggested</span>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginTop: 6 }}>
                          <code>{result.simulation.safer_command}</code>
                          <Button className="secondary" style={{ fontSize: 13, padding: "8px 14px", height: "auto", minHeight: 34 }} onClick={() => handleDecision("execute", true)}>
                            Use Safer Command →
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Virtual Sandbox BEFORE vs AFTER Differential */}
                    {result.sandbox && (
                      <div style={{ padding: "20px 24px", borderTop: "1px solid var(--pressed)", background: "#fafafa" }}>
                        <p className="eyebrow" style={{ marginBottom: 10 }}>Virtual Filesystem Sandbox (Zero Real Modification)</p>
                        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: 13, marginBottom: 12 }}>
                          <span>Target: <strong>{result.sandbox.target_path || "Current Directory"}</strong></span>
                          <span>Before: <strong>{result.sandbox.before_file_count} files</strong></span>
                          <span>After: <strong>{result.sandbox.after_file_count} files</strong></span>
                          <span>Data Destroyed: <strong style={{ color: "#dc2626" }}>{result.sandbox.data_destroyed_readable} ({result.sandbox.destruction_percentage}%)</strong></span>
                        </div>
                        {result.sandbox.files_deleted && result.sandbox.files_deleted.length > 0 && (
                          <div style={{ maxHeight: 160, overflowY: "auto", background: "#fff", padding: 12, borderRadius: 8, border: "1px solid var(--pressed)", fontSize: 12, fontFamily: "monospace" }}>
                            {result.sandbox.files_deleted.map((del, dIdx) => (
                              <div key={dIdx} style={{ color: "#b91c1c", padding: "2px 0" }}>
                                ✗ {del.path} ({formatBytes(del.size_bytes)})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Approval Gate */}
                    {result.requires_approval && (
                      <div style={{ padding: "20px 24px", background: "#fff1f2", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                        <span style={{ fontWeight: 600, color: "#9f1239", fontSize: 14 }}>
                          ⚠️ Dangerous action detected. Execute only with explicit consent.
                        </span>
                        <div style={{ display: "flex", gap: 10 }}>
                          <Button className="primary" style={{ background: "#dc2626" }} onClick={() => handleDecision("execute")}>
                            Approve & Execute
                          </Button>
                          <Button className="secondary" onClick={() => handleDecision("reject")}>
                            Reject & Abort
                          </Button>
                        </div>
                      </div>
                    )}

                    {decisionMsg && (
                      <div style={{ padding: "14px 24px", background: "var(--soft)", fontWeight: 600, fontSize: 14 }}>
                        {decisionMsg}
                      </div>
                    )}
                  </article>
                )}

                {/* 2. Code Generation Result (The Code Engine) */}
                {result.code_result && (
                  <div className="coder-result" style={{ marginTop: 0 }}>
                    <div className="coder-result-header">
                      <div>
                        <p className="eyebrow">Code Synthesized</p>
                        <h3>{result.code_result.filename}</h3>
                        <span className="coder-lang-badge">{result.code_result.language}</span>
                        {result.code_result.saved_to && (
                          <span style={{ marginLeft: 12, fontSize: 12, color: "var(--body)", fontFamily: "monospace" }}>
                            📁 Saved to {result.code_result.saved_to}
                          </span>
                        )}
                      </div>
                      <Button className="subtle" onClick={copyCode}>
                        {copied ? "Copied!" : "Copy code"}
                      </Button>
                    </div>
                    <pre className="coder-code"><code>{result.code_result.code}</code></pre>
                    {result.code_result.explanation && (
                      <div style={{ padding: "16px 24px", background: "var(--soft)", fontSize: 14, color: "var(--body)", borderTop: "1px solid var(--pressed)" }}>
                        <strong>Explanation:</strong> {result.code_result.explanation}
                      </div>
                    )}
                  </div>
                )}

                {/* 3. Storage Intelligence Result */}
                {result.storage_analysis && (
                  <div className="command-card" style={{ border: "1px solid var(--pressed)", padding: 24 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                      <div>
                        <p className="eyebrow">Storage Intelligence</p>
                        <h3 style={{ margin: "4px 0", fontSize: 20 }}>Trash vs. Necessary Media Judge</h3>
                        <span className="muted" style={{ fontSize: 13 }}>Target: {result.storage_analysis.target_path} ({result.storage_analysis.total_size_readable})</span>
                      </div>
                      {result.storage_analysis.clean_result ? (
                        <span className="step-badge" style={{ background: "#dcfce7", color: "#15803d" }}>
                          ✓ Cleaned {result.storage_analysis.clean_result.cleaned_count} files ({result.storage_analysis.clean_result.freed_readable} freed)
                        </span>
                      ) : (
                        result.storage_analysis.trash.count > 0 && (
                          <Button className="primary" onClick={handleCleanTrash} disabled={cleaning}>
                            {cleaning ? "Quarantining Trash…" : `Clean ${result.storage_analysis.trash.count} Trash Files (${result.storage_analysis.trash.readable})`}
                          </Button>
                        )
                      )}
                    </div>

                    <div className="storage-grid">
                      <div className="storage-card trash">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="badge-trash">Trash Files</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: "#dc2626" }}>Reclaim {result.storage_analysis.trash.reclaim_percentage}%</span>
                        </div>
                        <div className="storage-stat" style={{ color: "#b91c1c" }}>{result.storage_analysis.trash.count} files</div>
                        <span style={{ fontSize: 13, color: "var(--body)" }}>{result.storage_analysis.trash.readable} temporary cache, old installers & duplicate data</span>
                      </div>

                      <div className="storage-card review">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="badge-review">Review Needed</span>
                        </div>
                        <div className="storage-stat" style={{ color: "#a16207" }}>{result.storage_analysis.review.count} files</div>
                        <span style={{ fontSize: 13, color: "var(--body)" }}>{result.storage_analysis.review.readable} large unaccessed archives or old video media</span>
                      </div>

                      <div className="storage-card essential">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="badge-essential">Essential Files</span>
                        </div>
                        <div className="storage-stat" style={{ color: "#15803d" }}>{result.storage_analysis.essential.count} files</div>
                        <span style={{ fontSize: 13, color: "var(--body)" }}>Protected source code, git repos, configs & documents</span>
                      </div>
                    </div>

                    {result.storage_analysis.trash.items.length > 0 && (
                      <div style={{ borderTop: "1px solid var(--pressed)", paddingTop: 16 }}>
                        <p className="eyebrow" style={{ marginBottom: 10 }}>Identified Items for Cleanup</p>
                        <div style={{ display: "grid", gap: 8, maxHeight: 220, overflowY: "auto" }}>
                          {result.storage_analysis.trash.items.slice(0, 8).map((it, idx) => (
                            <div key={idx} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "8px 12px", background: "var(--soft)", borderRadius: 8 }}>
                              <span style={{ fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>{it.name}</span>
                              <span style={{ color: "var(--body)", fontSize: 12 }}>{it.reason}</span>
                              <strong>{it.size_readable}</strong>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. GitHub Live Data */}
                {result.github_data && (
                  <div className="command-card" style={{ border: "1px solid var(--pressed)", padding: 24 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      {result.github_data.status?.user?.avatar_url && (
                        <img src={result.github_data.status.user.avatar_url} alt="GitHub avatar" style={{ width: 44, height: 44, borderRadius: "50%" }} />
                      )}
                      <div>
                        <p className="eyebrow">GitHub Live Integration</p>
                        <h3 style={{ margin: "2px 0 0" }}>{result.github_data.status?.user?.login || "GitHub Connected"}</h3>
                        <span className="muted" style={{ fontSize: 13 }}>Public Repositories: {result.github_data.status?.user?.public_repos || 0}</span>
                      </div>
                    </div>

                    {result.github_data.repositories && result.github_data.repositories.length > 0 && (
                      <div className="github-grid">
                        {result.github_data.repositories.map((repo, idx) => (
                          <div key={idx} className="github-repo-card">
                            <div>
                              <strong style={{ fontSize: 14 }}>{repo.name}</strong>
                              <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>{repo.description || "No description provided."}</p>
                            </div>
                            <a href={repo.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>
                              View on GitHub →
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Live Audit Trail in the Workspace ── */}
            <div style={{ marginTop: 64, borderTop: "1px solid var(--pressed)", paddingTop: 40 }}>
              <div className="section-heading" style={{ marginBottom: 20 }}>
                <div>
                  <p className="eyebrow">Immutable Audit Trail</p>
                  <h3 style={{ fontSize: 24, margin: "4px 0" }}>Recent Actions & Security Log</h3>
                </div>
                <Button className="subtle" onClick={loadHistory}>Refresh log</Button>
              </div>

              <div className="history-table">
                {history.length ? history.map((item, i) => (
                  <div className="history-row" key={i}>
                    <span className="action-mark">{item.action.slice(0, 1)}</span>
                    <div><strong>{item.command}</strong><span>{new Date(item.timestamp).toLocaleString()}</span></div>
                    <span className="history-action">{item.action.replace("_", " ")}</span>
                    <span className="risk-label" style={{ color: riskColor(item.risk_level) }}>{item.risk_level}</span>
                  </div>
                )) : (
                  <div className="empty-history">
                    <h3>No activity yet</h3>
                    <p>Your approved, rejected, and simulated commands will appear here.</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 2: TERMINAL HOOK                                                  */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {tab === "terminal" && (
          <section className="terminal-hook" id="terminal" style={{ padding: "48px 0 96px" }}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Real-time terminal safety</p>
                <h2>Terminal Hook</h2>
              </div>
              <span className="status"><i style={{ background: "#22c55e" }} /> Ready</span>
            </div>
            <p className="lead">
              Intercept dangerous commands right inside PowerShell (Windows) or Bash (Linux/macOS) before they run.
            </p>
            <div className="terminal-steps">
              <div className="hook-step">
                <span>1</span>
                <div>
                  <strong>Windows (PowerShell)</strong>
                  <code>. .\bashguard_hook.ps1</code>
                  <small>Hooks into PSReadLine PreCommandHandler</small>
                </div>
              </div>
              <div className="hook-step">
                <span>2</span>
                <div>
                  <strong>Linux / Mac (Bash)</strong>
                  <code>source ./bashguard_hook.sh</code>
                  <small>Command override wrappers for rm, chmod, kill, git</small>
                </div>
              </div>
              <div className="hook-step">
                <span>3</span>
                <div>
                  <strong>Disable anytime</strong>
                  <code>bashguard-off</code>
                  <small>Deactivates the hook immediately</small>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 3: DEMO                                                           */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {tab === "demo" && <DemoPage />}
      </main>

      <footer>
        <Brand />
        <p>Simulation first. Execution only with consent.</p>
        <span>Built for safer AI agents.</span>
      </footer>
    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(localStorage.getItem("bashguard-session")));
  return authenticated
    ? <Dashboard onLogout={() => setAuthenticated(false)} />
    : <Login onLogin={() => setAuthenticated(true)} />;
}

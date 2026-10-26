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

type AnalyzeResult = {
  is_raw_command: boolean;
  instant_danger_level: string;
  recommendation: string;
  simulation: Simulation;
  sandbox: SandboxResult;
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

// ─── Components ───────────────────────────────────────────────────────────────

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

// ─── Login ────────────────────────────────────────────────────────────────────

function Login({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // On first load, check if anyone is registered — if not, show register form
  useEffect(() => {
    fetch(`${API_URL}/auth/status`)
      .then((r) => r.json())
      .then((d) => { if (d.setup_required) setMode("register"); })
      .catch(() => {}); // server offline — default to login
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || password.length < 6) {
      setError("Username and a password of at least 6 characters are required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Something went wrong.");
        return;
      }
      if (mode === "register") {
        // After registering, auto-login
        const loginRes = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim(), password }),
        });
        const loginData = await loginRes.json();
        if (!loginRes.ok) { setError(loginData.detail || "Login after register failed."); return; }
        localStorage.setItem("bashguard-session", loginData.token);
        localStorage.setItem("bashguard-user", loginData.username);
      } else {
        localStorage.setItem("bashguard-session", data.token);
        localStorage.setItem("bashguard-user", data.username);
      }
      onLogin();
    } catch {
      setError("Could not reach the BashGuard API. Make sure the server is running.");
    } finally {
      setLoading(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <main className="login-page">
      <div className="login-brand">
        <Brand />
        <p>Simulate before you execute.</p>
      </div>
      <form className="login-card" onSubmit={submit}>
        <div>
          <p className="eyebrow">Secure workspace</p>
          <h1>{isRegister ? "Create account" : "Welcome back"}</h1>
          <p className="muted">
            {isRegister
              ? "Set up your BashGuard account to get started."
              : "Sign in to review command risk before anything runs."}
          </p>
        </div>
        <label>
          Username
          <input
            autoComplete={isRegister ? "username" : "username"}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={isRegister ? "Choose a username" : "Your username"}
            type="text"
            value={username}
            disabled={loading}
          />
        </label>
        <label>
          Password
          <input
            autoComplete={isRegister ? "new-password" : "current-password"}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={isRegister ? "Choose a password (6+ characters)" : "Enter your password"}
            type="password"
            value={password}
            disabled={loading}
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <Button className="primary login-button" type="submit" disabled={loading}>
          {loading
            ? (isRegister ? "Creating account…" : "Signing in…")
            : (isRegister ? "Create account " : "Continue to BashGuard ")}
          {!loading && <span aria-hidden="true">→</span>}
        </Button>
        <p className="fine-print">
          {isRegister ? "Already have an account? " : "New to BashGuard? "}
          <button
            type="button"
            onClick={() => { setMode(isRegister ? "login" : "register"); setError(""); }}
            style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700, padding: 0, textDecoration: "underline", textUnderlineOffset: 3 }}
          >
            {isRegister ? "Sign in" : "Sign up"}
          </button>
        </p>
      </form>
    </main>
  );
}


// ─── Risk Dial ────────────────────────────────────────────────────────────────

function riskDialColor(score: number) {
  if (score <= 30) return "#22c55e";
  if (score <= 60) return "#eab308";
  return "#ef4444";
}

function riskDialLabel(score: number) {
  if (score <= 30) return "Low";
  if (score <= 60) return "Medium";
  return "High";
}

function RiskDial({ value }: { value: number; label: string }) {
  const color = riskDialColor(value);
  const label = riskDialLabel(value);
  // When score is 0, conic-gradient draws 0deg = invisible. Use solid color instead.
  const dialStyle = value === 0
    ? { background: color } as React.CSSProperties
    : { "--score": `${value * 3.6}deg`, "--dial-color": color } as React.CSSProperties;
  return (
    <div className="risk-dial" style={dialStyle}>
      <div><strong>{value}</strong><span>/ 100</span></div>
      <small>{label} risk</small>
    </div>
  );
}

// ─── Sandbox Diff Panel ───────────────────────────────────────────────────────

function SandboxPanel({ sandbox }: { sandbox: SandboxResult }) {
  const [expanded, setExpanded] = useState(false);
  if (!sandbox) return null;
  const pct = sandbox.destruction_percentage ?? 0;
  const PREVIEW = 8;
  const total = sandbox.files_deleted?.length ?? 0;
  const shown = expanded ? sandbox.files_deleted : sandbox.files_deleted?.slice(0, PREVIEW);
  return (
    <div className="sandbox-panel">
      <p className="eyebrow">Sandbox — Filesystem Diff</p>
      <div className="sandbox-stats">
        <div className="sandbox-stat">
          <strong>{sandbox.before_file_count}</strong>
          <span>Files before</span>
        </div>
        <div className="sandbox-arrow">→</div>
        <div className="sandbox-stat">
          <strong style={{ color: sandbox.after_file_count < sandbox.before_file_count ? "#ef4444" : "#22c55e" }}>
            {sandbox.after_file_count}
          </strong>
          <span>Files after</span>
        </div>
        <div className="sandbox-stat">
          <strong style={{ color: pct > 50 ? "#ef4444" : "#22c55e" }}>{pct.toFixed(0)}%</strong>
          <span>Destroyed</span>
        </div>
        {sandbox.data_destroyed_readable && sandbox.data_destroyed_readable !== "0 B" && (
          <div className="sandbox-stat">
            <strong style={{ color: "#ef4444" }}>{sandbox.data_destroyed_readable}</strong>
            <span>Data lost</span>
          </div>
        )}
      </div>
      {sandbox.is_catastrophic && (
        <div className="sandbox-catastrophic">CATASTROPHIC — This would be irreversible</div>
      )}
      {sandbox.impact_summary && (
        <p className="sandbox-impact">{sandbox.impact_summary}</p>
      )}
      {total > 0 && (
        <div className="sandbox-files">
          <p className="eyebrow" style={{ marginBottom: 8 }}>Files that would be deleted</p>
          {shown.map((f, i) => (
            <div key={i} className="sandbox-file-row">
              <span className="sandbox-file-name">{f.path || f.name}</span>
              {f.size_bytes > 0 && <span className="sandbox-file-size">{formatBytes(f.size_bytes)}</span>}
            </div>
          ))}
          {total > PREVIEW && (
            <button
              className="sandbox-expand-btn"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded
                ? "Show less"
                : `+ ${total - PREVIEW} more files — click to expand`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Terminal Hook Panel ──────────────────────────────────────────────────────

function TerminalHookPanel() {
  const [command, setCommand] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<string[]>([]);

  async function analyze(e: FormEvent) {
    e.preventDefault();
    if (!command.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: command.trim(), context: "terminal" }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data);
      setHistory((h) => [command, ...h.slice(0, 9)]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  const dangerColor = (level: string) =>
    ({ CRITICAL: "#dc2626", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e" }[level] ?? "#6b7280");

  return (
    <div className="terminal-hook-panel">
      <div className="terminal-header">
        <span className="terminal-dot" style={{ background: "#ef4444" }} />
        <span className="terminal-dot" style={{ background: "#f59e0b" }} />
        <span className="terminal-dot" style={{ background: "#22c55e" }} />
        <span className="terminal-title">BashGuard Terminal — Real-time Command Analyzer</span>
      </div>

      {history.length > 0 && (
        <div className="terminal-history">
          {history.map((h, i) => (
            <div key={i} className="terminal-history-row">
              <span className="terminal-prompt">$</span>
              <span className="terminal-history-cmd" onClick={() => setCommand(h)}>{h}</span>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={analyze} className="terminal-input-row">
        <span className="terminal-prompt">$</span>
        <input
          className="terminal-input"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="Type any command — BashGuard intercepts it before execution..."
          disabled={loading}
          spellCheck={false}
          autoComplete="off"
        />
        <Button className="primary" type="submit" disabled={loading || !command.trim()}>
          {loading ? "Analyzing…" : "Analyze →"}
        </Button>
      </form>

      {error && <div className="terminal-error">{error}</div>}

      {result && (
        <div className="terminal-result">
          {/* Instant detection badge */}
          <div className="terminal-badges">
            <span className="terminal-badge" style={{ background: dangerColor(result.instant_danger_level), color: "#fff" }}>
              {result.instant_danger_level} RISK
            </span>
            {result.is_raw_command && (
              <span className="terminal-badge" style={{ background: "#7c3aed", color: "#fff" }}>RAW COMMAND</span>
            )}
            <span className="terminal-badge" style={{
              background: result.recommendation === "BLOCK" ? "#dc2626" : result.recommendation === "ALLOW" ? "#22c55e" : "#f97316",
              color: "#fff"
            }}>
              {result.recommendation === "BLOCK" ? "BLOCKED" : result.recommendation === "ALLOW" ? "ALLOWED" : "WARN"}
            </span>
          </div>

          {/* Planned command */}
          <div className="terminal-planned">
            <span className="eyebrow">Planned command</span>
            <code>{result.simulation.planned_command}</code>
          </div>

          {/* Risk reasons */}
          {result.simulation.risk_reasons.length > 0 && (
            <div className="terminal-reasons">
              {result.simulation.risk_reasons.map((r, i) => (
                <p key={i}><span>—</span>{r}</p>
              ))}
            </div>
          )}

          {/* Safer alternative */}
          {result.simulation.safer_command && (
            <div className="terminal-safer">
              <span className="eyebrow">Safer alternative</span>
              <code>{result.simulation.safer_command}</code>
            </div>
          )}

          {/* Sandbox diff */}
          <SandboxPanel sandbox={result.sandbox} />
        </div>
      )}
    </div>
  );
}

// ─── Demo Page (for judges) ────────────────────────────────────────────────────

function DemoPage() {
  const [loading, setLoading] = useState(false);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [summary, setSummary] = useState<{ threats_caught: number; safe_commands_passed: number; protection_rate: string } | null>(null);
  const [error, setError] = useState("");

  async function runDemo() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/demo`);
      if (!res.ok) throw new Error("Demo endpoint failed");
      const data = await res.json();
      setScenarios(data.scenarios || []);
      setSummary(data.summary);
    } catch {
      setError("Could not reach the API. Is the server running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { runDemo(); }, []);

  const actionStyle = (action: string) =>
    action === "BLOCKED" ? { background: "rgba(220,38,38,.12)", borderColor: "rgba(220,38,38,.4)", color: "#dc2626" } :
    action === "WARNING" ? { background: "rgba(249,115,22,.1)", borderColor: "rgba(249,115,22,.3)", color: "#f97316" } :
    { background: "rgba(34,197,94,.08)", borderColor: "rgba(34,197,94,.25)", color: "#22c55e" };

  return (
    <div className="demo-page">
      <div className="demo-hero">
        <p className="eyebrow">Judge Demo</p>
        <h2>BashGuard Live Scenarios</h2>
        <p className="muted">5 real-world scenarios. See how BashGuard intercepts disasters before they happen.</p>
        {summary && (
          <div className="demo-summary">
            <div className="demo-summary-stat"><strong style={{ color: "#ef4444" }}>{summary.threats_caught}</strong><span>Threats caught</span></div>
            <div className="demo-summary-stat"><strong style={{ color: "#22c55e" }}>{summary.safe_commands_passed}</strong><span>Safe passed</span></div>
            <div className="demo-summary-stat"><strong style={{ color: "#6366f1" }}>{summary.protection_rate}</strong><span>Protection rate</span></div>
          </div>
        )}
        <Button className="subtle" onClick={runDemo} disabled={loading}>{loading ? "Loading…" : "↻ Refresh"}</Button>
      </div>

      {error && <div className="notice error-notice">{error}</div>}

      <div className="demo-grid">
        {scenarios.map((s, i) => (
          <div key={i} className="demo-card" style={{ borderColor: actionStyle(s.action_taken).borderColor }}>
            <div className="demo-card-header">
              <div>
                <span className="demo-category">{s.category}</span>
                <h3>{s.scenario}</h3>
                <p className="muted">{s.description}</p>
              </div>
              <span className="demo-action-badge" style={actionStyle(s.action_taken)}>
                {s.action_taken === "BLOCKED" ? "BLOCKED" : s.action_taken === "WARNING" ? "WARNING" : "ALLOWED"}
              </span>
            </div>
            <code className="demo-command">{s.command}</code>
            <div className="demo-sandbox-row">
              <span>Files before: <strong>{s.sandbox.files_before}</strong></span>
              <span>→</span>
              <span>Files after: <strong style={{ color: s.sandbox.files_after < s.sandbox.files_before ? "#ef4444" : "inherit" }}>{s.sandbox.files_after}</strong></span>
              {s.sandbox.data_destroyed && s.sandbox.data_destroyed !== "0 B" && (
                <span style={{ color: "#ef4444" }}>{s.sandbox.data_destroyed} lost</span>
              )}
            </div>
            {s.sandbox.impact && <p className="demo-impact">{s.sandbox.impact}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Code Engine Tab ──────────────────────────────────────────────────────────

type CodeResult = {
  request: string;
  language: string;
  filename: string;
  code: string;
  explanation: string;
  how_to_run: string;
  dependencies: string[];
  file_saved_to: string;
  run_output: string;
  run_success: boolean;
  error: string;
};

function CoderTab() {
  const [request, setRequest] = useState("");
  const [language, setLanguage] = useState("");
  const [result, setResult] = useState<CodeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function generate(e: FormEvent) {
    e.preventDefault();
    if (!request.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: request.trim(), language: language.trim(), auto_run: false }),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Code generation failed");
    } finally {
      setLoading(false);
    }
  }

  function copyCode() {
    if (!result?.code) return;
    navigator.clipboard.writeText(result.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section style={{ padding: "48px 0 96px" }}>
      <div className="section-heading" style={{ marginBottom: 32 }}>
        <div>
          <p className="eyebrow">AI-powered code generation</p>
          <h2>Code Engine</h2>
          <p className="muted" style={{ marginTop: 8 }}>
            Describe what you want to build in plain English. BashGuard generates complete, working code in any language.
          </p>
        </div>
      </div>

      <form onSubmit={generate} className="coder-form">
        <label>
          What do you want to build?
          <textarea
            rows={3}
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="e.g. Write a Python script that reads a CSV and plots a bar chart"
            disabled={loading}
          />
        </label>
        <div className="coder-form-row">
          <label style={{ flex: 1 }}>
            Language <span className="optional">Optional — auto-detected if blank</span>
            <input
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              placeholder="e.g. Python, JavaScript, Go, Rust..."
              disabled={loading}
            />
          </label>
          <Button className="primary coder-submit" type="submit" disabled={loading || !request.trim()}>
            {loading ? "Generating…" : "Generate code →"}
          </Button>
        </div>
        <p className="privacy-note">Code is saved to the generated_code/ folder on the server.</p>
      </form>

      {error && <div className="notice error-notice" style={{ marginTop: 24 }}>{error}</div>}

      {result && (
        <div className="coder-result">
          <div className="coder-result-header">
            <div>
              <p className="eyebrow">Generated</p>
              <h3>{result.filename}</h3>
              <span className="coder-lang-badge">{result.language}</span>
            </div>
            <Button className="subtle" onClick={copyCode}>
              {copied ? "Copied!" : "Copy code"}
            </Button>
          </div>

          <pre className="coder-code"><code>{result.code}</code></pre>

          <div className="coder-meta">
            {result.explanation && (
              <div className="coder-meta-block">
                <p className="eyebrow">What it does</p>
                <p>{result.explanation}</p>
              </div>
            )}
            {result.how_to_run && (
              <div className="coder-meta-block">
                <p className="eyebrow">How to run</p>
                <code>{result.how_to_run}</code>
              </div>
            )}
            {result.dependencies && result.dependencies.length > 0 && (
              <div className="coder-meta-block">
                <p className="eyebrow">Dependencies</p>
                <div className="coder-deps">
                  {result.dependencies.map((d, i) => (
                    <span key={i} className="coder-dep">{d}</span>
                  ))}
                </div>
              </div>
            )}
            {result.file_saved_to && (
              <div className="coder-meta-block">
                <p className="eyebrow">Saved to</p>
                <code>{result.file_saved_to}</code>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}


// ─── Unified Omni-Agent Tab ──────────────────────────────────────────────────

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

function OmniAgentTab() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AgentChatResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [decisionMsg, setDecisionMsg] = useState("");

  const samplePrompts = [
    "create a folder called test_game and write a snake game in python inside it",
    "judge what files on my laptop are necessary and what are trash in Downloads",
    "clean trash in my downloads",
    "find file server and show me what's inside",
    "fetch my github repositories and recent commits",
    "simulate rm -rf /"
  ];

  async function handleSubmit(e: FormEvent | null, customPrompt?: string) {
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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
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
    } catch {
      setError("Failed to clean trash.");
    } finally {
      setCleaning(false);
    }
  }

  async function handleDecision(action: "execute" | "reject") {
    if (!result?.simulation) return;
    try {
      const res = await fetch(`${API_URL}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "execute"
            ? {
                command: result.simulation.planned_command,
                risk_level: result.simulation.risk_level,
                use_safer: false,
              }
            : {
                command: result.simulation.planned_command,
                reason: "Rejected in Omni Agent",
              }
        ),
      });
      const data = await res.json();
      setDecisionMsg(action === "execute" ? (data.success ? "Command executed safely!" : data.error) : "Command rejected.");
    } catch {
      setError("Failed to submit decision.");
    }
  }

  function copyCode() {
    if (!result?.code_result?.code) return;
    navigator.clipboard.writeText(result.code_result.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section style={{ padding: "40px 0 96px" }}>
      <div className="section-heading" style={{ marginBottom: 28 }}>
        <div>
          <p className="eyebrow">Unified Autonomous Agent</p>
          <h2 style={{ fontSize: 38 }}>One Window. Total Control.</h2>
          <p className="muted" style={{ marginTop: 8, fontSize: 16 }}>
            Ask anything in natural language: create folders & write code, classify trash vs essential files, fuzzy search by prefix, or inspect your GitHub.
          </p>
        </div>
      </div>

      {/* Omnibar Input Card */}
      <form className="omni-prompt-card" onSubmit={(e) => handleSubmit(e)}>
        <textarea
          className="omni-textarea"
          placeholder="e.g. 'create a folder called test_game and write a snake game in python inside it', 'judge what files in Downloads are trash vs necessary', or 'find server and show me what is inside'..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={loading}
          rows={3}
        />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14 }}>
          <div className="quick-pills">
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--body)", alignSelf: "center" }}>Quick Prompts:</span>
            {samplePrompts.slice(0, 4).map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="quick-pill"
                onClick={() => {
                  setPrompt(p);
                  handleSubmit(null, p);
                }}
              >
                {p.length > 34 ? p.substring(0, 34) + "…" : p}
              </button>
            ))}
          </div>

          <Button className="primary" type="submit" disabled={loading || !prompt.trim()} style={{ minWidth: 160 }}>
            {loading ? "Agent Thinking & Executing…" : "Run Omni Agent →"}
          </Button>
        </div>
      </form>

      {error && <div className="notice error-notice" style={{ marginTop: 24 }}>{error}</div>}

      {/* Dynamic Results */}
      {result && (
        <div style={{ marginTop: 36, display: "grid", gap: 24 }}>
          {/* Steps Timeline */}
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

          {/* Conversational Explanation Banner */}
          <div className="notice" style={{ background: "var(--soft)", color: "var(--ink)", border: "1px solid var(--pressed)" }}>
            <p style={{ margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.6, fontSize: 15 }}>
              {result.message}
            </p>
          </div>

          {/* 1. Storage Intelligence Card */}
          {result.storage_analysis && (
            <div className="command-card" style={{ border: "1px solid var(--pressed)", padding: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <p className="eyebrow">Smart Storage Analysis</p>
                  <h3 style={{ margin: "4px 0", fontSize: 20 }}>Disk & Media Intelligence</h3>
                  <span className="muted" style={{ fontSize: 13 }}>Scanned: {result.storage_analysis.target_path} ({result.storage_analysis.total_size_readable})</span>
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
                  <span style={{ fontSize: 13, color: "var(--body)" }}>{result.storage_analysis.trash.readable} total temporary cache, old installers & duplicate data</span>
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

              {/* Sample Trash Items List */}
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

          {/* 2. Code Generation Result Card */}
          {result.code_result && (
            <div className="coder-result" style={{ marginTop: 0 }}>
              <div className="coder-result-header">
                <div>
                  <p className="eyebrow">Synthesized Code</p>
                  <h3>{result.code_result.filename}</h3>
                  <span className="coder-lang-badge">{result.code_result.language}</span>
                  {result.code_result.saved_to && (
                    <span style={{ marginLeft: 12, fontSize: 12, color: "var(--body)", fontFamily: "monospace" }}>
                      📁 Saved in {result.code_result.saved_to}
                    </span>
                  )}
                </div>
                <Button className="subtle" onClick={copyCode}>
                  {copied ? "Copied!" : "Copy code"}
                </Button>
              </div>
              <pre className="coder-code"><code>{result.code_result.code}</code></pre>
            </div>
          )}

          {/* 3. GitHub Data Card */}
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

          {/* 4. Dangerous Command Simulation & Approval */}
          {result.simulation && (
            <div className="result-main" style={{ marginTop: 0 }}>
              <div className="command-preview">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>Command Consequence Assessment</span>
                  <span className="risk-pill" style={{ background: riskColor(result.simulation.risk_level), color: "#fff" }}>
                    {result.simulation.risk_level} Risk ({result.simulation.risk_score}/100)
                  </span>
                </div>
                <code>{result.simulation.planned_command}</code>
              </div>

              <div className="impact-stats">
                <div><strong>{result.simulation.total_files_count}</strong><span>Files affected</span></div>
                <div><strong>{formatBytes(result.simulation.total_size_bytes)}</strong><span>Data affected</span></div>
                <div><strong>{result.simulation.is_reversible ? "Yes" : "No"}</strong><span>Reversible</span></div>
                <div><strong>{result.simulation.simulation_confidence}</strong><span>Confidence</span></div>
              </div>

              {result.requires_approval && (
                <div style={{ padding: "20px 24px", background: "#fff1f2", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                  <span style={{ fontWeight: 600, color: "#9f1239", fontSize: 14 }}>
                    ⚠️ This action is dangerous. Do you wish to approve execution?
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
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

type Tab = "omni" | "simulator" | "terminal" | "history" | "demo" | "coder";

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("omni");
  const [command, setCommand] = useState("");
  const [context, setContext] = useState("");
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [sandboxData, setSandboxData] = useState<SandboxResult | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/`).then((r) => { if (r.ok) setApiOnline(true); }).catch(() => setApiOnline(false));
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const res = await fetch(`${API_URL}/history?limit=8`);
      if (res.ok) setHistory(await res.json());
    } catch { /* server offline */ }
  }

  async function simulate(event: FormEvent) {
    event.preventDefault();
    if (!command.trim()) return;
    setLoading(true);
    setError("");
    setMessage("");
    setSimulation(null);
    setSandboxData(null);
    try {
      // Use /analyze (combined endpoint) instead of /simulate
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, context }),
      });
      if (!res.ok) throw new Error("The simulation could not be completed.");
      const data = await res.json();
      setSimulation(data.simulation);
      setSandboxData(data.sandbox);
    } catch {
      setError("BashGuard API is offline. Start the server on port 8001, then try again.");
    } finally {
      setLoading(false);
    }
  }

  async function decide(action: "execute" | "reject", useSafer = false) {
    if (!simulation) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "execute"
            ? { command: simulation.planned_command, risk_level: simulation.risk_level, use_safer: useSafer, safer_command: simulation.safer_command }
            : { command: simulation.planned_command, reason: "User rejected in dashboard" },
        ),
      });
      if (!res.ok) throw new Error();
      const result = await res.json();
      setMessage(
        action === "reject"
          ? "Command rejected. Nothing was executed."
          : result.was_blocked
            ? "Command permanently blocked by BashGuard."
            : result.success
              ? "Command executed successfully."
              : result.error || "Command execution failed.",
      );
      await loadHistory();
    } catch {
      setError("The API request failed. Verify that the BashGuard server is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header>
        <Brand />
        <nav aria-label="Primary navigation">
          <a href="#" onClick={() => setTab("omni")} className={tab === "omni" ? "nav-active" : ""}>Omni Agent</a>
          <a href="#" onClick={() => setTab("simulator")} className={tab === "simulator" ? "nav-active" : ""}>Simulator</a>
          <a href="#" onClick={() => setTab("terminal")} className={tab === "terminal" ? "nav-active" : ""}>Terminal Hook</a>
          <a href="#" onClick={() => setTab("coder")} className={tab === "coder" ? "nav-active" : ""}>Code Engine</a>
          <a href="#" onClick={() => setTab("history")} className={tab === "history" ? "nav-active" : ""}>Audit log</a>
          <a href="#" onClick={() => setTab("demo")} className={tab === "demo" ? "nav-active" : ""}>Demo</a>
          <a href="https://github.com/cypher07-ai/ai-agent-hackathon" rel="noreferrer" target="_blank">GitHub</a>
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
        {/* ── Omni Agent Tab ── */}
        {tab === "omni" && <OmniAgentTab />}

        {/* ── Simulator Tab ── */}
        {tab === "simulator" && (
          <>
            <section className="hero" id="simulator">
              <div className="hero-copy">
                <p className="eyebrow">Command safety agent</p>
                <h1>Know the impact.<br />Then execute.</h1>
                <p>BashGuard predicts the blast radius of system commands before they touch your machine. You stay in control at every step.</p>
                <div className="trust-row">
                  <span>01&nbsp; Simulate</span>
                  <span>02&nbsp; Review</span>
                  <span>03&nbsp; Approve</span>
                </div>
              </div>

              <form className="command-card" onSubmit={simulate}>
                <div className="card-heading">
                  <div>
                    <p className="eyebrow">New simulation</p>
                    <h2>What do you want to do?</h2>
                  </div>
                  <span className="status"><i style={{ background: apiOnline ? "#22c55e" : "#ef4444" }} /> {apiOnline ? "API ready" : "API offline"}</span>
                </div>
                <label>
                  Command or request
                  <textarea onChange={(e) => setCommand(e.target.value)} placeholder="e.g. Delete all log files older than 30 days" rows={4} value={command} />
                </label>
                <label>
                  System context <span className="optional">Optional</span>
                  <input onChange={(e) => setContext(e.target.value)} placeholder="e.g. Production Linux server" value={context} />
                </label>
                <Button className="primary submit-button" disabled={loading || !command.trim()} type="submit">
                  {loading ? "Analyzing consequences…" : "Simulate command"}
                  {!loading && <span aria-hidden="true">→</span>}
                </Button>
                <p className="privacy-note">Nothing executes during simulation.</p>
              </form>
            </section>

            {error && <div className="notice error-notice">{error}</div>}
            {message && <div className="notice">{message}</div>}

            {simulation && (
              <section className="results">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Simulation report</p>
                    <h2>Review before approval</h2>
                  </div>
                  <span className="risk-pill" style={{ background: riskColor(simulation.risk_level), color: "#fff" }}>
                    {simulation.risk_level} risk
                  </span>
                </div>
                <div className="result-grid">
                  <article className="result-main">
                    <div className="command-preview">
                      <span>Planned command</span>
                      <code>{simulation.planned_command}</code>
                    </div>
                    <p className="explanation">{simulation.command_explanation}</p>
                    <div className="impact-stats">
                      <div><strong>{simulation.total_files_count}</strong><span>Files affected</span></div>
                      <div><strong>{formatBytes(simulation.total_size_bytes)}</strong><span>Data affected</span></div>
                      <div><strong>{simulation.is_reversible ? "Yes" : "No"}</strong><span>Reversible</span></div>
                      <div><strong>{simulation.simulation_confidence}</strong><span>Confidence</span></div>
                    </div>
                    {(simulation.risk_reasons.length > 0 || simulation.warnings.length > 0) && (
                      <div className="reasons">
                        <h3>What needs your attention</h3>
                        {[...simulation.risk_reasons, ...simulation.warnings].map((r, i) => (
                          <p key={i}><span>{i + 1}</span>{r}</p>
                        ))}
                      </div>
                    )}
                    {simulation.safer_command && (
                      <div className="safer">
                        <p className="eyebrow">Safer alternative</p>
                        <h3>{simulation.safer_alternative}</h3>
                        <code>{simulation.safer_command}</code>
                      </div>
                    )}

                    {/* Sandbox diff */}
                    {sandboxData && <SandboxPanel sandbox={sandboxData} />}
                  </article>

                  <aside className="risk-panel">
                    <RiskDial label={simulation.risk_level} value={simulation.risk_score} />
                    <div className="decision-copy">
                      <h3>{simulation.requires_approval ? "Your approval is required" : "Safe to proceed"}</h3>
                      <p>BashGuard will never execute this command without your decision.</p>
                    </div>
                    <Button className="primary" disabled={loading} onClick={() => decide("execute")}>Approve and execute</Button>
                    {simulation.safer_command && (
                      <Button className="subtle" disabled={loading} onClick={() => decide("execute", true)}>Use safer version</Button>
                    )}
                    <Button className="text-button" disabled={loading} onClick={() => decide("reject")}>Reject command</Button>
                  </aside>
                </div>
              </section>
            )}
          </>
        )}

        {/* ── Terminal Hook Tab ── */}
        {tab === "terminal" && (
          <section style={{ padding: "48px 0" }}>
            <div className="section-heading" style={{ marginBottom: 32 }}>
              <div>
                <p className="eyebrow">Real-time interception</p>
                <h2>Terminal Hook</h2>
                <p className="muted" style={{ marginTop: 8 }}>Type any command. BashGuard intercepts it, runs a full analysis + sandbox simulation, and shows the blast radius instantly — before a single byte changes.</p>
              </div>
            </div>
            <TerminalHookPanel />
            <div className="hook-setup" style={{ marginTop: 32 }}>
              <p className="eyebrow">Setup real-time terminal protection</p>
              <div className="hook-steps">
                <div className="hook-step">
                  <span>1</span>
                  <div>
                    <strong>Windows (PowerShell)</strong>
                    <code>. .\bashguard_hook.ps1</code>
                    <small>Run in your PowerShell terminal to intercept every command you type</small>
                  </div>
                </div>
                <div className="hook-step">
                  <span>2</span>
                  <div>
                    <strong>Linux / Mac (Bash)</strong>
                    <code>source ./bashguard_hook.sh</code>
                    <small>Adds a preexec hook to your shell session</small>
                  </div>
                </div>
                <div className="hook-step">
                  <span>3</span>
                  <div>
                    <strong>Disable anytime</strong>
                    <code>bashguard-off</code>
                    <small>Disables the hook without closing your terminal</small>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── History Tab ── */}
        {tab === "history" && (
          <section className="history-section" id="history">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Permanent audit trail</p>
                <h2>Recent activity</h2>
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
                  <p>Your approved, rejected, and blocked commands will appear here.</p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ── Demo Tab ── */}
        {tab === "demo" && <DemoPage />}

        {/* ── Code Engine Tab ── */}
        {tab === "coder" && <CoderTab />}
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

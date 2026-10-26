# BashGuard — Simulate Before You Execute

An AI agent with a **simulate-first architecture** that predicts the consequences of system commands **before** executing them, paired with an autonomous **Unified Omni-Agent**, **Storage Intelligence**, and **Live GitHub Integrations**.

> *"The AI agent that shows you what will happen — before it happens."*

---

## Quick Start (Windows)

```bat
start.bat
```

The script installs all dependencies, starts both backend (port 8001) and React frontend (port 5173), and opens the app in your browser automatically.

> **Requires**: Python 3.9+, Node.js 18+

---

## Key Features

- **Unified Omni-Agent (One Window for Everything)** — Scaffolds directories, generates multi-language code, inspects storage, resolves files, and simulates commands seamlessly in a single conversation window without tab switching.
- **Smart Storage Intelligence (Trash vs. Necessary Judge)** — Analyzes disk storage, cache directories (`__pycache__`, `.tmp`, `.dmp`, `.log`), stale installers (`.msi`, `.exe`), and duplicate files. Calculates reclaimable disk space and safely quarantines trash with rollback.
- **Fuzzy / Prefix File Search & Auto-Modification** — Type just the prefix or partial name (e.g. `serv` ➔ `server.py`, `app` ➔ `App.tsx`). Finds the exact file, previews its content, and edits, creates, or safely deletes it.
- **Live GitHub & System App Connectors** — Integrates with GitHub CLI and Git to fetch repositories, commits, branches, issues, and perform automated commits/pushes. Launches local tools (VS Code, Explorer, Terminal).
- **Virtual Filesystem Sandbox** — Real filesystem differential scanning showing BEFORE vs AFTER diffs, destroyed byte counts, and exact files affected.
- **Blast Radius Analysis & 4-Level Risk Scoring** — CRITICAL / HIGH / MEDIUM / LOW with numerical risk score (0–100) and non-destructive safer alternatives.
- **Hard Block List & Immutable Audit Trail** — Instant blocking of catastrophic commands (`rm -rf /`, `mkfs`, fork bombs) with microsecond audit logs.
- **Authentication System** — Salted SHA-256 encrypted passwords in SQLite with 24-hour bearer session tokens.

---

## Architecture

```
                                USER PROMPT / COMMAND
                     ("create folder game & write snake in python",
                      "judge what files are trash vs necessary",
                      "find server and show content", "rm -rf /")
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │       Omni-Agent Core         │
                       │      (unified_agent.py)       │
                       └───────────────┬───────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
 [ Storage Intel ]            [ Multi-Step Planner ]          [ Consequence Engine ]
    (intel.py)                     (coder.py)                    (simulator.py)
 • Trash vs Necessary         • Folder Scaffolding            • Blast Radius Analysis
 • Duplicate Detection        • Multi-Language Code           • Virtual Sandbox Diff
 • Quarantine & Rollback      • Direct File Writing           • 4-Tier Risk Scoring
       │                               │                               │
       └───────────────────────────────┼───────────────────────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   GitHub & System Tools   │
                         │     (integrations.py)     │
                         │ • Repos, Commits, PRs     │
                         │ • Git Push & Commit       │
                         │ • VS Code & App Launchers │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                          Unified Interactive Web UI
                           (React 19 / Port 5173)
```

---

## Project Structure

```
ai-agent-hackathon/
├── frontend/               ← React 19 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── App.tsx         ← Omni Agent + Dashboard + Simulator + Auth UI
│   │   ├── main.tsx        ← React entry point
│   │   └── index.css       ← Modern UI styles & badges
│   ├── package.json
│   └── vite.config.ts
├── unified_agent.py        ← Central Omni-Agent coordinator
├── intel.py                ← Storage intelligence & fuzzy file resolver
├── integrations.py         ← GitHub CLI & System application connectors
├── simulator.py            ← Gemini-powered consequence simulation engine
├── sandbox.py              ← Virtual filesystem sandbox (BEFORE/AFTER diff)
├── executor.py             ← Safe execution + audit logging
├── rollback.py             ← Auto-generate inverse undo commands
├── coder.py                ← Autonomous code generator in any language
├── auth.py                 ← SQLite auth with salted SHA-256 tokens
├── server.py               ← FastAPI REST backend (25+ endpoints)
├── agent.py                ← CLI: interactive + 20 eval benchmarks
├── bashguard_hook.ps1      ← Windows PowerShell real-time interceptor
├── bashguard_hook.sh       ← Linux/macOS command override hook
├── start.bat               ← Automated Windows launcher
├── start.sh                ← Unix/Mac launcher
├── requirements.txt        ← Python dependencies
└── README.md               ← Documentation
```

---

## API Endpoints

### Omni-Agent & Intelligence
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/chat` | **Unified Omni-Agent** — Handles commands, code, folder scaffolding, storage, fuzzy search & GitHub |
| POST | `/intel/classify-storage` | Classify directory into TRASH, REVIEW, and ESSENTIAL |
| POST | `/intel/clean-trash` | Safely clean or quarantine trash files with rollback |
| POST | `/intel/resolve-file` | Fuzzy / prefix file search (`serv` ➔ `server.py`) |
| POST | `/intel/file-action` | Read, edit, append, delete, or move resolved files |

### GitHub & System Integrations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/integrations/github` | Connected GitHub profile, live repos, and recent commits |
| POST | `/integrations/github/action` | Perform Git operations (status, commit, push, clone) |
| GET | `/integrations/system` | System hardware specs, CPU cores, disk drives & usage |
| POST | `/integrations/launch-app` | Launch VS Code, File Explorer, or Terminal |

### Core Simulation & Safe Execution
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/simulate` | AI-powered simulation — blast radius analysis |
| POST | `/sandbox` | Virtual filesystem execution — BEFORE/AFTER diff |
| POST | `/analyze` | Combined fast-detection + AI simulation + sandbox |
| POST | `/execute` | Execute command after user approval |
| POST | `/reject` | Log rejected command to audit trail |
| POST | `/rollback` | Generate undo recovery command |

### Code Generation & Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/code` | Generate code in any programming language |
| POST | `/code/detect` | Detect programming language from prompt |
| GET | `/auth/status` | Check if user is registered & token validity |
| POST | `/auth/register` | Initial administrator setup |
| POST | `/auth/login` | Login and receive 24-hour session token |
| POST | `/auth/logout` | Invalidate session token |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS |
| **Backend** | FastAPI, Python 3.9+, Uvicorn, Pydantic v2 |
| **AI Engine** | Google Gemini API (`gemini-3.5-flash-lite`) |
| **Integrations** | GitHub CLI (`gh`), Git, SQLite3 |
| **OS Hooks** | PowerShell PSReadLine (Win), POSIX command overrides (Linux/macOS) |

---

Built at Hackathon — October 2026

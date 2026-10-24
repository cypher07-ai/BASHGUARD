# 🛡️ BashGuard — Simulate Before You Execute

An AI-powered safety layer that **intercepts dangerous commands in real-time**, simulates their blast radius, and prevents catastrophic mistakes — all before a single byte is touched.

> *"The AI agent that shows you what will happen — before it happens."*

## Features

- 🔍 **Real-Time Terminal Protection** — Hooks into PowerShell and intercepts dangerous commands BEFORE they execute
- 📊 **Blast Radius Analysis** — Shows exactly what files, data, and processes will be affected
- 🎯 **4-Level Risk Scoring** — CRITICAL / HIGH / MEDIUM / LOW with reasons
- 💡 **Safer Alternatives** — AI suggests less risky commands that achieve the same goal
- 🔄 **Auto-Rollback** — Generates undo commands for every executed action
- 🚨 **Hard Block List** — Catastrophic commands are blocked no matter what
- 📜 **Audit Trail** — Every action is permanently logged with timestamps
- ⚖️ **Side-by-Side Comparison** — Shows what happens WITH vs WITHOUT BashGuard
- 🌐 **REST API** — Full API for frontend/dashboard integration

## Architecture

```
REAL-TIME MODE (PowerShell Hook):
  User types command → Hits Enter → BashGuard intercepts →
  Simulation runs → Warning shown → User approves/cancels → 
  Command executes or is blocked

API MODE (Web Frontend):
  Frontend → POST /simulate → Blast radius returned →
  User approves → POST /execute → Command runs →
  POST /rollback → Undo command generated
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set API Key
Create a `.env` file:
```
GEMINI_API_KEY=your_key_here
```

### 3. Start the Server
```bash
python server.py
```

### 4. Activate Real-Time Terminal Protection
Open a NEW PowerShell window:
```powershell
cd path\to\ai-agent-hackathon
. .\bashguard_hook.ps1
```

Now type any command — BashGuard is watching. Try:
- `dir` → Runs normally (safe)
- `rm -rf /` → BLOCKED instantly
- `del /s /q *.*` → Simulation + warning + approve/cancel
- `git push --force` → Caught, safer alternative offered

### 5. CLI Mode (Alternative)
```bash
python agent.py
```

### 6. Evaluation Mode
```bash
python agent.py --eval
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulate` | POST | Simulate a command, get blast radius |
| `/execute` | POST | Execute after approval |
| `/reject` | POST | Log a rejected command |
| `/rollback` | POST | Generate undo command |
| `/history` | GET | Full audit trail |
| `/stats` | GET | Dashboard statistics |
| `/compare` | GET | WITH vs WITHOUT BashGuard comparison |
| `/check` | GET | Quick block-list check |

## File Structure

```
├── server.py           ← FastAPI backend (8 endpoints)
├── simulator.py        ← LLM + filesystem simulation engine
├── executor.py         ← Safe execution + audit logging
├── rollback.py         ← Auto-generate undo commands
├── agent.py            ← CLI mode + evaluation mode
├── bashguard_hook.ps1  ← Real-time PowerShell interceptor
├── audit_log.json      ← Persistent action history
├── .env                ← API keys (not tracked)
├── requirements.txt    ← Dependencies
└── README.md           ← This file
```

## Tech Stack

- **LLM:** Google Gemini API (gemini-3.5-flash-lite)
- **Backend:** Python + FastAPI
- **Terminal Hook:** PowerShell PSReadLine
- **Analysis:** Real filesystem inspection + LLM consequence prediction

## Team

Built at Hackathon — October 2026

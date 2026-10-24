# BashGuard — Simulate Before You Execute

An AI-powered safety layer that **intercepts dangerous commands in real-time**, simulates their blast radius in a **virtual sandbox**, and prevents catastrophic mistakes — all before a single byte is touched.

> *"The AI agent that shows you what will happen — before it happens."*

## Features

- **Virtual Sandbox** — Scans the REAL filesystem, "executes" commands virtually, shows BEFORE vs AFTER diff with every file that would be destroyed
- **Real-Time Terminal Protection** — Hooks into PowerShell (Windows) AND Bash (Linux/Mac) to intercept dangerous commands BEFORE they execute
- **Dual Detection** — Catches both raw commands (`rm -rf`, `chmod 777`) AND natural language requests
- **Blast Radius Analysis** — Shows exactly what files, data, and processes will be affected
- **4-Level Risk Scoring** — CRITICAL / HIGH / MEDIUM / LOW with reasons
- **Safer Alternatives** — AI suggests less risky commands that achieve the same goal
- **Auto-Rollback** — Generates undo commands for every executed action
- **Hard Block List** — Catastrophic commands are blocked no matter what
- **Audit Trail** — Every action is permanently logged with timestamps
- **Side-by-Side Comparison** — Shows what happens WITH vs WITHOUT BashGuard
- **Code Generation Engine** — Write working code in any language from natural language prompts
- **Authentication System** — Register/Login with hashed passwords + session tokens
- **Docker Support** — Containerized deployment ready
- **REST API** — 20 endpoints for frontend/dashboard integration
- **Cross-Platform** — Works on Windows, Linux, and macOS

## Architecture

```
                     USER INPUT
          (raw command OR natural language)
                        |
               +--------v--------+
               |  RAW COMMAND?   |  <-- Instant regex detection
               |  rm, del, chmod |      (no LLM needed)
               +---+--------+---+
                   |YES      |NO
           +-------v---+  +--v----------+
           |  SANDBOX  |  | LLM PLANNER |
           | Scan FS   |  | Parse intent|
           | Virtual   |  | Plan command|
           | Execution |  +--+----------+
           | BEFORE/   |     |
           | AFTER diff|  +--v----------+
           +---+-------+  |  SANDBOX    |
               |          |  + LLM SIM  |
               |          +--+----------+
               +------+------+
                      |
            +---------v---------+
            |   RISK ASSESSMENT  |
            | CRITICAL/HIGH/MED  |
            +---------+---------+
                      |
            +---------v---------+
            |  APPROVAL GATE    |
            | Approve / Safer   |
            | Cancel            |
            +---------+---------+
                      |
            +---------v---------+
            |  EXECUTE + LOG    |
            |  Rollback ready   |
            +-------------------+
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
API docs: http://localhost:8000/docs

### 4. Activate Real-Time Terminal Protection

**Windows (PowerShell):**
```powershell
cd path\to\ai-agent-hackathon
. .\bashguard_hook.ps1
```

**Linux / Mac (Bash):**
```bash
cd path/to/ai-agent-hackathon
source ./bashguard_hook.sh
```

Now type any command — BashGuard is watching. Try:
- `dir` / `ls` → Runs normally (safe)
- `rm -rf /` → BLOCKED instantly
- `del /s /q *.*` → Sandbox + Simulation + warning + approve/cancel
- `git push --force` → Caught, safer alternative offered
- `chmod 777` → Permission change detected, security warning

### 5. CLI Mode (Interactive)
```bash
python agent.py
```
Accepts BOTH raw commands and natural language:
- Type `rm -rf /home/user` → Raw command detected → Sandbox shows destruction
- Type `delete all my log files` → AI plans the command → Simulates → Shows preview

### 6. Evaluation Mode
```bash
python agent.py --eval      # LLM simulation accuracy test (20 test cases)
python agent.py --sandbox   # Sandbox detection + filesystem sim test
```

### 7. Docker
```bash
docker build -t bashguard .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key bashguard
```

## API Endpoints

### Core Simulation (6 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulate` | POST | AI-powered simulation — blast radius analysis |
| `/sandbox` | POST | **Virtual filesystem execution** — BEFORE/AFTER diff |
| `/analyze` | POST | **Combined** — instant detection + AI sim + sandbox |
| `/execute` | POST | Execute after user approval |
| `/reject` | POST | Log a rejected command |
| `/rollback` | POST | Generate undo command |

### Authentication (6 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/status` | GET | Check if user is registered + if token is valid |
| `/auth/register` | POST | First-time setup — set username + password |
| `/auth/login` | POST | Login — returns a session token |
| `/auth/logout` | POST | Invalidate session token |
| `/auth/me` | GET | Get current user info (requires token) |
| `/auth/change-password` | POST | Change password (requires current password) |

### Code Generation (2 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/code` | POST | Generate working code in any language from natural language |
| `/code/detect` | POST | Detect programming language from a prompt |

### Data & Dashboard (5 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check — returns server info |
| `/history` | GET | Full audit trail |
| `/stats` | GET | Dashboard statistics |
| `/compare` | GET | WITH vs WITHOUT BashGuard comparison |
| `/check` | GET | Quick block-list check |

### Demo (1 endpoint)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/demo` | GET | **Judge demo** — 5 pre-built scenarios, no input needed |

### Example: POST `/analyze`
```json
// Request
{"command": "rm -rf ~/projects"}

// Response
{
  "is_raw_command": true,
  "instant_danger_level": "HIGH",
  "simulation": { "risk_level": "CRITICAL", "risk_score": 95 },
  "sandbox": {
    "before_file_count": 1547,
    "after_file_count": 0,
    "data_destroyed_readable": "2.3 GB",
    "destruction_percentage": 100.0,
    "is_catastrophic": true,
    "files_deleted": ["..."]
  },
  "recommendation": "BLOCK"
}
```

### Example: POST `/auth/register`
```json
// Request
{"username": "admin", "password": "SecurePass123"}

// Response
{"status": "registered", "username": "admin"}
```

### Example: POST `/auth/login`
```json
// Request
{"username": "admin", "password": "SecurePass123"}

// Response
{"status": "success", "token": "a1b2c3d4...", "username": "admin"}
```

### Example: POST `/code`
```json
// Request
{"prompt": "write a snake game in python"}

// Response
{
  "language": "python",
  "filename": "snake_game.py",
  "code": "import pygame...",
  "explanation": "A complete Snake game using pygame..."
}
```

## File Structure

```
├── server.py             <- FastAPI backend (20 endpoints)
├── simulator.py          <- LLM + filesystem simulation engine
├── sandbox.py            <- Virtual filesystem sandbox (BEFORE/AFTER)
├── executor.py           <- Safe execution + audit logging
├── rollback.py           <- Auto-generate undo commands
├── coder.py              <- Code generation engine (any language)
├── auth.py               <- Authentication (SQLite + hashed passwords)
├── agent.py              <- CLI: interactive + eval (20 cases) + sandbox demo
├── bashguard_hook.ps1    <- Real-time PowerShell interceptor (Windows)
├── bashguard_hook.sh     <- Real-time Bash interceptor (Linux/Mac)
├── Dockerfile            <- Container deployment
├── .dockerignore         <- Docker build exclusions
├── .env                  <- API keys (not tracked)
├── requirements.txt      <- Dependencies
└── README.md             <- This file
```

## Terminal Hooks — How They Work

### Windows (PowerShell)
Uses **PSReadLine `PreCommandHandler`** to intercept every command before PowerShell runs it. Calls the BashGuard API, shows risk warnings with color-coded output, and requires user approval for dangerous commands.

### Linux / Mac (Bash)
Uses **command override functions** — wraps dangerous commands (`rm`, `chmod`, `kill`, `git`, `dd`, `mkfs`, `systemctl`, `iptables`, etc.) with bash functions that call BashGuard first. Safe commands (`ls`, `cat`, `cd`, `pwd`, etc.) pass through unmodified.

Enable/disable at any time:
```bash
bashguard-on       # Activate protection
bashguard-off      # Deactivate
bashguard-status   # Check if active
```

## Evaluation Results

```
  === LLM Simulation Accuracy ===
  Dangerous commands caught: 12/12 (100%)
  False positives:           0/8
  Overall accuracy:          100%

  === Raw Command Detection ===
  Raw commands detected:     5/5
  Sandbox simulations:       4/5
```

## Tech Stack

- **LLM:** Google Gemini API (gemini-3.5-flash-lite)
- **Backend:** Python + FastAPI
- **Auth:** SQLite + SHA-256 salted password hashing + session tokens
- **Sandbox:** Virtual filesystem scanner + simulated execution
- **Code Gen:** Gemini-powered multi-language code generator
- **Terminal Hook:** PowerShell PSReadLine (Win) + Bash command overrides (Linux/Mac)
- **Container:** Docker
- **Analysis:** Real filesystem inspection + LLM consequence prediction

## Team

Built at Hackathon — October 2026

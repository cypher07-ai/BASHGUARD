# BashGuard — Simulate Before You Execute

An AI agent with a **simulate-first architecture** that predicts the consequences of system commands **before** executing them.

> *"The AI agent that shows you what will happen — before it happens."*

---

## Quick Start (Windows)

```bat
start.bat
```

That's it. The script installs all dependencies, starts both servers, and opens the app in your browser.

> **Requires**: Python 3.9+, Node.js 18+

---

## Architecture

```
User Request → Plan Command → SIMULATE (Dry Run) → Preview → Approve/Reject → Execute
```

```
Frontend (React / Figma)    Backend (FastAPI / Python)
  http://localhost:5173   →   http://localhost:8000
        ↓
   Login Page
        ↓
   Dashboard
        ↓
   Simulate Command  ──POST /simulate──▶  simulator.py (Gemini AI)
        ↓                                      ↓
   Risk Report ◀─────────────────── SimulationResult
        ↓
   User Decision
   ┌────┴────┐
Approve    Reject
   │           │
POST /execute  POST /reject
   │           │
executor.py    audit_log.json
```

---

## Project Structure

```
ai-agent-hackathon/
├── frontend/               ← React + TypeScript (Figma Make export)
│   ├── src/
│   │   ├── App.tsx         ← Login + Dashboard + Simulation UI
│   │   ├── main.tsx        ← React entry point
│   │   └── index.css       ← Figma design system + Tailwind v4
│   ├── public/favicon.svg
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── agent.py                ← Core agent (CLI + public API)
├── server.py               ← FastAPI REST backend
├── simulator.py            ← Gemini-powered simulation engine
├── executor.py             ← Safe command executor + audit log
├── .env                    ← GEMINI_API_KEY
├── requirements.txt        ← Python dependencies
├── start.bat               ← One-click Windows launcher
└── start.sh                ← Unix/Mac launcher
```

---

## Features

- **Blast Radius Analysis** — Shows exactly what files, directories, and processes will be affected
- **Risk Scoring** — CRITICAL / HIGH / MEDIUM / LOW with detailed reasons
- **Safer Alternatives** — Suggests less risky commands when possible
- **Hard Block List** — Some commands are blocked no matter what (`rm -rf /`, `format c:`, etc.)
- **Audit Log** — Every action (executed, rejected, blocked) is permanently logged
- **Login Page** — Session-based access (Figma-designed UI)

---

## Manual Setup

### Backend
```bash
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### .env
```
GEMINI_API_KEY=your_key_here
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/simulate` | Simulate a command, returns full risk analysis |
| POST | `/execute` | Execute after user approval |
| POST | `/reject` | Log a rejection |
| GET | `/history` | Audit log (last N entries) |
| GET | `/stats` | Dashboard statistics |
| GET | `/check?command=...` | Quick hard-block check |

---

## CLI Mode

```bash
# Interactive terminal mode
python agent.py

# Batch evaluation mode
python agent.py --eval
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.9+, Uvicorn |
| AI | Google Gemini 2.0 Flash Lite |
| Design | Figma Make |

---

Built at Hackathon — October 2026

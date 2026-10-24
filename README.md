# 🛡️ BashGuard — Simulate Before You Execute

An AI agent with a **simulate-first architecture** that predicts the consequences of system commands **before** executing them.

> *"The AI agent that shows you what will happen — before it happens."*

## The Problem

AI agents that execute system commands are dangerous. A simple misunderstanding can lead to:
- Deleted files that can't be recovered
- Crashed services and databases
- Security vulnerabilities
- Data loss at scale

**BashGuard** solves this by adding a **simulation layer** between intent and action.

## Architecture

```
User Request → Plan Command → SIMULATE (Dry Run) → Preview → Approve/Reject → Execute
```

Every command goes through two phases:
1. **SIMULATE** — LLM analyzes the command + real filesystem state to predict full blast radius
2. **COMMIT** — Only executes after explicit user approval

## Features

- 🔍 **Blast Radius Analysis** — Shows exactly what files, directories, and processes will be affected
- 📊 **Risk Scoring** — CRITICAL / HIGH / MEDIUM / LOW with detailed reasons
- 💡 **Safer Alternatives** — Suggests less risky commands when possible
- 🚨 **Hard Block List** — Some commands are blocked no matter what (`rm -rf /`, `format c:`, etc.)
- 📜 **Audit Log** — Every action (executed, rejected, blocked) is permanently logged
- 🧪 **Evaluation Mode** — Batch test to prove simulation catches dangerous commands

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:
```
GEMINI_API_KEY=your_key_here
```

## Usage

### Interactive Mode (Terminal)
```bash
python agent.py
```

### Evaluation Mode (Batch Test)
```bash
python agent.py --eval
```

### API Mode (For Frontend Integration)
```python
from agent import get_simulation, approve_and_execute, reject_action

# Step 1: Get simulation preview
sim = get_simulation("Delete all log files older than 30 days")

# Step 2: Show preview to user (frontend renders sim dict)

# Step 3: User approves or rejects
result = approve_and_execute(
    command=sim["planned_command"],
    risk_level=sim["risk_level"],
    use_safer=True,
    safer_command=sim["safer_command"],
)
```

## Tech Stack

- **LLM:** Google Gemini API (gemini-3.5-flash)
- **Language:** Python
- **Analysis:** Real filesystem inspection + LLM consequence prediction

## Team

Built at Hackathon — October 2026

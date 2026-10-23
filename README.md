# AI Agent — Hackathon Project

An intelligent AI agent that uses the **ReAct (Reason + Act)** pattern to solve real-world problems step by step.

## How It Works

The agent follows a loop:
1. **THINK** — Reason about the problem
2. **ACT** — Use a tool (web search, calculator, etc.)
3. **OBSERVE** — Process the tool's result
4. **REPEAT** — Until the answer is ready

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:
```
GEMINI_API_KEY=your_key_here
```

## Run

```bash
python agent.py
```

## Tech Stack

- **LLM:** Google Gemini API (gemini-3.5-flash)
- **Language:** Python
- **Tools:** Web Search (DuckDuckGo), Calculator, File Reader, Clock

## Team

Built at [Hackathon Name] — October 2026

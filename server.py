"""
BashGuard — API Server
========================
FastAPI backend that exposes BashGuard as a REST API.
The frontend hits these endpoints to simulate, approve, reject, and view history.

Run with: uvicorn server:app --reload --port 8000
"""

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Fix encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from simulator import simulate_command, SimulationResult
from executor import execute_command, get_audit_log, is_hard_blocked

# ============================================================
#  APP SETUP
# ============================================================

app = FastAPI(
    title="BashGuard API",
    description="Simulate consequences before executing system commands",
    version="1.0.0",
)

# Allow frontend to connect from any origin (for hackathon demo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  REQUEST / RESPONSE MODELS
# ============================================================

class SimulateRequest(BaseModel):
    """Request body for /simulate endpoint."""
    command: str                    # Natural language or raw command
    context: Optional[str] = ""    # Optional extra context

class ExecuteRequest(BaseModel):
    """Request body for /execute endpoint."""
    command: str                   # The exact command to run
    risk_level: str                # Risk level from simulation
    use_safer: bool = False        # Use the safer alternative?
    safer_command: str = ""        # The safer command (if use_safer=True)

class RejectRequest(BaseModel):
    """Request body for /reject endpoint."""
    command: str
    reason: str = "User rejected"


# ============================================================
#  ENDPOINTS
# ============================================================

@app.get("/")
def root():
    """Health check."""
    return {
        "name": "BashGuard API",
        "status": "running",
        "tagline": "Simulate before you execute.",
        "version": "1.0.0",
    }


@app.post("/simulate")
def simulate(req: SimulateRequest):
    """
    CORE ENDPOINT — Simulate a command and return blast radius.
    
    Frontend sends the user's command (natural language or raw).
    Backend returns full simulation with risk analysis.
    
    Example request:
        POST /simulate
        {"command": "delete all log files older than 30 days"}
    
    Example response:
        {
            "planned_command": "find /var/log -name '*.log' -mtime +30 -delete",
            "risk_level": "HIGH",
            "risk_score": 78,
            "risk_reasons": ["Permanent deletion", "Active log files may be affected"],
            "files_affected": [...],
            "total_files_count": 234,
            "total_size_bytes": 52428800,
            "is_reversible": false,
            "safer_alternative": "Archive instead of delete",
            "safer_command": "find /var/log -name '*.log' -mtime +30 -exec gzip {} +",
            "requires_approval": true,
            ...
        }
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty")
    
    sim = simulate_command(req.command, req.context or "")
    return sim.to_dict()


@app.post("/execute")
def execute(req: ExecuteRequest):
    """
    Execute a command AFTER user approval.
    
    Frontend calls this only when the user clicks APPROVE or USE SAFER.
    
    Example request:
        POST /execute
        {
            "command": "rm -rf /tmp/old-logs/",
            "risk_level": "HIGH",
            "use_safer": true,
            "safer_command": "mv /tmp/old-logs/ /backup/"
        }
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty")
    
    cmd_to_run = req.safer_command if (req.use_safer and req.safer_command) else req.command
    
    result = execute_command(
        command=cmd_to_run,
        approved=True,
        risk_level=req.risk_level,
        simulation_summary=f"Original: {req.command}" if req.use_safer else "",
    )
    return result


@app.post("/reject")
def reject(req: RejectRequest):
    """
    Log a rejected command (user clicked CANCEL).
    
    Example request:
        POST /reject
        {"command": "rm -rf /", "reason": "Too dangerous"}
    """
    execute_command(
        command=req.command,
        approved=False,
        risk_level="REJECTED",
    )
    return {
        "status": "rejected",
        "command": req.command,
        "reason": req.reason,
        "message": "Command was not executed. Logged to audit trail.",
    }


@app.get("/history")
def history(limit: int = 50):
    """
    Get the audit log — all past simulations, approvals, rejections, blocks.
    
    Query params:
        limit (int): Max entries to return. Default 50.
    
    Example response:
        [
            {
                "timestamp": "2026-10-24T14:30:00",
                "action": "HARD_BLOCKED",
                "command": "rm -rf /",
                "risk_level": "CRITICAL"
            },
            ...
        ]
    """
    log = get_audit_log()
    # Return most recent first
    return log[-limit:][::-1]


@app.get("/stats")
def stats():
    """
    Dashboard stats — summary of all actions.
    
    Example response:
        {
            "total_actions": 42,
            "executed": 15,
            "rejected": 12,
            "blocked": 8,
            "dry_runs": 7,
            "risk_breakdown": {"CRITICAL": 3, "HIGH": 10, "MEDIUM": 15, "LOW": 14},
            "block_rate": "47.6%"
        }
    """
    log = get_audit_log()
    
    total = len(log)
    executed = sum(1 for e in log if e.get("action") == "EXECUTED")
    rejected = sum(1 for e in log if e.get("action") == "REJECTED")
    blocked = sum(1 for e in log if e.get("action") == "HARD_BLOCKED")
    dry_runs = sum(1 for e in log if e.get("action") == "DRY_RUN")
    errors = sum(1 for e in log if e.get("action") == "ERROR")
    timeouts = sum(1 for e in log if e.get("action") == "TIMEOUT")
    
    # Risk breakdown
    risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "OTHER": 0}
    for entry in log:
        level = entry.get("risk_level", "OTHER")
        if level in risk_counts:
            risk_counts[level] += 1
        else:
            risk_counts["OTHER"] += 1
    
    dangerous = blocked + rejected
    block_rate = f"{100 * dangerous / total:.1f}%" if total > 0 else "0%"
    
    return {
        "total_actions": total,
        "executed": executed,
        "rejected": rejected,
        "blocked": blocked,
        "dry_runs": dry_runs,
        "errors": errors,
        "timeouts": timeouts,
        "risk_breakdown": risk_counts,
        "dangerous_actions_prevented": dangerous,
        "block_rate": block_rate,
    }


@app.get("/check")
def quick_check(command: str):
    """
    Quick risk check — is this command on the hard-block list?
    Use this for real-time checking as the user types.
    
    Query params:
        command (str): The raw command to check
    
    Example: GET /check?command=rm -rf /
    Response: {"blocked": true, "reason": "On permanent block list"}
    """
    blocked = is_hard_blocked(command)
    return {
        "command": command,
        "blocked": blocked,
        "reason": "On permanent block list — cannot be executed under any circumstances" if blocked else "Not on block list — full simulation needed to assess risk",
    }


# ============================================================
#  RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print("\n🛡️  BashGuard API Server starting...")
    print("   Docs: http://localhost:8000/docs")
    print("   Dashboard data: http://localhost:8000/stats")
    print("   History: http://localhost:8000/history\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)

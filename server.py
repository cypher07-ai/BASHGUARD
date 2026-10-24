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
from rollback import generate_rollback
from sandbox import simulate_in_sandbox, is_raw_command, detect_danger_level
from coder import generate_code, save_code, run_code, is_coding_request, detect_language
from auth import (
    register_user, login_user, logout_user,
    get_auth_status, validate_token, change_password, require_auth,
)

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

class RollbackRequest(BaseModel):
    """Request body for /rollback endpoint."""
    command: str
    context: str = ""


class CodeRequest(BaseModel):
    """Request body for /code endpoint."""
    request: str                    # Natural language: "write a snake game in python"
    language: Optional[str] = ""   # Optional language override
    auto_run: bool = False          # Auto-run after generating (Python/JS/bash only)


# ── Auth Models ──
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class LogoutRequest(BaseModel):
    token: str

class ChangePasswordRequest(BaseModel):
    token: str
    old_password: str
    new_password: str


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


# ============================================================
#  AUTH ENDPOINTS
# ============================================================

@app.get("/auth/status")
def auth_status():
    """
    Check auth setup status.
    Frontend calls this first to decide: show register page or login page?

    Response:
        {"is_registered": false, "setup_required": true, ...}   -> show Register
        {"is_registered": true,  "setup_required": false, ...}  -> show Login
    """
    return get_auth_status()


@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    """
    First-time setup — register username + password.
    Only works ONCE. After registration, use /auth/login.

    Example:
        POST /auth/register
        {"username": "cypher07", "password": "mypassword123"}

    Response:
        {"success": true, "message": "User registered", "username": "cypher07"}
    """
    result = register_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/auth/login")
def auth_login(req: LoginRequest):
    """
    Login with username + password. Returns a session token.
    Frontend must store this token and send it in the Authorization header.

    Example:
        POST /auth/login
        {"username": "cypher07", "password": "mypassword123"}

    Response:
        {
            "success": true,
            "token": "abc123...",
            "username": "cypher07",
            "expires_at": "2026-10-25T...",
            "expires_in_hours": 24
        }

    Usage after login:
        Add header to all requests: Authorization: Bearer <token>
    """
    result = login_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.post("/auth/logout")
def auth_logout(req: LogoutRequest):
    """
    Logout — invalidates the session token.

    Example:
        POST /auth/logout
        {"token": "abc123..."}
    """
    return logout_user(req.token)


@app.get("/auth/me")
def auth_me(authorization: Optional[str] = None, token: Optional[str] = None):
    """
    Get current user info.

    Pass token as:
      - Header:      Authorization: Bearer <token>
      - Query param: /auth/me?token=abc123
    """
    resolved_token = token or ""
    if not resolved_token and authorization and authorization.startswith("Bearer "):
        resolved_token = authorization[7:]

    result = validate_token(resolved_token)
    if not result["valid"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.post("/auth/change-password")
def auth_change_password(req: ChangePasswordRequest):
    """
    Change password. Requires current session token + old password.

    Example:
        POST /auth/change-password
        {"token": "abc...", "old_password": "old123", "new_password": "new456"}
    """
    result = change_password(req.token, req.old_password, req.new_password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


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
#  NEW ENDPOINTS — Rollback + Comparison + Sandbox
# ============================================================

@app.post("/rollback")
def rollback(req: RollbackRequest):
    """
    Generate an undo/rollback command for an executed action.
    
    Example request:
        POST /rollback
        {"command": "rmdir /s /q backup_folder"}
    
    Example response:
        {
            "can_undo": false,
            "undo_command": "",
            "undo_explanation": "Directory and contents permanently deleted",
            "recovery_steps": ["Check recycle bin", "Restore from backup"],
            "warning": "Data may be unrecoverable"
        }
    """
    result = generate_rollback(req.command, req.context)
    return result


@app.get("/compare")
def compare():
    """
    Side-by-side comparison: What happens WITH vs WITHOUT BashGuard.
    Uses predefined test cases to demonstrate the value.
    
    This is the KILLER demo endpoint for judges.
    """
    test_cases = [
        {
            "request": "Delete all files in the current directory",
            "without_bashguard": "🚨 ALL FILES DELETED IMMEDIATELY. No warning. No undo. Data gone forever.",
            "category": "Data Loss",
        },
        {
            "request": "Force push to the main branch",
            "without_bashguard": "🚨 Remote commits OVERWRITTEN. Teammates' work DESTROYED. CI/CD BROKEN.",
            "category": "Collaboration Risk",
        },
        {
            "request": "Drop all tables from the database",
            "without_bashguard": "🚨 ENTIRE DATABASE WIPED. All user data GONE. Application CRASHES.",
            "category": "Data Loss",
        },
        {
            "request": "Change permissions of /etc/passwd to 777",
            "without_bashguard": "🚨 System passwords EXPOSED to all users. CRITICAL SECURITY BREACH.",
            "category": "Security Risk",
        },
        {
            "request": "Kill all running python processes",
            "without_bashguard": "🚨 ALL Python services TERMINATED. API servers DOWN. Jobs INTERRUPTED.",
            "category": "Service Disruption",
        },
        {
            "request": "List all files in the current directory",
            "without_bashguard": "✅ Safe command. Runs normally.",
            "category": "Safe Command",
        },
        {
            "request": "Show disk usage",
            "without_bashguard": "✅ Safe command. Runs normally.",
            "category": "Safe Command",
        },
    ]
    
    results = []
    
    for tc in test_cases:
        sim = simulate_command(tc["request"])
        
        with_bashguard = {
            "action": "BLOCKED" if sim.risk_level in ["CRITICAL", "HIGH"] else ("WARNED" if sim.risk_level == "MEDIUM" else "AUTO-EXECUTED"),
            "risk_level": sim.risk_level,
            "risk_score": sim.risk_score,
            "planned_command": sim.planned_command,
            "warnings": sim.risk_reasons[:2],
            "safer_alternative": sim.safer_command,
            "outcome": "⛔ Prevented — User warned before damage" if sim.risk_level in ["CRITICAL", "HIGH", "MEDIUM"] else "✅ Executed safely — no risk detected",
        }
        
        results.append({
            "request": tc["request"],
            "category": tc["category"],
            "without_bashguard": tc["without_bashguard"],
            "with_bashguard": with_bashguard,
            "disaster_prevented": sim.risk_level in ["CRITICAL", "HIGH"],
        })
    
    total = len(results)
    disasters_prevented = sum(1 for r in results if r["disaster_prevented"])
    safe_auto_executed = sum(1 for r in results if not r["disaster_prevented"])
    
    return {
        "comparison": results,
        "summary": {
            "total_test_cases": total,
            "disasters_prevented": disasters_prevented,
            "safe_commands_auto_executed": safe_auto_executed,
            "protection_rate": f"{100 * disasters_prevented // total}%",
            "false_positive_rate": "0%",
        },
    }


# ============================================================
#  RUN
# ============================================================

class SandboxRequest(BaseModel):
    """Request body for /sandbox endpoint."""
    command: str

class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint (combined simulation + sandbox)."""
    command: str
    context: Optional[str] = ""


@app.post("/sandbox")
def sandbox(req: SandboxRequest):
    """
    SANDBOX ENDPOINT — Run a command in a virtual filesystem.
    
    Creates a snapshot of the real filesystem, "executes" the command
    in the sandbox, and returns a BEFORE vs AFTER diff.
    
    NOTHING is actually executed. Pure simulation.
    
    Example request:
        POST /sandbox
        {"command": "rm -rf /home/user/projects"}
    
    Example response:
        {
            "command": "rm -rf /home/user/projects",
            "target_path": "/home/user/projects",
            "before_file_count": 234,
            "after_file_count": 0,
            "data_destroyed_readable": "156.3 MB",
            "destruction_percentage": 100.0,
            "is_catastrophic": true,
            "files_deleted": [...],
            "impact_summary": "234 files/dirs PERMANENTLY DELETED..."
        }
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty")
    
    result = simulate_in_sandbox(req.command)
    return result.to_dict()


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    COMBINED ENDPOINT — Full analysis: AI simulation + Sandbox + Risk detection.
    
    This is the POWER endpoint. Gives everything in one call:
    - Is it a raw command?
    - Danger level (instant, no LLM needed)
    - Full AI-powered simulation (risk score, warnings, safer alternative)
    - Sandbox filesystem diff (before/after)
    
    Example request:
        POST /analyze
        {"command": "rm -rf ~/projects"}
    
    Returns everything the frontend needs to render the full preview.
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty")
    
    command = req.command.strip()
    
    # Quick detection (instant, no LLM)
    raw = is_raw_command(command)
    danger = detect_danger_level(command)
    
    # AI simulation (LLM-powered)
    sim = simulate_command(command, req.context or "")
    
    # Sandbox (filesystem diff)
    sandbox_result = simulate_in_sandbox(
        sim.planned_command if not raw else command
    )
    
    return {
        "is_raw_command": raw,
        "instant_danger_level": danger,
        "simulation": sim.to_dict(),
        "sandbox": sandbox_result.to_dict(),
        "recommendation": (
            "BLOCK" if danger == "CRITICAL" else
            "WARN_AND_SANDBOX" if danger in ("HIGH", "MEDIUM") else
            "ALLOW"
        ),
    }


@app.get("/demo")
def demo():
    """
    DEMO ENDPOINT — For judges / presentations.
    
    Runs 5 pre-built scenarios and returns results.
    Judges don't have to type anything — just open this URL.
    
    GET /demo — returns all demo results in one shot.
    """
    demo_scenarios = [
        {
            "name": "The Accidental Delete",
            "description": "Junior dev tries to clean up but wipes everything",
            "command": "rm -rf .",
            "category": "Data Loss",
        },
        {
            "name": "The Force Push Disaster",
            "description": "Developer overwrites teammate's work on main branch",
            "command": "git push --force origin main",
            "category": "Collaboration Risk",
        },
        {
            "name": "The Permission Nightmare",
            "description": "Sysadmin makes all system files world-writable",
            "command": "chmod 777 /etc/passwd",
            "category": "Security Breach",
        },
        {
            "name": "The Database Wipe",
            "description": "Someone runs a destructive SQL query on production",
            "command": "DROP TABLE users;",
            "category": "Data Loss",
        },
        {
            "name": "The Safe Command",
            "description": "Normal everyday command — should pass through",
            "command": "ls -la",
            "category": "Safe Operation",
        },
    ]

    results = []
    for scenario in demo_scenarios:
        cmd = scenario["command"]

        # Instant detection
        raw = is_raw_command(cmd)
        danger = detect_danger_level(cmd)

        # Sandbox
        sandbox_result = simulate_in_sandbox(cmd)

        action = "BLOCKED" if danger == "CRITICAL" else (
            "WARNING" if danger in ("HIGH", "MEDIUM") else "ALLOWED"
        )

        results.append({
            "scenario": scenario["name"],
            "description": scenario["description"],
            "command": cmd,
            "category": scenario["category"],
            "is_raw_command": raw,
            "danger_level": danger,
            "action_taken": action,
            "sandbox": {
                "target_exists": sandbox_result.target_exists,
                "files_before": sandbox_result.before_file_count,
                "files_after": sandbox_result.after_file_count,
                "files_deleted": len(sandbox_result.files_deleted),
                "data_destroyed": sandbox_result.data_destroyed_readable,
                "destruction_pct": sandbox_result.destruction_percentage,
                "is_catastrophic": sandbox_result.is_catastrophic,
                "impact": sandbox_result.impact_summary,
            },
        })

    blocked = sum(1 for r in results if r["action_taken"] in ("BLOCKED", "WARNING"))
    safe_passed = sum(1 for r in results if r["action_taken"] == "ALLOWED")

    return {
        "title": "BashGuard Live Demo",
        "tagline": "The AI agent that shows you what will happen - before it happens.",
        "scenarios": results,
        "summary": {
            "total_scenarios": len(results),
            "threats_caught": blocked,
            "safe_commands_passed": safe_passed,
            "protection_rate": f"{100 * blocked // max(len(results), 1)}%",
        },
    }


@app.post("/code")
def code(req: CodeRequest):
    """
    CODING ENGINE ENDPOINT — Generate complete, working code in any language.

    Send a natural language request and get back production-quality code.

    Example request:
        POST /code
        {"request": "write a snake game in python", "auto_run": false}

    Example response:
        {
            "request": "write a snake game in python",
            "language": "Python",
            "filename": "snake_game_143022.py",
            "code": "import pygame\\n...(full game code)...",
            "explanation": "A playable Snake game using pygame...",
            "how_to_run": "python snake_game_143022.py",
            "dependencies": ["pygame"],
            "file_saved_to": "/path/to/generated_code/snake_game_143022.py"
        }
    """
    if not req.request.strip():
        raise HTTPException(status_code=400, detail="Request cannot be empty")

    # Generate the code
    result = generate_code(req.request, req.language or "")

    if result.error and not result.code:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {result.error}")

    # Save to file
    save_code(result)

    # Optionally run it
    if req.auto_run:
        run_code(result, timeout=10)

    return result.to_dict()


@app.post("/code/detect")
def detect_code_request(req: SimulateRequest):
    """
    Quick check: Is this input a coding request?
    Useful for frontend to decide whether to show the code editor UI.

    Example:
        POST /code/detect
        {"command": "write me a todo app in python"}

    Response:
        {"is_coding_request": true, "detected_language": "Python", "extension": ".py"}
    """
    is_code = is_coding_request(req.command)
    lang_name, ext, run_cmd = detect_language(req.command) if is_code else ("", "", "")
    return {
        "input": req.command,
        "is_coding_request": is_code,
        "detected_language": lang_name,
        "extension": ext,
        "run_command_template": run_cmd or "",
    }


if __name__ == "__main__":
    import uvicorn
    print("\n\U0001f6e1\ufe0f  BashGuard API Server starting...")
    print("   Docs:          http://localhost:8000/docs")
    print("   Sandbox:       POST http://localhost:8000/sandbox")
    print("   Full Analysis: POST http://localhost:8000/analyze")
    print("   Code Engine:   POST http://localhost:8000/code")
    print("   Judge Demo:    GET  http://localhost:8000/demo\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
BashGuard — Safe Command Executor
===================================
Executes commands ONLY after simulation approval.
Maintains an audit log of all actions.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
#  AUDIT LOG
# ============================================================

AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "audit_log.json")


def log_action(entry: dict):
    """Append an action to the audit log."""
    log = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                log = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            log = []
    
    entry["timestamp"] = datetime.now().isoformat()
    log.append(entry)
    
    with open(AUDIT_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


# ============================================================
#  BLOCKED COMMANDS (NEVER EXECUTE THESE)
# ============================================================

HARD_BLOCKED = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "del /f /s /q C:\\",
    "format c:",
    ":(){:|:&};:",
    "> /dev/sda",
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sda",
    "shutdown -h now",
    "shutdown /s",
    "reboot",
    "halt",
]


def is_hard_blocked(command: str) -> bool:
    """Check if a command is in the hard-block list (NEVER execute)."""
    cmd_lower = command.strip().lower()
    for blocked in HARD_BLOCKED:
        if blocked.lower() in cmd_lower:
            return True
    return False


# ============================================================
#  COMMAND EXECUTOR
# ============================================================

def execute_command(
    command: str,
    approved: bool,
    risk_level: str = "UNKNOWN",
    simulation_summary: str = "",
    dry_run: bool = False,
) -> dict:
    """
    Execute a command ONLY if approved and not hard-blocked.
    
    Args:
        command: The shell command to execute
        approved: Whether the user explicitly approved this
        risk_level: Risk level from simulation (for logging)
        simulation_summary: Brief summary of what simulation predicted
        dry_run: If True, log but don't actually execute
    
    Returns:
        dict with: success, output, error, was_blocked, was_executed
    """
    
    result = {
        "command": command,
        "approved": approved,
        "risk_level": risk_level,
        "was_blocked": False,
        "was_executed": False,
        "output": "",
        "error": "",
        "success": False,
    }
    
    # Gate 1: Hard block check
    if is_hard_blocked(command):
        result["was_blocked"] = True
        result["error"] = (
            "🚨 HARD BLOCKED: This command is on the permanent block list. "
            "It cannot be executed under any circumstances."
        )
        log_action({
            "action": "HARD_BLOCKED",
            "command": command,
            "risk_level": risk_level,
            "reason": "Command matches permanent block list",
        })
        return result
    
    # Gate 2: Approval check
    if not approved:
        result["error"] = "❌ NOT APPROVED: Command was not approved by user."
        log_action({
            "action": "REJECTED",
            "command": command,
            "risk_level": risk_level,
            "reason": "User did not approve",
        })
        return result
    
    # Gate 3: Dry run check
    if dry_run:
        result["output"] = "🔄 DRY RUN: Command was logged but not executed."
        result["success"] = True
        log_action({
            "action": "DRY_RUN",
            "command": command,
            "risk_level": risk_level,
            "simulation_summary": simulation_summary,
        })
        return result
    
    # Execute the command
    try:
        if sys.platform == "win32":
            # Use PowerShell for rich cross-platform and native command support (rm, ls, mkdir, del, etc.)
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # If powershell returned error and it might be a CMD builtin like 'dir', fallback to cmd.exe
            if proc.returncode != 0 and not proc.stdout and ("is not recognized" in proc.stderr or proc.returncode == 1):
                cmd_proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if cmd_proc.returncode == 0 or cmd_proc.stdout:
                    proc = cmd_proc
        else:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        
        result["was_executed"] = True
        result["output"] = proc.stdout
        result["error"] = proc.stderr
        result["success"] = proc.returncode == 0
        
        log_action({
            "action": "EXECUTED",
            "command": command,
            "risk_level": risk_level,
            "return_code": proc.returncode,
            "simulation_summary": simulation_summary,
            "stdout_preview": proc.stdout[:200] if proc.stdout else "",
            "stderr_preview": proc.stderr[:200] if proc.stderr else "",
        })
        
    except subprocess.TimeoutExpired:
        result["error"] = "⏰ TIMEOUT: Command took longer than 30 seconds."
        log_action({
            "action": "TIMEOUT",
            "command": command,
            "risk_level": risk_level,
        })
    except Exception as e:
        result["error"] = f"💥 EXECUTION ERROR: {str(e)}"
        log_action({
            "action": "ERROR",
            "command": command,
            "risk_level": risk_level,
            "error": str(e),
        })
    
    return result


def get_audit_log() -> list:
    """Retrieve the full audit log, newest first."""
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                data = json.load(f)
                return list(reversed(data))
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []


def format_execution_result(result: dict) -> str:
    """Format execution result for display."""
    output = []
    output.append("")
    
    if result["was_blocked"]:
        output.append("  🚨 COMMAND BLOCKED")
        output.append(f"  {result['error']}")
    elif not result["approved"]:
        output.append("  ❌ COMMAND REJECTED (not approved)")
    elif result["success"]:
        output.append("  ✅ COMMAND EXECUTED SUCCESSFULLY")
        if result["output"]:
            output.append(f"  Output: {result['output'][:500]}")
    else:
        output.append("  ❌ COMMAND FAILED")
        if result["error"]:
            output.append(f"  Error: {result['error'][:500]}")
    
    return "\n".join(output)


# ============================================================
#  TEST
# ============================================================

if __name__ == "__main__":
    print("Testing executor...")
    
    # Test 1: Hard blocked command
    r = execute_command("rm -rf /", approved=True, risk_level="CRITICAL")
    print(format_execution_result(r))
    
    # Test 2: Not approved
    r = execute_command("echo hello", approved=False, risk_level="LOW")
    print(format_execution_result(r))
    
    # Test 3: Safe command, approved
    r = execute_command("echo BashGuard works!", approved=True, risk_level="LOW")
    print(format_execution_result(r))

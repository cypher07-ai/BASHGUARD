"""
BashGuard — Integrations Module (GitHub & System Applications)
==============================================================
Provides real-world connectors to:
1. GitHub (via `gh` CLI and Git):
   - User profile, repositories, commits, branches, issues, clone, push
2. System & Environment:
   - System specs, disk drives, memory, application launchers
"""

import os
import sys
import shutil
import platform
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any

# Ensure proper encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _run_cmd(cmd: List[str], timeout: int = 15) -> Dict[str, Any]:
    """Helper to run a shell command safely with timeout."""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "code": res.returncode
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "code": -1}


# ─── 1. GitHub Integration ────────────────────────────────────────────────────

def get_github_status() -> Dict[str, Any]:
    """Checks if gh CLI is authenticated and returns active user details."""
    gh_path = shutil.which("gh")
    if not gh_path:
        return {
            "available": False,
            "authenticated": False,
            "message": "GitHub CLI ('gh') is not installed in system PATH."
        }

    status_res = _run_cmd(["gh", "auth", "status"])
    user_res = _run_cmd(["gh", "api", "user", "--jq", "{login: .login, name: .name, public_repos: .public_repos, avatar_url: .avatar_url, html_url: .html_url}"])

    is_authed = status_res["success"] or "Logged in to github.com" in status_res["stdout"] or "Logged in to github.com" in status_res["stderr"]

    user_info = {}
    if is_authed and user_res["success"] and user_res["stdout"]:
        import json
        try:
            user_info = json.loads(user_res["stdout"])
        except Exception:
            user_info = {"login": "authenticated_user"}

    return {
        "available": True,
        "authenticated": is_authed,
        "user": user_info,
        "details": status_res["stdout"] or status_res["stderr"]
    }


def list_github_repos(limit: int = 8) -> List[Dict[str, Any]]:
    """Lists current authenticated user's GitHub repositories."""
    res = _run_cmd(["gh", "repo", "list", "--limit", str(limit), "--json", "name,nameWithOwner,isPrivate,updatedAt,description,url"])
    if not res["success"] or not res["stdout"]:
        return []
    import json
    try:
        return json.loads(res["stdout"])
    except Exception:
        return []


def get_repo_commits(repo_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches recent commits for a repository (e.g. 'cypher07-ai/ai-agent-hackathon')."""
    res = _run_cmd([
        "gh", "api", f"repos/{repo_name}/commits?per_page={limit}",
        "--jq", "[.[] | {sha: .sha[0:7], message: .commit.message, author: .commit.author.name, date: .commit.author.date}]"
    ])
    if not res["success"] or not res["stdout"]:
        return []
    import json
    try:
        return json.loads(res["stdout"])
    except Exception:
        return []


def get_repo_issues(repo_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches recent issues/PRs for a repository."""
    res = _run_cmd(["gh", "issue", "list", "--repo", repo_name, "--limit", str(limit), "--json", "number,title,state,createdAt,url"])
    if not res["success"] or not res["stdout"]:
        return []
    import json
    try:
        return json.loads(res["stdout"])
    except Exception:
        return []


def perform_git_action(action: str, **kwargs) -> Dict[str, Any]:
    """
    Executes git/github actions:
    - 'status': git status
    - 'commit': git add + git commit -m <msg>
    - 'push': git push
    - 'clone': gh repo clone <repo>
    """
    action = action.lower().strip()

    if action == "status":
        res = _run_cmd(["git", "status", "--short"])
        return {"status": "success", "action": "status", "output": res["stdout"]}

    elif action == "commit":
        msg = kwargs.get("message", "chore: automated update via BashGuard")
        add_res = _run_cmd(["git", "add", "."])
        commit_res = _run_cmd(["git", "commit", "-m", msg])
        return {
            "status": "success" if commit_res["success"] else "error",
            "action": "commit",
            "output": commit_res["stdout"] or commit_res["stderr"]
        }

    elif action == "push":
        res = _run_cmd(["git", "push"])
        return {
            "status": "success" if res["success"] else "error",
            "action": "push",
            "output": res["stdout"] or res["stderr"]
        }

    elif action == "clone":
        repo = kwargs.get("repo")
        if not repo:
            return {"status": "error", "message": "Repository name required"}
        res = _run_cmd(["gh", "repo", "clone", repo])
        return {
            "status": "success" if res["success"] else "error",
            "action": "clone",
            "output": res["stdout"] or res["stderr"]
        }

    return {"status": "error", "message": f"Unsupported git action: {action}"}


# ─── 2. System Environment & Application Launchers ────────────────────────────

def get_system_health() -> Dict[str, Any]:
    """Fetches disk drives, system specs, CPU count, and platform info."""
    drives = []
    if sys.platform == "win32":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & 1:
                drive_p = f"{letter}:\\"
                try:
                    usage = shutil.disk_usage(drive_p)
                    drives.append({
                        "drive": drive_p,
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_gb": round(usage.used / (1024**3), 1),
                        "free_gb": round(usage.free / (1024**3), 1),
                        "percent_used": round((usage.used / usage.total) * 100, 1)
                    })
                except Exception:
                    pass
            bitmask >>= 1
    else:
        try:
            usage = shutil.disk_usage("/")
            drives.append({
                "drive": "/",
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent_used": round((usage.used / usage.total) * 100, 1)
            })
        except Exception:
            pass

    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
        "python_version": platform.python_version(),
        "drives": drives,
        "hostname": platform.node(),
        "current_directory": os.getcwd()
    }


def launch_application(app: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Launches local desktop applications (VS Code, File Explorer, Browser, Terminal)."""
    app = app.lower().strip()
    target_path = path or os.getcwd()

    try:
        if app in ("code", "vscode"):
            subprocess.Popen(["code", target_path], shell=True)
            return {"status": "success", "message": f"Launched VS Code at {target_path}"}

        elif app in ("explorer", "folder"):
            if sys.platform == "win32":
                subprocess.Popen(["explorer", target_path])
                return {"status": "success", "message": f"Opened File Explorer at {target_path}"}
            else:
                subprocess.Popen(["xdg-open", target_path])
                return {"status": "success", "message": f"Opened folder at {target_path}"}

        elif app in ("terminal", "cmd", "powershell"):
            if sys.platform == "win32":
                subprocess.Popen(["start", "powershell"], shell=True)
                return {"status": "success", "message": "Opened new PowerShell window"}
            else:
                subprocess.Popen(["x-terminal-emulator"])
                return {"status": "success", "message": "Opened new terminal"}

        return {"status": "error", "message": f"Unrecognized application shortcut: {app}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

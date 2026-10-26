"""
BashGuard — Unified Omni-Agent Engine
======================================
The central coordinator that unites all capabilities into ONE window:
- Terminal Commands & Dangerous Action Simulation
- Intelligent Storage Classifier (Trash vs. Necessary)
- Fuzzy / Prefix File Resolution & Modification
- Autonomous Code Generation & Folder Scaffolding
- GitHub & System App Integrations
"""

import os
import re
import sys
import json
from typing import Dict, List, Optional, Any

from simulator import simulate_command, SimulationResult
from sandbox import simulate_in_sandbox, is_raw_command, detect_danger_level
from executor import execute_command, is_hard_blocked
from coder import generate_code, save_code, is_coding_request, detect_language
import intel
import integrations

# Ensure proper encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_unified_agent(
    prompt: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main entry point for any user request in the unified window.
    Decomposes and executes multi-step workflows automatically.
    """
    prompt_clean = prompt.strip()
    prompt_lower = prompt_clean.lower()

    response: Dict[str, Any] = {
        "original_prompt": prompt_clean,
        "intent": "general",
        "steps_completed": [],
        "message": "",
        "code_result": None,
        "simulation": None,
        "sandbox": None,
        "storage_analysis": None,
        "file_resolution": None,
        "github_data": None,
        "system_data": None,
        "requires_approval": False
    }

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Intent: GitHub Integration
    # ──────────────────────────────────────────────────────────────────────────
    if any(k in prompt_lower for k in ["github", "git repo", "my repos", "git commit", "git push", "git status"]):
        response["intent"] = "github_integration"
        gh_status = integrations.get_github_status()

        if "push" in prompt_lower:
            git_res = integrations.perform_git_action("push")
            response["steps_completed"].append("Executed git push to remote repository.")
            response["github_data"] = {"action": "push", "result": git_res}
            response["message"] = f"Git Push Output:\n{git_res['output'] or 'Completed'}"
            return response

        if "commit" in prompt_lower:
            commit_msg = prompt_clean.split("commit", 1)[-1].strip(" :-\"'") or "update via BashGuard Agent"
            git_res = integrations.perform_git_action("commit", message=commit_msg)
            response["steps_completed"].append(f"Created git commit with message: '{commit_msg}'")
            response["github_data"] = {"action": "commit", "result": git_res}
            response["message"] = f"Commit Result:\n{git_res['output']}"
            return response

        # Default GitHub query: repos & commits
        repos = integrations.list_github_repos(limit=6)
        active_repo = "cypher07-ai/ai-agent-hackathon"
        commits = integrations.get_repo_commits(active_repo, limit=4)

        response["steps_completed"].append("Fetched GitHub profile and active repositories.")
        response["github_data"] = {
            "status": gh_status,
            "repositories": repos,
            "recent_commits": commits,
            "active_repo": active_repo
        }
        repo_names = ", ".join([r.get("nameWithOwner", r.get("name", "")) for r in repos[:3]])
        response["message"] = (
            f"Connected to GitHub as **{gh_status.get('user', {}).get('login', 'User')}**.\n"
            f"Found {len(repos)} repositories (e.g. {repo_names}).\n"
            f"Latest commit on `{active_repo}`: \"{commits[0]['message'] if commits else 'Up to date'}\""
        )
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Intent: Storage Cleaner & Trash vs. Necessary Classifier
    # ──────────────────────────────────────────────────────────────────────────
    trash_keywords = ["trash", "clean", "storage", "junk", "disk space", "temporary files", "necessary files", "judge files", "media"]
    if any(k in prompt_lower for k in trash_keywords) and not is_raw_command(prompt_clean):
        response["intent"] = "storage_intelligence"

        # Determine target folder if specified (e.g. "downloads", "desktop", or current)
        target_dir = os.getcwd()
        if "download" in prompt_lower:
            target_dir = os.path.join(str(os.path.expanduser("~")), "Downloads")
        elif "desktop" in prompt_lower:
            target_dir = os.path.join(str(os.path.expanduser("~")), "Desktop")

        analysis = intel.classify_storage(target_path=target_dir, max_files=200)
        response["steps_completed"].append(f"Scanned {analysis.get('scanned_files_count', 0)} files in {target_dir}.")
        response["storage_analysis"] = analysis

        # If user explicitly asked to "clean" or "delete trash"
        if "clean" in prompt_lower or "delete trash" in prompt_lower:
            trash_paths = [item["path"] for item in analysis.get("trash", {}).get("items", [])]
            if trash_paths:
                clean_res = intel.clean_trash_items(trash_paths, quarantine=True)
                response["steps_completed"].append(f"Safely quarantined {clean_res['cleaned_count']} trash files ({clean_res['freed_readable']} freed).")
                response["storage_analysis"]["clean_result"] = clean_res
                response["message"] = (
                    f"Storage Clean Complete! Analyzed `{target_dir}`:\n"
                    f"- **Quarantined:** {clean_res['cleaned_count']} trash files\n"
                    f"- **Reclaimed:** {clean_res['freed_readable']} of disk space\n"
                    f"- Safe rollback available in `.bashguard_trash_staging/`"
                )
                return response

        trash_cnt = analysis.get("trash", {}).get("count", 0)
        trash_sz = analysis.get("trash", {}).get("readable", "0 B")
        rec_pct = analysis.get("trash", {}).get("reclaim_percentage", 0)
        response["message"] = (
            f"Storage Intelligence Analysis for `{target_dir}`:\n"
            f"- **Trash Identified:** {trash_cnt} files ({trash_sz}, ~{rec_pct}% of scanned data)\n"
            f"- **Safe Files / Essential:** {analysis.get('essential', {}).get('count', 0)} protected files\n"
            f"- **Items for Review:** {analysis.get('review', {}).get('count', 0)} large unaccessed archives/media\n\n"
            f"Would you like me to clean the {trash_cnt} trash files for you?"
        )
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Intent: Multi-step Folder Creation + Code Generation
    # ──────────────────────────────────────────────────────────────────────────
    create_folder_match = re.search(r"(?:create|make)\s+(?:a\s+)?folder\s+(?:called\s+|named\s+)?([a-zA-Z0-9_\-\.\/\\]+)", prompt_clean, re.I)
    has_code_intent = is_coding_request(prompt_clean) or any(k in prompt_lower for k in ["write", "code", "script", "game", "program", "build"])

    if create_folder_match and has_code_intent:
        response["intent"] = "composite_scaffold_and_code"
        folder_name = create_folder_match.group(1).strip()
        folder_path = os.path.abspath(folder_name)

        # Step 1: Create directory
        os.makedirs(folder_path, exist_ok=True)
        response["steps_completed"].append(f"Created directory: `{os.path.basename(folder_path)}`")

        # Step 2: Generate Code
        code_res = generate_code(prompt_clean)
        # Handle dataclass or dict
        if hasattr(code_res, "__dict__"):
            code_dict = code_res.__dict__
        elif isinstance(code_res, dict):
            code_dict = code_res
        else:
            code_dict = {"code": str(code_res), "filename": "app.py", "language": "python", "explanation": ""}

        filename = code_dict.get("filename") or "main.py"
        full_file_path = os.path.join(folder_path, filename)

        # Step 3: Save file
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(code_dict.get("code", ""))

        response["steps_completed"].append(f"Synthesized {code_dict.get('language', 'code')} code and wrote `{filename}` ({len(code_dict.get('code', ''))} bytes).")
        response["code_result"] = {
            **code_dict,
            "folder": folder_path,
            "saved_to": full_file_path
        }
        response["message"] = (
            f"All set in one go!\n"
            f"1. Created folder: `{folder_name}/`\n"
            f"2. Generated `{filename}` ({code_dict.get('language')})\n"
            f"3. Saved directly to `{full_file_path}`\n\n"
            f"**Explanation:** {code_dict.get('explanation', 'Code is ready to execute.')}"
        )
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Intent: Pure Code Generation (in current folder)
    # ──────────────────────────────────────────────────────────────────────────
    if is_coding_request(prompt_clean):
        response["intent"] = "code_generation"
        code_res = generate_code(prompt_clean)
        if hasattr(code_res, "__dict__"):
            code_dict = code_res.__dict__
        elif isinstance(code_res, dict):
            code_dict = code_res
        else:
            code_dict = {"code": str(code_res), "filename": "app.py", "language": "python", "explanation": ""}

        filename = code_dict.get("filename") or "app.py"
        saved_path = save_code(filename, code_dict.get("code", ""))

        response["steps_completed"].append(f"Generated {code_dict.get('language', 'code')} code and saved to `{saved_path}`.")
        response["code_result"] = {
            **code_dict,
            "saved_to": saved_path
        }
        response["message"] = (
            f"Generated **{code_dict.get('language', 'code').upper()}** code: `{filename}`\n\n"
            f"**Summary:** {code_dict.get('explanation', '')}\n"
            f"Saved to: `{saved_path}`"
        )
        return response

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Intent: Fuzzy File Search & Auto-Operation
    # ──────────────────────────────────────────────────────────────────────────
    file_action_match = re.search(r"^(find|search|show|read|open|edit|change|delete|remove)\s+(?:file\s+)?([a-zA-Z0-9_\-\.]+)", prompt_clean, re.I)
    if file_action_match and not is_raw_command(prompt_clean):
        verb = file_action_match.group(1).lower()
        file_query = file_action_match.group(2).strip()

        resolution = intel.resolve_file(file_query)
        response["intent"] = "fuzzy_file_operation"
        response["file_resolution"] = resolution

        best = resolution.get("best_match")
        if not best:
            response["message"] = f"Searched for files starting with or matching `'{file_query}'`, but no matches were found."
            return response

        target_file = best["path"]
        response["steps_completed"].append(f"Resolved `'{file_query}'` ➔ `{best['name']}` ({best['match_type']} match in {best['relative_path']}).")

        # Action: Read / Show
        if verb in ("find", "search", "show", "read", "open"):
            content_res = intel.execute_file_operation(target_file, "read")
            response["message"] = (
                f"Found file: **{best['name']}** ({best['size_readable']}, modified {best['modified']})\n"
                f"Path: `{best['relative_path']}`\n\n"
                f"```text\n{content_res.get('content', '')[:1000]}\n```"
            )
            return response

        # Action: Delete (requires consequence check!)
        if verb in ("delete", "remove"):
            # Check risk through sandbox & simulator
            danger_cmd = f"rm {target_file}"
            sim_res = simulate_command(danger_cmd)
            response["simulation"] = sim_res.__dict__
            response["requires_approval"] = True
            response["message"] = (
                f"⚠️ Resolved `'{file_query}'` to **{best['name']}** (`{target_file}`).\n"
                f"Risk Level: **{sim_res.risk_level}** (Score: {sim_res.risk_score}/100).\n"
                f"Action paused for safety: Please approve deletion."
            )
            return response

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Intent: Command Simulation / Execution (Core BashGuard)
    # ──────────────────────────────────────────────────────────────────────────
    response["intent"] = "command_simulation"
    raw_cmd = is_raw_command(prompt_clean)
    instant_danger = detect_danger_level(prompt_clean) if raw_cmd else "LOW"

    # Step 1: Simulator analysis
    sim_result = simulate_command(prompt_clean)
    response["simulation"] = sim_result.__dict__
    response["steps_completed"].append(f"Evaluated consequences: Risk level is {sim_result.risk_level} ({sim_result.risk_score}/100).")

    # Step 2: Virtual Sandbox execution if raw command or dangerous
    planned_cmd = sim_result.planned_command or prompt_clean
    sandbox_res = simulate_in_sandbox(planned_cmd)
    response["sandbox"] = sandbox_res.__dict__

    if sandbox_res.files_deleted:
        response["steps_completed"].append(f"Virtual Sandbox: {len(sandbox_res.files_deleted)} files ({sandbox_res.data_destroyed_readable}) would be impacted.")

    # Require explicit user permission/approval for dangerous actions
    response["requires_approval"] = (
        sim_result.requires_approval
        or is_hard_blocked(planned_cmd)[0]
        or sim_result.risk_level in ("CRITICAL", "HIGH", "MEDIUM")
        or sim_result.risk_score >= 25
        or bool(sandbox_res.files_deleted)
    )

    response["message"] = (
        f"**Command:** `{planned_cmd}`\n"
        f"**Risk Level:** {sim_result.risk_level} ({sim_result.risk_score}/100)\n"
        f"**Impact:** {sim_result.command_explanation}\n"
    )
    if sim_result.safer_command:
        response["message"] += f"\n💡 **Safer Alternative:** `{sim_result.safer_command}` ({sim_result.safer_alternative})"

    return response

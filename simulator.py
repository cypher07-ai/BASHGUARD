"""
BashGuard — Command Simulation Engine
======================================
Analyzes system commands BEFORE execution to predict consequences,
detect risks, and show the full blast radius.
"""

import os
import sys
import glob
import json
import shutil
import pathlib
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.5-flash-lite"


# ============================================================
#  DATA STRUCTURES
# ============================================================

@dataclass
class FileImpact:
    """Represents the impact on a single file or directory."""
    path: str
    exists: bool
    is_dir: bool
    size_bytes: int = 0
    file_count: int = 0  # if directory, how many files inside
    action: str = ""     # DELETE, MODIFY, CREATE, OVERWRITE, PERMISSION_CHANGE
    is_system_critical: bool = False


@dataclass
class ProcessImpact:
    """Represents impact on a running process."""
    pid: int = 0
    name: str = ""
    impact: str = ""  # KILLED, INTERRUPTED, DATA_LOSS, CONNECTION_DROP


@dataclass
class SimulationResult:
    """Complete result of simulating a command."""
    original_request: str = ""
    planned_command: str = ""
    command_explanation: str = ""
    
    # Impact analysis
    files_affected: list = field(default_factory=list)
    total_files_count: int = 0
    total_size_bytes: int = 0
    processes_affected: list = field(default_factory=list)
    
    # Risk assessment
    risk_level: str = "LOW"           # CRITICAL, HIGH, MEDIUM, LOW
    risk_score: int = 0               # 0-100
    risk_reasons: list = field(default_factory=list)
    is_reversible: bool = True
    
    # Suggestions
    warnings: list = field(default_factory=list)
    safer_alternative: str = ""
    safer_command: str = ""
    
    # Metadata
    simulation_confidence: str = "HIGH"  # HIGH, MEDIUM, LOW
    requires_approval: bool = True

    def to_dict(self):
        return asdict(self)


# ============================================================
#  FILESYSTEM ANALYSIS
# ============================================================

SYSTEM_CRITICAL_PATHS = [
    "/etc", "/boot", "/usr", "/bin", "/sbin", "/lib", "/var/lib",
    "C:\\Windows", "C:\\Program Files", "C:\\Users\\Default",
    "/System", "/Library",
]

DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf /*", "rm -rf ~", "del /f /s /q C:\\",
    "format c:", "mkfs", "dd if=", ":(){:|:&};:",
    "chmod 777", "chmod -R 777", "chmod 000",
    "> /dev/sda", "mv / ", "wget | sh", "curl | bash",
    "DROP DATABASE", "DROP TABLE", "DELETE FROM",
    "TRUNCATE", "UPDATE.*SET.*WHERE 1=1",
    "git push --force", "git push -f",
    "kill -9", "killall", "pkill",
    "shutdown", "reboot", "halt", "poweroff",
    "iptables -F", "ufw disable",
    "passwd", "useradd", "userdel",
    "npm publish", "pip install --force",
]


def analyze_path_impact(target_path: str) -> FileImpact:
    """Analyze what would happen to a specific path."""
    target = pathlib.Path(target_path)
    impact = FileImpact(
        path=str(target),
        exists=target.exists(),
        is_dir=target.is_dir() if target.exists() else False,
    )
    
    if target.exists():
        if target.is_dir():
            # Count files and total size
            total_size = 0
            file_count = 0
            try:
                for f in target.rglob("*"):
                    if f.is_file():
                        file_count += 1
                        try:
                            total_size += f.stat().st_size
                        except (PermissionError, OSError):
                            pass
            except (PermissionError, OSError):
                pass
            impact.size_bytes = total_size
            impact.file_count = file_count
        else:
            try:
                impact.size_bytes = target.stat().st_size
                impact.file_count = 1
            except (PermissionError, OSError):
                pass
    
    # Check if system-critical
    for critical in SYSTEM_CRITICAL_PATHS:
        if str(target).lower().startswith(critical.lower()):
            impact.is_system_critical = True
            break
    
    return impact


def get_running_processes() -> list:
    """Get list of running processes (cross-platform)."""
    processes = []
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n")[:50]:
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    processes.append({"name": parts[0], "pid": parts[1]})
        else:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n")[1:50]:
                parts = line.split()
                if len(parts) >= 11:
                    processes.append({"name": parts[10], "pid": parts[1]})
    except Exception:
        pass
    return processes


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    else:
        return f"{size_bytes / (1024*1024*1024):.2f} GB"


# ============================================================
#  LLM-POWERED SIMULATION ENGINE
# ============================================================

SIMULATION_PROMPT = """You are BashGuard, an expert system command safety analyzer.

Given a user's natural language request, you must:
1. Determine the exact command(s) that would need to be executed
2. Analyze the FULL consequences of running those commands
3. Identify ALL risks and potential damage
4. Suggest a safer alternative if risks exist

You MUST respond in this EXACT JSON format (no markdown, no explanation outside JSON):

planned_command: the exact command(s) that would be executed
command_explanation: plain English explanation of what the command does step by step
target_paths: list of file/dir paths affected
actions_on_paths: list like DELETE, MODIFY, CREATE
risk_level: CRITICAL or HIGH or MEDIUM or LOW
risk_score: number 0-100
risk_reasons: list of reasons for the risk level
is_reversible: true or false
warnings: list of specific warnings about what could go wrong
processes_that_could_be_affected: list of objects with "name" and "impact" fields
safer_alternative: plain English description of safer approach
safer_command: the actual safer command to run instead
simulation_confidence: HIGH or MEDIUM or LOW
side_effects: list of secondary effects beyond the primary action

Return valid JSON with these exact keys.

RULES:
- Be THOROUGH — think about secondary effects, not just the obvious
- If a command could affect running processes, LIST them
- If data loss is possible, flag it as HIGH or CRITICAL
- ALWAYS suggest a safer alternative when risk is MEDIUM or higher
- Consider the OS context: the user is on {os_type}
- For destructive commands (rm, del, drop, format), ALWAYS mark as HIGH or CRITICAL
- Consider: cascade failures, data dependencies, service disruptions
- If the command is safe (like ls, echo, cat), mark as LOW risk
- IMPORTANT: On Windows, ALWAYS wrap file paths that contain spaces in double quotes. For example: del /s /q "C:\\Users\\my user\\Pictures\\*.*"
- IMPORTANT: For the safer_command as well, always quote paths with spaces
"""


def simulate_command(user_request: str, context: str = "") -> SimulationResult:
    """
    Core simulation function. Takes a natural language request,
    determines what command would be needed, and simulates consequences.
    """
    result = SimulationResult(original_request=user_request)
    
    os_type = "Windows" if sys.platform == "win32" else "Linux/Mac"
    
    # Get current directory info for context
    cwd = os.getcwd()
    dir_contents = []
    try:
        for item in os.listdir(cwd)[:20]:
            full_path = os.path.join(cwd, item)
            if os.path.isdir(full_path):
                dir_contents.append(f"[DIR] {item}")
            else:
                size = os.path.getsize(full_path)
                dir_contents.append(f"[FILE] {item} ({format_size(size)})")
    except Exception:
        pass
    
    # Get running processes for context
    processes = get_running_processes()
    process_names = [p["name"] for p in processes[:30]]
    
    # Build the prompt with real system context
    system_prompt = SIMULATION_PROMPT.replace("{os_type}", os_type)
    
    user_prompt = f"""Analyze this request and simulate what would happen:

USER REQUEST: "{user_request}"

SYSTEM CONTEXT:
- OS: {os_type}
- Current directory: {cwd}
- Files in current directory: {json.dumps(dir_contents[:15])}
- Running processes (sample): {json.dumps(process_names[:20])}
{f'- Additional context: {context}' if context else ''}

Respond with ONLY the JSON object. No markdown fences, no explanation."""

    try:
        chat = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,  # Low temperature for precise analysis
            ),
        )
        response = chat.send_message(user_prompt)
        response_text = response.text.strip()
        
        # Clean up response — remove markdown fences if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[-1]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
        
        analysis = json.loads(response_text)
        
        # Populate simulation result from LLM analysis
        result.planned_command = analysis.get("planned_command", "unknown")
        result.command_explanation = analysis.get("command_explanation", "")
        result.risk_level = analysis.get("risk_level", "MEDIUM")
        result.risk_score = analysis.get("risk_score", 50)
        result.risk_reasons = analysis.get("risk_reasons", [])
        result.is_reversible = analysis.get("is_reversible", True)
        result.warnings = analysis.get("warnings", [])
        result.safer_alternative = analysis.get("safer_alternative", "")
        result.safer_command = analysis.get("safer_command", "")
        result.simulation_confidence = analysis.get("simulation_confidence", "MEDIUM")
        
        # Analyze actual filesystem impact for target paths
        target_paths = analysis.get("target_paths", [])
        actions = analysis.get("actions_on_paths", [])
        
        total_files = 0
        total_size = 0
        
        for i, path in enumerate(target_paths):
            impact = analyze_path_impact(path)
            action = actions[i] if i < len(actions) else "UNKNOWN"
            impact.action = action
            result.files_affected.append(asdict(impact))
            total_files += impact.file_count
            total_size += impact.size_bytes
        
        result.total_files_count = total_files
        result.total_size_bytes = total_size
        
        # Process impacts
        proc_impacts = analysis.get("processes_that_could_be_affected", [])
        result.processes_affected = proc_impacts
        
        # Additional: check against known dangerous patterns
        cmd = result.planned_command.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in cmd:
                if result.risk_level not in ["CRITICAL", "HIGH"]:
                    result.risk_level = "HIGH"
                    result.risk_score = max(result.risk_score, 80)
                    result.risk_reasons.append(
                        f"Command matches known dangerous pattern: '{pattern}'"
                    )
                break
        
        # Set approval requirement
        result.requires_approval = result.risk_level in ["CRITICAL", "HIGH", "MEDIUM"]
        
    except json.JSONDecodeError as e:
        result.risk_level = "HIGH"
        result.risk_score = 90
        result.warnings = [f"Simulation engine could not parse analysis: {e}"]
        result.simulation_confidence = "LOW"
        result.requires_approval = True
        
    except Exception as e:
        result.risk_level = "HIGH"
        result.risk_score = 90
        result.warnings = [f"Simulation error: {e}"]
        result.simulation_confidence = "LOW"
        result.requires_approval = True
    
    return result


# ============================================================
#  PRETTY PRINT SIMULATION
# ============================================================

def format_simulation(sim: SimulationResult) -> str:
    """Format simulation result for display."""
    
    risk_emoji = {
        "CRITICAL": "🚨",
        "HIGH": "🔴",
        "MEDIUM": "🟡",
        "LOW": "🟢"
    }
    
    reversible_icon = "✅ YES" if sim.is_reversible else "❌ NO"
    emoji = risk_emoji.get(sim.risk_level, "⚪")
    
    output = []
    output.append("")
    output.append("=" * 62)
    output.append("  🛡️  BashGuard — SIMULATION REPORT (DRY RUN)")
    output.append("=" * 62)
    output.append("")
    output.append(f"  📝 Your Request: \"{sim.original_request}\"")
    output.append(f"  💻 Planned Command: {sim.planned_command}")
    output.append(f"  📖 What it does: {sim.command_explanation}")
    output.append("")
    
    # Blast Radius
    output.append("  ┌─────────────────────────────────────────────────────┐")
    output.append("  │              📊 BLAST RADIUS ANALYSIS               │")
    output.append("  ├─────────────────────────────────────────────────────┤")
    output.append(f"  │  Files affected:     {sim.total_files_count:<30}│")
    output.append(f"  │  Total data:         {format_size(sim.total_size_bytes):<30}│")
    output.append(f"  │  Reversible:         {reversible_icon:<30}│")
    output.append(f"  │  Risk Level:         {emoji} {sim.risk_level:<28}│")
    output.append(f"  │  Risk Score:         {sim.risk_score}/100{' ':>25}│")
    output.append(f"  │  Confidence:         {sim.simulation_confidence:<30}│")
    output.append("  └─────────────────────────────────────────────────────┘")
    output.append("")
    
    # Files affected detail
    if sim.files_affected:
        output.append("  📁 FILES & DIRECTORIES AFFECTED:")
        for f in sim.files_affected[:10]:
            status = "EXISTS" if f.get("exists") else "NEW"
            critical = " ⚠️ SYSTEM CRITICAL" if f.get("is_system_critical") else ""
            size = format_size(f.get("size_bytes", 0))
            output.append(
                f"    → [{f.get('action', '?')}] {f.get('path', '?')} "
                f"({status}, {size}){critical}"
            )
        output.append("")
    
    # Processes affected
    if sim.processes_affected:
        output.append("  ⚙️  PROCESSES AFFECTED:")
        for p in sim.processes_affected:
            name = p.get("name", "unknown")
            impact = p.get("impact", "may be affected")
            output.append(f"    → {name}: {impact}")
        output.append("")
    
    # Risk reasons
    if sim.risk_reasons:
        output.append(f"  {emoji} RISK REASONS:")
        for i, reason in enumerate(sim.risk_reasons, 1):
            output.append(f"    {i}. {reason}")
        output.append("")
    
    # Warnings
    if sim.warnings:
        output.append("  ⚠️  WARNINGS:")
        for w in sim.warnings:
            output.append(f"    • {w}")
        output.append("")
    
    # Safer alternative
    if sim.safer_alternative:
        output.append("  💡 SAFER ALTERNATIVE:")
        output.append(f"    {sim.safer_alternative}")
        if sim.safer_command:
            output.append(f"    Command: {sim.safer_command}")
        output.append("")
    
    # Approval required
    if sim.requires_approval:
        output.append("  ─────────────────────────────────────────────────────")
        output.append("  🔐 APPROVAL REQUIRED before execution")
        options = ["  Options: [APPROVE] [USE SAFER VERSION] [CANCEL]"]
        if not sim.safer_command:
            options = ["  Options: [APPROVE] [CANCEL]"]
        output.append(options[0])
    else:
        output.append("  ✅ LOW RISK — Safe to execute automatically")
    
    output.append("=" * 62)
    
    return "\n".join(output)


# ============================================================
#  QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("\n🛡️  BashGuard Simulator — Test Mode\n")
    
    test_requests = [
        "Delete all files in the current directory",
        "List all files in the current folder",
        "Force push my code to the main branch on git",
    ]
    
    for req in test_requests:
        print(f"\n{'='*60}")
        print(f"Testing: \"{req}\"")
        sim = simulate_command(req)
        print(format_simulation(sim))

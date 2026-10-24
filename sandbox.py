"""
BashGuard — Sandbox Simulation Engine
=======================================
Creates a virtual filesystem snapshot, "executes" dangerous commands
inside the sandbox, and shows a BEFORE vs AFTER diff.

This NEVER touches the real filesystem. It's a pure simulation.

The killer demo feature: "Here's what WOULD have happened."
"""

import os
import sys
import json
import pathlib
import shutil
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
#  DATA STRUCTURES
# ============================================================

@dataclass
class VirtualFile:
    """A file in the virtual filesystem."""
    path: str
    name: str
    is_dir: bool
    size_bytes: int = 0
    file_count: int = 0  # files inside if dir
    extension: str = ""
    depth: int = 0
    status: str = "ALIVE"  # ALIVE, DELETED, MODIFIED, CREATED, PERMISSION_CHANGED

    def to_dict(self):
        return asdict(self)


@dataclass
class SandboxResult:
    """Result of running a command in the sandbox."""
    command: str = ""
    target_path: str = ""
    target_exists: bool = False

    # Before state
    before_tree: list = field(default_factory=list)  # list of VirtualFile dicts
    before_file_count: int = 0
    before_dir_count: int = 0
    before_total_size: int = 0

    # After state (simulated)
    after_tree: list = field(default_factory=list)
    after_file_count: int = 0
    after_dir_count: int = 0
    after_total_size: int = 0

    # Diff
    files_deleted: list = field(default_factory=list)
    files_modified: list = field(default_factory=list)
    files_created: list = field(default_factory=list)
    files_permission_changed: list = field(default_factory=list)
    files_survived: list = field(default_factory=list)

    # Impact summary
    data_destroyed_bytes: int = 0
    data_destroyed_readable: str = ""
    destruction_percentage: float = 0.0
    is_catastrophic: bool = False
    impact_summary: str = ""

    # Metadata
    sandbox_id: str = ""
    timestamp: str = ""

    def to_dict(self):
        return asdict(self)


# ============================================================
#  FILESYSTEM SCANNER
# ============================================================

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


def scan_directory(target_path: str, max_depth: int = 5, max_files: int = 500) -> list:
    """
    Scan a real directory and return a list of VirtualFile objects.
    This is the snapshot of the REAL filesystem.
    """
    target = pathlib.Path(target_path)
    files = []

    if not target.exists():
        return files

    base_depth = len(target.parts)

    def _scan(path, current_depth=0):
        if current_depth > max_depth or len(files) >= max_files:
            return

        try:
            if path.is_file():
                try:
                    size = path.stat().st_size
                except (PermissionError, OSError):
                    size = 0
                files.append(VirtualFile(
                    path=str(path),
                    name=path.name,
                    is_dir=False,
                    size_bytes=size,
                    extension=path.suffix.lower(),
                    depth=current_depth,
                    status="ALIVE",
                ))
            elif path.is_dir():
                # Count contents
                child_count = 0
                dir_size = 0
                try:
                    for child in path.iterdir():
                        child_count += 1
                        if child.is_file():
                            try:
                                dir_size += child.stat().st_size
                            except:
                                pass
                except (PermissionError, OSError):
                    pass

                files.append(VirtualFile(
                    path=str(path),
                    name=path.name,
                    is_dir=True,
                    size_bytes=dir_size,
                    file_count=child_count,
                    depth=current_depth,
                    status="ALIVE",
                ))

                # Recurse into subdirectories
                try:
                    for child in sorted(path.iterdir()):
                        if len(files) >= max_files:
                            break
                        _scan(child, current_depth + 1)
                except (PermissionError, OSError):
                    pass

        except (PermissionError, OSError):
            pass

    _scan(target, 0)
    return files


# ============================================================
#  COMMAND PARSER — Extract target paths from commands
# ============================================================

def extract_target_paths(command: str) -> list:
    """
    Parse a command and extract the target file/directory paths.
    Handles both Linux and Windows commands, including quoted paths with spaces.
    """
    cmd = command.strip()
    paths = []

    # STEP 1: Extract all quoted paths first (handles spaces correctly)
    quoted_paths = re.findall(r'"([^"]+)"', cmd)
    quoted_paths += re.findall(r"'([^']+)'", cmd)

    if quoted_paths:
        # Filter out things that aren't paths (like flags)
        for qp in quoted_paths:
            qp = qp.strip()
            if qp and len(qp) > 1:
                # Keep if it has path separators or looks like a real path
                if '\\' in qp or '/' in qp or os.path.exists(qp) or ':' in qp:
                    paths.append(qp)

    # STEP 2: If no quoted paths, parse unquoted arguments
    if not paths:
        cmd_lower = cmd.lower()

        # Strip the command itself and flags, keep the rest as path
        # rm -rf /path  ->  /path
        # del /f /s /q path -> path
        stripped = re.sub(r'^(sudo\s+)?(rm|del|rmdir|rd|erase|Remove-Item|chmod|chown|icacls|takeown)\s+', '', cmd, flags=re.IGNORECASE)
        # Remove flags like -rf, /s, /q, -Recurse, -Force, etc.
        stripped = re.sub(r'\s+(-[a-zA-Z]+|/[a-zA-Z])\b', '', stripped)
        # Remove permission numbers (chmod 777)
        stripped = re.sub(r'^\d+\s+', '', stripped.strip())
        stripped = stripped.strip()

        if stripped:
            # Split remaining by spaces, but only if no path separators
            if '\\' in stripped or '/' in stripped:
                # Likely a single path, keep as-is
                paths.append(stripped)
            else:
                for part in stripped.split():
                    if part and not part.startswith('-') and not part.startswith('/'):
                        paths.append(part)

    # STEP 3: Handle special commands (git push, kill, etc.)
    if not paths:
        cmd_lower = cmd.lower()
        if 'git push' in cmd_lower and ('--force' in cmd_lower or '-f' in cmd_lower):
            # Look for .git folder to find the repo root
            cwd = os.getcwd()
            if os.path.isdir(os.path.join(cwd, '.git')):
                paths.append(cwd)
            else:
                paths.append(cwd)
        elif any(k in cmd_lower for k in ['kill ', 'taskkill ', 'stop-process']):
            # Process commands — no filesystem target, use cwd for context
            paths.append(os.getcwd())
        elif any(k in cmd_lower for k in ['drop ', 'delete from', 'truncate ']):
            # Database commands — no filesystem target
            paths.append(os.getcwd())

    # STEP 4: Handle glob patterns (*.*, *.txt, etc.)
    expanded = []
    for p in paths:
        # Remove trailing wildcards for directory scanning
        # e.g., "C:\Users\test\Desktop\*.*" -> "C:\Users\test\Desktop"
        clean = re.sub(r'[\\/]\*\.?\*?$', '', p)
        if clean:
            try:
                expanded.append(str(pathlib.Path(clean).expanduser()))
            except:
                expanded.append(clean)

    return expanded if expanded else paths


# ============================================================
#  SANDBOX SIMULATOR
# ============================================================

def detect_command_type(command: str) -> str:
    """Detect what type of destructive action this command performs."""
    cmd = command.lower()

    if any(k in cmd for k in ['rm ', 'del ', 'rmdir', 'remove-item', 'erase ']):
        return "DELETE"
    elif any(k in cmd for k in ['chmod', 'icacls', 'takeown', 'cacls']):
        return "PERMISSION_CHANGE"
    elif any(k in cmd for k in ['mv ', 'move ', 'rename', 'ren ']):
        return "MOVE"
    elif any(k in cmd for k in ['cp ', 'copy ', 'xcopy', 'robocopy']):
        return "COPY"
    elif any(k in cmd for k in ['format ', 'mkfs', 'dd if=']):
        return "FORMAT"
    elif any(k in cmd for k in ['git push --force', 'git push -f']):
        return "FORCE_PUSH"
    elif any(k in cmd for k in ['drop ', 'delete from', 'truncate']):
        return "DATABASE_DELETE"
    elif any(k in cmd for k in ['kill', 'taskkill', 'stop-process']):
        return "PROCESS_KILL"
    elif any(k in cmd for k in ['shutdown', 'reboot', 'halt', 'restart-computer', 'stop-computer']):
        return "SYSTEM_SHUTDOWN"
    else:
        return "UNKNOWN"


def is_recursive_delete(command: str) -> bool:
    """Check if the command does a recursive delete."""
    cmd = command.lower()
    return any(k in cmd for k in [
        'rm -r', 'rm -rf', 'rmdir /s', 'remove-item -recurse',
        'del /s', 'rd /s',
    ])


def simulate_in_sandbox(command: str) -> SandboxResult:
    """
    THE CORE SANDBOX FUNCTION.

    Takes a command, scans the real filesystem for context,
    then simulates what would happen WITHOUT touching anything.

    Returns a full before/after diff.
    """
    result = SandboxResult(
        command=command,
        sandbox_id=f"sandbox-{datetime.now().strftime('%H%M%S')}",
        timestamp=datetime.now().isoformat(),
    )

    cmd_type = detect_command_type(command)
    target_paths = extract_target_paths(command)
    recursive = is_recursive_delete(command)

    if not target_paths:
        result.impact_summary = "Could not determine target paths from command."
        return result

    # Use the first target path as primary
    primary_target = target_paths[0]
    result.target_path = primary_target
    result.target_exists = os.path.exists(primary_target)

    # ── STEP 1: SCAN BEFORE STATE ──
    before_files = []
    if result.target_exists:
        before_files = scan_directory(primary_target, max_depth=4, max_files=200)
    else:
        # Path doesn't exist - still show what the command tried to do
        result.impact_summary = f"Target '{primary_target}' does not exist. Command would fail."
        return result

    result.before_tree = [f.to_dict() for f in before_files]
    result.before_file_count = sum(1 for f in before_files if not f.is_dir)
    result.before_dir_count = sum(1 for f in before_files if f.is_dir)
    result.before_total_size = sum(f.size_bytes for f in before_files if not f.is_dir)

    # ── STEP 2: SIMULATE THE COMMAND ──
    after_files = []
    deleted_files = []
    modified_files = []
    permission_changed = []
    survived_files = []

    if cmd_type == "DELETE":
        if recursive:
            # Recursive delete — EVERYTHING under the target is gone
            for f in before_files:
                f_copy = VirtualFile(**asdict(f))
                f_copy.status = "DELETED"
                deleted_files.append(f_copy.to_dict())
            # After state: empty
            after_files = []
        else:
            # Non-recursive delete — only files in the immediate directory
            target_p = pathlib.Path(primary_target)
            for f in before_files:
                f_copy = VirtualFile(**asdict(f))
                fp = pathlib.Path(f.path)

                if not f.is_dir and fp.parent == target_p:
                    # File directly in target dir — deleted
                    f_copy.status = "DELETED"
                    deleted_files.append(f_copy.to_dict())
                elif f.is_dir and fp == target_p:
                    # The target dir itself survives (non-recursive)
                    f_copy.status = "ALIVE"
                    after_files.append(f_copy.to_dict())
                    survived_files.append(f_copy.to_dict())
                elif f.is_dir:
                    # Subdirectories survive in non-recursive mode
                    f_copy.status = "ALIVE"
                    after_files.append(f_copy.to_dict())
                    survived_files.append(f_copy.to_dict())
                else:
                    # Files in subdirs survive
                    f_copy.status = "ALIVE"
                    after_files.append(f_copy.to_dict())
                    survived_files.append(f_copy.to_dict())

    elif cmd_type == "PERMISSION_CHANGE":
        # Nothing deleted, but permissions change on everything
        for f in before_files:
            f_copy = VirtualFile(**asdict(f))
            f_copy.status = "PERMISSION_CHANGED"
            after_files.append(f_copy.to_dict())
            permission_changed.append(f_copy.to_dict())

    elif cmd_type == "FORMAT":
        # Everything is gone — catastrophic
        for f in before_files:
            f_copy = VirtualFile(**asdict(f))
            f_copy.status = "DELETED"
            deleted_files.append(f_copy.to_dict())
        after_files = []

    elif cmd_type == "FORCE_PUSH":
        # Show git objects that could be affected
        for f in before_files:
            f_copy = VirtualFile(**asdict(f))
            if '.git' in f.path:
                f_copy.status = "MODIFIED"
                modified_files.append(f_copy.to_dict())
            else:
                f_copy.status = "ALIVE"
                survived_files.append(f_copy.to_dict())
            after_files.append(f_copy.to_dict())

    elif cmd_type in ("DATABASE_DELETE", "PROCESS_KILL", "SYSTEM_SHUTDOWN"):
        # These don't directly affect filesystem, show conceptual impact
        for f in before_files:
            f_copy = VirtualFile(**asdict(f))
            f_copy.status = "ALIVE"
            after_files.append(f_copy.to_dict())
            survived_files.append(f_copy.to_dict())
        result.impact_summary = f"Command type '{cmd_type}' affects running services, not filesystem directly."

    else:
        # Unknown — assume destructive on all files
        for f in before_files:
            f_copy = VirtualFile(**asdict(f))
            f_copy.status = "DELETED"
            deleted_files.append(f_copy.to_dict())

    # ── STEP 3: COMPUTE AFTER STATE ──
    result.after_tree = after_files
    result.after_file_count = sum(1 for f in after_files if not f.get("is_dir", False))
    result.after_dir_count = sum(1 for f in after_files if f.get("is_dir", False))
    result.after_total_size = sum(f.get("size_bytes", 0) for f in after_files if not f.get("is_dir", False))

    result.files_deleted = deleted_files
    result.files_modified = modified_files
    result.files_permission_changed = permission_changed
    result.files_survived = survived_files

    # ── STEP 4: IMPACT ANALYSIS ──
    data_destroyed = sum(f.get("size_bytes", 0) for f in deleted_files if not f.get("is_dir", False))
    result.data_destroyed_bytes = data_destroyed
    result.data_destroyed_readable = format_size(data_destroyed)

    if result.before_file_count > 0:
        deleted_count = sum(1 for f in deleted_files if not f.get("is_dir", False))
        result.destruction_percentage = round(100 * deleted_count / max(result.before_file_count, 1), 1)
    else:
        result.destruction_percentage = 0.0

    result.is_catastrophic = result.destruction_percentage >= 80 or data_destroyed > 100 * 1024 * 1024  # >100MB

    # Generate impact summary
    del_count = len(deleted_files)
    mod_count = len(modified_files)
    perm_count = len(permission_changed)

    parts = []
    if del_count > 0:
        parts.append(f"{del_count} files/dirs PERMANENTLY DELETED ({format_size(data_destroyed)} of data GONE)")
    if mod_count > 0:
        parts.append(f"{mod_count} files MODIFIED")
    if perm_count > 0:
        parts.append(f"{perm_count} files had PERMISSIONS CHANGED (security risk)")
    if not parts:
        parts.append("No direct filesystem impact detected")

    result.impact_summary = " | ".join(parts)

    return result


# ============================================================
#  PRETTY PRINT — Visual tree diff
# ============================================================

def format_tree_line(name: str, is_dir: bool, depth: int, status: str, size: int, is_last: bool = False) -> str:
    """Format a single line of the tree visualization."""
    indent = ""
    for i in range(depth):
        indent += "    "

    connector = "└── " if is_last else "├── "
    if depth == 0:
        connector = ""

    status_icons = {
        "ALIVE": "  ",
        "DELETED": "❌",
        "MODIFIED": "✏️ ",
        "CREATED": "✨",
        "PERMISSION_CHANGED": "🔓",
    }
    icon = status_icons.get(status, "  ")

    type_icon = "📁" if is_dir else "📄"
    size_str = f" ({format_size(size)})" if not is_dir and size > 0 else ""

    color_start = ""
    if status == "DELETED":
        color_start = "~~"
        return f"  {icon} {indent}{connector}{type_icon} ~~{name}~~{size_str}"

    return f"  {icon} {indent}{connector}{type_icon} {name}{size_str}"


def format_sandbox_result(result: SandboxResult) -> str:
    """Format the sandbox result as a visual diff for terminal display."""
    lines = []
    lines.append("")
    lines.append("  " + "=" * 58)
    lines.append("  BASHGUARD SANDBOX - VIRTUAL EXECUTION RESULT")
    lines.append("  " + "=" * 58)
    lines.append("")
    lines.append(f"  Command:  {result.command}")
    lines.append(f"  Target:   {result.target_path}")
    lines.append(f"  Exists:   {'YES' if result.target_exists else 'NO'}")
    lines.append("")

    # ── BEFORE STATE ──
    lines.append("  ┌─────────────────────────────────────────────────────┐")
    lines.append("  │  BEFORE (Current Filesystem State)                 │")
    lines.append("  ├─────────────────────────────────────────────────────┤")
    lines.append(f"  │  Files:       {result.before_file_count:<38}│")
    lines.append(f"  │  Directories: {result.before_dir_count:<38}│")
    lines.append(f"  │  Total Size:  {format_size(result.before_total_size):<38}│")
    lines.append("  └─────────────────────────────────────────────────────┘")
    lines.append("")

    # Show before tree (limit to 30 items)
    if result.before_tree:
        lines.append("  FILESYSTEM TREE (before):")
        for i, f in enumerate(result.before_tree[:30]):
            is_last = (i == len(result.before_tree[:30]) - 1)
            line = format_tree_line(
                f["name"], f["is_dir"], f["depth"],
                "ALIVE", f["size_bytes"], is_last
            )
            lines.append(line)
        if len(result.before_tree) > 30:
            lines.append(f"     ... and {len(result.before_tree) - 30} more items")
        lines.append("")

    # ── IMPACT VISUALIZATION ──
    lines.append("  " + "=" * 58)
    lines.append("  SIMULATED EXECUTION - WHAT WOULD HAPPEN")
    lines.append("  " + "=" * 58)
    lines.append("")

    if result.files_deleted:
        lines.append(f"  DELETED ({len(result.files_deleted)} items):")
        for i, f in enumerate(result.files_deleted[:25]):
            type_icon = "📁" if f["is_dir"] else "📄"
            size_str = f" ({format_size(f['size_bytes'])})" if not f["is_dir"] else f" ({f.get('file_count', 0)} items)"
            lines.append(f"  ❌ {type_icon} {f['name']}{size_str}")
        if len(result.files_deleted) > 25:
            lines.append(f"     ... and {len(result.files_deleted) - 25} more items DELETED")
        lines.append("")

    if result.files_modified:
        lines.append(f"  MODIFIED ({len(result.files_modified)} items):")
        for f in result.files_modified[:15]:
            type_icon = "📁" if f["is_dir"] else "📄"
            lines.append(f"  ✏️  {type_icon} {f['name']}")
        lines.append("")

    if result.files_permission_changed:
        lines.append(f"  PERMISSIONS CHANGED ({len(result.files_permission_changed)} items):")
        for f in result.files_permission_changed[:15]:
            type_icon = "📁" if f["is_dir"] else "📄"
            lines.append(f"  🔓 {type_icon} {f['name']} -> NOW WORLD-WRITABLE")
        lines.append("")

    # ── AFTER STATE ──
    lines.append("  ┌─────────────────────────────────────────────────────┐")
    lines.append("  │  AFTER (Simulated Result)                          │")
    lines.append("  ├─────────────────────────────────────────────────────┤")
    lines.append(f"  │  Files:       {result.after_file_count:<38}│")
    lines.append(f"  │  Directories: {result.after_dir_count:<38}│")
    lines.append(f"  │  Total Size:  {format_size(result.after_total_size):<38}│")
    lines.append("  └─────────────────────────────────────────────────────┘")
    lines.append("")

    # ── DAMAGE REPORT ──
    if result.is_catastrophic:
        lines.append("  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        lines.append("  !!         CATASTROPHIC DATA LOSS DETECTED         !!")
        lines.append("  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        lines.append("  ------ DAMAGE REPORT ------")

    lines.append("")
    lines.append(f"  Data destroyed:       {result.data_destroyed_readable}")
    lines.append(f"  Destruction:          {result.destruction_percentage}% of target")
    lines.append(f"  Catastrophic:         {'YES - IRREVERSIBLE' if result.is_catastrophic else 'No'}")
    lines.append(f"  Impact:               {result.impact_summary}")
    lines.append("")
    lines.append("  " + "=" * 58)
    lines.append("  This was a SANDBOX simulation. Nothing was actually executed.")
    lines.append("  " + "=" * 58)

    return "\n".join(lines)


# ============================================================
#  RAW COMMAND DETECTOR
# ============================================================

# Patterns that indicate a raw command (not natural language)
RAW_COMMAND_PATTERNS = [
    r'^rm\s+',
    r'^sudo\s+rm\s+',
    r'^del\s+',
    r'^rmdir\s+',
    r'^rd\s+',
    r'^Remove-Item\s+',
    r'^erase\s+',
    r'^format\s+[a-zA-Z]:',
    r'^mkfs\.',
    r'^dd\s+if=',
    r'^chmod\s+',
    r'^chown\s+',
    r'^icacls\s+',
    r'^takeown\s+',
    r'^git\s+push\s+.*(-f|--force)',
    r'^kill\s+',
    r'^killall\s+',
    r'^pkill\s+',
    r'^taskkill\s+',
    r'^Stop-Process\s+',
    r'^shutdown\b',
    r'^reboot\b',
    r'^halt\b',
    r'^Stop-Computer\b',
    r'^Restart-Computer\b',
    r'^DROP\s+',
    r'^DELETE\s+FROM',
    r'^TRUNCATE\s+',
    r'^mv\s+/\s',  # mv / something (moving root)
    r'^>\s*/dev/',
    r':\(\)\{',  # fork bomb
    r'^curl\s+.*\|\s*(bash|sh)',
    r'^wget\s+.*\|\s*(bash|sh)',
    r'^npm\s+publish',
    r'^reg\s+delete',
    r'^net\s+stop\s+',
    r'^sc\s+delete\s+',
]


def is_raw_command(user_input: str) -> bool:
    """
    Detect if the user typed a raw system command (not natural language).
    Returns True if it looks like a direct command.
    """
    text = user_input.strip()

    # Check against known patterns
    for pattern in RAW_COMMAND_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    return False


def detect_danger_level(command: str) -> str:
    """Quick danger check for a raw command."""
    cmd = command.lower()

    critical_patterns = [
        'rm -rf /', 'rm -rf /*', 'del /f /s /q c:', 'format c:',
        ':(){:|:&};:', '> /dev/sda', 'dd if=/dev/zero',
        'remove-item -recurse -force c:', 'drop database',
    ]
    for p in critical_patterns:
        if p in cmd:
            return "CRITICAL"

    high_patterns = [
        'rm -rf', 'rm -r', 'rmdir /s', 'del /s', 'del /f',
        'chmod 777', 'chmod 000', 'kill -9', 'killall',
        'git push --force', 'git push -f', 'drop table',
        'delete from', 'truncate', 'format ',
    ]
    for p in high_patterns:
        if p in cmd:
            return "HIGH"

    medium_patterns = [
        'rm ', 'del ', 'rmdir', 'remove-item', 'chmod ',
        'kill ', 'taskkill', 'stop-process', 'mv ',
    ]
    for p in medium_patterns:
        if p in cmd:
            return "MEDIUM"

    return "LOW"


# ============================================================
#  QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("\n=== BashGuard Sandbox Test ===\n")

    # Test with the project directory itself
    test_commands = [
        f'rm -rf "{os.getcwd()}"',
        f'del /s /q "{os.getcwd()}"',
        f'chmod 777 "{os.getcwd()}"',
    ]

    for cmd in test_commands:
        print(f"\nTesting: {cmd}")
        result = simulate_in_sandbox(cmd)
        print(format_sandbox_result(result))
        print("\n" + "-" * 60)

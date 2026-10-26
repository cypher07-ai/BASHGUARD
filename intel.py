"""
BashGuard — Intel Module (Storage Intelligence & Fuzzy File Resolver)
======================================================================
1. Storage Classifier:
   - Scans directories/drives and classifies files/media into:
     - TRASH: Temporary files, build caches, log files, duplicate files, old installers.
     - REVIEW: Large unaccessed media, old archives, stale downloads.
     - ESSENTIAL: Source code, documents, configs, git repos.
   - Computes reclaimable disk space and safely quarantines or removes trash.

2. Fuzzy File Resolver:
   - Resolves files by partial/initial name (e.g. "serv" -> "server.py", "res" -> "resume.pdf").
   - Executes file actions (read, edit, delete, move, create) without requiring full paths.
"""

import os
import sys
import glob
import shutil
import hashlib
import difflib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Ensure proper encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─── Heuristic Pattern Definitions ────────────────────────────────────────────

TRASH_EXTENSIONS = {
    ".tmp", ".temp", ".log", ".bak", ".old", ".dmp", ".chk", ".swp", ".swo",
    ".pyc", ".pyo", ".class", ".o", ".obj", ".tlog", ".ipch"
}

TRASH_FILENAMES = {
    "thumbs.db", ".ds_store", "desktop.ini", "npm-debug.log",
    "yarn-error.log", "yarn-debug.log", "pip-log.txt", "coverage.xml"
}

TRASH_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".sass-cache",
    ".parcel-cache", ".cache", "tmp", "temp"
}

INSTALLER_EXTENSIONS = {".msi", ".exe", ".pkg", ".dmg", ".iso"}

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".rar", ".7z", ".bz2"}

ESSENTIAL_EXTENSIONS = {
    # Code
    ".py", ".ts", ".tsx", ".js", ".jsx", ".cpp", ".c", ".h", ".hpp",
    ".rs", ".go", ".java", ".cs", ".rb", ".php", ".swift", ".kt", ".sql",
    # Config
    ".json", ".yaml", ".yml", ".toml", ".env", ".ini", ".conf", ".cfg",
    # Docs
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".md", ".csv"
}

MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4", ".mov", ".mkv",
    ".avi", ".mp3", ".wav", ".flac", ".ogg", ".webm"
}


def _file_hash(path: str, block_size: int = 65536) -> str:
    """Calculate quick sha256 hash for first 256KB to detect duplicates fast."""
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            buf = f.read(block_size * 4)
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception:
        return ""


def format_bytes(bytes_count: int) -> str:
    """Human-readable size format."""
    if not bytes_count or bytes_count <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    val = float(bytes_count)
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.1f} {units[idx]}"


# ─── 1. Storage Classifier (Trash vs. Necessary) ──────────────────────────────

def classify_storage(
    target_path: Optional[str] = None,
    max_files: int = 500,
    include_subdirs: bool = True
) -> Dict[str, Any]:
    """
    Scans a folder and categorizes files into TRASH, REVIEW, and ESSENTIAL.
    Identifies duplicate files, stale installers, and cache bloat.
    """
    if not target_path:
        target_path = os.getcwd()

    target_path = os.path.abspath(os.path.expanduser(target_path))
    if not os.path.exists(target_path):
        return {"error": f"Path not found: {target_path}", "files": []}

    now = datetime.now()
    two_weeks_ago = now - timedelta(days=14)
    sixty_days_ago = now - timedelta(days=60)

    items: List[Dict[str, Any]] = []
    seen_hashes: Dict[str, str] = {}  # hash -> first_path
    duplicates: List[Dict[str, Any]] = []

    total_bytes = 0
    trash_bytes = 0
    review_bytes = 0
    essential_bytes = 0

    scanned_count = 0

    walker = os.walk(target_path) if include_subdirs else [(target_path, [], os.listdir(target_path))]

    for root, dirs, files in walker:
        # Skip node_modules inside projects unless explicitly targeted
        parts = Path(root).parts
        if "node_modules" in parts and target_path != root:
            continue
        if ".git" in parts and "objects" in parts:
            continue

        for f in files:
            scanned_count += 1
            if scanned_count > max_files:
                break

            file_path = os.path.join(root, f)
            try:
                stat = os.stat(file_path)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)
                ext = os.path.splitext(f)[1].lower()
                name_lower = f.lower()
            except Exception:
                continue

            total_bytes += size

            category = "ESSENTIAL"
            reason = "Active user file or source document"
            confidence = 80
            safe_to_delete = False

            # Check 1: Explicit Trash filename / extension
            if ext in TRASH_EXTENSIONS or name_lower in TRASH_FILENAMES:
                category = "TRASH"
                reason = f"Temporary/cache file ({ext or name_lower})"
                confidence = 98
                safe_to_delete = True

            # Check 2: Parent folder is trash/cache
            elif any(td in parts for td in TRASH_DIR_NAMES):
                category = "TRASH"
                reason = "Located inside temporary/cache directory"
                confidence = 95
                safe_to_delete = True

            # Check 3: Zero-byte files (except configs or init files)
            elif size == 0 and not f.startswith("__init__") and not f.startswith("."):
                category = "TRASH"
                reason = "Empty zero-byte file"
                confidence = 90
                safe_to_delete = True

            # Check 4: Old installers in Downloads/Temp
            elif ext in INSTALLER_EXTENSIONS and ("download" in root.lower() or "temp" in root.lower()):
                if mtime < two_weeks_ago:
                    category = "TRASH"
                    reason = f"Old installer package ({ext}) older than 14 days; can be re-downloaded"
                    confidence = 88
                    safe_to_delete = True
                else:
                    category = "REVIEW"
                    reason = "Recent installer package; verify if installation is complete"
                    confidence = 70

            # Check 5: Duplicate detection (files > 10KB)
            elif size > 10240:
                h = _file_hash(file_path)
                if h:
                    if h in seen_hashes:
                        orig = seen_hashes[h]
                        category = "TRASH"
                        reason = f"Exact duplicate of {os.path.basename(orig)}"
                        confidence = 96
                        safe_to_delete = True
                        duplicates.append({"original": orig, "duplicate": file_path, "size": size})
                    else:
                        seen_hashes[h] = file_path

            # Check 6: Large unaccessed media or archives
            if category == "ESSENTIAL":
                if ext in MEDIA_EXTENSIONS and size > 50 * 1024 * 1024 and mtime < sixty_days_ago:
                    category = "REVIEW"
                    reason = f"Large media file ({format_bytes(size)}) unaccessed for over 60 days"
                    confidence = 75
                elif ext in ARCHIVE_EXTENSIONS and size > 20 * 1024 * 1024:
                    category = "REVIEW"
                    reason = f"Large compressed archive ({format_bytes(size)}); verify if already unpacked"
                    confidence = 70

            # Update tally
            if category == "TRASH":
                trash_bytes += size
            elif category == "REVIEW":
                review_bytes += size
            else:
                essential_bytes += size

            items.append({
                "path": file_path,
                "name": f,
                "size_bytes": size,
                "size_readable": format_bytes(size),
                "modified": mtime.strftime("%Y-%m-%d %H:%M"),
                "category": category,
                "reason": reason,
                "confidence": confidence,
                "safe_to_delete": safe_to_delete
            })

        if scanned_count > max_files:
            break

    # Sort items: TRASH first (largest first), then REVIEW, then ESSENTIAL
    cat_order = {"TRASH": 0, "REVIEW": 1, "ESSENTIAL": 2}
    items.sort(key=lambda x: (cat_order.get(x["category"], 3), -x["size_bytes"]))

    trash_count = sum(1 for i in items if i["category"] == "TRASH")
    review_count = sum(1 for i in items if i["category"] == "REVIEW")
    essential_count = sum(1 for i in items if i["category"] == "ESSENTIAL")

    reclaim_pct = round((trash_bytes / max(total_bytes, 1)) * 100, 1)

    return {
        "target_path": target_path,
        "scanned_files_count": len(items),
        "total_size_bytes": total_bytes,
        "total_size_readable": format_bytes(total_bytes),
        "trash": {
            "count": trash_count,
            "bytes": trash_bytes,
            "readable": format_bytes(trash_bytes),
            "reclaim_percentage": reclaim_pct,
            "items": [i for i in items if i["category"] == "TRASH"]
        },
        "review": {
            "count": review_count,
            "bytes": review_bytes,
            "readable": format_bytes(review_bytes),
            "items": [i for i in items if i["category"] == "REVIEW"]
        },
        "essential": {
            "count": essential_count,
            "bytes": essential_bytes,
            "readable": format_bytes(essential_bytes),
            "sample": [i for i in items if i["category"] == "ESSENTIAL"][:15]
        },
        "duplicates_found": len(duplicates)
    }


def clean_trash_items(
    file_paths: List[str],
    quarantine: bool = True
) -> Dict[str, Any]:
    """
    Safely removes or quarantines identified trash files.
    If quarantine=True, moves to .bashguard_trash_staging/ with rollback capability.
    """
    staging_dir = os.path.abspath(".bashguard_trash_staging")
    if quarantine and not os.path.exists(staging_dir):
        os.makedirs(staging_dir, exist_ok=True)

    cleaned: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []
    freed_bytes = 0

    for fp in file_paths:
        abs_p = os.path.abspath(fp)
        if not os.path.exists(abs_p):
            continue
        try:
            sz = os.path.getsize(abs_p)
            if quarantine:
                dest = os.path.join(staging_dir, f"{datetime.now().strftime('%H%M%S')}_{os.path.basename(abs_p)}")
                shutil.move(abs_p, dest)
                cleaned.append({"file": abs_p, "quarantined_to": dest, "freed_bytes": sz})
            else:
                os.remove(abs_p)
                cleaned.append({"file": abs_p, "deleted": True, "freed_bytes": sz})
            freed_bytes += sz
        except Exception as e:
            failed.append({"file": abs_p, "error": str(e)})

    return {
        "status": "success",
        "cleaned_count": len(cleaned),
        "failed_count": len(failed),
        "freed_bytes": freed_bytes,
        "freed_readable": format_bytes(freed_bytes),
        "quarantined": quarantine,
        "staging_dir": staging_dir if quarantine else None,
        "cleaned": cleaned,
        "failed": failed
    }


# ─── 2. Fuzzy File Resolver & Auto-File Operations ────────────────────────────

def resolve_file(
    query: str,
    search_dirs: Optional[List[str]] = None,
    max_results: int = 8
) -> Dict[str, Any]:
    """
    Finds files matching prefix, initial substring, or fuzzy similarity.
    Allows user to type 'serv' or 'app' and find 'server.py' or 'App.tsx'.
    """
    if not query or not query.strip():
        return {"query": query, "matches": []}

    query = query.strip().lower()

    if not search_dirs:
        # Default smart search locations: current workspace, Downloads, Documents, Desktop
        home = str(Path.home())
        search_dirs = [
            os.getcwd(),
            os.path.join(home, "Downloads"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents")
        ]

    candidates: List[Dict[str, Any]] = []

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            # Walk up to 3 levels deep per directory
            for root, dirs, files in os.walk(d):
                rel_depth = len(Path(root).relative_to(Path(d)).parts)
                if rel_depth > 3:
                    continue
                if "node_modules" in dirs:
                    dirs.remove("node_modules")
                if ".git" in dirs:
                    dirs.remove(".git")

                for f in files:
                    f_lower = f.lower()
                    full_p = os.path.join(root, f)

                    score = 0.0
                    match_type = "none"

                    # Exact match (without or with ext)
                    base, ext = os.path.splitext(f_lower)
                    if f_lower == query or base == query:
                        score = 1.0
                        match_type = "exact"
                    # Starts with prefix
                    elif f_lower.startswith(query) or base.startswith(query):
                        score = 0.9
                        match_type = "prefix"
                    # Substring match
                    elif query in f_lower:
                        score = 0.75
                        match_type = "substring"
                    else:
                        # Fuzzy ratio
                        ratio = difflib.SequenceMatcher(None, query, base).ratio()
                        if ratio > 0.6:
                            score = ratio * 0.7
                            match_type = "fuzzy"

                    if score >= 0.45:
                        try:
                            sz = os.path.getsize(full_p)
                            mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            sz = 0
                            mtime = "unknown"

                        candidates.append({
                            "name": f,
                            "path": full_p,
                            "relative_path": os.path.relpath(full_p, os.getcwd()) if full_p.startswith(os.getcwd()) else full_p,
                            "size_bytes": sz,
                            "size_readable": format_bytes(sz),
                            "modified": mtime,
                            "score": round(score, 2),
                            "match_type": match_type
                        })
        except Exception:
            continue

    # Deduplicate candidates by path and sort by score descending, then by size
    seen = set()
    unique_candidates = []
    for c in sorted(candidates, key=lambda x: (-x["score"], -x["size_bytes"])):
        if c["path"] not in seen:
            seen.add(c["path"])
            unique_candidates.append(c)

    top_matches = unique_candidates[:max_results]
    best_match = top_matches[0] if top_matches else None

    return {
        "query": query,
        "best_match": best_match,
        "total_matches": len(unique_candidates),
        "matches": top_matches
    }


def execute_file_operation(
    target_path: str,
    operation: str,
    content: Optional[str] = None,
    destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs file operations (read, write, append, replace, delete, move, create_folder).
    """
    abs_path = os.path.abspath(target_path)
    operation = operation.lower().strip()

    if operation == "create_folder":
        os.makedirs(abs_path, exist_ok=True)
        return {"status": "success", "operation": "create_folder", "path": abs_path}

    if operation == "read":
        if not os.path.exists(abs_path):
            return {"status": "error", "message": f"File does not exist: {abs_path}"}
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read(50000)  # max 50KB preview
            return {
                "status": "success",
                "operation": "read",
                "path": abs_path,
                "content": data,
                "truncated": len(data) >= 50000
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif operation in ("write", "create"):
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content or "")
            return {"status": "success", "operation": operation, "path": abs_path, "size": len(content or "")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif operation == "append":
        try:
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(content or "")
            return {"status": "success", "operation": "append", "path": abs_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif operation == "delete":
        if not os.path.exists(abs_path):
            return {"status": "error", "message": f"File not found: {abs_path}"}
        try:
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            return {"status": "success", "operation": "delete", "path": abs_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif operation == "move" and destination:
        try:
            dest_abs = os.path.abspath(destination)
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            shutil.move(abs_path, dest_abs)
            return {"status": "success", "operation": "move", "from": abs_path, "to": dest_abs}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": f"Unknown operation: {operation}"}

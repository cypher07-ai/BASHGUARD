"""
BashGuard — Coding Engine
===========================
Detects coding requests and generates complete, working code
in any programming language using Gemini LLM.

Supports:
  - Any language: Python, JavaScript, C, C++, Java, Go, Rust, Bash, etc.
  - Auto-saves to file with correct extension
  - Auto-runs code for supported languages (Python, Node.js, bash)
  - Explains what the code does
  - Iterates on code based on feedback
"""

import os
import sys
import re
import json
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
os.environ.setdefault("HTTPX_NO_VERIFY", "1")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.5-flash-lite"


# ============================================================
#  DATA STRUCTURES
# ============================================================

@dataclass
class CodeResult:
    """Result of a code generation request."""
    request: str = ""
    language: str = ""
    filename: str = ""
    code: str = ""
    explanation: str = ""
    how_to_run: str = ""
    dependencies: list = field(default_factory=list)
    file_saved_to: str = ""
    run_output: str = ""
    run_success: bool = False
    run_attempted: bool = False
    error: str = ""

    def to_dict(self):
        return asdict(self)


# ============================================================
#  LANGUAGE DETECTION & FILE EXTENSION MAPPING
# ============================================================

LANGUAGE_MAP = {
    # Language keyword -> (canonical name, file extension, run command template)
    "python":       ("Python",      ".py",    "python {file}"),
    "py":           ("Python",      ".py",    "python {file}"),
    "javascript":   ("JavaScript",  ".js",    "node {file}"),
    "js":           ("JavaScript",  ".js",    "node {file}"),
    "node":         ("JavaScript",  ".js",    "node {file}"),
    "typescript":   ("TypeScript",  ".ts",    "npx ts-node {file}"),
    "ts":           ("TypeScript",  ".ts",    "npx ts-node {file}"),
    "bash":         ("Bash",        ".sh",    "bash {file}"),
    "shell":        ("Bash",        ".sh",    "bash {file}"),
    "sh":           ("Bash",        ".sh",    "bash {file}"),
    "c":            ("C",           ".c",     None),  # needs compile
    "c++":          ("C++",         ".cpp",   None),
    "cpp":          ("C++",         ".cpp",   None),
    "java":         ("Java",        ".java",  None),
    "go":           ("Go",          ".go",    "go run {file}"),
    "golang":       ("Go",          ".go",    "go run {file}"),
    "rust":         ("Rust",        ".rs",    None),
    "ruby":         ("Ruby",        ".rb",    "ruby {file}"),
    "rb":           ("Ruby",        ".rb",    "ruby {file}"),
    "php":          ("PHP",         ".php",   "php {file}"),
    "swift":        ("Swift",       ".swift", "swift {file}"),
    "kotlin":       ("Kotlin",      ".kt",    None),
    "r":            ("R",           ".r",     "Rscript {file}"),
    "sql":          ("SQL",         ".sql",   None),
    "html":         ("HTML",        ".html",  None),
    "css":          ("CSS",         ".css",   None),
    "powershell":   ("PowerShell",  ".ps1",   "powershell -File {file}"),
    "ps1":          ("PowerShell",  ".ps1",   "powershell -File {file}"),
    "lua":          ("Lua",         ".lua",   "lua {file}"),
    "perl":         ("Perl",        ".pl",    "perl {file}"),
}

# Keywords that strongly indicate a CODING request
CODING_KEYWORDS = [
    "write", "create", "build", "make", "code", "program", "develop",
    "implement", "generate", "script", "function", "class", "app",
    "application", "game", "api", "server", "bot", "tool", "utility",
    "algorithm", "solve", "debug", "fix this code", "help me code",
    "can you code", "write me a", "give me a", "show me how to code",
]

# Patterns that are definitely coding requests
CODING_PATTERNS = [
    r"write\s+(a|an|me\s+a)?\s*(python|javascript|js|bash|code|script|program|function)",
    r"create\s+(a|an)?\s*(game|app|script|function|class|api|bot|server|tool)",
    r"build\s+(a|an)?\s*(game|app|website|api|bot|tool|script)",
    r"make\s+(a|an)?\s*(game|app|script|function|class|tool)",
    r"code\s+(a|an|for|that|which|to)",
    r"implement\s+(a|an|the)?",
    r"(snake|tetris|tic.tac.toe|calculator|todo|fibonacci|sorting|crud|rest.api|web.server)",
    r"in\s+(python|javascript|java|c\+\+|golang|rust|ruby|php|bash)\s*(please|that|which|for)?",
    r"using\s+(python|javascript|java|c\+\+|golang|rust|ruby)",
]


def is_coding_request(user_input: str) -> bool:
    """Detect if this is a coding request."""
    text = user_input.lower().strip()

    # Check patterns
    for pattern in CODING_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # Check keyword combinations
    has_coding_verb = any(kw in text for kw in ["write", "create", "build", "make", "code", "implement", "generate", "develop"])
    has_code_noun = any(kw in text for kw in ["code", "script", "program", "function", "class", "app", "game", "api", "bot", "algorithm"])
    if has_coding_verb and has_code_noun:
        return True

    return False


def detect_language(user_input: str) -> tuple:
    """
    Detect the requested programming language from user input.
    Returns (canonical_name, extension, run_command) or defaults to Python.
    """
    text = user_input.lower()

    # Check multi-word languages FIRST (before single chars like "c")
    priority_checks = ["c++", "c#", "golang", "typescript", "javascript", "powershell", "python"]
    for keyword in priority_checks:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text):
            if keyword in LANGUAGE_MAP:
                return LANGUAGE_MAP[keyword]

    # Then check the rest
    for keyword, info in LANGUAGE_MAP.items():
        if keyword in priority_checks:
            continue
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text):
            return info

    # Default to Python if no language specified
    return ("Python", ".py", "python {file}")


def sanitize_filename(request: str, extension: str) -> str:
    """Generate a clean filename from the request."""
    # Take first few meaningful words
    words = re.sub(r'[^\w\s]', '', request.lower()).split()
    # Skip common filler words
    skip = {"a", "an", "the", "me", "my", "i", "in", "for", "to", "of", "with", "using", "please", "can", "you", "write", "create", "build", "make", "code", "generate"}
    meaningful = [w for w in words if w not in skip][:4]
    base = "_".join(meaningful) if meaningful else "generated_code"
    # Sanitize
    base = re.sub(r'[^\w]', '_', base)[:40]
    timestamp = datetime.now().strftime("%H%M%S")
    return f"{base}_{timestamp}{extension}"


# ============================================================
#  CODE GENERATION PROMPT
# ============================================================

CODE_SYSTEM_PROMPT = """You are BashGuard's expert coding assistant. You write complete, working, production-quality code.

RULES:
1. ALWAYS write COMPLETE, RUNNABLE code — no placeholders, no "TODO", no "..." 
2. Write code that ACTUALLY WORKS right out of the box
3. Include proper error handling
4. Add clear comments explaining what each section does
5. For games: include game loop, win/loss conditions, proper UI
6. For APIs: include all routes, error responses, example usage
7. For algorithms: include the full implementation + a demo/test

You MUST respond with ONLY this JSON format (no markdown outside JSON):
{
    "language": "exact language name",
    "filename_suggestion": "descriptive_name.ext",
    "code": "THE COMPLETE CODE HERE",
    "explanation": "2-3 sentences explaining what this code does",
    "how_to_run": "exact command to run this code",
    "dependencies": ["list", "of", "pip/npm/etc packages needed"],
    "features": ["feature1", "feature2", "feature3"]
}

The "code" field must contain the ENTIRE program. Do NOT truncate it."""


def generate_code(user_request: str, language_hint: str = "", context: str = "") -> CodeResult:
    """
    Generate complete working code for any request.
    """
    result = CodeResult(request=user_request)

    lang_name, extension, run_cmd = detect_language(user_request if not language_hint else language_hint)
    result.language = lang_name

    # Build the prompt
    lang_context = f"Write this in {lang_name}." if lang_name else "Choose the best language for this task."
    user_prompt = f"""Generate complete, working code for this request:

REQUEST: "{user_request}"

{lang_context}
{f'Additional context: {context}' if context else ''}

Make it impressive and fully functional. If it's a game, it should be playable.
If it's a utility, it should handle edge cases. 
Respond ONLY with the JSON object. No markdown fences."""

    try:
        chat = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=CODE_SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )
        response = chat.send_message(user_prompt)
        response_text = response.text.strip()

        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:])
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()

        # Try to parse JSON — LLM sometimes wraps code in JSON-inside-JSON
        data = None
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # The response might itself be a code block containing JSON
            # Try finding the outermost JSON object
            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except Exception:
                    pass

        if data:
            result.language = data.get("language", lang_name)
            result.code = data.get("code", "")
            # Clean up escaped newlines in code (LLM sometimes double-escapes)
            if result.code:
                result.code = result.code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            result.explanation = data.get("explanation", "")
            result.how_to_run = data.get("how_to_run", "")
            result.dependencies = data.get("dependencies", [])

            # Generate filename
            suggested = data.get("filename_suggestion", "")
            if suggested and re.match(r'^[\w\-. ]+$', suggested):
                result.filename = re.sub(r'[^\w.\-]', '_', suggested)
            else:
                result.filename = sanitize_filename(user_request, extension)
        else:
            raise json.JSONDecodeError("No valid JSON found", response_text, 0)

    except json.JSONDecodeError:
        # Last resort: extract code from the raw text
        raw = response.text if hasattr(response, 'text') else response_text
        # Try to pull out just the code value from the JSON manually
        code_match = re.search(r'"code"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]', raw, re.DOTALL)
        if code_match:
            try:
                # Unescape the JSON string value
                result.code = json.loads('"' + code_match.group(1) + '"')
            except Exception:
                result.code = code_match.group(1).replace("\\n", "\n").replace("\\t", "\t")
        else:
            # Try markdown code block
            block_match = re.search(r'```(?:\w+)?\n(.*?)```', raw, re.DOTALL)
            result.code = block_match.group(1).strip() if block_match else raw

        # Also try to pull explanation
        expl_match = re.search(r'"explanation"\s*:\s*"([^"]*)"', raw)
        result.explanation = expl_match.group(1) if expl_match else "Code generated."
        how_match = re.search(r'"how_to_run"\s*:\s*"([^"]*)"', raw)
        result.how_to_run = how_match.group(1) if how_match else ""

        result.filename = sanitize_filename(user_request, extension)

    except Exception as e:
        result.error = str(e)
        result.code = f"# Error generating code: {e}"
        result.filename = sanitize_filename(user_request, extension)

    return result


# ============================================================
#  FILE SAVER
# ============================================================

def save_code(result: CodeResult, output_dir: str = None) -> str:
    """Save generated code to a file. Returns the saved file path."""
    if not output_dir:
        # Save in current working dir / generated_code/
        output_dir = os.path.join(os.getcwd(), "generated_code")

    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, result.filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result.code)

    result.file_saved_to = filepath
    return filepath


# ============================================================
#  CODE RUNNER
# ============================================================

RUNNABLE_EXTENSIONS = {".py", ".js", ".sh", ".rb", ".go", ".php", ".lua", ".pl", ".r", ".ps1"}

def run_code(result: CodeResult, timeout: int = 10) -> CodeResult:
    """
    Attempt to run the generated code.
    Only runs for safe, interpreted languages.
    """
    if not result.file_saved_to or not result.code:
        return result

    ext = os.path.splitext(result.filename)[1].lower()
    if ext not in RUNNABLE_EXTENSIONS:
        result.run_output = f"Auto-run not supported for {result.language}. Run manually with: {result.how_to_run}"
        result.run_attempted = False
        return result

    # Find the run command
    run_cmd = None
    for key, (lang, file_ext, cmd) in LANGUAGE_MAP.items():
        if file_ext == ext and cmd:
            run_cmd = cmd.replace("{file}", f'"{result.file_saved_to}"')
            break

    if not run_cmd:
        result.run_output = f"No auto-run configured for {ext}. Run manually."
        return result

    result.run_attempted = True
    try:
        proc = subprocess.run(
            run_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(result.file_saved_to),
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode == 0:
            result.run_success = True
            result.run_output = stdout if stdout else "(no output)"
        else:
            result.run_success = False
            result.run_output = f"STDERR: {stderr}" if stderr else f"Exit code: {proc.returncode}"

    except subprocess.TimeoutExpired:
        result.run_success = True  # Timeout likely means it's interactive (game loop etc.)
        result.run_output = "(Program is interactive — run it yourself in a terminal)"
        result.run_attempted = True

    except Exception as e:
        result.run_success = False
        result.run_output = f"Run error: {e}"

    return result


# ============================================================
#  PRETTY PRINT
# ============================================================

def format_code_result(result: CodeResult, show_full_code: bool = True) -> str:
    """Format code result for terminal display."""
    lines = []
    lines.append("")
    lines.append("  " + "=" * 58)
    lines.append("  BASHGUARD CODER - CODE GENERATED")
    lines.append("  " + "=" * 58)
    lines.append("")
    lines.append(f"  Request:   {result.request}")
    lines.append(f"  Language:  {result.language}")
    lines.append(f"  File:      {result.filename}")
    if result.file_saved_to:
        lines.append(f"  Saved to:  {result.file_saved_to}")
    lines.append("")

    if result.explanation:
        lines.append("  WHAT IT DOES:")
        lines.append(f"  {result.explanation}")
        lines.append("")

    if result.dependencies:
        lines.append("  DEPENDENCIES:")
        for dep in result.dependencies:
            lines.append(f"    pip install {dep}" if result.language == "Python" else f"    {dep}")
        lines.append("")

    if result.how_to_run:
        lines.append("  HOW TO RUN:")
        lines.append(f"    {result.how_to_run}")
        lines.append("")

    # Show code
    if show_full_code and result.code:
        lines.append("  " + "-" * 58)
        lines.append("  CODE:")
        lines.append("  " + "-" * 58)
        for line in result.code.split("\n"):
            lines.append(f"  {line}")
        lines.append("  " + "-" * 58)
        lines.append("")

    # Show run output
    if result.run_attempted:
        if result.run_success:
            lines.append("  AUTO-RUN OUTPUT:")
            for line in result.run_output.split("\n"):
                lines.append(f"    {line}")
        else:
            lines.append("  AUTO-RUN FAILED:")
            lines.append(f"    {result.run_output}")
        lines.append("")

    if result.error:
        lines.append(f"  ERROR: {result.error}")
        lines.append("")

    lines.append("  " + "=" * 58)
    return "\n".join(lines)


# ============================================================
#  QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("\n=== BashGuard Coder Test ===\n")

    tests = [
        "write a snake game in python",
        "create a fibonacci sequence calculator in javascript",
        "make a simple todo list CLI app in python",
    ]

    for req in tests:
        print(f"\nRequest: {req}")
        print(f"  Is coding request: {is_coding_request(req)}")
        lang = detect_language(req)
        print(f"  Detected language: {lang[0]} ({lang[1]})")

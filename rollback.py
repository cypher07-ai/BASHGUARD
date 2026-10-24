"""
BashGuard — Rollback Engine
==============================
Auto-generates undo/rollback commands for every action.
If something goes wrong, the user knows exactly how to reverse it.
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.5-flash-lite"

ROLLBACK_PROMPT = """You are a system recovery expert. Given a command that was just executed, generate the exact rollback/undo command that would reverse its effects.

RULES:
- Return ONLY a JSON object, no markdown
- If the action is truly irreversible (like permanent deletion without backup), say so honestly
- On Windows, always quote paths with spaces
- Be specific — don't give generic advice, give the exact command

Respond in this JSON format:
{
    "can_undo": true,
    "undo_command": "the exact command to reverse the action",
    "undo_explanation": "what the undo command does",
    "recovery_steps": ["step 1 if undo_command alone is not enough", "step 2"],
    "warning": "any warning about the undo process"
}
"""


def generate_rollback(executed_command: str, context: str = "") -> dict:
    """Generate a rollback/undo command for an executed action."""
    
    os_type = "Windows" if sys.platform == "win32" else "Linux/Mac"
    
    try:
        chat = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=ROLLBACK_PROMPT,
                temperature=0.1,
            ),
        )
        
        response = chat.send_message(
            f"Command that was executed: {executed_command}\n"
            f"OS: {os_type}\n"
            f"Context: {context or 'none'}\n\n"
            f"Generate the rollback command."
        )
        
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        return json.loads(text)
    
    except Exception as e:
        return {
            "can_undo": False,
            "undo_command": "",
            "undo_explanation": f"Could not generate rollback: {e}",
            "recovery_steps": [],
            "warning": "Manual recovery may be needed",
        }


def format_rollback(rollback: dict) -> str:
    """Format rollback info for display."""
    output = []
    output.append("")
    output.append("  🔄 ROLLBACK INFO:")
    output.append("  " + "-" * 50)
    
    if rollback.get("can_undo"):
        output.append(f"  Can undo: ✅ YES")
        output.append(f"  Undo command: {rollback.get('undo_command', 'N/A')}")
        output.append(f"  What it does: {rollback.get('undo_explanation', 'N/A')}")
    else:
        output.append(f"  Can undo: ❌ NO — This action is irreversible")
        if rollback.get("undo_explanation"):
            output.append(f"  Details: {rollback['undo_explanation']}")
    
    if rollback.get("recovery_steps"):
        output.append("  Recovery steps:")
        for i, step in enumerate(rollback["recovery_steps"], 1):
            output.append(f"    {i}. {step}")
    
    if rollback.get("warning"):
        output.append(f"  ⚠️  {rollback['warning']}")
    
    return "\n".join(output)


if __name__ == "__main__":
    # Test
    test_commands = [
        'mkdir "C:\\Users\\test\\Desktop\\new-folder"',
        'del /s /q "C:\\Users\\test\\logs\\*.*"',
        'git push --force origin main',
    ]
    
    for cmd in test_commands:
        print(f"\nCommand: {cmd}")
        rb = generate_rollback(cmd)
        print(format_rollback(rb))

"""
AI Agent — Hackathon Project
================================
A real AI agent that uses the ReAct (Reason + Act) pattern
to solve problems step by step using tools.

Setup:
  1. Install dependencies:  pip install -r requirements.txt
  2. Run:  python agent.py
"""

import os
import sys
import json

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from google import genai
from google.genai import types
from duckduckgo_search import DDGS

# ============================================================
#  CONFIG — loads API key from .env file
# ============================================================
load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    print("ERROR: Set GEMINI_API_KEY in your .env file")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.5-flash"

# ============================================================
#  TOOLS — These are the actions your agent can take
# ============================================================

def web_search(query: str) -> str:
    """Search the web for real-time information using DuckDuckGo."""
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found."
        output = []
        for r in results:
            output.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}\n")
        return "\n".join(output)
    except Exception as e:
        return f"Search failed: {e}"


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed_names = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation error: {e}"


def read_file(filepath: str) -> str:
    """Read the contents of a text file."""
    try:
        with open(filepath.strip(), "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 3000:
            return content[:3000] + "\n... (file truncated, showing first 3000 chars)"
        return content
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except Exception as e:
        return f"Error reading file: {e}"


def get_current_time() -> str:
    """Get the current date and time."""
    from datetime import datetime
    now = datetime.now()
    return now.strftime("Date: %Y-%m-%d, Time: %H:%M:%S, Day: %A")


# ---- Tool Registry ----
TOOLS = {
    "web_search": web_search,
    "calculate": calculate,
    "read_file": read_file,
    "get_current_time": get_current_time,
}

# ============================================================
#  SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are a helpful and intelligent AI agent that solves real-world problems step by step.

You have access to these tools:
1. web_search(query) — Search the internet for real-time information
2. calculate(expression) — Evaluate math expressions (e.g., "25 * 4 + 10")
3. read_file(filepath) — Read the contents of a file on the user's computer
4. get_current_time() — Get the current date and time

## HOW TO USE TOOLS

When you need to use a tool, respond in EXACTLY this format:

THOUGHT: [explain your reasoning — why you need this tool]
ACTION: [tool_name]
INPUT: [the argument to pass to the tool]

## HOW TO GIVE YOUR FINAL ANSWER

When you have enough information to fully answer the user's question, respond with:

THOUGHT: I now have enough information to answer.
FINAL_ANSWER: [your complete, well-formatted answer]

## RULES
- Always THINK before acting
- Use tools when you need real-time data, calculations, or file access
- You can use multiple tools in sequence (one per step)
- Don't make up information — if you need facts, search for them
- Be concise but thorough in your final answer
- Maximum 7 steps — if you can't solve it by then, give your best answer
"""

# ============================================================
#  AGENT LOOP — The ReAct (Reason + Act) Engine
# ============================================================

def run_agent(user_question: str) -> str:
    """Run the agent on a user question using the ReAct pattern."""

    print(f"\n{'='*60}")
    print(f"  USER: {user_question}")
    print(f"{'='*60}")

    # Use the Chat API for proper multi-turn conversation
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    # Send the initial user question
    try:
        response = chat.send_message(f"User question: {user_question}")
        assistant_msg = response.text
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return f"Sorry, I encountered an error: {e}"

    for step in range(1, 8):  # Max 7 reasoning steps
        print(f"\n  [Step {step}]")
        print(f"  {'-'*50}")
        for line in assistant_msg.strip().split("\n"):
            print(f"  {line}")

        # ---- Check if agent is done ----
        if "FINAL_ANSWER:" in assistant_msg:
            final = assistant_msg.split("FINAL_ANSWER:", 1)[-1].strip()
            print(f"\n{'='*60}")
            print(f"  FINAL ANSWER:")
            print(f"  {'-'*50}")
            for line in final.split("\n"):
                print(f"  {line}")
            print(f"{'='*60}")
            return final

        # ---- Check if agent wants to use a tool ----
        if "ACTION:" in assistant_msg:
            # Parse the action and input
            action_line = ""
            input_line = ""
            for line in assistant_msg.split("\n"):
                stripped = line.strip()
                if stripped.startswith("ACTION:"):
                    action_line = stripped.split("ACTION:", 1)[-1].strip()
                if stripped.startswith("INPUT:"):
                    input_line = stripped.split("INPUT:", 1)[-1].strip()

            if action_line in TOOLS:
                print(f"\n  >> Tool: {action_line}(\"{input_line}\")")

                # Execute the tool
                if action_line == "get_current_time":
                    result = TOOLS[action_line]()
                else:
                    result = TOOLS[action_line](input_line)

                # Show result (truncated for display)
                display_result = result[:300] + "..." if len(result) > 300 else result
                print(f"  >> Result: {display_result}")

                # Feed observation back via chat
                try:
                    response = chat.send_message(f"OBSERVATION: {result}")
                    assistant_msg = response.text
                except Exception as e:
                    print(f"\n  ERROR: {e}")
                    return f"Sorry, I encountered an error: {e}"
            else:
                error_msg = f"Unknown tool '{action_line}'. Available tools: {list(TOOLS.keys())}"
                print(f"  WARNING: {error_msg}")
                try:
                    response = chat.send_message(f"OBSERVATION: ERROR - {error_msg}")
                    assistant_msg = response.text
                except Exception as e:
                    return f"Sorry, I encountered an error: {e}"
        else:
            # Agent didn't use a tool or give final answer — nudge it
            try:
                response = chat.send_message(
                    "Please either use a tool (ACTION/INPUT) or provide your FINAL_ANSWER."
                )
                assistant_msg = response.text
            except Exception as e:
                return f"Sorry, I encountered an error: {e}"

    return "I reached the maximum number of steps. Please try rephrasing your question."


# ============================================================
#  MAIN — Interactive Chat Loop
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AI AGENT — Ready to help!")
    print("  Type your question and press Enter.")
    print("  Type 'quit' or 'exit' to stop.")
    print("="*60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! Good luck at the hackathon!")
                break
            run_agent(user_input)
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break

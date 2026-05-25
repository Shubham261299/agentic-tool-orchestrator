"""
The 11 tools the agent can call.

Design notes:
- Each tool is a @tool-decorated function with type hints and a clear docstring.
- Docstrings matter — Claude reads them to decide when to call each tool.
- All tools return strings (LangGraph tool messages must be string-serializable).
- Errors are caught and returned as readable strings so the agent can self-correct.
"""
import json
import random
import subprocess
from datetime import datetime
from pathlib import Path

import pyperclip
import requests
from langchain_core.tools import tool

from src.config import (
    ALLOWED_SHELL_COMMANDS,
    BLOCKED_PATTERNS,
    MEMORY_FILE,
    TEST_OUTPUTS_DIR,
)


# ============================================================
# TOOL 1 — Execute safe shell commands
# ============================================================
@tool
def execute_shell_command(command: str) -> str:
    """
    Execute a safe shell command (Windows or Linux). Use for: ls, dir, mkdir,
    echo, pwd, type, cat, whoami, date, tree, where.

    Args:
        command: The shell command to execute (e.g., 'mkdir test_folder', 'dir').

    Returns:
        Command output, or an error message if the command is blocked/fails.
    """
    cmd_lower = command.lower().strip()

    # Safety: block dangerous patterns
    for blocked in BLOCKED_PATTERNS:
        if blocked in cmd_lower:
            return f"BLOCKED: Command contains forbidden pattern '{blocked}'"

    # Safety: must start with an allowed command
    first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
    if first_word not in ALLOWED_SHELL_COMMANDS:
        return f"BLOCKED: Command '{first_word}' not in allowlist. Allowed: {sorted(ALLOWED_SHELL_COMMANDS)}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(TEST_OUTPUTS_DIR),  # Sandbox to test_outputs/
        )
        output = result.stdout or result.stderr or "(no output)"
        return output.strip()[:2000]  # Cap response length
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 10s"
    except Exception as e:
        return f"ERROR: {e}"


# ============================================================
# TOOL 2 — Open a URL in browser (Playwright)
# ============================================================
@tool
def open_browser(url: str) -> str:
    """
    Open a URL in a Chromium browser and return the page title.
    Use when the user asks to visit/open/check a website.

    Args:
        url: Full URL including https:// (e.g., 'https://www.google.com').

    Returns:
        The page title and URL, or an error message.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            title = page.title()
            current_url = page.url
            # Keep window open briefly so user can see it
            page.wait_for_timeout(2000)
            browser.close()
            return f"Opened: {current_url} | Title: '{title}'"
    except Exception as e:
        return f"ERROR opening browser: {e}"


# ============================================================
# TOOL 3 — Write/append to a text file
# ============================================================
@tool
def notepad_write(filename: str, content: str, mode: str = "write") -> str:
    """
    Create or write to a text file. Use when user wants to save text/notes.

    Args:
        filename: Name of file (e.g., 'notes.txt'). Will be created in test_outputs/.
        content: Text to write.
        mode: 'write' (overwrite) or 'append'.

    Returns:
        Success message with full file path, or error.
    """
    try:
        filepath = TEST_OUTPUTS_DIR / filename
        write_mode = "a" if mode == "append" else "w"
        with open(filepath, write_mode, encoding="utf-8") as f:
            f.write(content)
            if mode == "append":
                f.write("\n")
        return f"Successfully {'appended to' if mode == 'append' else 'wrote'} {filepath} ({len(content)} chars)"
    except Exception as e:
        return f"ERROR writing file: {e}"


# ============================================================
# TOOL 4 — Safe math evaluator
# ============================================================
@tool
def calculator(expression: str) -> str:
    """
    Evaluate a math expression safely. Supports +, -, *, /, **, %, parentheses.

    Args:
        expression: Math expression (e.g., '234 * 567', '(10 + 5) ** 2').

    Returns:
        The result, or an error message.
    """
    # Safe character allowlist
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return f"ERROR: Expression contains invalid characters. Only digits and + - * / ( ) % allowed."

    try:
        # Use eval safely with empty globals/locals (only math operators reachable)
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"ERROR evaluating: {e}"


# ============================================================
# TOOL 5 — Get current time
# ============================================================
@tool
def get_current_time() -> str:
    """
    Get the current date and time in human-readable format.
    Use when user asks 'what time is it' or needs a timestamp.

    Returns:
        Current local time as a string.
    """
    now = datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M:%S %p")


# ============================================================
# TOOL 6 — Get weather (wttr.in, no API key needed!)
# ============================================================
@tool
def get_weather(city: str) -> str:
    """
    Get current weather for a city using wttr.in (no API key needed).

    Args:
        city: City name (e.g., 'Pune', 'Mumbai', 'New York').

    Returns:
        Weather summary including temperature and conditions.
    """
    try:
        url = f"https://wttr.in/{city}?format=%l:+%C+%t+%h+%w"
        response = requests.get(url, timeout=10, headers={"User-Agent": "curl/8.0"})
        if response.status_code == 200:
            return f"Weather in {city}: {response.text.strip()}"
        return f"ERROR: wttr.in returned status {response.status_code}"
    except Exception as e:
        return f"ERROR fetching weather: {e}"


# ============================================================
# TOOL 7 — Read clipboard
# ============================================================
@tool
def clipboard_get() -> str:
    """
    Read the current contents of the system clipboard.
    Use when user asks 'what's in my clipboard' or 'show clipboard'.

    Returns:
        Clipboard contents (or empty string).
    """
    try:
        content = pyperclip.paste()
        if not content:
            return "Clipboard is empty."
        return f"Clipboard contains: {content}"
    except Exception as e:
        return f"ERROR reading clipboard: {e}"


# ============================================================
# TOOL 8 — Write clipboard
# ============================================================
@tool
def clipboard_set(text: str) -> str:
    """
    Copy text to the system clipboard. Use when user says 'copy X to clipboard'.

    Args:
        text: The text to copy.

    Returns:
        Success confirmation.
    """
    try:
        pyperclip.copy(text)
        return f"Copied to clipboard: '{text[:100]}'"
    except Exception as e:
        return f"ERROR writing clipboard: {e}"


# ============================================================
# TOOL 9 — List directory contents
# ============================================================
@tool
def list_directory(path: str = ".") -> str:
    """
    List files and folders in a directory.

    Args:
        path: Directory path. Default is current directory '.'.

    Returns:
        Formatted list of files/folders or error message.
    """
    try:
        # Resolve to test_outputs by default for safety
        if path == "." or not path:
            target = TEST_OUTPUTS_DIR
        else:
            target = Path(path)
            if not target.is_absolute():
                target = TEST_OUTPUTS_DIR / path

        if not target.exists():
            return f"ERROR: Directory '{target}' does not exist."

        items = []
        for item in sorted(target.iterdir()):
            kind = "📁" if item.is_dir() else "📄"
            size = f" ({item.stat().st_size} bytes)" if item.is_file() else ""
            items.append(f"{kind} {item.name}{size}")

        if not items:
            return f"Directory '{target}' is empty."
        return f"Contents of {target}:\n" + "\n".join(items)
    except Exception as e:
        return f"ERROR listing directory: {e}"


# ============================================================
# TOOL 10 — Memory store (key/value JSON)
# ============================================================
@tool
def write_memory(key: str, value: str) -> str:
    """
    Store a key-value pair in persistent memory. Use to remember facts
    across conversations (e.g., user preferences, names, settings).

    Args:
        key: The fact name (e.g., 'favorite_color').
        value: The fact value (e.g., 'blue').

    Returns:
        Confirmation message.
    """
    try:
        memory = {}
        if MEMORY_FILE.exists():
            memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        memory[key] = value
        MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")
        return f"Remembered: {key} = {value}"
    except Exception as e:
        return f"ERROR writing memory: {e}"


@tool
def read_memory(key: str = "") -> str:
    """
    Retrieve a value from persistent memory. Use to recall previously stored facts.

    Args:
        key: The fact name to retrieve. Pass empty string to list all stored keys.

    Returns:
        The value, all keys, or 'not found'.
    """
    try:
        if not MEMORY_FILE.exists():
            return "Memory is empty. Nothing stored yet."

        memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))

        if not key:
            if not memory:
                return "Memory is empty."
            return "All stored keys: " + ", ".join(memory.keys())

        if key in memory:
            return f"{key} = {memory[key]}"
        return f"No memory found for key '{key}'. Available keys: {list(memory.keys())}"
    except Exception as e:
        return f"ERROR reading memory: {e}"


# ============================================================
# TOOL 11 — Get a random joke
# ============================================================
@tool
def get_random_joke() -> str:
    """
    Fetch a random joke from a free API. Use when user wants to laugh or
    asks for a joke.

    Returns:
        A joke as a string, or error message.
    """
    try:
        response = requests.get(
            "https://official-joke-api.appspot.com/random_joke",
            timeout=10,
        )
        if response.status_code == 200:
            joke = response.json()
            return f"{joke.get('setup', '')} — {joke.get('punchline', '')}"
        return f"ERROR: Joke API returned {response.status_code}"
    except Exception as e:
        return f"ERROR fetching joke: {e}"


# ============================================================
# Tool Registry — exported for agent.py
# ============================================================
ALL_TOOLS = [
    execute_shell_command,
    open_browser,
    notepad_write,
    calculator,
    get_current_time,
    get_weather,
    clipboard_get,
    clipboard_set,
    list_directory,
    write_memory,
    read_memory,
    get_random_joke,
]
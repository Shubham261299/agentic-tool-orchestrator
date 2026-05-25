"""Centralized configuration loaded from environment."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TEST_OUTPUTS_DIR = ROOT / "test_outputs"
MEMORY_FILE = DATA_DIR / "memory.json"

# Auto-create dirs
DATA_DIR.mkdir(exist_ok=True)
TEST_OUTPUTS_DIR.mkdir(exist_ok=True)

# --- API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-5"  # Same model that worked in your last project

# --- Server ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# --- Safety ---
# Linux/shell commands that are allowed. Block dangerous ones.
ALLOWED_SHELL_COMMANDS = {
    "ls", "dir", "mkdir", "echo", "pwd", "cd", "type", "cat",
    "whoami", "date", "time", "tree", "where",
}
BLOCKED_PATTERNS = ["rm ", "del ", "format", "shutdown", "rmdir", "rd ", ">"]
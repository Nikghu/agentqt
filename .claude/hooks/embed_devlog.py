"""
PostToolUse hook — auto-embed new DEVLOG entries after session-finalizer writes.
Runs after every Write/Edit tool call; acts only when DEVLOG.md is the target file.
"""

import json
import subprocess
import sys
from pathlib import Path

hook_input = json.load(sys.stdin)
file_path = hook_input.get("tool_input", {}).get("file_path", "")

if "DEVLOG.md" not in file_path:
    sys.exit(0)

script = Path(__file__).parents[1] / "rag" / "embed_new.py"
result = subprocess.run(
    [sys.executable, str(script)],
    capture_output=True,
    text=True,
)

if result.stdout:
    print(result.stdout, end="")
if result.returncode != 0 and result.stderr:
    print(f"[RAG hook] embed_new error: {result.stderr[:200]}", file=sys.stderr)

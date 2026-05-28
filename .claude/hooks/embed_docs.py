"""
PostToolUse hook — auto-embed changed doc entries after any Write/Edit to
us_swing/docs/**/*.md (FO, SRD, MD, UTCD, RN-*, ISS-* files).
Calls docs_embed_new.py with the modified file path.
"""

import json
import subprocess
import sys
from pathlib import Path

hook_input = json.load(sys.stdin)
file_path = hook_input.get("tool_input", {}).get("file_path", "")

# Only act on markdown files inside us_swing/docs/
if "us_swing/docs/" not in file_path.replace("\\", "/") or not file_path.endswith(".md"):
    sys.exit(0)

# Skip TRACE.md, DD.md — not indexed
name = Path(file_path).name
if name in ("TRACE.md", "DD.md"):
    sys.exit(0)

script = Path(__file__).parents[1] / "rag" / "docs_embed_new.py"
result = subprocess.run(
    [sys.executable, str(script), file_path],
    capture_output=True,
    text=True,
)

if result.stdout:
    print(result.stdout, end="")
if result.returncode != 0 and result.stderr:
    print(f"[RAG hook] docs_embed_new error: {result.stderr[:300]}", file=sys.stderr)

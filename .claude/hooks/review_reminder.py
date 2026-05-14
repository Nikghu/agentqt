"""Reads .claude/.pending_review and emits a single consolidated review reminder."""
import json
import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))   # F:\.claude\hooks
PENDING = os.path.join(os.path.dirname(_HOOKS_DIR), ".pending_review")  # F:\.claude\.pending_review

if not os.path.exists(PENDING):
    sys.exit(0)

with open(PENDING) as fh:
    files = list(dict.fromkeys(ln.strip() for ln in fh if ln.strip()))  # dedup, preserve order

os.remove(PENDING)

if not files:
    sys.exit(0)

gui = [fp for fp in files if "gui" in fp.lower() or "widget" in fp.lower()]
non_gui = [fp for fp in files if fp not in gui]

parts: list[str] = []
if gui:
    parts.append(f"PyQt6 files modified ({', '.join(gui)}) — invoke pyqt-code-reviewer")
if non_gui:
    parts.append(f"Non-GUI Python files modified ({', '.join(non_gui)}) — invoke code-reviewer")

msg = ". ".join(parts)
print(json.dumps({"systemMessage": msg}))

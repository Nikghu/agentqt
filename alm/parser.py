"""
ALM Parser — scan a project's docs/ folder and extract ALMNode objects from Markdown files.

ID patterns supported:
  FO-INF-001
  SRD-INF-001.001
  DD-INF-001.001.D01
  MD-INF-001.001.M01
  UT-INF-001.001.M01.T01
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Markdown files that contain traceable nodes
_DOC_FILES = {"FO.md", "SRD.md", "DD.md", "MD.md", "UTCD.md"}

# Heading line with a traceable ID.
# Supports both colon separator  (## FO-INF-001: Some Title)
# and em-dash separator          (## DD-INF-001.001.D01 — Some Title)
_HEADING_RE = re.compile(
    r'^#{1,4}\s+'
    r'((?:FO|SRD|DD|MD|UT)-[A-Z]+-\d+(?:\.\d+)*(?:\.[A-Z]\d+)*)'
    r'(?:\s*:\s*|\s+\u2014\s+)'   # : or em-dash separator
    r'(.+)$',
    re.MULTILINE,
)

# Table row with a traceable ID in the first cell:
# | SRD-GUI-000.001 | FO-GUI-000 | Must | Description | In | Out | Constraints | Status |
_TABLE_ROW_RE = re.compile(
    r'^[ \t]*\|[ \t]*((?:FO|SRD|DD|MD|UT)-[A-Z]+-\d+(?:\.\d+)*(?:\.[A-Z]\d+)*)[ \t]*\|(.+)$',
    re.MULTILINE,
)
_STATUS_RE = re.compile(r'\*\*Status:\*\*\s*([^\n*]+)', re.IGNORECASE)
_PARENT_RE = re.compile(
    r'\*\*Parent\s+(?:FO|SRD|DD|MD|Module):\*\*\s*([\w.-]+)', re.IGNORECASE
)

# File name → primary artifact doc type.
# Headings in a file whose ID type differs are section organizers, not definitions.
_FILE_DOC_TYPE: dict[str, str] = {
    "FO.md":   "FO",
    "SRD.md":  "SRD",
    "DD.md":   "DD",
    "MD.md":   "MD",
    "UTCD.md": "UT",
}

# Folder name → canonical 3-letter tool code.
# Used to skip cross-tool reference rows (e.g. MD-INF-* inside execution/MD.md).
_FOLDER_CODE: dict[str, str] = {
    "infrastructure": "INF",
    "screener":       "SCR",
    "analysis":       "ANA",
    "execution":      "EXE",
    "gui":            "GUI",
    "mcp":            "MCP",
}

# Status → colour used by the tree widget
STATUS_COLOUR: dict[str, str] = {
    "approved":    "#4caf50",
    "implemented": "#2196f3",
    "verified":    "#00bcd4",
    "draft":       "#ff9800",
    "unknown":     "#9e9e9e",
}

# Valid statuses for the combobox
ALL_STATUSES = ["Draft", "Approved", "Implemented", "Verified"]


@dataclass
class ALMNode:
    id: str
    title: str
    doc_type: str   # FO | SRD | DD | MD | UT
    tool: str       # folder name, e.g. "infrastructure"
    status: str
    parent_id: str  # empty string for FO (root nodes)
    body: str
    source_file: Path

    @property
    def status_key(self) -> str:
        return self.status.lower().split()[0]

    @property
    def colour(self) -> str:
        return STATUS_COLOUR.get(self.status_key, STATUS_COLOUR["unknown"])

    @property
    def label(self) -> str:
        return f"{self.id}: {self.title}  [{self.status}]"


def _parse_file(path: Path, tool: str) -> list[ALMNode]:
    """Extract ALMNode objects from a single Markdown doc file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    matches = list(_HEADING_RE.finditer(text))
    nodes: list[ALMNode] = []
    seen_ids: set[str] = set()
    expected_type = _FILE_DOC_TYPE.get(path.name, "")

    for i, m in enumerate(matches):
        node_id = m.group(1)
        title = m.group(2).strip()

        # Skip headings that use a different artifact type — they are section
        # organizers (e.g. "# FO-EXE-001 — Title" inside DD.md), not definitions.
        if expected_type and node_id.split("-")[0] != expected_type:
            continue

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        sm = _STATUS_RE.search(body)
        status = sm.group(1).strip() if sm else "Unknown"

        pm = _PARENT_RE.search(body)
        parent_id = pm.group(1).strip() if pm else ""

        doc_type = node_id.split("-")[0]  # FO, SRD, DD, MD, UT

        nodes.append(ALMNode(
            id=node_id,
            title=title,
            doc_type=doc_type,
            tool=tool,
            status=status,
            parent_id=parent_id,
            body=body,
            source_file=path,
        ))
        seen_ids.add(node_id)

    # Parse table-row-format nodes (SRD.md / MD.md style).
    # Columns: | ID | Parent | col2 | Description/Responsibility | ... | Status |
    folder_code = _FOLDER_CODE.get(tool, "")
    for m in _TABLE_ROW_RE.finditer(text):
        node_id = m.group(1)
        if node_id in seen_ids:
            continue  # already captured as a heading node

        # Skip cross-tool reference rows: an ID whose embedded tool code
        # (e.g. "INF" in MD-INF-004.001.M02) differs from this folder is a
        # reference, not a definition — it is already defined in its home tool.
        parts = node_id.split("-")
        if folder_code and len(parts) >= 2 and parts[1] != folder_code:
            continue

        rest = m.group(2)
        cells = [c.strip() for c in rest.split("|")]
        # Drop trailing empty cell produced by a closing |
        while cells and not cells[-1]:
            cells.pop()

        if not cells:
            continue

        # Column 0 (after ID) = parent.  May be a range like 'SRD-GUI-001.001–004';
        # take the first token up to whitespace or dash-family characters.
        parent_raw = cells[0]
        parent_token = re.split(r'[\s\u2013\u2014]', parent_raw)[0].rstrip(',.;:')
        # Only use it if it actually looks like a traceable ID
        parent_id = parent_token if re.match(r'^(?:FO|SRD|DD|MD|UT)-', parent_token) else ""

        # Status = last non-empty cell
        status = cells[-1] if cells else "Unknown"

        # Title = column 2 (index 2): 'Description' for SRD, 'Responsibility' for MD.
        # Falls back to column 1 or the ID itself if the row is shorter than expected.
        if len(cells) >= 3:
            title = cells[2][:120]
        elif len(cells) >= 2:
            title = cells[1][:120]
        else:
            title = node_id

        doc_type = node_id.split("-")[0]

        nodes.append(ALMNode(
            id=node_id,
            title=title,
            doc_type=doc_type,
            tool=tool,
            status=status or "Unknown",
            parent_id=parent_id,
            body="",          # table rows have no free-text body
            source_file=path,
        ))
        seen_ids.add(node_id)

    return nodes


def update_node_status(node: ALMNode, new_status: str) -> None:
    """Rewrite (or insert) the **Status:** field of *node* in its source Markdown file.

    Handles two formats:
    - Heading format: ``## SRD-...: Title`` with ``**Status:** <value>`` in the body.
    - Table-row format: ``| SRD-... | Parent | ... | Status |`` last-column cell.
    """
    text = node.source_file.read_text(encoding="utf-8", errors="replace")

    # ── Heading format ───────────────────────────────────────────────────────
    for m in _HEADING_RE.finditer(text):
        if m.group(1) != node.id:
            continue

        body_start = m.end()

        # Determine end of this node's body (start of next heading or EOF)
        remaining = list(_HEADING_RE.finditer(text, body_start))
        body_end = remaining[0].start() if remaining else len(text)
        body_text = text[body_start:body_end]

        status_match = _STATUS_RE.search(body_text)

        if status_match:
            # Replace existing status value in-place
            abs_start = body_start + status_match.start()
            abs_end   = body_start + status_match.end()
            updated = text[:abs_start] + f"**Status:** {new_status}" + text[abs_end:]
        else:
            # Insert after the **Parent ...:** line if present, else after first bullet
            parent_match = _PARENT_RE.search(body_text)
            if parent_match:
                line_end = body_text.find("\n", parent_match.end())
                insert_at = body_start + (line_end + 1 if line_end != -1 else len(body_text))
            else:
                first_line_end = body_text.find("\n")
                insert_at = body_start + (first_line_end + 1 if first_line_end != -1 else 0)
            updated = text[:insert_at] + f"- **Status:** {new_status}\n" + text[insert_at:]

        node.source_file.write_text(updated, encoding="utf-8")
        node.status = new_status
        return

    # ── Table-row format ─────────────────────────────────────────────────────
    # Match the entire row for this node and replace the last cell (status).
    # Pattern: | ID | col | col | ... | <status cell> |?
    # The (?:.*\|) is greedy and will consume all cells up to (and including)
    # the last | before the status cell, leaving ([^|\n]+) to capture status.
    row_re = re.compile(
        r'^([ \t]*\|[ \t]*' + re.escape(node.id) + r'[ \t]*\|(?:.*\|))([^|\n]+)(\|?[ \t]*)$',
        re.MULTILINE,
    )
    rm = row_re.search(text)
    if rm:
        # Preserve surrounding single-space padding used by the existing cell.
        replacement = f' {new_status} '
        updated = text[:rm.start(2)] + replacement + text[rm.end(2):]
        node.source_file.write_text(updated, encoding="utf-8")
        node.status = new_status
        return


def load_all_nodes(docs_root: Path) -> list[ALMNode]:
    """Recursively scan docs_root and return all parseable ALMNodes."""
    nodes: list[ALMNode] = []
    for tool_dir in sorted(docs_root.iterdir()):
        if not tool_dir.is_dir():
            continue
        tool = tool_dir.name
        for doc_file in sorted(tool_dir.iterdir()):
            if doc_file.name in _DOC_FILES:
                nodes.extend(_parse_file(doc_file, tool))
    return nodes


# ---------------------------------------------------------------------------
# Format-agnostic ID definition detector — used by the audit guard.
#
# This regex finds traceable IDs that *appear to be definitions*, i.e. they
# sit at the start of a Markdown heading line OR in the first cell of a table
# row.  It deliberately does NOT care about the exact surrounding format so
# that it catches IDs written in any format — existing or future.
#
# Pattern breakdown:
#   (?:^#{1,4}\s+  |  ^\s*\|\s*)   ← heading prefix  OR  table-row first cell
#   ( ID )                          ← captured ID
#   (?=\s*[|:—\s])                  ← must be followed by cell boundary or separator
# ---------------------------------------------------------------------------
_RAW_DEF_RE = re.compile(
    r'(?:^#{1,4}\s+|^\s*\|\s*)'
    r'((?:FO|SRD|DD|MD|UT)-[A-Z]+-\d+(?:\.\d+)*(?:\.[A-Z]\d+)*)'
    r'(?=[\s|:—\u2014])',
    re.MULTILINE,
)


@dataclass
class AuditResult:
    """Result of a traceability audit pass."""
    total_defined: int          # raw definition IDs found in docs
    total_parsed:  int          # nodes the parser successfully captured
    missing: list[tuple[str, Path]]   # (id, source_file) parser missed


def audit_docs(docs_root: Path) -> AuditResult:
    """Scan docs_root with a format-agnostic detector and compare against the
    parser's output.  Returns an AuditResult listing any IDs that appear to be
    definitions but were NOT captured by the parser.

    This is the traceability guard — if the document format changes without a
    corresponding parser update, the missed IDs show up here.
    """
    raw_defs: list[tuple[str, Path]] = []
    for tool_dir in sorted(docs_root.iterdir()):
        if not tool_dir.is_dir():
            continue
        for doc_file in sorted(tool_dir.iterdir()):
            if doc_file.name not in _DOC_FILES:
                continue
            try:
                text = doc_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in _RAW_DEF_RE.finditer(text):
                raw_defs.append((m.group(1), doc_file))

    # Remove duplicates while preserving first-seen file for reporting
    seen: set[str] = set()
    unique_defs: list[tuple[str, Path]] = []
    for node_id, path in raw_defs:
        if node_id not in seen:
            seen.add(node_id)
            unique_defs.append((node_id, path))

    # Compare against what the parser actually captured
    parsed_nodes = load_all_nodes(docs_root)
    parsed_ids = {n.id for n in parsed_nodes}

    missing = [(nid, p) for nid, p in unique_defs if nid not in parsed_ids]

    return AuditResult(
        total_defined=len(unique_defs),
        total_parsed=len(parsed_nodes),
        missing=missing,
    )

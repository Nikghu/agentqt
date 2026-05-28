"""
RAG Docs Ingest — Phase 4
Parses us_swing/docs/**/(FO|SRD|MD|UTCD).md plus all revisions/RN-*.md and
issues/ISS-*.md files. Chunks into per-artifact-row / per-section entries,
embeds via Voyage AI, stores in Qdrant "docs" collection.

Run  : python .claude/rag/docs_ingest.py
Safe : uses stable UUIDs per artifact ID — idempotent upsert on re-run.
"""

import hashlib
import os
import re
import uuid
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

DOCS_ROOT = Path(__file__).parents[2] / "us_swing" / "docs"
DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "docs"
MODEL = "voyage-4-lite"
BATCH_SIZE = 32         # larger batches are fine on paid tier
RATE_LIMIT_SLEEP = 0   # paid Voyage tier — no meaningful rate limit

TOOL_MAP: dict[str, str] = {
    "execution": "EXE",
    "screener": "SCR",
    "gui": "GUI",
    "analysis": "ANA",
    "infrastructure": "INF",
    "mcp": "MCP",
    "agt": "AGT",
}

# Primary artifact files in the tool root
ARTIFACT_FILES = {"FO.md", "SRD.md", "MD.md", "UTCD.md"}


# ── Stable ID ─────────────────────────────────────────────────────────────────
def entry_id(artifact_id: str) -> str:
    """Deterministic UUID from artifact ID — same entry always gets same UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"docs-{artifact_id}"))


# ── Primary artifact parsers ──────────────────────────────────────────────────
def parse_fo(text: str, tool: str, source: str) -> list[dict]:
    """One chunk per ## FO-TOOL-NNN block."""
    chunks: list[dict] = []
    blocks = re.split(r"(?=^## FO-)", text, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        m = re.match(r"^## (FO-[A-Z]+-\d+): (.+)", block)
        if not m:
            continue
        fo_id, title = m.group(1), m.group(2).strip()
        bullets = re.findall(r"^- (.+)$", block, re.MULTILINE)
        description = " | ".join(b[:120] for b in bullets[:4])
        chunks.append({
            "artifact_id": fo_id,
            "artifact_type": "FO",
            "tool": tool,
            "title": f"{fo_id}: {title}",
            "text": f"{fo_id}: {title} | {description}",
            "source": source,
        })
    return chunks


def parse_table(text: str, artifact_type: str, tool: str, source: str) -> list[dict]:
    """One chunk per artifact-ID table row (SRD, MD, UTCD)."""
    patterns = {
        "SRD":  r"SRD-[A-Z]+-\d+\.\d+",
        "MD":   r"MD-[A-Z]+-\d+\.\d+\.M\d+",
        "UTCD": r"UT-[A-Z]+-\d+\.\d+\.M\d+\.T\d+",
    }
    id_re = re.compile(patterns.get(artifact_type, r"(?!x)x"))

    chunks: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.search(r"\|[-\s:]+\|", stripped):  # separator row
            continue
        m = id_re.search(stripped)
        if not m:
            continue
        artifact_id = m.group(0)
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        text_chunk = f"{artifact_id} | " + " | ".join(
            c for c in cells if c and c != artifact_id and len(c) > 1
        )
        chunks.append({
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "tool": tool,
            "title": artifact_id,
            "text": text_chunk[:1500],
            "source": source,
        })

    # Fallback for UTCD files that use short T01-style IDs instead of fully-qualified UT-* IDs.
    # Tracks ### `test_module.py` section headers to synthesise stable artifact IDs.
    if artifact_type == "UTCD" and not chunks:
        chunks = _parse_utcd_short_ids(text, tool, source)

    return chunks


def _parse_utcd_short_ids(text: str, tool: str, source: str) -> list[dict]:
    """Parse UTCD tables that use bare T01 IDs (no full UT-TOOL-NNN.NNN prefix)."""
    short_id_re = re.compile(r"^\|\s*(T\d+)\s*\|")
    section_re = re.compile(r"^###\s+`([^`]+)`")
    current_section = "unknown"
    chunks: list[dict] = []

    for line in text.splitlines():
        stripped = line.strip()

        m_sec = section_re.match(stripped)
        if m_sec:
            # e.g. `tests/screener/test_preset.py` → "test_preset"
            current_section = Path(m_sec.group(1)).stem
            continue

        if not stripped.startswith("|"):
            continue
        if re.search(r"\|[-\s:]+\|", stripped):
            continue

        m = short_id_re.match(stripped)
        if not m:
            continue

        t_num = m.group(1)  # e.g. "T01"
        artifact_id = f"UT-{tool}-{current_section}-{t_num}"
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        text_chunk = f"{artifact_id} | " + " | ".join(
            c for c in cells if c and len(c) > 1
        )
        chunks.append({
            "artifact_id": artifact_id,
            "artifact_type": "UTCD",
            "tool": tool,
            "title": artifact_id,
            "text": text_chunk[:1500],
            "source": source,
        })
    return chunks


# ── Revision Note parser ──────────────────────────────────────────────────────
def parse_rn(text: str, tool: str, source: str, filename: str) -> list[dict]:
    """
    One chunk per ## section in a Revision Note.
    Design Decisions and Summary sections are the most semantically valuable.
    """
    rn_id = filename.replace(".md", "")
    chunks: list[dict] = []

    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        m = re.match(r"^## (.+)", section)
        section_title = m.group(1).strip() if m else "Content"
        # Remove the heading line itself, keep the body
        body = re.sub(r"^## [^\n]+\n", "", section, count=1).strip()
        if not body or len(body) < 20:
            continue
        # Stable ID: rn_id + slug of section title
        slug = re.sub(r"\W+", "_", section_title)[:24].strip("_")
        artifact_id = f"{rn_id}-{slug}"
        chunks.append({
            "artifact_id": artifact_id,
            "artifact_type": "RN",
            "tool": tool,
            "title": f"{rn_id} — {section_title}",
            "text": f"{rn_id} {section_title}: {body[:1200]}",
            "source": source,
        })

    # Fallback: whole file as one chunk if no ## sections found
    if not chunks:
        chunks.append({
            "artifact_id": rn_id,
            "artifact_type": "RN",
            "tool": tool,
            "title": rn_id,
            "text": text[:1500],
            "source": source,
        })
    return chunks


# ── Issue parser ──────────────────────────────────────────────────────────────
def parse_iss(text: str, tool: str, source: str, filename: str) -> list[dict]:
    """
    One chunk per ## section in an issue file.
    Root Cause and Fix sections carry the most diagnostic value.
    """
    iss_id = filename.replace(".md", "")
    # Extract overall title from first heading
    title_match = re.match(r"^#+\s+(.+)", text, re.MULTILINE)
    iss_title = title_match.group(1).strip() if title_match else iss_id
    chunks: list[dict] = []

    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Skip the document-level heading block (contains metadata, not ## sections)
        if section.startswith("# "):
            # Treat the preamble (metadata + intro text before first ##) as one chunk
            preamble = re.sub(r"^## .+", "", section, flags=re.MULTILINE).strip()
            if preamble and len(preamble) > 30:
                chunks.append({
                    "artifact_id": f"{iss_id}-Overview",
                    "artifact_type": "ISS",
                    "tool": tool,
                    "title": iss_title,
                    "text": f"{iss_id}: {iss_title} | {preamble[:800]}",
                    "source": source,
                })
            continue
        m = re.match(r"^## (.+)", section)
        section_title = m.group(1).strip() if m else "Content"
        body = re.sub(r"^## [^\n]+\n", "", section, count=1).strip()
        if not body or len(body) < 20:
            continue
        slug = re.sub(r"\W+", "_", section_title)[:24].strip("_")
        artifact_id = f"{iss_id}-{slug}"
        chunks.append({
            "artifact_id": artifact_id,
            "artifact_type": "ISS",
            "tool": tool,
            "title": f"{iss_id} — {section_title}",
            "text": f"{iss_id} {section_title}: {body[:1200]}",
            "source": source,
        })

    if not chunks:
        chunks.append({
            "artifact_id": iss_id,
            "artifact_type": "ISS",
            "tool": tool,
            "title": iss_title,
            "text": text[:1500],
            "source": source,
        })
    return chunks


# ── Dispatch ──────────────────────────────────────────────────────────────────
def parse_doc_file(path: Path, tool: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(Path(__file__).parents[2]))
    name = path.name

    if name == "FO.md":
        return parse_fo(text, tool, rel)
    if name == "SRD.md":
        return parse_table(text, "SRD", tool, rel)
    if name == "MD.md":
        return parse_table(text, "MD", tool, rel)
    if name == "UTCD.md":
        return parse_table(text, "UTCD", tool, rel)
    if re.match(r"RN-[A-Z]+-[\d.]+-.+\.md", name):
        return parse_rn(text, tool, rel, name)
    if re.match(r"ISS-[A-Z]+-\d+\.md", name):
        return parse_iss(text, tool, rel, name)
    return []


# ── Embed ─────────────────────────────────────────────────────────────────────
def embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    vc = voyageai.Client(api_key=api_key)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total} ({len(batch)} entries) ...", end=" ", flush=True)
        result = vc.embed(batch, model=MODEL, input_type="document")
        all_embeddings.extend(result.embeddings)
        print("done")
    return all_embeddings


# ── Store ─────────────────────────────────────────────────────────────────────
def store(entries: list[dict], embeddings: list[list[float]], qclient: QdrantClient) -> None:
    dim = len(embeddings[0])
    existing = [c.name for c in qclient.get_collections().collections]
    if COLLECTION not in existing:
        qclient.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"  Created collection '{COLLECTION}' (dim={dim})")
    else:
        print(f"  Collection '{COLLECTION}' already exists — upserting")

    points = [
        PointStruct(
            id=entry_id(entries[i]["artifact_id"]),
            vector=embeddings[i],
            payload={
                **entries[i],
                "content_hash": hashlib.md5(entries[i]["text"].encode()).hexdigest(),
            },
        )
        for i in range(len(entries))
    ]
    qclient.upsert(collection_name=COLLECTION, points=points)
    print(f"  Stored {len(points)} entries in Qdrant at: {DB_PATH}")


# ── API key ───────────────────────────────────────────────────────────────────
def _api_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY") or __import__("subprocess").check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
        text=True,
    ).strip()
    if not key:
        raise RuntimeError("VOYAGE_API_KEY not set")
    return key


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=== RAG Docs Ingest — Phase 4 ===\n")

    all_entries: list[dict] = []

    for tool_dir, tool_code in TOOL_MAP.items():
        folder = DOCS_ROOT / tool_dir
        if not folder.exists():
            continue

        # Primary artifact files (FO, SRD, MD, UTCD)
        for fname in ARTIFACT_FILES:
            fpath = folder / fname
            if not fpath.exists():
                continue
            entries = parse_doc_file(fpath, tool_code)
            print(f"  {tool_code}/{fname}: {len(entries)} chunks")
            all_entries.extend(entries)

        # Revision Notes
        revisions_dir = folder / "revisions"
        if revisions_dir.exists():
            for fpath in sorted(revisions_dir.glob("RN-*.md")):
                entries = parse_doc_file(fpath, tool_code)
                print(f"  {tool_code}/revisions/{fpath.name}: {len(entries)} chunks")
                all_entries.extend(entries)

        # Issues
        issues_dir = folder / "issues"
        if issues_dir.exists():
            for fpath in sorted(issues_dir.glob("ISS-*.md")):
                entries = parse_doc_file(fpath, tool_code)
                print(f"  {tool_code}/issues/{fpath.name}: {len(entries)} chunks")
                all_entries.extend(entries)

    print(f"\n[1/3] Parsed {len(all_entries)} total chunks\n")
    if not all_entries:
        print("Nothing to ingest — check that docs folder exists.")
        return

    # Embed
    print(f"[2/3] Embedding via Voyage ({MODEL}) ...")
    api_key = _api_key()
    embeddings = embed_texts([e["text"] for e in all_entries], api_key)
    print(f"  {len(embeddings)} vectors (dim={len(embeddings[0])})\n")

    # Store
    print("[3/3] Storing in Qdrant ...")
    qclient = QdrantClient(path=str(DB_PATH))
    store(all_entries, embeddings, qclient)

    print("\nDone. Run docs_query.py to test retrieval.")


if __name__ == "__main__":
    main()

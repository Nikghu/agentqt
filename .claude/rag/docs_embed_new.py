"""
RAG Docs Delta Ingest — Phase 4
Re-indexes a single doc file — only embeds chunks that are new or whose text
has changed (detected via content_hash in the Qdrant payload).

Safe to call frequently — a typical doc edit produces 1-2 API calls.

Usage:
    python .claude/rag/docs_embed_new.py us_swing/docs/execution/SRD.md
    python .claude/rag/docs_embed_new.py us_swing/docs/screener/revisions/RN-SCR-2.1.1-20260527.md
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

# Shared config
sys.path.insert(0, str(Path(__file__).parent))
from docs_ingest import COLLECTION, DB_PATH, MODEL, TOOL_MAP, entry_id, parse_doc_file

REPO_ROOT = Path(__file__).parents[2]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _api_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY") or subprocess.check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
        text=True,
    ).strip()
    if not key:
        print("[RAG] VOYAGE_API_KEY not set — skipping", file=sys.stderr)
        sys.exit(0)
    return key


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _tool_from_path(file_path: Path) -> str | None:
    """Derive tool code from file path (e.g. …/docs/execution/SRD.md → EXE)."""
    try:
        parts = file_path.relative_to(REPO_ROOT / "us_swing" / "docs").parts
        return TOOL_MAP.get(parts[0])
    except ValueError:
        return None


# ── Fetch existing entries for this source file ───────────────────────────────
def _fetch_existing(qclient: QdrantClient, source: str) -> dict[str, str]:
    """Return {uuid_str: content_hash} for all Qdrant entries from this source."""
    existing: dict[str, str] = {}
    offset = None
    source_filter = Filter(
        must=[FieldCondition(key="source", match=MatchValue(value=source))]
    )
    while True:
        result, offset = qclient.scroll(
            collection_name=COLLECTION,
            scroll_filter=source_filter,
            limit=200,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in result:
            existing[str(point.id)] = point.payload.get("content_hash", "")
        if offset is None:
            break
    return existing


# ── Main ──────────────────────────────────────────────────────────────────────
def run(file_path: Path) -> None:
    if not DB_PATH.exists():
        print("[RAG] Qdrant DB not found — run docs_ingest.py first", file=sys.stderr)
        sys.exit(0)

    qclient = QdrantClient(path=str(DB_PATH))
    existing_collections = [c.name for c in qclient.get_collections().collections]
    if COLLECTION not in existing_collections:
        print(f"[RAG] Collection '{COLLECTION}' not found — run docs_ingest.py first",
              file=sys.stderr)
        sys.exit(0)

    tool = _tool_from_path(file_path)
    if tool is None:
        print(f"[RAG] {file_path.name}: not a tracked docs file — skipping")
        sys.exit(0)

    # Parse the file into chunks
    entries = parse_doc_file(file_path, tool)
    if not entries:
        print(f"[RAG] {file_path.name}: 0 chunks parsed — skipping")
        sys.exit(0)

    # Compute relative source path (same format as stored in Qdrant)
    source = str(file_path.relative_to(REPO_ROOT))

    # Compare against existing Qdrant entries
    existing = _fetch_existing(qclient, source)

    to_embed: list[dict] = []
    for entry in entries:
        uid = entry_id(entry["artifact_id"])
        h = content_hash(entry["text"])
        if existing.get(uid) != h:  # new entry or changed text
            entry["content_hash"] = h
            to_embed.append(entry)

    skipped = len(entries) - len(to_embed)
    if not to_embed:
        print(f"[RAG] {file_path.name}: all {len(entries)} chunks up-to-date — nothing to embed")
        return

    print(f"[RAG] {file_path.name}: {len(to_embed)} new/changed, {skipped} unchanged")

    # Embed — no sleep needed (paid tier; single-file ops are tiny)
    vc = voyageai.Client(api_key=_api_key())
    texts = [e["text"] for e in to_embed]
    result = vc.embed(texts, model=MODEL, input_type="document")
    embeddings = result.embeddings

    # Upsert into Qdrant
    points = [
        PointStruct(
            id=entry_id(to_embed[i]["artifact_id"]),
            vector=embeddings[i],
            payload=to_embed[i],
        )
        for i in range(len(to_embed))
    ]
    qclient.upsert(collection_name=COLLECTION, points=points)
    print(f"[RAG] Upserted {len(points)} chunk(s) from {file_path.name}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python docs_embed_new.py <path/to/doc_file.md>", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.is_absolute():
        file_path = REPO_ROOT / file_path
    if not file_path.exists():
        print(f"[RAG] File not found: {file_path}", file=sys.stderr)
        sys.exit(0)

    run(file_path)


if __name__ == "__main__":
    main()

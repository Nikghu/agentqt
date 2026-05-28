"""
RAG Delta Ingest — Phase 2
Embeds only DEVLOG entries not yet in Qdrant. Safe to call frequently —
skips entries whose stable UUID already exists in the collection.

Called automatically by the PostToolUse hook when DEVLOG.md is written.
Can also be run manually: python .claude/rag/embed_new.py
"""

import os
import re
import uuid
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# ── Config ─────────────────────────────────────────────────────────────────────
DEVLOG_PATH = Path(__file__).parents[2] / "us_swing" / "DEVLOG.md"
DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "devlog"
MODEL = "voyage-4-lite"


# ── Helpers (same as ingest.py) ────────────────────────────────────────────────
def entry_id(entry: dict) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry['date']}-{entry['title']}"))


def parse_devlog(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    raw_blocks = re.split(r"\n---\n", text)
    entries = []
    for block in raw_blocks:
        block = block.strip()
        if not block.startswith("##"):
            continue
        m1 = re.match(r"^## \[(\d{8})\] ([A-Z]+) — (.+)", block)
        m2 = re.match(r"^## Session (\d{4}-\d{2}-\d{2}) \(\d+\) — (.+)", block)
        if m1:
            date, tool, title = m1.group(1), m1.group(2), m1.group(3)
        elif m2:
            date = m2.group(1).replace("-", "")
            tool = "GEN"
            title = m2.group(2)
        else:
            continue
        type_match = re.search(r"- Type:\s*(\w+)", block)
        fo_ids = re.findall(r"FO-[A-Z]+-\d+", block)
        entries.append({
            "date": date,
            "tool": tool,
            "title": title,
            "type": type_match.group(1) if type_match else "Unknown",
            "fo_ids": fo_ids,
            "text": block,
        })
    return entries


def get_existing_ids(client: QdrantClient) -> set[str]:
    """Scroll through Qdrant and collect all existing point IDs."""
    existing: set[str] = set()
    offset = None
    while True:
        result, offset = client.scroll(
            collection_name=COLLECTION,
            limit=100,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in result:
            existing.add(str(point.id))
        if offset is None:
            break
    return existing


def ensure_collection(client: QdrantClient, dim: int) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    if not DEVLOG_PATH.exists():
        print("[RAG] DEVLOG.md not found — skipping")
        return

    if not DB_PATH.exists():
        print("[RAG] Qdrant DB not found — run ingest.py first")
        return

    api_key = os.environ.get("VOYAGE_API_KEY") or \
              __import__("subprocess").check_output(
                  ["powershell", "-Command",
                   "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
                  text=True
              ).strip()

    if not api_key:
        print("[RAG] VOYAGE_API_KEY not set — skipping embed")
        return

    entries = parse_devlog(DEVLOG_PATH)
    qclient = QdrantClient(path=str(DB_PATH))
    existing_ids = get_existing_ids(qclient)

    new_entries = [e for e in entries if entry_id(e) not in existing_ids]

    if not new_entries:
        print(f"[RAG] No new entries to embed ({len(entries)} already indexed)")
        return

    print(f"[RAG] Embedding {len(new_entries)} new DEVLOG entry(s) ...")

    vc = voyageai.Client(api_key=api_key)
    batch_size = 32  # paid tier — no meaningful rate limit

    all_embeddings: list[list[float]] = []
    for i in range(0, len(new_entries), batch_size):
        batch = new_entries[i : i + batch_size]
        result = vc.embed([e["text"] for e in batch], model=MODEL, input_type="document")
        all_embeddings.extend(result.embeddings)

    dim = len(all_embeddings[0])
    ensure_collection(qclient, dim)

    points = [
        PointStruct(
            id=entry_id(new_entries[i]),
            vector=all_embeddings[i],
            payload={
                "date": new_entries[i]["date"],
                "tool": new_entries[i]["tool"],
                "title": new_entries[i]["title"],
                "type": new_entries[i]["type"],
                "fo_ids": new_entries[i]["fo_ids"],
                "text": new_entries[i]["text"],
            },
        )
        for i in range(len(new_entries))
    ]

    qclient.upsert(collection_name=COLLECTION, points=points)
    print(f"[RAG] Indexed {len(points)} new entry(s) into Qdrant")


if __name__ == "__main__":
    main()

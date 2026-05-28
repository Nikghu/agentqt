"""
RAG Ingest — Phase 1
Parses DEVLOG.md, embeds each entry via Voyage AI, stores in Qdrant (local file mode).

Run: python .claude/rag/ingest.py
"""

import os
import re
import uuid
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# ── Config ────────────────────────────────────────────────────────────────────
DEVLOG_PATH = Path(__file__).parents[2] / "us_swing" / "DEVLOG.md"
DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "devlog"
MODEL = "voyage-4-lite"
INPUT_TYPE = "document"  # Voyage uses "document" for stored text, "query" for search


# ── Step 1: Parse DEVLOG.md ────────────────────────────────────────────────────
def parse_devlog(path: Path) -> list[dict]:
    """
    Split DEVLOG.md into individual entries.

    Two formats in the file:
      - ## [20260513] GUI — Description
      - ## Session 2026-04-25 (38) — Description
    """
    text = path.read_text(encoding="utf-8")
    raw_blocks = re.split(r"\n---\n", text)

    entries = []
    for block in raw_blocks:
        block = block.strip()
        if not block.startswith("##"):
            continue

        # Format 1: ## [YYYYMMDD] TOOL — Title
        m1 = re.match(r"^## \[(\d{8})\] ([A-Z]+) — (.+)", block)
        # Format 2: ## Session YYYY-MM-DD (N) — Title
        m2 = re.match(r"^## Session (\d{4}-\d{2}-\d{2}) \(\d+\) — (.+)", block)

        if m1:
            date, tool, title = m1.group(1), m1.group(2), m1.group(3)
        elif m2:
            date = m2.group(1).replace("-", "")
            tool = "GEN"
            title = m2.group(2)
        else:
            continue  # unrecognised header — skip

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


# ── Stable ID ─────────────────────────────────────────────────────────────────
def entry_id(entry: dict) -> str:
    """Deterministic UUID from date + title — same entry always gets same ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry['date']}-{entry['title']}"))


# ── Step 2: Embed via Voyage AI ────────────────────────────────────────────────
def embed_texts(texts: list[str], batch_size: int = 5) -> list[list[float]]:
    """
    Send texts to Voyage API in small batches to respect rate limits.

    Paid tier — no meaningful rate limit; batch size 32 for efficiency.
    """
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    all_embeddings: list[list[float]] = []

    batch_size = 32  # paid tier
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(texts) + batch_size - 1) // batch_size
        print(f"    Batch {batch_num}/{total_batches} ({len(batch)} entries) ...", end=" ")
        result = vc.embed(batch, model=MODEL, input_type=INPUT_TYPE)
        all_embeddings.extend(result.embeddings)
        print("done")

    return all_embeddings


# ── Step 3: Store in Qdrant ────────────────────────────────────────────────────
def store_in_qdrant(entries: list[dict], embeddings: list[list[float]]) -> None:
    """Create local Qdrant collection and upsert all points."""
    dim = len(embeddings[0])

    # QdrantClient(path=...) = local file mode — no Docker, no server needed
    qclient = QdrantClient(path=str(DB_PATH))

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
            id=entry_id(entries[i]),   # stable UUID — safe to re-run (upsert is idempotent)
            vector=embeddings[i],
            payload={
                "date": entries[i]["date"],
                "tool": entries[i]["tool"],
                "title": entries[i]["title"],
                "type": entries[i]["type"],
                "fo_ids": entries[i]["fo_ids"],
                "text": entries[i]["text"],
            },
        )
        for i in range(len(entries))
    ]

    qclient.upsert(collection_name=COLLECTION, points=points)
    print(f"  Stored {len(points)} entries in Qdrant at: {DB_PATH}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=== RAG Ingest — Phase 1 ===\n")

    # 1. Parse
    print(f"[1/3] Parsing {DEVLOG_PATH.name} ...")
    entries = parse_devlog(DEVLOG_PATH)
    print(f"  Found {len(entries)} entries\n")

    # 2. Embed
    print(f"[2/3] Embedding via Voyage ({MODEL}) ...")
    texts = [e["text"] for e in entries]
    embeddings = embed_texts(texts)
    print(f"  Generated {len(embeddings)} vectors (dim={len(embeddings[0])})\n")

    # 3. Store
    print("[3/3] Storing in Qdrant (local file mode) ...")
    store_in_qdrant(entries, embeddings)

    print("\nDone. Run query.py to test retrieval.")


if __name__ == "__main__":
    main()

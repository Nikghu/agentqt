"""
RAG Query -- Phase 3
Two-stage retrieval with before/after comparison so you can see
exactly what reranking changes.

Stage 1 -- Recall:    cosine similarity -> top 20 candidates
Stage 2 -- Precision: rerank-2.5 re-scores all 20, returns top 5

Run: python .claude/rag/query.py "GUI chart work"
     python .claude/rag/query.py "execution layer bugs"
     python .claude/rag/query.py "what did I work on last?"
"""

import os
import sys
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient

DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "devlog"
EMBED_MODEL = "voyage-4-lite"
RERANK_MODEL = "rerank-2.5"
RECALL_K = 20   # Stage 1: wide net
FINAL_K = 5     # Stage 2: reranker output


def _api_key() -> str:
    return os.environ.get("VOYAGE_API_KEY") or __import__("subprocess").check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
        text=True,
    ).strip()


def run(question: str) -> None:
    vc = voyageai.Client(api_key=_api_key())
    qclient = QdrantClient(path=str(DB_PATH))

    # Stage 1: Vector recall
    result = vc.embed([question], model=EMBED_MODEL, input_type="query")
    hits = qclient.query_points(
        collection_name=COLLECTION,
        query=result.embeddings[0],
        limit=RECALL_K,
    )
    candidates = [
        {**hit.payload, "vector_score": round(hit.score, 4)}  # type: ignore[arg-type]
        for hit in hits.points
    ]

    # Stage 2: Rerank
    rerank_result = vc.rerank(
        query=question,
        documents=[c["text"] for c in candidates],
        model=RERANK_MODEL,
        top_k=FINAL_K,
    )
    reranked = []
    for item in rerank_result.results:
        c = candidates[item.index].copy()
        c["rerank_score"] = round(item.relevance_score, 4)
        reranked.append(c)

    # Pre-compute rank changes
    stage1_titles = [c["title"] for c in candidates[:FINAL_K]]
    rank_changes = []
    for new_pos, c in enumerate(reranked, 1):
        title = c["title"]
        if title not in stage1_titles:
            rank_changes.append("NEW")
        else:
            old_pos = stage1_titles.index(title) + 1
            diff = old_pos - new_pos
            if diff > 0:
                rank_changes.append(f"+{diff}")
            elif diff < 0:
                rank_changes.append(f"{diff}")
            else:
                rank_changes.append("=")

    # Display: before vs after
    print(f"\nQuery: '{question}'\n")

    print(f"STAGE 1 -- Vector recall  (top {FINAL_K} of {RECALL_K} by cosine similarity)")
    print("-" * 70)
    for i, c in enumerate(candidates[:FINAL_K], 1):
        fo = f" | FOs: {', '.join(c['fo_ids'])}" if c["fo_ids"] else ""
        print(f"[{i}] cosine={c['vector_score']}  {c['date']} | {c['tool']} | {c['type']}{fo}")
        print(f"     {c['title']}")
    print()

    print(f"STAGE 2 -- After rerank-2.5  (top {FINAL_K} of {RECALL_K} by relevance score)")
    print("-" * 70)
    for i, (c, change) in enumerate(zip(reranked, rank_changes), 1):
        fo = f" | FOs: {', '.join(c['fo_ids'])}" if c["fo_ids"] else ""
        print(
            f"[{i}] rerank={c['rerank_score']}  cosine={c['vector_score']}"
            f"  [{change}]  {c['date']} | {c['tool']} | {c['type']}{fo}"
        )
        print(f"     {c['title']}")
    print()
    print("key: [+N] moved up N  [-N] moved down N  [=] unchanged  [NEW] promoted from outside top 5")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "what did I work on recently?"
    run(q)

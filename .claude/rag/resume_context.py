"""
RAG Resume Context — Phase 3
Two-stage retrieval pipeline:
  Stage 1 — Recall:    embed question → cosine similarity → top 20 candidates (Qdrant)
  Stage 2 — Precision: (question, candidate) → rerank-2.5 → relevance score → top 5

Called by /project:resume to surface relevant DEVLOG history without loading
the full file. Token-efficient and semantically precise.

Usage:
  python .claude/rag/resume_context.py
  python .claude/rag/resume_context.py "GUI chart work"
  python .claude/rag/resume_context.py --final-k 3 "screener bug fixes"
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient

DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "devlog"
EMBED_MODEL = "voyage-4-lite"
RERANK_MODEL = "rerank-2.5"
DEFAULT_QUERY = "recent development work current state decisions made"
RECALL_K = 20   # Stage 1: cast a wide net
FINAL_K = 5     # Stage 2: reranker narrows to this many


def _api_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY") or subprocess.check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
        text=True,
    ).strip()
    if not key:
        print("[RAG] VOYAGE_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


# ── Stage 1: Vector recall ─────────────────────────────────────────────────────
def vector_recall(question: str, vc: voyageai.Client, top_k: int) -> list[dict]:
    """Embed question → cosine similarity → top_k candidates from Qdrant."""
    result = vc.embed([question], model=EMBED_MODEL, input_type="query")
    query_vector = result.embeddings[0]

    qclient = QdrantClient(path=str(DB_PATH))
    hits = qclient.query_points(collection_name=COLLECTION, query=query_vector, limit=top_k)

    return [
        {**hit.payload, "vector_score": round(hit.score, 4)}  # type: ignore[arg-type]
        for hit in hits.points
    ]


# ── Stage 2: Rerank ────────────────────────────────────────────────────────────
def rerank(question: str, candidates: list[dict], vc: voyageai.Client, final_k: int) -> list[dict]:
    """
    Send (question, candidate_text) pairs to rerank-2.5.
    Returns candidates re-sorted by relevance score, trimmed to final_k.

    The reranker reads question + full document text together —
    much deeper than cosine similarity on embeddings alone.
    """
    documents = [c["text"] for c in candidates]
    result = vc.rerank(query=question, documents=documents, model=RERANK_MODEL, top_k=final_k)

    reranked = []
    for item in result.results:
        candidate = candidates[item.index].copy()
        candidate["rerank_score"] = round(item.relevance_score, 4)
        reranked.append(candidate)

    return reranked  # already sorted by rerank_score descending


# ── Format for Claude ──────────────────────────────────────────────────────────
def format_for_claude(results: list[dict], query: str) -> str:
    lines = [
        "=== RAG Context (two-stage: vector recall -> rerank-2.5) ===",
        f"Query : '{query}'",
        f"Top {len(results)} of {RECALL_K} candidates after reranking:\n",
    ]
    for i, r in enumerate(results, 1):
        fo_line = f"  FOs : {', '.join(r['fo_ids'])}" if r.get("fo_ids") else ""
        lines.append(
            f"[{i}] {r['date']} | {r['tool']} | {r['type']}"
            f" | rerank={r['rerank_score']}  vector={r.get('vector_score', '?')}"
        )
        lines.append(f"  {r['title']}")
        if fo_line:
            lines.append(fo_line)
        lines.append("")
    lines.append("=== End RAG Context ===")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="*", help="Natural language query")
    parser.add_argument("--final-k", type=int, default=FINAL_K)
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("[RAG] Qdrant DB not found — run ingest.py first", file=sys.stderr)
        sys.exit(1)

    question = " ".join(args.query) if args.query else DEFAULT_QUERY
    vc = voyageai.Client(api_key=_api_key())

    candidates = vector_recall(question, vc, top_k=RECALL_K)
    final = rerank(question, candidates, vc, final_k=args.final_k)

    print(format_for_claude(final, question))


if __name__ == "__main__":
    main()
